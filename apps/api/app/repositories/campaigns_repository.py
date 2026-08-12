"""Data access for public.campaigns itself (brief/targeting fields).
Rep-side campaign *participation* state (campaign_reps rows) lives in
campaign_reps_repository.py -- this module is for reading campaign
definitions, used by GET /reps/campaigns/available's matching query and
by the accept/decline/submit/withdraw routes to validate campaign
existence/status.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import asyncpg

_COLUMNS = (
    "id, brand_id, title, status, product_name, campaign_goal, key_messaging, "
    "prohibited_content, deliverables_description, target_categories, target_cities, "
    "max_reps, reps_accepted_count, budget_cents, platform_fee_cents, rep_pool_cents, "
    "payout_per_rep_cents, start_date, end_date, stripe_payment_intent_id, payment_type, created_at, updated_at"
)

# Statuses from which a brand may still cancel (Build Prompt 8
# deliverable 6). 'completed' and 'cancelled' are terminal. See
# docs/campaign-cancellation-refund-policy.md for what happens to any
# money already captured for 'active'/'paused' campaigns -- that split
# is an explicitly unresolved business decision, not implemented here.
CANCELLABLE_STATUSES = ("draft", "pending_payment", "payment_failed", "active", "paused")

# A successful Stripe charge only exists once a campaign has reached
# 'active' at least once (per the campaign_status enum's own comment:
# pending_payment -> active happens on payment_intent.succeeded). Used
# by /cancel to decide whether a refund is owed at all.
STATUSES_WITH_CAPTURED_PAYMENT = ("active", "paused")


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
    stripe_payment_intent_id: str | None
    payment_type: str
    created_at: datetime
    updated_at: datetime

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
            stripe_payment_intent_id=row["stripe_payment_intent_id"],
            payment_type=row["payment_type"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


async def get_by_id(conn: asyncpg.Connection, campaign_id: str) -> Campaign | None:
    row = await conn.fetchrow(f"SELECT {_COLUMNS} FROM public.campaigns WHERE id = $1", campaign_id)
    return Campaign.from_row(row) if row else None


async def get_by_id_and_brand(conn: asyncpg.Connection, campaign_id: str, brand_id: str) -> Campaign | None:
    row = await conn.fetchrow(
        f"SELECT {_COLUMNS} FROM public.campaigns WHERE id = $1 AND brand_id = $2", campaign_id, brand_id
    )
    return Campaign.from_row(row) if row else None


async def list_for_brand(conn: asyncpg.Connection, brand_id: str) -> list[Campaign]:
    rows = await conn.fetch(
        f"SELECT {_COLUMNS} FROM public.campaigns WHERE brand_id = $1 ORDER BY created_at DESC", brand_id
    )
    return [Campaign.from_row(row) for row in rows]


async def create_campaign(
    conn: asyncpg.Connection,
    *,
    brand_id: str,
    title: str,
    product_name: str,
    campaign_goal: str,
    key_messaging: str,
    prohibited_content: str | None,
    deliverables_description: str,
    target_categories: list[str],
    target_cities: list[str],
    max_reps: int,
    budget_cents: int,
    platform_fee_cents: int,
    rep_pool_cents: int,
    payout_per_rep_cents: int,
    start_date: date,
    end_date: date,
    payment_type: str = "flat",
) -> Campaign:
    row = await conn.fetchrow(
        f"""
        INSERT INTO public.campaigns
            (brand_id, title, product_name, campaign_goal, key_messaging, prohibited_content,
             deliverables_description, target_categories, target_cities, max_reps,
             budget_cents, platform_fee_cents, rep_pool_cents, payout_per_rep_cents,
             start_date, end_date, payment_type)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
        RETURNING {_COLUMNS}
        """,
        brand_id,
        title,
        product_name,
        campaign_goal,
        key_messaging,
        prohibited_content,
        deliverables_description,
        target_categories,
        target_cities,
        max_reps,
        budget_cents,
        platform_fee_cents,
        rep_pool_cents,
        payout_per_rep_cents,
        start_date,
        end_date,
        payment_type,
    )
    return Campaign.from_row(row)


async def update_campaign(
    conn: asyncpg.Connection,
    campaign_id: str,
    brand_id: str,
    *,
    title: str,
    product_name: str,
    campaign_goal: str,
    key_messaging: str,
    prohibited_content: str | None,
    deliverables_description: str,
    target_categories: list[str],
    target_cities: list[str],
    max_reps: int,
    budget_cents: int,
    platform_fee_cents: int,
    rep_pool_cents: int,
    payout_per_rep_cents: int,
    start_date: date,
    end_date: date,
) -> Campaign | None:
    """Legal only while status='draft' (Build Prompt 8 acceptance
    criterion: "Cannot edit a campaign that has left 'draft'"). Returns
    None if the row isn't a draft owned by this brand, so the caller can
    raise a 409 rather than a misleading 404 when the campaign exists
    but has moved on."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaigns
        SET title = $3, product_name = $4, campaign_goal = $5, key_messaging = $6,
            prohibited_content = $7, deliverables_description = $8, target_categories = $9,
            target_cities = $10, max_reps = $11, budget_cents = $12, platform_fee_cents = $13,
            rep_pool_cents = $14, payout_per_rep_cents = $15, start_date = $16, end_date = $17,
            updated_at = now()
        WHERE id = $1 AND brand_id = $2 AND status = 'draft'
        RETURNING {_COLUMNS}
        """,
        campaign_id,
        brand_id,
        title,
        product_name,
        campaign_goal,
        key_messaging,
        prohibited_content,
        deliverables_description,
        target_categories,
        target_cities,
        max_reps,
        budget_cents,
        platform_fee_cents,
        rep_pool_cents,
        payout_per_rep_cents,
        start_date,
        end_date,
    )
    return Campaign.from_row(row) if row else None


async def set_pending_payment(conn: asyncpg.Connection, campaign_id: str, *, stripe_payment_intent_id: str) -> Campaign | None:
    """POST /brands/campaigns/:id/activate. Legal only from 'draft' --
    a campaign already in 'payment_failed' must use retry_payment
    instead (Build Prompt 8 deliverable 5's dedicated error path)."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaigns
        SET status = 'pending_payment', stripe_payment_intent_id = $2, updated_at = now()
        WHERE id = $1 AND status = 'draft'
        RETURNING {_COLUMNS}
        """,
        campaign_id,
        stripe_payment_intent_id,
    )
    return Campaign.from_row(row) if row else None


async def retry_payment(conn: asyncpg.Connection, campaign_id: str, *, stripe_payment_intent_id: str) -> Campaign | None:
    """POST /brands/campaigns/:id/retry-payment. Legal only from
    'payment_failed'. Always a NEW PaymentIntent id, never the failed
    one reused (Build Prompt 8 deliverable 5 / acceptance criterion) --
    the caller is responsible for creating a fresh Stripe PaymentIntent
    before calling this."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaigns
        SET status = 'pending_payment', stripe_payment_intent_id = $2, updated_at = now()
        WHERE id = $1 AND status = 'payment_failed'
        RETURNING {_COLUMNS}
        """,
        campaign_id,
        stripe_payment_intent_id,
    )
    return Campaign.from_row(row) if row else None


async def set_active(conn: asyncpg.Connection, campaign_id: str) -> Campaign | None:
    """payment_intent.succeeded webhook (Build Prompt 10 deliverable 3).
    Legal only from 'pending_payment', per the campaign_status enum's
    own comment."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaigns SET status = 'active', updated_at = now()
        WHERE id = $1 AND status = 'pending_payment'
        RETURNING {_COLUMNS}
        """,
        campaign_id,
    )
    return Campaign.from_row(row) if row else None


async def set_payment_failed(conn: asyncpg.Connection, campaign_id: str) -> Campaign | None:
    """payment_intent.payment_failed webhook (Build Prompt 10 deliverable
    3). Legal only from 'pending_payment'."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaigns SET status = 'payment_failed', updated_at = now()
        WHERE id = $1 AND status = 'pending_payment'
        RETURNING {_COLUMNS}
        """,
        campaign_id,
    )
    return Campaign.from_row(row) if row else None


async def get_by_stripe_payment_intent_id(conn: asyncpg.Connection, payment_intent_id: str) -> Campaign | None:
    """Looked up by the payment_intent.succeeded/payment_failed webhook
    handlers, which identify the campaign by Stripe PaymentIntent id."""
    row = await conn.fetchrow(f"SELECT {_COLUMNS} FROM public.campaigns WHERE stripe_payment_intent_id = $1", payment_intent_id)
    return Campaign.from_row(row) if row else None


async def set_paused(conn: asyncpg.Connection, campaign_id: str) -> Campaign | None:
    """Legal only from 'active', per Section 8's route description
    ("Pause active campaign")."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaigns SET status = 'paused', updated_at = now()
        WHERE id = $1 AND status = 'active'
        RETURNING {_COLUMNS}
        """,
        campaign_id,
    )
    return Campaign.from_row(row) if row else None


async def set_resumed(conn: asyncpg.Connection, campaign_id: str) -> Campaign | None:
    """Not a separate Section 8 route -- 'paused' has no documented
    un-pause endpoint, but leaving a paused campaign with no way back to
    'active' would be a dead end. Exposed defensively; not wired to a
    route in this prompt since Section 8 doesn't list one (flagged, not
    assumed)."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaigns SET status = 'active', updated_at = now()
        WHERE id = $1 AND status = 'paused'
        RETURNING {_COLUMNS}
        """,
        campaign_id,
    )
    return Campaign.from_row(row) if row else None


async def set_cancelled(conn: asyncpg.Connection, campaign_id: str) -> Campaign | None:
    """See CANCELLABLE_STATUSES / docs/campaign-cancellation-refund-policy.md
    -- this only performs the status transition. Whether/how much money
    gets refunded for a campaign that had a captured payment is decided
    by the caller (app/routers/brands.py), not this function."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.campaigns SET status = 'cancelled', updated_at = now()
        WHERE id = $1 AND status = ANY($2::campaign_status[])
        RETURNING {_COLUMNS}
        """,
        campaign_id,
        list(CANCELLABLE_STATUSES),
    )
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
