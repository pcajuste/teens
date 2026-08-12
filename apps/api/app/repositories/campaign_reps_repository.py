"""Data access for the parent-facing slice of public.campaign_reps:
the campaign-approval queue and the monthly-digest campaign stats.
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
