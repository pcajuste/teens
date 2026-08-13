"""Data access for public.campaign_talents: the parent-facing slice
(campaign-approval queue, monthly-digest stats -- Prompt 4A) plus the
talent-facing participation state machine (apply/accept/decline/submit/
withdraw, earnings breakdown -- Prompt 5).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import asyncpg


@dataclass(frozen=True, slots=True)
class PendingApproval:
    campaign_talent_id: str
    campaign_id: str
    parent_approval_deadline: datetime | None
    brand_name: str
    title: str
    product_name: str
    campaign_goal: str
    key_messaging: str
    prohibited_content: str | None
    deliverables_description: str
    payout_per_talent_cents: int | None
    start_date: str
    end_date: str
    requires_in_person_activation: bool


_BRIEF_COLUMNS = """
        cr.id AS campaign_talent_id, cr.campaign_id, cr.parent_approval_deadline,
        bp.company_name AS brand_name,
        c.title, c.product_name, c.campaign_goal, c.key_messaging, c.prohibited_content,
        c.deliverables_description, c.payout_per_talent_cents, c.start_date, c.end_date,
        c.target_categories
"""

_PENDING_QUERY = f"""
    SELECT {_BRIEF_COLUMNS}
    FROM public.campaign_talents cr
    JOIN public.campaigns c ON c.id = cr.campaign_id
    JOIN public.brand_profiles bp ON bp.id = c.brand_id
    WHERE cr.talent_id = $1 AND cr.parent_approval_status = 'pending'
    ORDER BY cr.invited_at ASC
"""

_BY_talent_AND_CAMPAIGN_QUERY = f"""
    SELECT {_BRIEF_COLUMNS}
    FROM public.campaign_talents cr
    JOIN public.campaigns c ON c.id = cr.campaign_id
    JOIN public.brand_profiles bp ON bp.id = c.brand_id
    WHERE cr.talent_id = $1 AND cr.campaign_id = $2
"""


def _pending_from_row(row: asyncpg.Record) -> PendingApproval:
    return PendingApproval(
        campaign_talent_id=str(row["campaign_talent_id"]),
        campaign_id=str(row["campaign_id"]),
        parent_approval_deadline=row["parent_approval_deadline"],
        brand_name=row["brand_name"],
        title=row["title"],
        product_name=row["product_name"],
        campaign_goal=row["campaign_goal"],
        key_messaging=row["key_messaging"],
        prohibited_content=row["prohibited_content"],
        deliverables_description=row["deliverables_description"],
        payout_per_talent_cents=row["payout_per_talent_cents"],
        start_date=row["start_date"].isoformat(),
        end_date=row["end_date"].isoformat(),
        requires_in_person_activation="in_person_travel_required" in (row["target_categories"] or []),
    )


async def list_pending_for_rep(conn: asyncpg.Connection, talent_id: str) -> list[PendingApproval]:
    rows = await conn.fetch(_PENDING_QUERY, talent_id)
    return [_pending_from_row(row) for row in rows]


async def get_brief_for_talent_and_campaign(
    conn: asyncpg.Connection, talent_id: str, campaign_id: str
) -> PendingApproval | None:
    row = await conn.fetchrow(_BY_talent_AND_CAMPAIGN_QUERY, talent_id, campaign_id)
    return _pending_from_row(row) if row else None


async def get_campaign_talent_approval_status(
    conn: asyncpg.Connection, talent_id: str, campaign_id: str
) -> str | None:
    return await conn.fetchval(
        "SELECT parent_approval_status FROM public.campaign_talents WHERE talent_id = $1 AND campaign_id = $2",
        talent_id,
        campaign_id,
    )


async def approve_campaign(conn: asyncpg.Connection, talent_id: str, campaign_id: str, *, decided_at: datetime) -> None:
    await conn.execute(
        """
        UPDATE public.campaign_talents
        SET parent_approval_status = 'approved', parent_decided_at = $3
        WHERE talent_id = $1 AND campaign_id = $2 AND parent_approval_status = 'pending'
        """,
        talent_id,
        campaign_id,
        decided_at,
    )


async def block_campaign(conn: asyncpg.Connection, talent_id: str, campaign_id: str, *, decided_at: datetime) -> None:
    # 'declined' is the same brand-visible status a talent's own decline
    # produces -- the brand never learns a parent was involved.
    await conn.execute(
        """
        UPDATE public.campaign_talents
        SET parent_approval_status = 'blocked', parent_decided_at = $3, status = 'declined'
        WHERE talent_id = $1 AND campaign_id = $2
        """,
        talent_id,
        campaign_id,
        decided_at,
    )


async def monthly_digest_stats(conn: asyncpg.Connection, talent_id: str, *, since: datetime) -> dict:
    row = await conn.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (WHERE cr.status = 'paid' AND cr.paid_at >= $2) AS campaigns_completed_this_month,
            COALESCE(SUM(cr.payout_cents) FILTER (WHERE cr.status = 'paid' AND cr.paid_at >= $2), 0) AS earnings_this_month_cents,
            ARRAY_AGG(DISTINCT c.target_categories) FILTER (WHERE cr.status = 'paid' AND cr.paid_at >= $2) AS category_arrays
        FROM public.campaign_talents cr
        JOIN public.campaigns c ON c.id = cr.campaign_id
        WHERE cr.talent_id = $1
        """,
        talent_id,
        since,
    )
    category_arrays = row["category_arrays"] or []
    active_categories = sorted({category for arr in category_arrays for category in (arr or [])})
    return {
        "campaigns_completed_this_month": row["campaigns_completed_this_month"],
        "earnings_this_month_cents": row["earnings_this_month_cents"],
        "active_categories": active_categories,
    }


# ══════════════════════════════════════════════════════════════════
# Talent-facing participation state machine (Build Prompt 5)
# ══════════════════════════════════════════════════════════════════

_CR_COLUMNS = """
    id, campaign_id, talent_id, status, ftc_disclosure_accepted, ftc_accepted_at,
    parent_approval_status, parent_approval_deadline, parent_decided_at,
    submission_text, submission_file_urls, revision_note,
    brand_rating, brand_rating_note, payout_cents, payout_status,
    invited_at, accepted_at, submitted_at, confirmed_at, paid_at,
    milestones_completed_count, total_milestone_payout_cents
"""

# Legal talent-initiated transitions out of each current status. Declining
# and withdrawing both land on 'declined' -- talent_campaign_status
# (Section 7) has no separate 'withdrawn' value, and the schema is
# treated as verbatim/authoritative (CLAUDE.md), so withdrawal reuses
# 'declined' rather than inventing a new enum member. This is a
# deliberate design decision, not an oversight: withdraw_campaign()
# below never touches payout_cents/payout_status, so a withdrawal after
# submission/confirmation does not retroactively cancel payout
# eligibility already earned for that work (Build Prompt 5 deliverable
# 9's "payout protection for work already submitted and confirmed").
_WITHDRAWABLE_STATUSES = {"invited", "accepted", "submitted", "revision_requested"}


@dataclass(frozen=True, slots=True)
class CampaignTalent:
    id: str
    campaign_id: str
    talent_id: str
    status: str
    ftc_disclosure_accepted: bool
    ftc_accepted_at: datetime | None
    parent_approval_status: str
    parent_approval_deadline: datetime | None
    parent_decided_at: datetime | None
    submission_text: str | None
    submission_file_urls: list[str]
    revision_note: str | None
    brand_rating: int | None
    brand_rating_note: str | None
    payout_cents: int | None
    payout_status: str | None
    invited_at: datetime
    accepted_at: datetime | None
    submitted_at: datetime | None
    confirmed_at: datetime | None
    paid_at: datetime | None
    milestones_completed_count: int
    total_milestone_payout_cents: int

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "CampaignTalent":
        return cls(
            id=str(row["id"]),
            campaign_id=str(row["campaign_id"]),
            talent_id=str(row["talent_id"]),
            status=row["status"],
            ftc_disclosure_accepted=row["ftc_disclosure_accepted"],
            ftc_accepted_at=row["ftc_accepted_at"],
            parent_approval_status=row["parent_approval_status"],
            parent_approval_deadline=row["parent_approval_deadline"],
            parent_decided_at=row["parent_decided_at"],
            submission_text=row["submission_text"],
            submission_file_urls=list(row["submission_file_urls"] or []),
            revision_note=row["revision_note"],
            brand_rating=row["brand_rating"],
            brand_rating_note=row["brand_rating_note"],
            payout_cents=row["payout_cents"],
            payout_status=row["payout_status"],
            invited_at=row["invited_at"],
            accepted_at=row["accepted_at"],
            submitted_at=row["submitted_at"],
            confirmed_at=row["confirmed_at"],
            paid_at=row["paid_at"],
            milestones_completed_count=row["milestones_completed_count"],
            total_milestone_payout_cents=row["total_milestone_payout_cents"],
        )


async def get_for_talent_and_campaign(conn: asyncpg.Connection, talent_id: str, campaign_id: str) -> CampaignTalent | None:
    row = await conn.fetchrow(
        f"SELECT {_CR_COLUMNS} FROM public.campaign_talents WHERE talent_id = $1 AND campaign_id = $2",
        talent_id,
        campaign_id,
    )
    return CampaignTalent.from_row(row) if row else None


async def create_application(
    conn: asyncpg.Connection,
    *,
    talent_id: str,
    campaign_id: str,
    parent_approval_status: str,
    parent_approval_deadline: datetime | None,
) -> CampaignTalent:
    """POST /campaigns/:id/apply -- creates the campaign_talents row. A talent
    self-applying and a brand inviting a talent both converge on the same
    row shape (status='invited'); Prompt 5 only implements the
    talent-initiated apply path, since brand-initiated invites are a
    Prompt 8 concern."""
    row = await conn.fetchrow(
        f"""
        INSERT INTO public.campaign_talents (campaign_id, talent_id, parent_approval_status, parent_approval_deadline)
        VALUES ($1, $2, $3, $4)
        RETURNING {_CR_COLUMNS}
        """,
        campaign_id,
        talent_id,
        parent_approval_status,
        parent_approval_deadline,
    )
    return CampaignTalent.from_row(row)


async def accept(
    conn: asyncpg.Connection,
    talent_id: str,
    campaign_id: str,
    *,
    at: datetime,
    ftc_disclosure_accepted: bool,
) -> CampaignTalent | None:
    """Legal only from 'invited'. Returns None (caller raises 409) if
    the current row isn't in that state. `ftc_disclosure_accepted`, if
    True, is recorded here too (CLAUDE.md Section 9: "FTC sponsorship
    disclosure checkbox required before a talent can accept any campaign")
    -- but this alone does not satisfy the submit-time gate below if the
    talent passed False; POST /campaigns/:id/submit re-checks the stored
    column independently."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaign_talents
        SET status = 'accepted', accepted_at = $3,
            ftc_disclosure_accepted = ftc_disclosure_accepted OR $4,
            ftc_accepted_at = CASE WHEN $4 THEN $3 ELSE ftc_accepted_at END
        WHERE talent_id = $1 AND campaign_id = $2 AND status = 'invited'
        RETURNING {_CR_COLUMNS}
        """,
        talent_id,
        campaign_id,
        at,
        ftc_disclosure_accepted,
    )
    return CampaignTalent.from_row(row) if row else None


async def decline(conn: asyncpg.Connection, talent_id: str, campaign_id: str) -> CampaignTalent | None:
    """Legal only from 'invited'."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaign_talents
        SET status = 'declined'
        WHERE talent_id = $1 AND campaign_id = $2 AND status = 'invited'
        RETURNING {_CR_COLUMNS}
        """,
        talent_id,
        campaign_id,
    )
    return CampaignTalent.from_row(row) if row else None


async def submit(
    conn: asyncpg.Connection,
    talent_id: str,
    campaign_id: str,
    *,
    submission_text: str,
    submission_file_urls: list[str],
    at: datetime,
) -> CampaignTalent | None:
    """Legal only from 'accepted' or 'revision_requested'. Callers must
    verify ftc_disclosure_accepted=TRUE themselves before calling this
    (Build Prompt 5 deliverable 8) -- not re-checked here so the 403
    "ftc disclosure required" error can be raised with its own
    dedicated code rather than colliding with the generic 409 this
    function returns for a bad state transition."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaign_talents
        SET status = 'submitted', submitted_at = $3,
            submission_text = $4, submission_file_urls = $5, revision_note = NULL
        WHERE talent_id = $1 AND campaign_id = $2 AND status IN ('accepted', 'revision_requested')
        RETURNING {_CR_COLUMNS}
        """,
        talent_id,
        campaign_id,
        at,
        submission_text,
        submission_file_urls,
    )
    return CampaignTalent.from_row(row) if row else None


async def withdraw(conn: asyncpg.Connection, talent_id: str, campaign_id: str) -> CampaignTalent | None:
    """One-tap withdrawal 'from any campaign at any time' (Build Prompt
    5 deliverable 9), scoped here to the statuses where withdrawal is
    still meaningful -- 'declined'/'confirmed'/'paid' are already
    terminal (confirmed/paid specifically because payout eligibility is
    already locked in and must not be disturbed). payout_cents/
    payout_status are deliberately left untouched by this UPDATE."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaign_talents
        SET status = 'declined'
        WHERE talent_id = $1 AND campaign_id = $2 AND status = ANY($3::talent_campaign_status[])
        RETURNING {_CR_COLUMNS}
        """,
        talent_id,
        campaign_id,
        list(_WITHDRAWABLE_STATUSES),
    )
    return CampaignTalent.from_row(row) if row else None


async def list_active_for_rep(conn: asyncpg.Connection, talent_id: str) -> list[CampaignTalent]:
    rows = await conn.fetch(
        f"""
        SELECT {_CR_COLUMNS} FROM public.campaign_talents
        WHERE talent_id = $1 AND status IN ('accepted', 'submitted', 'revision_requested')
        ORDER BY accepted_at DESC
        """,
        talent_id,
    )
    return [CampaignTalent.from_row(row) for row in rows]


async def list_history_for_rep(conn: asyncpg.Connection, talent_id: str) -> list[CampaignTalent]:
    rows = await conn.fetch(
        f"""
        SELECT {_CR_COLUMNS} FROM public.campaign_talents
        WHERE talent_id = $1 AND status IN ('confirmed', 'paid', 'declined')
        ORDER BY invited_at DESC
        """,
        talent_id,
    )
    return [CampaignTalent.from_row(row) for row in rows]


async def earnings_breakdown(conn: asyncpg.Connection, talent_id: str) -> dict:
    """Pending/confirmed/paid breakdown straight from campaign_talents --
    never the talent_profiles.total_earnings_cents cache, which is only a
    lifetime-paid convenience total (Build Prompt 5 deliverable 5)."""
    row = await conn.fetchrow(
        """
        SELECT
            COALESCE(SUM(payout_cents) FILTER (WHERE payout_status = 'pending'), 0) AS pending_cents,
            COALESCE(SUM(payout_cents) FILTER (WHERE payout_status = 'processing'), 0) AS confirmed_cents,
            COALESCE(SUM(payout_cents) FILTER (WHERE payout_status = 'paid'), 0) AS paid_cents
        FROM public.campaign_talents
        WHERE talent_id = $1
        """,
        talent_id,
    )
    return {
        "pending_cents": row["pending_cents"],
        "confirmed_cents": row["confirmed_cents"],
        "paid_cents": row["paid_cents"],
    }


async def list_expired_pending_parent_approvals(conn: asyncpg.Connection, *, now: datetime) -> list[CampaignTalent]:
    rows = await conn.fetch(
        f"""
        SELECT {_CR_COLUMNS} FROM public.campaign_talents
        WHERE status = 'invited' AND parent_approval_status = 'pending' AND parent_approval_deadline < $1
        """,
        now,
    )
    return [CampaignTalent.from_row(row) for row in rows]


async def auto_decline_expired_parent_approvals(conn: asyncpg.Connection, *, now: datetime) -> int:
    """The 48h parent-approval auto-decline job (Build Prompt 5
    deliverable 7). parent_approval_status is set to 'blocked' here, the
    same terminal value block_campaign() above uses for an explicit
    parent block -- NOT left at 'pending'. Leaving it 'pending' would
    keep the row surfacing forever in the parent's pending-approval
    queue (list_pending_for_rep filters on parent_approval_status =
    'pending'), showing an invitation the talent can no longer act on, and
    would let a parent later call approve_campaign() (which only checks
    parent_approval_status = 'pending', not campaign_talents.status) on an
    already-terminal row -- producing status='declined' AND
    parent_approval_status='approved' simultaneously. parent_decided_at
    is left NULL (distinct from an explicit block, which sets it) so a
    caller can still tell an auto-decline apart from a parent's own
    action if that distinction ever matters."""
    result = await conn.execute(
        """
        UPDATE public.campaign_talents
        SET status = 'declined', parent_approval_status = 'blocked'
        WHERE status = 'invited' AND parent_approval_status = 'pending' AND parent_approval_deadline < $1
        """,
        now,
    )
    # asyncpg execute() returns a string like "UPDATE 3"
    return int(result.split()[-1])


# ══════════════════════════════════════════════════════════════════
# Brand-facing talent management within a campaign (Build Prompt 8)
# ══════════════════════════════════════════════════════════════════

# Rows still "in flight" for capacity purposes -- excludes 'declined'
# (talent said no / withdrew / was auto-declined / parent blocked) since
# that frees up a slot. Used to enforce max_talents at invite time without
# trusting the campaigns.talents_accepted_count cache column, which
# nothing in this codebase currently increments (a separate, flagged
# gap -- see app/routers/brands.py's invite endpoint).
_NON_DECLINED_STATUSES = ("invited", "accepted", "submitted", "revision_requested", "confirmed", "paid")


async def count_non_declined_for_campaign(conn: asyncpg.Connection, campaign_id: str) -> int:
    return await conn.fetchval(
        "SELECT COUNT(*) FROM public.campaign_talents WHERE campaign_id = $1 AND status = ANY($2::talent_campaign_status[])",
        campaign_id,
        list(_NON_DECLINED_STATUSES),
    )


async def create_invite(
    conn: asyncpg.Connection,
    *,
    campaign_id: str,
    talent_id: str,
    parent_approval_status: str,
    parent_approval_deadline: datetime | None,
) -> CampaignTalent:
    """Brand-initiated equivalent of create_application -- same
    resulting row shape (status='invited'), so /accept, /decline,
    /submit, /withdraw all work identically regardless of who started
    the invitation. Kept as a distinctly-named function (not reusing
    create_application) because the brand-invite route path has already
    verified campaign ownership and capacity, which is a different set
    of preconditions than the talent-apply path -- collapsing them into one
    function would require the caller to smuggle in a flag for which
    checks already happened."""
    row = await conn.fetchrow(
        f"""
        INSERT INTO public.campaign_talents (campaign_id, talent_id, parent_approval_status, parent_approval_deadline)
        VALUES ($1, $2, $3, $4)
        RETURNING {_CR_COLUMNS}
        """,
        campaign_id,
        talent_id,
        parent_approval_status,
        parent_approval_deadline,
    )
    return CampaignTalent.from_row(row)


async def list_for_campaign(conn: asyncpg.Connection, campaign_id: str) -> list[CampaignTalent]:
    """GET /brands/campaigns/:id/talents -- every talent on this campaign,
    any status."""
    rows = await conn.fetch(
        f"SELECT {_CR_COLUMNS} FROM public.campaign_talents WHERE campaign_id = $1 ORDER BY invited_at DESC",
        campaign_id,
    )
    return [CampaignTalent.from_row(row) for row in rows]


async def get_by_id(conn: asyncpg.Connection, campaign_talent_id: str) -> CampaignTalent | None:
    """Unscoped-by-campaign lookup -- used by app/services/payout_service.py,
    which is handed a bare campaign_talent_id (from the /confirm route,
    which has already verified campaign ownership before calling it)."""
    row = await conn.fetchrow(f"SELECT {_CR_COLUMNS} FROM public.campaign_talents WHERE id = $1", campaign_talent_id)
    return CampaignTalent.from_row(row) if row else None


async def get_by_stripe_transfer_id(conn: asyncpg.Connection, stripe_transfer_id: str) -> CampaignTalent | None:
    """Looked up by the transfer.paid/transfer.failed webhook handlers
    (Build Prompt 10), which identify the row by Stripe transfer id, not
    our own campaign_talent_id -- mirrors
    talent_profiles_repository.get_by_stripe_account_id's shape for the
    account.updated handler."""
    row = await conn.fetchrow(
        f"SELECT {_CR_COLUMNS} FROM public.campaign_talents WHERE stripe_transfer_id = $1", stripe_transfer_id
    )
    return CampaignTalent.from_row(row) if row else None


async def get_by_id_and_campaign(conn: asyncpg.Connection, campaign_talent_id: str, campaign_id: str) -> CampaignTalent | None:
    row = await conn.fetchrow(
        f"SELECT {_CR_COLUMNS} FROM public.campaign_talents WHERE id = $1 AND campaign_id = $2",
        campaign_talent_id,
        campaign_id,
    )
    return CampaignTalent.from_row(row) if row else None


async def get_by_talent_and_campaign_id(conn: asyncpg.Connection, talent_id: str, campaign_id: str) -> CampaignTalent | None:
    """Same lookup as get_for_talent_and_campaign but named for the
    brand-side caller (app/routers/brands.py addresses talents by
    talent_id in the URL, e.g. .../talents/:talent_id/confirm), kept as a
    thin alias rather than having brands.py import a
    talent-perspective-named function -- purely a readability choice at
    the call site, not a behavioral difference."""
    return await get_for_talent_and_campaign(conn, talent_id, campaign_id)


async def confirm(
    conn: asyncpg.Connection, campaign_talent_id: str, campaign_id: str, *, payout_cents: int, at: datetime
) -> CampaignTalent | None:
    """POST .../talents/:talent_id/confirm. Legal only from 'submitted' --
    payout_cents is recorded here (server-computed by the caller from
    the campaign's payout_per_talent_cents, never client-submitted) but the
    actual Stripe transfer is Prompt 10's job (stripe_transfer_id /
    payout_status stay at their defaults; this only sets status and
    payout_cents)."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaign_talents
        SET status = 'confirmed', payout_cents = $3, confirmed_at = $4
        WHERE id = $1 AND campaign_id = $2 AND status = 'submitted'
        RETURNING {_CR_COLUMNS}
        """,
        campaign_talent_id,
        campaign_id,
        payout_cents,
        at,
    )
    return CampaignTalent.from_row(row) if row else None


async def mark_confirmed_via_final_milestone(conn: asyncpg.Connection, campaign_talent_id: str, *, at: datetime) -> CampaignTalent | None:
    """Build Prompt 8B deliverable 5: "After the final milestone is
    confirmed: update campaign_talents.status to 'confirmed' (matching flat
    campaign behavior) so the rating flow and overall campaign status
    logic from Prompt 10 still work without modification." A milestone
    campaign's campaign_talents row never goes through the flat submit/
    confirm state machine (there is no single campaign-wide submission
    for a milestone campaign -- each milestone has its own), so this is
    legal from 'accepted' directly, not 'submitted' like confirm()
    above. Idempotent: legal only from 'accepted', so calling this
    again after the row is already 'confirmed'/'paid' is a no-op
    (returns None) rather than re-stamping confirmed_at -- matters
    because bump_campaign_talent_milestone_totals-driven callers (both the
    brand-confirm route and the auto-release job) recompute "is this
    the final milestone" from scratch on every call, so a milestone
    landing exactly on 100% twice (a defensive scenario, not a normal
    one) must not overwrite an already-set confirmed_at."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaign_talents
        SET status = 'confirmed', confirmed_at = $2
        WHERE id = $1 AND status = 'accepted'
        RETURNING {_CR_COLUMNS}
        """,
        campaign_talent_id,
        at,
    )
    return CampaignTalent.from_row(row) if row else None


async def request_revision(conn: asyncpg.Connection, campaign_talent_id: str, campaign_id: str, *, note: str) -> CampaignTalent | None:
    """POST .../talents/:talent_id/revision. Legal only from 'submitted' --
    sends the talent back to 'accepted' (not a dedicated 'revision_requested'
    intermediate re-submit state distinct from the original accept) so
    POST /campaigns/:id/submit's existing WHERE clause
    (status IN ('accepted', 'revision_requested')) already covers a
    resubmission after revision without any change there -- but the
    schema DOES have a 'revision_requested' enum value distinct from
    'accepted', so this sets that value specifically (not 'accepted')
    to preserve the talent-visible distinction between "never submitted
    yet" and "submitted, brand asked for changes"."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaign_talents
        SET status = 'revision_requested', revision_note = $3
        WHERE id = $1 AND campaign_id = $2 AND status = 'submitted'
        RETURNING {_CR_COLUMNS}
        """,
        campaign_talent_id,
        campaign_id,
        note,
    )
    return CampaignTalent.from_row(row) if row else None


# ══════════════════════════════════════════════════════════════════
# Payout engine (Build Prompt 10) -- transitions app/services/
# payout_service.py drives after a row reaches 'confirmed'.
# ══════════════════════════════════════════════════════════════════


async def set_payout_processing(conn: asyncpg.Connection, campaign_talent_id: str, *, stripe_transfer_id: str) -> CampaignTalent | None:
    """A Stripe Transfer has been created (payout_service.release_payout)
    -- legal only from payout_status='pending' (the DB default), which
    is what makes a retried release_payout call a no-op rather than a
    second Transfer: the WHERE clause simply matches no row the second
    time, and the caller (release_payout) checks payout_status before
    ever reaching this far as its own first line of defense."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaign_talents
        SET payout_status = 'processing', stripe_transfer_id = $2, payout_processing_started_at = now()
        WHERE id = $1 AND status = 'confirmed' AND payout_status = 'pending'
        RETURNING {_CR_COLUMNS}
        """,
        campaign_talent_id,
        stripe_transfer_id,
    )
    return CampaignTalent.from_row(row) if row else None


async def set_payout_paid(conn: asyncpg.Connection, campaign_talent_id: str, *, at: datetime) -> CampaignTalent | None:
    """transfer.paid webhook. status 'confirmed' -> 'paid' (the terminal
    talent_campaign_status value -- distinct from payout_status='paid'),
    payout_status 'processing' -> 'paid', paid_at set. Legal only from
    payout_status='processing' so a duplicate webhook delivery (already
    deduped at the stripe_events layer, but defended here too) is a
    no-op, not a double-count in talent_profiles' cached totals."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaign_talents
        SET status = 'paid', payout_status = 'paid', paid_at = $2
        WHERE id = $1 AND payout_status = 'processing'
        RETURNING {_CR_COLUMNS}
        """,
        campaign_talent_id,
        at,
    )
    return CampaignTalent.from_row(row) if row else None


async def set_payout_failed(conn: asyncpg.Connection, campaign_talent_id: str) -> CampaignTalent | None:
    """transfer.failed webhook. Legal only from payout_status='processing'.
    No admin-queue table exists yet (Prompt 13) -- until then,
    payout_status='failed' rows are the queue."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaign_talents
        SET payout_status = 'failed'
        WHERE id = $1 AND payout_status = 'processing'
        RETURNING {_CR_COLUMNS}
        """,
        campaign_talent_id,
    )
    return CampaignTalent.from_row(row) if row else None


async def sum_committed_payouts_for_campaign(conn: asyncpg.Connection, campaign_id: str) -> int:
    """Sum of payout_cents already transferred or in flight
    ('processing' or 'paid') for a campaign -- used by /cancel to
    compute the un-paid remainder that's still refundable. See
    docs/campaign-cancellation-refund-policy.md."""
    return await conn.fetchval(
        """
        SELECT COALESCE(SUM(payout_cents), 0) FROM public.campaign_talents
        WHERE campaign_id = $1 AND payout_status IN ('processing', 'paid')
        """,
        campaign_id,
    )


async def rate(conn: asyncpg.Connection, campaign_talent_id: str, campaign_id: str, *, brand_rating: int, brand_rating_note: str | None) -> CampaignTalent | None:
    """POST .../talents/:talent_id/rate. Write-once, legal only after
    confirmation (Build Prompt 8 deliverable 9: "1-5 stars, write-once,
    legal only after confirmation. No PUT/PATCH route for ratings.") --
    enforced here by requiring status IN ('confirmed', 'paid') AND
    brand_rating IS NULL, so a second call (even after the talent has been
    paid) returns None -> 409, not a silent overwrite."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaign_talents
        SET brand_rating = $3, brand_rating_note = $4
        WHERE id = $1 AND campaign_id = $2 AND status IN ('confirmed', 'paid') AND brand_rating IS NULL
        RETURNING {_CR_COLUMNS}
        """,
        campaign_talent_id,
        campaign_id,
        brand_rating,
        brand_rating_note,
    )
    return CampaignTalent.from_row(row) if row else None
