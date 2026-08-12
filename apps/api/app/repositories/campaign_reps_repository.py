"""Data access for public.campaign_reps: the parent-facing slice
(campaign-approval queue, monthly-digest stats -- Prompt 4A) plus the
rep-facing participation state machine (apply/accept/decline/submit/
withdraw, earnings breakdown -- Prompt 5).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import asyncpg


@dataclass(frozen=True, slots=True)
class PendingApproval:
    campaign_rep_id: str
    campaign_id: str
    parent_approval_deadline: datetime | None
    brand_name: str
    title: str
    product_name: str
    campaign_goal: str
    key_messaging: str
    prohibited_content: str | None
    deliverables_description: str
    payout_per_rep_cents: int | None
    start_date: str
    end_date: str
    requires_in_person_activation: bool


_BRIEF_COLUMNS = """
        cr.id AS campaign_rep_id, cr.campaign_id, cr.parent_approval_deadline,
        bp.company_name AS brand_name,
        c.title, c.product_name, c.campaign_goal, c.key_messaging, c.prohibited_content,
        c.deliverables_description, c.payout_per_rep_cents, c.start_date, c.end_date,
        c.target_categories
"""

_PENDING_QUERY = f"""
    SELECT {_BRIEF_COLUMNS}
    FROM public.campaign_reps cr
    JOIN public.campaigns c ON c.id = cr.campaign_id
    JOIN public.brand_profiles bp ON bp.id = c.brand_id
    WHERE cr.rep_id = $1 AND cr.parent_approval_status = 'pending'
    ORDER BY cr.invited_at ASC
"""

_BY_REP_AND_CAMPAIGN_QUERY = f"""
    SELECT {_BRIEF_COLUMNS}
    FROM public.campaign_reps cr
    JOIN public.campaigns c ON c.id = cr.campaign_id
    JOIN public.brand_profiles bp ON bp.id = c.brand_id
    WHERE cr.rep_id = $1 AND cr.campaign_id = $2
"""


def _pending_from_row(row: asyncpg.Record) -> PendingApproval:
    return PendingApproval(
        campaign_rep_id=str(row["campaign_rep_id"]),
        campaign_id=str(row["campaign_id"]),
        parent_approval_deadline=row["parent_approval_deadline"],
        brand_name=row["brand_name"],
        title=row["title"],
        product_name=row["product_name"],
        campaign_goal=row["campaign_goal"],
        key_messaging=row["key_messaging"],
        prohibited_content=row["prohibited_content"],
        deliverables_description=row["deliverables_description"],
        payout_per_rep_cents=row["payout_per_rep_cents"],
        start_date=row["start_date"].isoformat(),
        end_date=row["end_date"].isoformat(),
        requires_in_person_activation="in_person_travel_required" in (row["target_categories"] or []),
    )


async def list_pending_for_rep(conn: asyncpg.Connection, rep_id: str) -> list[PendingApproval]:
    rows = await conn.fetch(_PENDING_QUERY, rep_id)
    return [_pending_from_row(row) for row in rows]


async def get_brief_for_rep_and_campaign(
    conn: asyncpg.Connection, rep_id: str, campaign_id: str
) -> PendingApproval | None:
    row = await conn.fetchrow(_BY_REP_AND_CAMPAIGN_QUERY, rep_id, campaign_id)
    return _pending_from_row(row) if row else None


async def get_campaign_rep_approval_status(
    conn: asyncpg.Connection, rep_id: str, campaign_id: str
) -> str | None:
    return await conn.fetchval(
        "SELECT parent_approval_status FROM public.campaign_reps WHERE rep_id = $1 AND campaign_id = $2",
        rep_id,
        campaign_id,
    )


async def approve_campaign(conn: asyncpg.Connection, rep_id: str, campaign_id: str, *, decided_at: datetime) -> None:
    await conn.execute(
        """
        UPDATE public.campaign_reps
        SET parent_approval_status = 'approved', parent_decided_at = $3
        WHERE rep_id = $1 AND campaign_id = $2 AND parent_approval_status = 'pending'
        """,
        rep_id,
        campaign_id,
        decided_at,
    )


async def block_campaign(conn: asyncpg.Connection, rep_id: str, campaign_id: str, *, decided_at: datetime) -> None:
    # 'declined' is the same brand-visible status a rep's own decline
    # produces -- the brand never learns a parent was involved.
    await conn.execute(
        """
        UPDATE public.campaign_reps
        SET parent_approval_status = 'blocked', parent_decided_at = $3, status = 'declined'
        WHERE rep_id = $1 AND campaign_id = $2
        """,
        rep_id,
        campaign_id,
        decided_at,
    )


_CR_COLUMNS = """
    id, campaign_id, rep_id, status, ftc_disclosure_accepted, ftc_accepted_at,
    parent_approval_status, parent_approval_deadline, parent_decided_at,
    submission_text, submission_file_urls, revision_note, brand_rating,
    brand_rating_note, payout_cents, payout_status, stripe_transfer_id,
    invited_at, accepted_at, submitted_at, confirmed_at, paid_at
"""


@dataclass(frozen=True, slots=True)
class CampaignRep:
    id: str
    campaign_id: str
    rep_id: str
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
    stripe_transfer_id: str | None
    invited_at: datetime
    accepted_at: datetime | None
    submitted_at: datetime | None
    confirmed_at: datetime | None
    paid_at: datetime | None

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "CampaignRep":
        return cls(
            id=str(row["id"]),
            campaign_id=str(row["campaign_id"]),
            rep_id=str(row["rep_id"]),
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
            stripe_transfer_id=row["stripe_transfer_id"],
            invited_at=row["invited_at"],
            accepted_at=row["accepted_at"],
            submitted_at=row["submitted_at"],
            confirmed_at=row["confirmed_at"],
            paid_at=row["paid_at"],
        )


async def get_by_rep_and_campaign(conn: asyncpg.Connection, rep_id: str, campaign_id: str) -> CampaignRep | None:
    row = await conn.fetchrow(
        f"SELECT {_CR_COLUMNS} FROM public.campaign_reps WHERE rep_id = $1 AND campaign_id = $2",
        rep_id,
        campaign_id,
    )
    return CampaignRep.from_row(row) if row else None


async def create_application(
    conn: asyncpg.Connection,
    *,
    campaign_id: str,
    rep_id: str,
    parent_approval_status: str,
    parent_approval_deadline: datetime | None,
) -> CampaignRep:
    """Creates the campaign_reps row a rep's own POST .../apply
    produces. Starts in the 'invited' rep_campaign_status regardless of
    who initiated it (self-apply here vs. a future brand-initiated
    invite in Prompt 8) so /accept and /decline work identically either
    way."""
    row = await conn.fetchrow(
        f"""
        INSERT INTO public.campaign_reps
            (campaign_id, rep_id, parent_approval_status, parent_approval_deadline)
        VALUES ($1, $2, $3, $4)
        RETURNING {_CR_COLUMNS}
        """,
        campaign_id,
        rep_id,
        parent_approval_status,
        parent_approval_deadline,
    )
    return CampaignRep.from_row(row)


async def set_accepted(
    conn: asyncpg.Connection, campaign_rep_id: str, *, at: datetime, ftc_accepted_at: datetime
) -> CampaignRep:
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaign_reps
        SET status = 'accepted', accepted_at = $2,
            ftc_disclosure_accepted = TRUE, ftc_accepted_at = $3
        WHERE id = $1
        RETURNING {_CR_COLUMNS}
        """,
        campaign_rep_id,
        at,
        ftc_accepted_at,
    )
    return CampaignRep.from_row(row)


async def set_declined(conn: asyncpg.Connection, campaign_rep_id: str) -> CampaignRep:
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaign_reps SET status = 'declined'
        WHERE id = $1
        RETURNING {_CR_COLUMNS}
        """,
        campaign_rep_id,
    )
    return CampaignRep.from_row(row)


async def set_submitted(
    conn: asyncpg.Connection,
    campaign_rep_id: str,
    *,
    submission_text: str,
    submission_file_urls: list[str],
    at: datetime,
) -> CampaignRep:
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaign_reps
        SET status = 'submitted', submission_text = $2, submission_file_urls = $3,
            submitted_at = $4
        WHERE id = $1
        RETURNING {_CR_COLUMNS}
        """,
        campaign_rep_id,
        submission_text,
        submission_file_urls,
        at,
    )
    return CampaignRep.from_row(row)


async def set_withdrawn(conn: asyncpg.Connection, campaign_rep_id: str) -> CampaignRep:
    """Withdrawal has no dedicated rep_campaign_status value in the
    schema enum -- it reuses 'declined', the same terminal status a
    rep's own decline or a parent block produces. No penalty is applied
    (no payout_cents change); payout protection for already-
    submitted/confirmed work is enforced upstream by rep_service, which
    refuses the withdraw call entirely once status is 'confirmed' or
    'paid' rather than trying to claw back an already-earned payout."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaign_reps SET status = 'declined'
        WHERE id = $1
        RETURNING {_CR_COLUMNS}
        """,
        campaign_rep_id,
    )
    return CampaignRep.from_row(row)


_ACTIVE_STATUSES = ("accepted", "submitted", "revision_requested")
_HISTORY_STATUSES = ("declined", "confirmed", "paid")


async def list_active_for_rep(conn: asyncpg.Connection, rep_id: str) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT cr.id AS campaign_rep_id, cr.campaign_id, cr.status, cr.ftc_disclosure_accepted,
               cr.parent_approval_status, cr.submitted_at, cr.accepted_at,
               c.title, c.product_name, bp.company_name AS brand_name,
               c.payout_per_rep_cents, c.start_date, c.end_date
        FROM public.campaign_reps cr
        JOIN public.campaigns c ON c.id = cr.campaign_id
        JOIN public.brand_profiles bp ON bp.id = c.brand_id
        WHERE cr.rep_id = $1 AND cr.status = ANY($2::rep_campaign_status[])
        ORDER BY cr.invited_at DESC
        """,
        rep_id,
        list(_ACTIVE_STATUSES),
    )
    return [dict(row) for row in rows]


async def list_history_for_rep(conn: asyncpg.Connection, rep_id: str) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT cr.id AS campaign_rep_id, cr.campaign_id, cr.status, cr.payout_cents,
               cr.payout_status, cr.confirmed_at, cr.paid_at, cr.brand_rating,
               c.title, c.product_name, bp.company_name AS brand_name,
               c.payout_per_rep_cents, c.start_date, c.end_date
        FROM public.campaign_reps cr
        JOIN public.campaigns c ON c.id = cr.campaign_id
        JOIN public.brand_profiles bp ON bp.id = c.brand_id
        WHERE cr.rep_id = $1 AND cr.status = ANY($2::rep_campaign_status[])
        ORDER BY cr.invited_at DESC
        """,
        rep_id,
        list(_HISTORY_STATUSES),
    )
    return [dict(row) for row in rows]


async def earnings_breakdown(conn: asyncpg.Connection, rep_id: str) -> dict:
    """Pending/confirmed/paid breakdown (Prompt 5 deliverable 5) rather
    than only the cached rep_profiles.total_earnings_cents.

    Design decision (payout amounts aren't finalized until a brand
    confirms a submission -- Prompt 10's payout engine owns
    campaign_reps.payout_cents from that point on):
      - pending_cents: rows in ('accepted', 'submitted',
        'revision_requested') -- work in progress, valued at the
        campaign's payout_per_rep_cents as an estimate since no
        rep-specific payout_cents is assigned this early.
      - confirmed_cents: rows with status='confirmed', using the
        finalized payout_cents (falling back to payout_per_rep_cents if
        a payout amount hasn't been written yet).
      - paid_cents: rows with status='paid', summed from payout_cents
        (server-computed by Prompt 10, never client-submitted).
    """
    row = await conn.fetchrow(
        """
        SELECT
            COALESCE(SUM(c.payout_per_rep_cents) FILTER (
                WHERE cr.status IN ('accepted', 'submitted', 'revision_requested')
            ), 0) AS pending_cents,
            COALESCE(SUM(COALESCE(cr.payout_cents, c.payout_per_rep_cents)) FILTER (
                WHERE cr.status = 'confirmed'
            ), 0) AS confirmed_cents,
            COALESCE(SUM(cr.payout_cents) FILTER (WHERE cr.status = 'paid'), 0) AS paid_cents
        FROM public.campaign_reps cr
        JOIN public.campaigns c ON c.id = cr.campaign_id
        WHERE cr.rep_id = $1
        """,
        rep_id,
    )
    return {
        "pending_cents": row["pending_cents"],
        "confirmed_cents": row["confirmed_cents"],
        "paid_cents": row["paid_cents"],
    }


async def auto_decline_expired_parent_approvals(conn: asyncpg.Connection, *, now: datetime) -> list[str]:
    """Prompt 5 deliverable 7 / job: auto-decline invitations where the
    48-hour parent-approval window has lapsed. Scoped specifically to
    parent_approval_status='pending' rows per the deliverable text
    ("auto-decline invitations where parent approval window has
    lapsed") -- general invite expiry independent of the parent gate is
    not part of this job.

    Terminal status: rep_campaign_status has no 'expired' value, so
    status is set to 'declined' -- the same value a rep's own decline or
    a parent's explicit block produces (see block_campaign above, which
    already establishes this reuse). parent_approval_status is set to
    'blocked' rather than left at 'pending', for the same reason
    block_campaign sets it there: leaving it 'pending' would keep the
    row surfacing in the parent's pending-approval queue
    (list_pending_for_rep filters on parent_approval_status='pending')
    even though the rep-facing status has already gone terminal.
    """
    rows = await conn.fetch(
        """
        UPDATE public.campaign_reps
        SET status = 'declined', parent_approval_status = 'blocked', parent_decided_at = $1
        WHERE status = 'invited' AND parent_approval_status = 'pending' AND parent_approval_deadline < $1
        RETURNING id
        """,
        now,
    )
    return [str(row["id"]) for row in rows]


async def monthly_digest_stats(conn: asyncpg.Connection, rep_id: str, *, since: datetime) -> dict:
    row = await conn.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (WHERE cr.status = 'paid' AND cr.paid_at >= $2) AS campaigns_completed_this_month,
            COALESCE(SUM(cr.payout_cents) FILTER (WHERE cr.status = 'paid' AND cr.paid_at >= $2), 0) AS earnings_this_month_cents,
            ARRAY_AGG(DISTINCT c.target_categories) FILTER (WHERE cr.status = 'paid' AND cr.paid_at >= $2) AS category_arrays
        FROM public.campaign_reps cr
        JOIN public.campaigns c ON c.id = cr.campaign_id
        WHERE cr.rep_id = $1
        """,
        rep_id,
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
# Rep-facing participation state machine (Build Prompt 5)
# ══════════════════════════════════════════════════════════════════

_CR_COLUMNS = """
    id, campaign_id, rep_id, status, ftc_disclosure_accepted, ftc_accepted_at,
    parent_approval_status, parent_approval_deadline, parent_decided_at,
    submission_text, submission_file_urls, revision_note,
    brand_rating, brand_rating_note, payout_cents, payout_status,
    invited_at, accepted_at, submitted_at, confirmed_at, paid_at
"""

# Legal rep-initiated transitions out of each current status. Declining
# and withdrawing both land on 'declined' -- rep_campaign_status
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
class CampaignRep:
    id: str
    campaign_id: str
    rep_id: str
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

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "CampaignRep":
        return cls(
            id=str(row["id"]),
            campaign_id=str(row["campaign_id"]),
            rep_id=str(row["rep_id"]),
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
        )


async def get_for_rep_and_campaign(conn: asyncpg.Connection, rep_id: str, campaign_id: str) -> CampaignRep | None:
    row = await conn.fetchrow(
        f"SELECT {_CR_COLUMNS} FROM public.campaign_reps WHERE rep_id = $1 AND campaign_id = $2",
        rep_id,
        campaign_id,
    )
    return CampaignRep.from_row(row) if row else None


async def create_application(
    conn: asyncpg.Connection,
    *,
    rep_id: str,
    campaign_id: str,
    parent_approval_status: str,
    parent_approval_deadline: datetime | None,
) -> CampaignRep:
    """POST /campaigns/:id/apply -- creates the campaign_reps row. A rep
    self-applying and a brand inviting a rep both converge on the same
    row shape (status='invited'); Prompt 5 only implements the
    rep-initiated apply path, since brand-initiated invites are a
    Prompt 8 concern."""
    row = await conn.fetchrow(
        f"""
        INSERT INTO public.campaign_reps (campaign_id, rep_id, parent_approval_status, parent_approval_deadline)
        VALUES ($1, $2, $3, $4)
        RETURNING {_CR_COLUMNS}
        """,
        campaign_id,
        rep_id,
        parent_approval_status,
        parent_approval_deadline,
    )
    return CampaignRep.from_row(row)


async def accept(
    conn: asyncpg.Connection,
    rep_id: str,
    campaign_id: str,
    *,
    at: datetime,
    ftc_disclosure_accepted: bool,
) -> CampaignRep | None:
    """Legal only from 'invited'. Returns None (caller raises 409) if
    the current row isn't in that state. `ftc_disclosure_accepted`, if
    True, is recorded here too (CLAUDE.md Section 9: "FTC sponsorship
    disclosure checkbox required before a rep can accept any campaign")
    -- but this alone does not satisfy the submit-time gate below if the
    rep passed False; POST /campaigns/:id/submit re-checks the stored
    column independently."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaign_reps
        SET status = 'accepted', accepted_at = $3,
            ftc_disclosure_accepted = ftc_disclosure_accepted OR $4,
            ftc_accepted_at = CASE WHEN $4 THEN $3 ELSE ftc_accepted_at END
        WHERE rep_id = $1 AND campaign_id = $2 AND status = 'invited'
        RETURNING {_CR_COLUMNS}
        """,
        rep_id,
        campaign_id,
        at,
        ftc_disclosure_accepted,
    )
    return CampaignRep.from_row(row) if row else None


async def decline(conn: asyncpg.Connection, rep_id: str, campaign_id: str) -> CampaignRep | None:
    """Legal only from 'invited'."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaign_reps
        SET status = 'declined'
        WHERE rep_id = $1 AND campaign_id = $2 AND status = 'invited'
        RETURNING {_CR_COLUMNS}
        """,
        rep_id,
        campaign_id,
    )
    return CampaignRep.from_row(row) if row else None


async def submit(
    conn: asyncpg.Connection,
    rep_id: str,
    campaign_id: str,
    *,
    submission_text: str,
    submission_file_urls: list[str],
    at: datetime,
) -> CampaignRep | None:
    """Legal only from 'accepted' or 'revision_requested'. Callers must
    verify ftc_disclosure_accepted=TRUE themselves before calling this
    (Build Prompt 5 deliverable 8) -- not re-checked here so the 403
    "ftc disclosure required" error can be raised with its own
    dedicated code rather than colliding with the generic 409 this
    function returns for a bad state transition."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaign_reps
        SET status = 'submitted', submitted_at = $3,
            submission_text = $4, submission_file_urls = $5, revision_note = NULL
        WHERE rep_id = $1 AND campaign_id = $2 AND status IN ('accepted', 'revision_requested')
        RETURNING {_CR_COLUMNS}
        """,
        rep_id,
        campaign_id,
        at,
        submission_text,
        submission_file_urls,
    )
    return CampaignRep.from_row(row) if row else None


async def withdraw(conn: asyncpg.Connection, rep_id: str, campaign_id: str) -> CampaignRep | None:
    """One-tap withdrawal 'from any campaign at any time' (Build Prompt
    5 deliverable 9), scoped here to the statuses where withdrawal is
    still meaningful -- 'declined'/'confirmed'/'paid' are already
    terminal (confirmed/paid specifically because payout eligibility is
    already locked in and must not be disturbed). payout_cents/
    payout_status are deliberately left untouched by this UPDATE."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaign_reps
        SET status = 'declined'
        WHERE rep_id = $1 AND campaign_id = $2 AND status = ANY($3::rep_campaign_status[])
        RETURNING {_CR_COLUMNS}
        """,
        rep_id,
        campaign_id,
        list(_WITHDRAWABLE_STATUSES),
    )
    return CampaignRep.from_row(row) if row else None


async def list_active_for_rep(conn: asyncpg.Connection, rep_id: str) -> list[CampaignRep]:
    rows = await conn.fetch(
        f"""
        SELECT {_CR_COLUMNS} FROM public.campaign_reps
        WHERE rep_id = $1 AND status IN ('accepted', 'submitted', 'revision_requested')
        ORDER BY accepted_at DESC
        """,
        rep_id,
    )
    return [CampaignRep.from_row(row) for row in rows]


async def list_history_for_rep(conn: asyncpg.Connection, rep_id: str) -> list[CampaignRep]:
    rows = await conn.fetch(
        f"""
        SELECT {_CR_COLUMNS} FROM public.campaign_reps
        WHERE rep_id = $1 AND status IN ('confirmed', 'paid', 'declined')
        ORDER BY invited_at DESC
        """,
        rep_id,
    )
    return [CampaignRep.from_row(row) for row in rows]


async def earnings_breakdown(conn: asyncpg.Connection, rep_id: str) -> dict:
    """Pending/confirmed/paid breakdown straight from campaign_reps --
    never the rep_profiles.total_earnings_cents cache, which is only a
    lifetime-paid convenience total (Build Prompt 5 deliverable 5)."""
    row = await conn.fetchrow(
        """
        SELECT
            COALESCE(SUM(payout_cents) FILTER (WHERE payout_status = 'pending'), 0) AS pending_cents,
            COALESCE(SUM(payout_cents) FILTER (WHERE payout_status = 'processing'), 0) AS confirmed_cents,
            COALESCE(SUM(payout_cents) FILTER (WHERE payout_status = 'paid'), 0) AS paid_cents
        FROM public.campaign_reps
        WHERE rep_id = $1
        """,
        rep_id,
    )
    return {
        "pending_cents": row["pending_cents"],
        "confirmed_cents": row["confirmed_cents"],
        "paid_cents": row["paid_cents"],
    }


async def list_expired_pending_parent_approvals(conn: asyncpg.Connection, *, now: datetime) -> list[CampaignRep]:
    rows = await conn.fetch(
        f"""
        SELECT {_CR_COLUMNS} FROM public.campaign_reps
        WHERE status = 'invited' AND parent_approval_status = 'pending' AND parent_approval_deadline < $1
        """,
        now,
    )
    return [CampaignRep.from_row(row) for row in rows]


async def auto_decline_expired_parent_approvals(conn: asyncpg.Connection, *, now: datetime) -> int:
    """The 48h parent-approval auto-decline job (Build Prompt 5
    deliverable 7). parent_approval_status is deliberately left as
    'pending' rather than invented as some 'expired' value not present
    in the parent_approval_status enum (Section 7 is verbatim/
    authoritative) -- status='declined' plus parent_decided_at being
    NULL is what distinguishes an auto-decline from an explicit
    accept/decline for any caller that needs to tell them apart."""
    result = await conn.execute(
        """
        UPDATE public.campaign_reps
        SET status = 'declined'
        WHERE status = 'invited' AND parent_approval_status = 'pending' AND parent_approval_deadline < $1
        """,
        now,
    )
    # asyncpg execute() returns a string like "UPDATE 3"
    return int(result.split()[-1])
