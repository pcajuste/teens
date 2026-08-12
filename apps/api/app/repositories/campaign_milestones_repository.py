"""Data access for public.campaign_milestones (campaign-level milestone
definitions) and public.campaign_rep_milestones (per-rep milestone
progress) -- Build Prompt 8B.

Kept as its own module rather than folded into campaigns_repository.py
/campaign_reps_repository.py: milestone rows have a materially
different lifecycle (per-milestone submit/confirm/dispute state
machine, layered underneath the existing campaign_reps state machine
those two modules already own) and this keeps that new surface area
from bloating the existing, already-large files.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import asyncpg

# ══════════════════════════════════════════════════════════════════
# campaign_milestones -- campaign-level milestone definitions
# ══════════════════════════════════════════════════════════════════

_MILESTONE_COLUMNS = """
    id, campaign_id, milestone_number, title, description, verification_method,
    payout_percentage, sequence_required, created_at
"""


@dataclass(frozen=True, slots=True)
class CampaignMilestone:
    id: str
    campaign_id: str
    milestone_number: int
    title: str
    description: str | None
    verification_method: str
    payout_percentage: int
    sequence_required: bool
    created_at: datetime

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "CampaignMilestone":
        return cls(
            id=str(row["id"]),
            campaign_id=str(row["campaign_id"]),
            milestone_number=row["milestone_number"],
            title=row["title"],
            description=row["description"],
            verification_method=row["verification_method"],
            payout_percentage=row["payout_percentage"],
            sequence_required=row["sequence_required"],
            created_at=row["created_at"],
        )


async def create_milestones(
    conn: asyncpg.Connection, campaign_id: str, milestones: list[dict]
) -> list[CampaignMilestone]:
    """Bulk-inserts the campaign's milestone rows. Caller (POST
    /brands/campaigns) is responsible for wrapping this in the same
    transaction as the campaign INSERT and for all server-side
    validation (percentages sum to 100, sequential numbering, etc. --
    see app/services/campaign_service.validate_milestones) before
    calling this; this function does no validation of its own beyond
    what the DB schema itself enforces (payout_percentage 1-100,
    UNIQUE (campaign_id, milestone_number))."""
    created: list[CampaignMilestone] = []
    for m in milestones:
        row = await conn.fetchrow(
            f"""
            INSERT INTO public.campaign_milestones
                (campaign_id, milestone_number, title, description, verification_method,
                 payout_percentage, sequence_required)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING {_MILESTONE_COLUMNS}
            """,
            campaign_id,
            m["milestone_number"],
            m["title"],
            m.get("description"),
            m["verification_method"],
            m["payout_percentage"],
            m["sequence_required"],
        )
        created.append(CampaignMilestone.from_row(row))
    return created


async def list_for_campaign(conn: asyncpg.Connection, campaign_id: str) -> list[CampaignMilestone]:
    rows = await conn.fetch(
        f"SELECT {_MILESTONE_COLUMNS} FROM public.campaign_milestones WHERE campaign_id = $1 ORDER BY milestone_number ASC",
        campaign_id,
    )
    return [CampaignMilestone.from_row(r) for r in rows]


async def get_by_id_and_campaign(conn: asyncpg.Connection, milestone_id: str, campaign_id: str) -> CampaignMilestone | None:
    row = await conn.fetchrow(
        f"SELECT {_MILESTONE_COLUMNS} FROM public.campaign_milestones WHERE id = $1 AND campaign_id = $2",
        milestone_id,
        campaign_id,
    )
    return CampaignMilestone.from_row(row) if row else None


# ══════════════════════════════════════════════════════════════════
# campaign_rep_milestones -- per-rep milestone progress
# ══════════════════════════════════════════════════════════════════

_CRM_COLUMNS = """
    id, campaign_rep_id, campaign_milestone_id, status, rep_submission_text,
    rep_submission_file_urls, brand_confirmation_note, payout_cents,
    stripe_transfer_id, payout_status, dispute_flag, submitted_at, confirmed_at, paid_at
"""

# Same column list, qualified with the crm. alias -- needed whenever
# this table is joined against another table that also has an `id`
# column (campaign_milestones does), since an unqualified `id` in the
# SELECT list is otherwise ambiguous.
_CRM_COLUMNS_QUALIFIED = """
    crm.id, crm.campaign_rep_id, crm.campaign_milestone_id, crm.status, crm.rep_submission_text,
    crm.rep_submission_file_urls, crm.brand_confirmation_note, crm.payout_cents,
    crm.stripe_transfer_id, crm.payout_status, crm.dispute_flag, crm.submitted_at, crm.confirmed_at, crm.paid_at
"""


@dataclass(frozen=True, slots=True)
class CampaignRepMilestone:
    id: str
    campaign_rep_id: str
    campaign_milestone_id: str
    status: str
    rep_submission_text: str | None
    rep_submission_file_urls: list[str]
    brand_confirmation_note: str | None
    payout_cents: int | None
    stripe_transfer_id: str | None
    payout_status: str
    dispute_flag: bool
    submitted_at: datetime | None
    confirmed_at: datetime | None
    paid_at: datetime | None

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "CampaignRepMilestone":
        return cls(
            id=str(row["id"]),
            campaign_rep_id=str(row["campaign_rep_id"]),
            campaign_milestone_id=str(row["campaign_milestone_id"]),
            status=row["status"],
            rep_submission_text=row["rep_submission_text"],
            rep_submission_file_urls=list(row["rep_submission_file_urls"] or []),
            brand_confirmation_note=row["brand_confirmation_note"],
            payout_cents=row["payout_cents"],
            stripe_transfer_id=row["stripe_transfer_id"],
            payout_status=row["payout_status"],
            dispute_flag=row["dispute_flag"],
            submitted_at=row["submitted_at"],
            confirmed_at=row["confirmed_at"],
            paid_at=row["paid_at"],
        )


async def initialize_for_accept(conn: asyncpg.Connection, campaign_rep_id: str, campaign_id: str) -> list[CampaignRepMilestone]:
    """Creates one campaign_rep_milestones row (status='pending') per
    campaign_milestones row on this campaign. Called by POST
    /campaigns/:id/accept immediately after campaign_reps_repository.accept
    succeeds, inside the same transaction, for milestone-payment-type
    campaigns only -- a no-op (returns []) for a flat campaign, which
    has no campaign_milestones rows to iterate."""
    rows = await conn.fetch(
        f"""
        INSERT INTO public.campaign_rep_milestones (campaign_rep_id, campaign_milestone_id)
        SELECT $1, cm.id FROM public.campaign_milestones cm WHERE cm.campaign_id = $2
        RETURNING {_CRM_COLUMNS}
        """,
        campaign_rep_id,
        campaign_id,
    )
    return [CampaignRepMilestone.from_row(r) for r in rows]


async def list_for_campaign_rep(conn: asyncpg.Connection, campaign_rep_id: str) -> list[CampaignRepMilestone]:
    rows = await conn.fetch(
        f"SELECT {_CRM_COLUMNS} FROM public.campaign_rep_milestones WHERE campaign_rep_id = $1",
        campaign_rep_id,
    )
    return [CampaignRepMilestone.from_row(r) for r in rows]


async def get_by_id(conn: asyncpg.Connection, campaign_rep_milestone_id: str) -> CampaignRepMilestone | None:
    row = await conn.fetchrow(
        f"SELECT {_CRM_COLUMNS} FROM public.campaign_rep_milestones WHERE id = $1", campaign_rep_milestone_id
    )
    return CampaignRepMilestone.from_row(row) if row else None


def compute_actionable_map(
    milestones: list["CampaignMilestone"], crm_list: list["CampaignRepMilestone"]
) -> dict[str, bool]:
    """Build Prompt 8B deliverable 3: "whether it is currently
    actionable (sequence_required milestone where all prior milestones
    are confirmed, or a non-sequential milestone [once all
    sequence_required milestones are confirmed])." Pure function (no DB
    access) so it can be shared by GET /reps/campaigns/active (display)
    and POST .../milestones/:milestone_id/submit (server-side
    enforcement) without those two ever disagreeing about what's
    actionable. Only a 'pending' milestone can ever be actionable --
    one already submitted/confirmed/paid has nothing left to act on."""
    status_by_milestone_id = {crm.campaign_milestone_id: crm.status for crm in crm_list}
    ordered = sorted(milestones, key=lambda m: m.milestone_number)
    sequence_required = [m for m in ordered if m.sequence_required]
    all_sequence_required_done = all(
        status_by_milestone_id.get(m.id) in ("confirmed", "paid") for m in sequence_required
    )

    result: dict[str, bool] = {}
    prior_sequence_done = True
    for m in ordered:
        current_status = status_by_milestone_id.get(m.id, "pending")
        if m.sequence_required:
            result[m.id] = prior_sequence_done and current_status == "pending"
            prior_sequence_done = prior_sequence_done and current_status in ("confirmed", "paid")
        else:
            result[m.id] = all_sequence_required_done and current_status == "pending"
    return result


async def compute_payout_cents(conn: asyncpg.Connection, campaign_rep_milestone_id: str) -> int | None:
    """Build Prompt 8B deliverable 5's rounding rule: payout_cents =
    floor(payout_percentage / 100 * payout_per_rep_cents) for every
    milestone except the one with the highest milestone_number on its
    campaign (the "final milestone"), which instead gets
    payout_per_rep_cents minus the sum of every other already-
    confirmed-or-paid milestone's payout_cents for this campaign_rep --
    guaranteeing total_milestone_payout_cents can never exceed
    payout_per_rep_cents regardless of how unevenly the percentages
    divide. Shared by both confirmation paths (POST .../confirm in
    app/routers/brands.py, and the milestone_auto_release job in
    app/jobs/runner.py) so the two can never compute this differently.
    Returns None if the row/campaign can't be found."""
    row = await conn.fetchrow(
        """
        SELECT cm.milestone_number, cm.payout_percentage, c.payout_per_rep_cents,
               (SELECT MAX(m2.milestone_number) FROM public.campaign_milestones m2
                  WHERE m2.campaign_id = cm.campaign_id) AS max_milestone_number,
               (SELECT COALESCE(SUM(crm2.payout_cents), 0) FROM public.campaign_rep_milestones crm2
                  WHERE crm2.campaign_rep_id = crm.campaign_rep_id AND crm2.id <> crm.id
                    AND crm2.status IN ('confirmed', 'paid')) AS other_payout_cents
        FROM public.campaign_rep_milestones crm
        JOIN public.campaign_milestones cm ON cm.id = crm.campaign_milestone_id
        JOIN public.campaign_reps cr ON cr.id = crm.campaign_rep_id
        JOIN public.campaigns c ON c.id = cr.campaign_id
        WHERE crm.id = $1
        """,
        campaign_rep_milestone_id,
    )
    if row is None:
        return None
    payout_per_rep_cents = row["payout_per_rep_cents"] or 0
    if row["milestone_number"] == row["max_milestone_number"]:
        return payout_per_rep_cents - row["other_payout_cents"]
    return (payout_per_rep_cents * row["payout_percentage"]) // 100


async def get_by_campaign_rep_and_milestone(
    conn: asyncpg.Connection, campaign_rep_id: str, campaign_milestone_id: str
) -> CampaignRepMilestone | None:
    row = await conn.fetchrow(
        f"""
        SELECT {_CRM_COLUMNS} FROM public.campaign_rep_milestones
        WHERE campaign_rep_id = $1 AND campaign_milestone_id = $2
        """,
        campaign_rep_id,
        campaign_milestone_id,
    )
    return CampaignRepMilestone.from_row(row) if row else None


async def get_by_stripe_transfer_id(conn: asyncpg.Connection, stripe_transfer_id: str) -> CampaignRepMilestone | None:
    row = await conn.fetchrow(
        f"SELECT {_CRM_COLUMNS} FROM public.campaign_rep_milestones WHERE stripe_transfer_id = $1", stripe_transfer_id
    )
    return CampaignRepMilestone.from_row(row) if row else None


async def submit(
    conn: asyncpg.Connection,
    campaign_rep_milestone_id: str,
    *,
    submission_text: str,
    submission_file_urls: list[str],
    at: datetime,
) -> CampaignRepMilestone | None:
    """Legal only from 'pending'. Sequence-actionability is checked by
    the caller (app/routers/reps.py) before this is called, since it
    needs to look across every milestone on the campaign, not just this
    row."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaign_rep_milestones
        SET status = 'submitted', submitted_at = $2, rep_submission_text = $3, rep_submission_file_urls = $4
        WHERE id = $1 AND status = 'pending'
        RETURNING {_CRM_COLUMNS}
        """,
        campaign_rep_milestone_id,
        at,
        submission_text,
        submission_file_urls,
    )
    return CampaignRepMilestone.from_row(row) if row else None


async def confirm(
    conn: asyncpg.Connection, campaign_rep_milestone_id: str, *, payout_cents: int, at: datetime
) -> CampaignRepMilestone | None:
    """Legal only from 'submitted'. Does not touch payout_status/
    stripe_transfer_id -- that's payout_service.release_milestone_payout's
    job, called right after this by the router (mirrors how
    campaign_reps_repository.confirm/payout_service.release_payout are
    split for flat campaigns)."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaign_rep_milestones
        SET status = 'confirmed', payout_cents = $2, confirmed_at = $3
        WHERE id = $1 AND status = 'submitted'
        RETURNING {_CRM_COLUMNS}
        """,
        campaign_rep_milestone_id,
        payout_cents,
        at,
    )
    return CampaignRepMilestone.from_row(row) if row else None


async def set_dispute_flag(conn: asyncpg.Connection, campaign_rep_milestone_id: str) -> CampaignRepMilestone | None:
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaign_rep_milestones SET dispute_flag = TRUE
        WHERE id = $1 AND status = 'submitted'
        RETURNING {_CRM_COLUMNS}
        """,
        campaign_rep_milestone_id,
    )
    return CampaignRepMilestone.from_row(row) if row else None


async def reset_to_submitted(conn: asyncpg.Connection, campaign_rep_milestone_id: str) -> CampaignRepMilestone | None:
    """Admin dispute decline: milestone goes back to 'submitted'
    (dispute_flag cleared) so the auto-release/confirm path can run
    again -- never left in a permanently disputed dead end."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaign_rep_milestones SET dispute_flag = FALSE
        WHERE id = $1
        RETURNING {_CRM_COLUMNS}
        """,
        campaign_rep_milestone_id,
    )
    return CampaignRepMilestone.from_row(row) if row else None


async def set_payout_processing(conn: asyncpg.Connection, campaign_rep_milestone_id: str, *, stripe_transfer_id: str) -> CampaignRepMilestone | None:
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaign_rep_milestones
        SET payout_status = 'processing', stripe_transfer_id = $2
        WHERE id = $1 AND status = 'confirmed' AND payout_status = 'pending'
        RETURNING {_CRM_COLUMNS}
        """,
        campaign_rep_milestone_id,
        stripe_transfer_id,
    )
    return CampaignRepMilestone.from_row(row) if row else None


async def set_payout_paid(conn: asyncpg.Connection, campaign_rep_milestone_id: str, *, at: datetime) -> CampaignRepMilestone | None:
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaign_rep_milestones
        SET status = 'paid', payout_status = 'paid', paid_at = $2
        WHERE id = $1 AND payout_status = 'processing'
        RETURNING {_CRM_COLUMNS}
        """,
        campaign_rep_milestone_id,
        at,
    )
    return CampaignRepMilestone.from_row(row) if row else None


async def set_payout_failed(conn: asyncpg.Connection, campaign_rep_milestone_id: str) -> CampaignRepMilestone | None:
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaign_rep_milestones SET payout_status = 'failed'
        WHERE id = $1 AND payout_status = 'processing'
        RETURNING {_CRM_COLUMNS}
        """,
        campaign_rep_milestone_id,
    )
    return CampaignRepMilestone.from_row(row) if row else None


async def list_eligible_for_auto_release(conn: asyncpg.Connection, *, older_than: datetime) -> list[CampaignRepMilestone]:
    """milestone_auto_release job (every 30 min): rep_submission
    milestones sitting in 'submitted', older than the 24h review
    window, with no dispute raised."""
    rows = await conn.fetch(
        f"""
        SELECT {_CRM_COLUMNS_QUALIFIED}
        FROM public.campaign_rep_milestones crm
        JOIN public.campaign_milestones cm ON cm.id = crm.campaign_milestone_id
        WHERE cm.verification_method = 'rep_submission'
          AND crm.status = 'submitted'
          AND crm.submitted_at < $1
          AND crm.dispute_flag = FALSE
        """,
        older_than,
    )
    return [CampaignRepMilestone.from_row(r) for r in rows]


# ══════════════════════════════════════════════════════════════════
# campaign_reps aggregate columns (milestones_completed_count,
# total_milestone_payout_cents)
# ══════════════════════════════════════════════════════════════════


async def bump_campaign_rep_milestone_totals(conn: asyncpg.Connection, campaign_rep_id: str) -> asyncpg.Record:
    """Recomputes milestones_completed_count/total_milestone_payout_cents
    from scratch off campaign_rep_milestones (COUNT/SUM of confirmed-or-
    later rows) rather than a bare increment -- makes this call
    idempotent-safe against being invoked twice for the same milestone
    (confirm() above is itself guarded to run once, but recompute-from-
    source is cheap here and avoids any drift risk from an increment
    ever being double counted). Returns the updated
    (milestones_completed_count, total_milestone_payout_cents,
    total_milestones) row so the caller can tell whether this was the
    final milestone without a second query."""
    return await conn.fetchrow(
        """
        WITH agg AS (
            SELECT
                COUNT(*) FILTER (WHERE status IN ('confirmed', 'paid')) AS completed_count,
                COALESCE(SUM(payout_cents) FILTER (WHERE status IN ('confirmed', 'paid')), 0) AS total_payout_cents,
                COUNT(*) AS total_milestones
            FROM public.campaign_rep_milestones
            WHERE campaign_rep_id = $1
        )
        UPDATE public.campaign_reps cr
        SET milestones_completed_count = agg.completed_count,
            total_milestone_payout_cents = agg.total_payout_cents
        FROM agg
        WHERE cr.id = $1
        RETURNING agg.completed_count, agg.total_payout_cents, agg.total_milestones
        """,
        campaign_rep_id,
    )
