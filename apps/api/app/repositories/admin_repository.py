"""Data access for the Admin Portal (Build Prompt 13).

Deliberately its own module rather than spread across
users_repository/campaigns_repository/campaign_reps_repository: every
query here is admin-scoped (cross-account, cross-role), unlike the
single-caller-scoped queries those modules expose to their own portals.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import asyncpg


# ══════════════════════════════════════════════════════════════════
# Deliverable 1: approval queues
# ══════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class QueueEntry:
    user_id: str
    email: str
    role: str
    account_status: str
    pending_reason: str  # 'awaiting_parent_consent' | 'awaiting_admin_approval'
    display_name: str
    created_at: datetime


async def queue_reps(conn: asyncpg.Connection) -> list[QueueEntry]:
    """Reps never require admin approval at MVP (Section 5 Phase 1 /
    Section 8: "If date_of_birth indicates age 16+: set account_status
    = 'active' immediately" and under-16 reps go 'active' the moment a
    parent completes double opt-in, also without admin involvement).
    A rep only ever sits in 'pending' while awaiting parent consent, so
    every row here is tagged that way -- there is no
    'awaiting_admin_approval' rep state, and POST /admin/approve|reject
    /rep is intentionally unsupported (see admin.py)."""
    rows = await conn.fetch(
        """
        SELECT u.id, u.email, u.role, u.account_status, u.created_at, rp.display_name
        FROM public.users u
        JOIN public.rep_profiles rp ON rp.user_id = u.id
        WHERE u.role = 'rep' AND u.account_status = 'pending'
        ORDER BY u.created_at ASC
        """
    )
    return [
        QueueEntry(
            user_id=str(r["id"]),
            email=r["email"],
            role=r["role"],
            account_status=r["account_status"],
            pending_reason="awaiting_parent_consent",
            display_name=r["display_name"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


async def queue_brands(conn: asyncpg.Connection) -> list[QueueEntry]:
    rows = await conn.fetch(
        """
        SELECT u.id, u.email, u.role, u.account_status, u.created_at, bp.company_name AS display_name
        FROM public.users u
        JOIN public.brand_profiles bp ON bp.user_id = u.id
        WHERE u.role = 'brand' AND u.account_status = 'pending'
        ORDER BY u.created_at ASC
        """
    )
    return [
        QueueEntry(
            user_id=str(r["id"]),
            email=r["email"],
            role=r["role"],
            account_status=r["account_status"],
            pending_reason="awaiting_admin_approval",
            display_name=r["display_name"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


async def queue_recruiters(conn: asyncpg.Connection) -> list[QueueEntry]:
    rows = await conn.fetch(
        """
        SELECT u.id, u.email, u.role, u.account_status, u.created_at, rp.institution_name AS display_name
        FROM public.users u
        JOIN public.recruiter_profiles rp ON rp.user_id = u.id
        WHERE u.role = 'recruiter' AND u.account_status = 'pending'
        ORDER BY u.created_at ASC
        """
    )
    return [
        QueueEntry(
            user_id=str(r["id"]),
            email=r["email"],
            role=r["role"],
            account_status=r["account_status"],
            pending_reason="awaiting_admin_approval",
            display_name=r["display_name"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


async def approve_account(conn: asyncpg.Connection, *, user_id: str, admin_id: str) -> asyncpg.Record | None:
    row = await conn.fetchrow(
        """
        UPDATE public.users
        SET account_status = 'active', reviewed_by = $2, reviewed_at = now(),
            rejection_reason = NULL, updated_at = now()
        WHERE id = $1 AND account_status = 'pending'
        RETURNING id, email, role, account_status
        """,
        user_id,
        admin_id,
    )
    if row is not None and row["role"] == "brand":
        await conn.execute(
            "UPDATE public.brand_profiles SET verified = TRUE, verified_at = now(), verified_by = $2 WHERE user_id = $1",
            user_id,
            admin_id,
        )
    return row


async def reject_account(
    conn: asyncpg.Connection, *, user_id: str, admin_id: str, reason: str
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        UPDATE public.users
        SET account_status = 'rejected', rejection_reason = $3, reviewed_by = $2, reviewed_at = now(),
            updated_at = now()
        WHERE id = $1 AND account_status = 'pending'
        RETURNING id, email, role, account_status
        """,
        user_id,
        admin_id,
        reason,
    )


# ══════════════════════════════════════════════════════════════════
# Deliverable 2: campaign oversight
# ══════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class AdminCampaignRow:
    id: str
    title: str
    status: str
    brand_name: str
    budget_cents: int
    target_categories: list[str]
    flagged_at: datetime | None
    flagged_reason: str | None
    resolved_at: datetime | None
    resolution_action: str | None
    created_at: datetime


_ADMIN_CAMPAIGN_COLUMNS = """
    c.id, c.title, c.status, bp.company_name AS brand_name, c.budget_cents, c.target_categories,
    c.flagged_at, c.flagged_reason, c.resolved_at, c.resolution_action, c.created_at
"""


def _admin_campaign_from_row(row: asyncpg.Record) -> AdminCampaignRow:
    return AdminCampaignRow(
        id=str(row["id"]),
        title=row["title"],
        status=row["status"],
        brand_name=row["brand_name"],
        budget_cents=row["budget_cents"],
        target_categories=list(row["target_categories"] or []),
        flagged_at=row["flagged_at"],
        flagged_reason=row["flagged_reason"],
        resolved_at=row["resolved_at"],
        resolution_action=row["resolution_action"],
        created_at=row["created_at"],
    )


async def list_campaigns(conn: asyncpg.Connection, *, status_filter: str | None, flagged_only: bool) -> list[AdminCampaignRow]:
    conditions = []
    args: list = []
    if status_filter is not None:
        args.append(status_filter)
        conditions.append(f"c.status = ${len(args)}")
    if flagged_only:
        conditions.append("c.flagged_at IS NOT NULL AND c.resolved_at IS NULL")
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = await conn.fetch(
        f"""
        SELECT {_ADMIN_CAMPAIGN_COLUMNS}
        FROM public.campaigns c
        JOIN public.brand_profiles bp ON bp.id = c.brand_id
        {where}
        ORDER BY c.created_at DESC
        """,
        *args,
    )
    return [_admin_campaign_from_row(r) for r in rows]


async def flag_campaign(conn: asyncpg.Connection, campaign_id: str, *, admin_id: str, reason: str) -> AdminCampaignRow | None:
    result = await conn.execute(
        "UPDATE public.campaigns SET flagged_at = now(), flagged_reason = $2, flagged_by = $3 WHERE id = $1",
        campaign_id,
        reason,
        admin_id,
    )
    if result == "UPDATE 0":
        return None
    return await get_admin_campaign(conn, campaign_id)


async def get_admin_campaign(conn: asyncpg.Connection, campaign_id: str) -> AdminCampaignRow | None:
    row = await conn.fetchrow(
        f"""
        SELECT {_ADMIN_CAMPAIGN_COLUMNS}
        FROM public.campaigns c
        JOIN public.brand_profiles bp ON bp.id = c.brand_id
        WHERE c.id = $1
        """,
        campaign_id,
    )
    return _admin_campaign_from_row(row) if row else None


async def mark_campaign_resolved(
    conn: asyncpg.Connection, campaign_id: str, *, admin_id: str, action: str
) -> AdminCampaignRow | None:
    await conn.execute(
        """
        UPDATE public.campaigns
        SET resolved_at = now(), resolution_action = $2, resolved_by = $3
        WHERE id = $1
        """,
        campaign_id,
        action,
        admin_id,
    )
    return await get_admin_campaign(conn, campaign_id)


# ══════════════════════════════════════════════════════════════════
# Deliverable 3: payment management
# ══════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class StuckPayout:
    campaign_rep_id: str
    campaign_id: str
    rep_id: str
    payout_cents: int | None
    payout_status: str
    stripe_transfer_id: str | None
    payout_processing_started_at: datetime | None
    hours_stuck: float


STUCK_PAYOUT_THRESHOLD_HOURS = 48


async def list_stuck_payments(conn: asyncpg.Connection) -> list[StuckPayout]:
    """'Stuck' = payout_status='processing' for longer than
    STUCK_PAYOUT_THRESHOLD_HOURS (Section 8: "Transfers in processing >
    48 hours"). A real timestamp comparison against
    payout_processing_started_at, not a placeholder -- acceptance
    criterion requires a 49-hour-old row to be included and a 40-hour-
    old row excluded."""
    rows = await conn.fetch(
        """
        SELECT id AS campaign_rep_id, campaign_id, rep_id, payout_cents, payout_status,
               stripe_transfer_id, payout_processing_started_at,
               EXTRACT(EPOCH FROM (now() - payout_processing_started_at)) / 3600.0 AS hours_stuck
        FROM public.campaign_reps
        WHERE payout_status = 'processing'
          AND payout_processing_started_at IS NOT NULL
          AND payout_processing_started_at < now() - make_interval(hours => $1)
        ORDER BY payout_processing_started_at ASC
        """,
        STUCK_PAYOUT_THRESHOLD_HOURS,
    )
    return [
        StuckPayout(
            campaign_rep_id=str(r["campaign_rep_id"]),
            campaign_id=str(r["campaign_id"]),
            rep_id=str(r["rep_id"]),
            payout_cents=r["payout_cents"],
            payout_status=r["payout_status"],
            stripe_transfer_id=r["stripe_transfer_id"],
            payout_processing_started_at=r["payout_processing_started_at"],
            hours_stuck=float(r["hours_stuck"]),
        )
        for r in rows
    ]


async def get_by_stripe_transfer_id(conn: asyncpg.Connection, stripe_transfer_id: str) -> asyncpg.Record | None:
    return await conn.fetchrow(
        "SELECT id, campaign_id, rep_id, payout_status, payout_cents FROM public.campaign_reps WHERE stripe_transfer_id = $1",
        stripe_transfer_id,
    )


async def mark_admin_released(
    conn: asyncpg.Connection, campaign_rep_id: str, *, admin_id: str, stripe_transfer_id: str
) -> None:
    """Admin-initiated manual release audit flag (deliverable 3). Called
    by app/services/payout_service.admin_release_payout right after it
    creates the new Stripe Transfer -- this stamps who/when for the
    audit trail, records the new transfer id, and resets
    payout_processing_started_at so the row drops out of the
    stuck-payments query with a fresh clock on the new transfer."""
    await conn.execute(
        """
        UPDATE public.campaign_reps
        SET admin_released = TRUE, admin_released_by = $2, admin_released_at = now(),
            payout_processing_started_at = now(), payout_status = 'processing',
            stripe_transfer_id = $3
        WHERE id = $1
        """,
        campaign_rep_id,
        admin_id,
        stripe_transfer_id,
    )


# ══════════════════════════════════════════════════════════════════
# Deliverable 4: analytics
# ══════════════════════════════════════════════════════════════════


async def revenue_by_stream_and_period(conn: asyncpg.Connection) -> list[dict]:
    """Section 4's three revenue streams:
      - brand_campaign_fees: platform_fee_cents captured on campaigns
        that ever reached a paid status (active/paused/completed).
      - intelligence_subscription: out of scope until Build Prompt 14
        (no billing table exists yet) -- reported as 0 with a note,
        not fabricated.
      - recruiter_subscriptions: not billed via a cents column this
        repo owns (Stripe is the source of truth for subscription
        amounts) -- reported as a count of active subscriptions
        (recruiter_profiles.stripe_subscription_id IS NOT NULL) as the
        best available proxy at MVP, flagged as such in the schema.
    """
    rows = await conn.fetch(
        """
        SELECT to_char(date_trunc('month', created_at), 'YYYY-MM') AS period,
               COALESCE(SUM(platform_fee_cents), 0) AS platform_fee_cents
        FROM public.campaigns
        WHERE status IN ('active', 'paused', 'completed')
        GROUP BY 1
        ORDER BY 1
        """
    )
    recruiter_active_subscriptions = await conn.fetchval(
        "SELECT COUNT(*) FROM public.recruiter_profiles WHERE stripe_subscription_id IS NOT NULL"
    )
    return [
        {
            "period": r["period"],
            "brand_campaign_fees_cents": r["platform_fee_cents"],
            "intelligence_subscription_cents": 0,
            "recruiter_active_subscriptions": recruiter_active_subscriptions,
        }
        for r in rows
    ]


async def reps_by_city_and_category(conn: asyncpg.Connection) -> dict:
    by_city = await conn.fetch(
        "SELECT city, state, COUNT(*) AS n FROM public.rep_profiles GROUP BY city, state ORDER BY n DESC"
    )
    by_category = await conn.fetch(
        "SELECT category, COUNT(*) AS n FROM public.rep_profiles, unnest(categories) AS category GROUP BY category ORDER BY n DESC"
    )
    return {
        "by_city": [{"city": r["city"], "state": r["state"], "count": r["n"]} for r in by_city],
        "by_category": [{"category": r["category"], "count": r["n"]} for r in by_category],
    }


async def campaigns_by_status_and_category(conn: asyncpg.Connection) -> dict:
    by_status = await conn.fetch("SELECT status, COUNT(*) AS n FROM public.campaigns GROUP BY status ORDER BY n DESC")
    by_category = await conn.fetch(
        "SELECT category, COUNT(*) AS n FROM public.campaigns, unnest(target_categories) AS category GROUP BY category ORDER BY n DESC"
    )
    return {
        "by_status": [{"status": r["status"], "count": r["n"]} for r in by_status],
        "by_category": [{"category": r["category"], "count": r["n"]} for r in by_category],
    }


async def consent_status_breakdown(conn: asyncpg.Connection) -> list[dict]:
    """GET /admin/analytics/consent-status -- addition beyond Section 8
    (flagged per deliverable 4), needed to give admin visibility into
    the double opt-in funnel (Section 9): how many under-16 signups are
    stuck awaiting parent consent vs. verified."""
    rows = await conn.fetch(
        """
        SELECT
          CASE
            WHEN parent_email IS NULL THEN 'not_required'
            WHEN parent_verified_at IS NOT NULL THEN 'verified'
            ELSE 'awaiting_verification'
          END AS consent_state,
          COUNT(*) AS n
        FROM public.users
        WHERE role = 'rep'
        GROUP BY 1
        """
    )
    return [{"consent_state": r["consent_state"], "count": r["n"]} for r in rows]


# ══════════════════════════════════════════════════════════════════
# Deliverable 5: outlier-rating detection
# ══════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class OutlierBrand:
    brand_id: str
    company_name: str
    rating_count: int
    average_rating: float
    reason: str


MIN_RATINGS_FOR_OUTLIER_CHECK = 3
OUTLIER_STDDEV_THRESHOLD = 2.0


async def flagged_outlier_brands(conn: asyncpg.Connection) -> list[OutlierBrand]:
    """Concrete rule (deliverable 5): a brand with at least
    MIN_RATINGS_FOR_OUTLIER_CHECK ratings is flagged if either
      (a) 100% of its ratings are five-star (a classic rating-gaming
          signature -- see Section 9's compliance note: "Flag outlier
          rating patterns in admin panel"), or
      (b) its average rating differs from the platform-wide mean by
          more than OUTLIER_STDDEV_THRESHOLD standard deviations.
    Computed directly in SQL against campaign_reps.brand_rating so the
    threshold always reflects live data, not a cached snapshot."""
    platform_row = await conn.fetchrow(
        "SELECT AVG(brand_rating) AS mean, STDDEV_POP(brand_rating) AS stddev "
        "FROM public.campaign_reps WHERE brand_rating IS NOT NULL"
    )
    if platform_row is None or platform_row["mean"] is None:
        return []
    mean = float(platform_row["mean"])
    stddev = float(platform_row["stddev"] or 0.0)

    rows = await conn.fetch(
        """
        SELECT bp.id AS brand_id, bp.company_name,
               COUNT(cr.brand_rating) AS rating_count,
               AVG(cr.brand_rating) AS average_rating,
               COUNT(*) FILTER (WHERE cr.brand_rating = 5) AS five_star_count
        FROM public.campaign_reps cr
        JOIN public.campaigns c ON c.id = cr.campaign_id
        JOIN public.brand_profiles bp ON bp.id = c.brand_id
        WHERE cr.brand_rating IS NOT NULL
        GROUP BY bp.id, bp.company_name
        HAVING COUNT(cr.brand_rating) >= $1
        """,
        MIN_RATINGS_FOR_OUTLIER_CHECK,
    )

    flagged: list[OutlierBrand] = []
    for r in rows:
        avg = float(r["average_rating"])
        count = r["rating_count"]
        if count == r["five_star_count"]:
            flagged.append(
                OutlierBrand(
                    brand_id=str(r["brand_id"]),
                    company_name=r["company_name"],
                    rating_count=count,
                    average_rating=avg,
                    reason="100% five-star ratings",
                )
            )
        elif stddev > 0 and abs(avg - mean) > OUTLIER_STDDEV_THRESHOLD * stddev:
            flagged.append(
                OutlierBrand(
                    brand_id=str(r["brand_id"]),
                    company_name=r["company_name"],
                    rating_count=count,
                    average_rating=avg,
                    reason=f"average rating {avg:.2f} is >{OUTLIER_STDDEV_THRESHOLD}SD from platform mean {mean:.2f}",
                )
            )
    return flagged


# ══════════════════════════════════════════════════════════════════
# Deliverable 6: parent suspension queue
# ══════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class ParentSuspendedRep:
    rep_id: str
    rep_user_id: str
    display_name: str
    parent_id: str
    suspended_by_parent_at: datetime


async def list_parent_suspended_reps(conn: asyncpg.Connection) -> list[ParentSuspendedRep]:
    """Distinct from admin-initiated suspension (parent.py's
    module-level note): only rows where parent_records.
    suspended_by_parent_at IS NOT NULL are reversible by admin here."""
    rows = await conn.fetch(
        """
        SELECT rp.id AS rep_id, u.id AS rep_user_id, rp.display_name, pr.parent_id, pr.suspended_by_parent_at
        FROM public.parent_records pr
        JOIN public.rep_profiles rp ON rp.id = pr.rep_id
        JOIN public.users u ON u.id = rp.user_id
        WHERE pr.suspended_by_parent_at IS NOT NULL AND u.account_status = 'suspended'
        ORDER BY pr.suspended_by_parent_at ASC
        """
    )
    return [
        ParentSuspendedRep(
            rep_id=str(r["rep_id"]),
            rep_user_id=str(r["rep_user_id"]),
            display_name=r["display_name"],
            parent_id=str(r["parent_id"]),
            suspended_by_parent_at=r["suspended_by_parent_at"],
        )
        for r in rows
    ]


async def reverse_parent_suspension(conn: asyncpg.Connection, rep_id: str, *, admin_id: str) -> asyncpg.Record | None:
    row = await conn.fetchrow(
        """
        UPDATE public.parent_records
        SET suspended_by_parent_at = NULL, suspension_reversed_by = $2, suspension_reversed_at = now()
        WHERE rep_id = $1 AND suspended_by_parent_at IS NOT NULL
        RETURNING parent_id, rep_id
        """,
        rep_id,
        admin_id,
    )
    return row


# ══════════════════════════════════════════════════════════════════
# Deliverable 7: safety report queue (highest priority lane)
# ══════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class SafetyReport:
    id: str
    reporter_rep_id: str
    reporter_display_name: str
    campaign_id: str | None
    reason: str
    description: str | None
    status: str
    created_at: datetime
    resolved_at: datetime | None
    resolution_note: str | None


_SAFETY_REPORT_COLUMNS = """
    sr.id, sr.reporter_rep_id, rp.display_name AS reporter_display_name, sr.campaign_id,
    sr.reason, sr.description, sr.status, sr.created_at, sr.resolved_at, sr.resolution_note
"""


def _safety_report_from_row(row: asyncpg.Record) -> SafetyReport:
    return SafetyReport(
        id=str(row["id"]),
        reporter_rep_id=str(row["reporter_rep_id"]),
        reporter_display_name=row["reporter_display_name"],
        campaign_id=str(row["campaign_id"]) if row["campaign_id"] else None,
        reason=row["reason"],
        description=row["description"],
        status=row["status"],
        created_at=row["created_at"],
        resolved_at=row["resolved_at"],
        resolution_note=row["resolution_note"],
    )


async def create_safety_report(
    conn: asyncpg.Connection, *, reporter_rep_id: str, campaign_id: str | None, reason: str, description: str | None
) -> SafetyReport:
    row = await conn.fetchrow(
        """
        INSERT INTO public.safety_reports (reporter_rep_id, campaign_id, reason, description)
        VALUES ($1, $2, $3, $4)
        RETURNING id
        """,
        reporter_rep_id,
        campaign_id,
        reason,
        description,
    )
    return await get_safety_report(conn, str(row["id"]))


async def get_safety_report(conn: asyncpg.Connection, report_id: str) -> SafetyReport:
    row = await conn.fetchrow(
        f"""
        SELECT {_SAFETY_REPORT_COLUMNS}
        FROM public.safety_reports sr
        JOIN public.rep_profiles rp ON rp.id = sr.reporter_rep_id
        WHERE sr.id = $1
        """,
        report_id,
    )
    return _safety_report_from_row(row)


async def list_safety_reports(conn: asyncpg.Connection, *, open_only: bool = True) -> list[SafetyReport]:
    where = "WHERE sr.status = 'open'" if open_only else ""
    rows = await conn.fetch(
        f"""
        SELECT {_SAFETY_REPORT_COLUMNS}
        FROM public.safety_reports sr
        JOIN public.rep_profiles rp ON rp.id = sr.reporter_rep_id
        {where}
        ORDER BY sr.created_at ASC
        """
    )
    return [_safety_report_from_row(r) for r in rows]


async def resolve_safety_report(
    conn: asyncpg.Connection, report_id: str, *, admin_id: str, status: str, resolution_note: str | None
) -> SafetyReport | None:
    row = await conn.fetchrow(
        """
        UPDATE public.safety_reports
        SET status = $2, resolved_at = now(), resolved_by = $3, resolution_note = $4
        WHERE id = $1 AND status = 'open'
        RETURNING id
        """,
        report_id,
        status,
        admin_id,
        resolution_note,
    )
    if row is None:
        return None
    return await get_safety_report(conn, report_id)


# ══════════════════════════════════════════════════════════════════
# Build Prompt 8B deliverable 7: milestone dispute queue -- its own
# category, distinct from campaign-wide disputes (campaigns.flagged_*
# above) and stuck-payment-transfer disputes (payout_status='failed'/
# 'processing'). Modeled as its own table (public.milestone_disputes),
# following the safety_reports precedent above rather than a new
# QueueEntry.pending_reason literal -- see
# supabase/migrations/20260812120000_milestone_payments.sql's own note
# for the full rationale.
# ══════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class MilestoneDispute:
    id: str
    campaign_rep_milestone_id: str
    campaign_id: str
    campaign_title: str
    milestone_title: str
    rep_id: str
    rep_display_name: str
    raised_by: str
    reason: str | None
    status: str
    created_at: datetime
    resolved_at: datetime | None
    resolved_by: str | None
    resolution_note: str | None


_MILESTONE_DISPUTE_COLUMNS = """
    md.id, md.campaign_rep_milestone_id, c.id AS campaign_id, c.title AS campaign_title,
    cm.title AS milestone_title, cr.rep_id, rp.display_name AS rep_display_name,
    md.raised_by, md.reason, md.status, md.created_at, md.resolved_at, md.resolved_by, md.resolution_note
"""

_MILESTONE_DISPUTE_JOIN = """
    FROM public.milestone_disputes md
    JOIN public.campaign_rep_milestones crm ON crm.id = md.campaign_rep_milestone_id
    JOIN public.campaign_milestones cm ON cm.id = crm.campaign_milestone_id
    JOIN public.campaign_reps cr ON cr.id = crm.campaign_rep_id
    JOIN public.campaigns c ON c.id = cr.campaign_id
    JOIN public.rep_profiles rp ON rp.id = cr.rep_id
"""


def _milestone_dispute_from_row(row: asyncpg.Record) -> MilestoneDispute:
    return MilestoneDispute(
        id=str(row["id"]),
        campaign_rep_milestone_id=str(row["campaign_rep_milestone_id"]),
        campaign_id=str(row["campaign_id"]),
        campaign_title=row["campaign_title"],
        milestone_title=row["milestone_title"],
        rep_id=str(row["rep_id"]),
        rep_display_name=row["rep_display_name"],
        raised_by=str(row["raised_by"]),
        reason=row["reason"],
        status=row["status"],
        created_at=row["created_at"],
        resolved_at=row["resolved_at"],
        resolved_by=str(row["resolved_by"]) if row["resolved_by"] else None,
        resolution_note=row["resolution_note"],
    )


async def create_milestone_dispute(
    conn: asyncpg.Connection, *, campaign_rep_milestone_id: str, raised_by: str, reason: str | None
) -> MilestoneDispute:
    row = await conn.fetchrow(
        """
        INSERT INTO public.milestone_disputes (campaign_rep_milestone_id, raised_by, reason)
        VALUES ($1, $2, $3)
        RETURNING id
        """,
        campaign_rep_milestone_id,
        raised_by,
        reason,
    )
    return await get_milestone_dispute(conn, str(row["id"]))


async def get_milestone_dispute(conn: asyncpg.Connection, dispute_id: str) -> MilestoneDispute | None:
    row = await conn.fetchrow(
        f"SELECT {_MILESTONE_DISPUTE_COLUMNS} {_MILESTONE_DISPUTE_JOIN} WHERE md.id = $1", dispute_id
    )
    return _milestone_dispute_from_row(row) if row else None


async def list_milestone_disputes(conn: asyncpg.Connection, *, open_only: bool = True) -> list[MilestoneDispute]:
    where = "WHERE md.status = 'open'" if open_only else ""
    rows = await conn.fetch(f"SELECT {_MILESTONE_DISPUTE_COLUMNS} {_MILESTONE_DISPUTE_JOIN} {where} ORDER BY md.created_at ASC")
    return [_milestone_dispute_from_row(r) for r in rows]


async def resolve_milestone_dispute(
    conn: asyncpg.Connection, dispute_id: str, *, admin_id: str, confirmed: bool, resolution_note: str | None
) -> MilestoneDispute | None:
    """`confirmed` maps to status 'resolved_confirmed' (triggers payout
    via the caller, app/routers/admin.py) or 'resolved_declined' (resets
    the milestone to 'submitted'). Legal only from 'open' -- a dispute
    can only be resolved once."""
    new_status = "resolved_confirmed" if confirmed else "resolved_declined"
    row = await conn.fetchrow(
        """
        UPDATE public.milestone_disputes
        SET status = $2, resolved_at = now(), resolved_by = $3, resolution_note = $4
        WHERE id = $1 AND status = 'open'
        RETURNING id
        """,
        dispute_id,
        new_status,
        admin_id,
        resolution_note,
    )
    if row is None:
        return None
    return await get_milestone_dispute(conn, dispute_id)
