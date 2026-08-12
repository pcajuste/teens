"""Data access for public.campaigns itself (brief/targeting fields).
Rep-side campaign *participation* state (campaign_reps rows) lives in
campaign_reps_repository.py -- this module is for reading campaign
definitions, used by GET /reps/campaigns/available's matching query and
by the accept/decline/submit/withdraw routes to validate campaign
existence/status.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import asyncpg

_COLUMNS = (
    "id, brand_id, title, status, product_name, campaign_goal, key_messaging, "
    "prohibited_content, deliverables_description, target_categories, target_cities, "
    "max_reps, reps_accepted_count, budget_cents, platform_fee_cents, rep_pool_cents, "
    "payout_per_rep_cents, start_date, end_date"
)


@dataclass(frozen=True, slots=True)
class Campaign:
    id: str
    brand_id: str
    title: str
    status: str
    product_name: str
    campaign_goal: str
    key_messaging: str
    prohibited_content: str | None
    deliverables_description: str
    target_categories: list[str]
    target_cities: list[str]
    max_reps: int
    reps_accepted_count: int
    budget_cents: int
    platform_fee_cents: int
    rep_pool_cents: int
    payout_per_rep_cents: int | None
    start_date: date
    end_date: date

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "Campaign":
        return cls(
            id=str(row["id"]),
            brand_id=str(row["brand_id"]),
            title=row["title"],
            status=row["status"],
            product_name=row["product_name"],
            campaign_goal=row["campaign_goal"],
            key_messaging=row["key_messaging"],
            prohibited_content=row["prohibited_content"],
            deliverables_description=row["deliverables_description"],
            target_categories=list(row["target_categories"] or []),
            target_cities=list(row["target_cities"] or []),
            max_reps=row["max_reps"],
            reps_accepted_count=row["reps_accepted_count"],
            budget_cents=row["budget_cents"],
            platform_fee_cents=row["platform_fee_cents"],
            rep_pool_cents=row["rep_pool_cents"],
            payout_per_rep_cents=row["payout_per_rep_cents"],
            start_date=row["start_date"],
            end_date=row["end_date"],
        )


async def get_by_id(conn: asyncpg.Connection, campaign_id: str) -> Campaign | None:
    row = await conn.fetchrow(f"SELECT {_COLUMNS} FROM public.campaigns WHERE id = $1", campaign_id)
    return Campaign.from_row(row) if row else None


async def list_available_for_rep(
    conn: asyncpg.Connection, *, rep_id: str, categories: list[str], city: str
) -> list[Campaign]:
    """Open campaigns (status='active') matching the rep's categories
    and city, that the rep does not already have a campaign_reps row
    for. Values-filter exclusion (parent-blocked categories) is applied
    by the caller (app/routers/reps.py), one apply_values_filter() call
    per candidate campaign category -- reused from
    app.services.parent_service, not reimplemented here (Build Prompt 5
    deliverable 3's explicit instruction)."""
    rows = await conn.fetch(
        f"""
        SELECT {_COLUMNS} FROM public.campaigns c
        WHERE c.status = 'active'
          AND c.target_categories && $2::text[]
          AND (
                array_length(c.target_cities, 1) IS NULL
                OR $3 = ANY (c.target_cities)
              )
          AND NOT EXISTS (
                SELECT 1 FROM public.campaign_reps cr
                WHERE cr.campaign_id = c.id AND cr.rep_id = $1
              )
        ORDER BY c.created_at DESC
        """,
        rep_id,
        categories,
        city,
    )
    return [Campaign.from_row(row) for row in rows]
