"""Data access for public.category_exclusivity_agreements (Build Prompt
8C). Kept as its own module rather than folded into brand_profiles/
campaigns_repository.py -- exclusivity agreements have an independent
lifecycle (purchase -> paid/failed -> expired/cancelled) that never
joins against campaigns at the schema level (Section 8C: "the campaign
itself does not store a reference to an exclusivity agreement").
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import asyncpg

_COLUMNS = """
    id, brand_id, category, city, starts_at, ends_at, status, fee_cents,
    stripe_payment_intent_id, payment_status, cancelled_at,
    cancellation_reason, refund_cents, created_at
"""


@dataclass(frozen=True, slots=True)
class ExclusivityAgreement:
    id: str
    brand_id: str
    category: str
    city: str | None
    starts_at: datetime
    ends_at: datetime
    status: str
    fee_cents: int
    stripe_payment_intent_id: str
    payment_status: str
    cancelled_at: datetime | None
    cancellation_reason: str | None
    refund_cents: int | None
    created_at: datetime

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "ExclusivityAgreement":
        return cls(
            id=str(row["id"]),
            brand_id=str(row["brand_id"]),
            category=row["category"],
            city=row["city"],
            starts_at=row["starts_at"],
            ends_at=row["ends_at"],
            status=row["status"],
            fee_cents=row["fee_cents"],
            stripe_payment_intent_id=row["stripe_payment_intent_id"],
            payment_status=row["payment_status"],
            cancelled_at=row["cancelled_at"],
            cancellation_reason=row["cancellation_reason"],
            refund_cents=row["refund_cents"],
            created_at=row["created_at"],
        )


async def check_conflict_for_update(
    conn: asyncpg.Connection,
    *,
    category: str,
    city: str | None,
    starts_at: datetime,
    ends_at: datetime,
    exclude_brand_id: str | None,
) -> str | None:
    """Returns the conflicting brand_id (as str) if an active, paid
    exclusivity agreement overlaps [starts_at, ends_at) for `category`
    at either `city` or platform-wide (city IS NULL), excluding
    `exclude_brand_id`'s own agreements (self-conflict exemption).

    Section 8C's own text asks for "SELECT FOR UPDATE SKIP LOCKED" --
    but SKIP LOCKED is a work-queue primitive (safe only when skipping a
    locked row means "someone else is already handling it, move on"),
    not a correctness tool for a existence/conflict check: if this
    query skipped a row another concurrent transaction happened to be
    holding a lock on, it would silently report "no conflict" for an
    exclusivity agreement that is, in fact, still active and paid --
    exactly the false negative the acceptance criteria explicitly rule
    out ("exactly one succeeds, one receives 409", not "whichever one
    got unlucky with lock timing succeeds"). This uses plain
    SELECT ... FOR UPDATE instead: every concurrent caller queues on the
    same row lock and each, in turn, still sees the true committed
    state once it acquires the lock -- concurrency-safe by blocking
    rather than by skipping. Must run inside the caller's own
    transaction so the lock is held until that transaction commits or
    rolls back, which is what actually serializes concurrent
    purchases/campaign-creations against each other (see
    exclusivity_service.check_exclusivity_conflict's docstring)."""
    query = """
        SELECT brand_id
        FROM public.category_exclusivity_agreements
        WHERE category = $1
          AND status = 'active'
          AND payment_status = 'paid'
          AND starts_at < $3
          AND ends_at > $2
          AND (city = $4 OR city IS NULL)
          AND ($5::uuid IS NULL OR brand_id != $5)
        FOR UPDATE
        LIMIT 1
    """
    row = await conn.fetchrow(query, category, starts_at, ends_at, city, exclude_brand_id)
    return str(row["brand_id"]) if row is not None else None


async def create_agreement(
    conn: asyncpg.Connection,
    *,
    brand_id: str,
    category: str,
    city: str | None,
    starts_at: datetime,
    ends_at: datetime,
    fee_cents: int,
    stripe_payment_intent_id: str,
) -> ExclusivityAgreement:
    row = await conn.fetchrow(
        f"""
        INSERT INTO public.category_exclusivity_agreements
            (brand_id, category, city, starts_at, ends_at, fee_cents, stripe_payment_intent_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING {_COLUMNS}
        """,
        brand_id,
        category,
        city,
        starts_at,
        ends_at,
        fee_cents,
        stripe_payment_intent_id,
    )
    return ExclusivityAgreement.from_row(row)


async def get_by_id(conn: asyncpg.Connection, agreement_id: str) -> ExclusivityAgreement | None:
    row = await conn.fetchrow(
        f"SELECT {_COLUMNS} FROM public.category_exclusivity_agreements WHERE id = $1", agreement_id
    )
    return ExclusivityAgreement.from_row(row) if row is not None else None


async def get_by_payment_intent_id(conn: asyncpg.Connection, payment_intent_id: str) -> ExclusivityAgreement | None:
    row = await conn.fetchrow(
        f"SELECT {_COLUMNS} FROM public.category_exclusivity_agreements WHERE stripe_payment_intent_id = $1",
        payment_intent_id,
    )
    return ExclusivityAgreement.from_row(row) if row is not None else None


async def list_for_brand(conn: asyncpg.Connection, brand_id: str) -> list[ExclusivityAgreement]:
    rows = await conn.fetch(
        f"SELECT {_COLUMNS} FROM public.category_exclusivity_agreements WHERE brand_id = $1 ORDER BY created_at DESC",
        brand_id,
    )
    return [ExclusivityAgreement.from_row(r) for r in rows]


async def list_all(conn: asyncpg.Connection, *, limit: int, offset: int) -> list[ExclusivityAgreement]:
    rows = await conn.fetch(
        f"SELECT {_COLUMNS} FROM public.category_exclusivity_agreements ORDER BY created_at DESC LIMIT $1 OFFSET $2",
        limit,
        offset,
    )
    return [ExclusivityAgreement.from_row(r) for r in rows]


async def count_all(conn: asyncpg.Connection) -> int:
    return await conn.fetchval("SELECT COUNT(*) FROM public.category_exclusivity_agreements")


async def list_active(conn: asyncpg.Connection) -> list[ExclusivityAgreement]:
    rows = await conn.fetch(f"SELECT {_COLUMNS} FROM public.category_exclusivity_agreements WHERE status = 'active' ORDER BY ends_at ASC")
    return [ExclusivityAgreement.from_row(r) for r in rows]


async def set_payment_status(conn: asyncpg.Connection, agreement_id: str, *, payment_status: str) -> ExclusivityAgreement | None:
    row = await conn.fetchrow(
        f"""
        UPDATE public.category_exclusivity_agreements
        SET payment_status = $2
        WHERE id = $1
        RETURNING {_COLUMNS}
        """,
        agreement_id,
        payment_status,
    )
    return ExclusivityAgreement.from_row(row) if row is not None else None


async def mark_paid(conn: asyncpg.Connection, agreement_id: str) -> ExclusivityAgreement | None:
    """Only transitions a row still 'pending' -- idempotent against a
    replayed webhook (stripe_events_repository.record_if_new already
    guards duplicate delivery at the dispatch layer; this WHERE guard is
    a second, cheap belt-and-suspenders check consistent with every
    other state-machine UPDATE in this codebase, e.g.
    campaigns_repository.set_active)."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.category_exclusivity_agreements
        SET payment_status = 'paid'
        WHERE id = $1 AND payment_status = 'pending'
        RETURNING {_COLUMNS}
        """,
        agreement_id,
    )
    return ExclusivityAgreement.from_row(row) if row is not None else None


async def mark_payment_failed(conn: asyncpg.Connection, agreement_id: str) -> ExclusivityAgreement | None:
    row = await conn.fetchrow(
        f"""
        UPDATE public.category_exclusivity_agreements
        SET payment_status = 'failed', status = 'cancelled'
        WHERE id = $1 AND payment_status = 'pending'
        RETURNING {_COLUMNS}
        """,
        agreement_id,
    )
    return ExclusivityAgreement.from_row(row) if row is not None else None


async def expire_due(conn: asyncpg.Connection, *, now: datetime) -> list[ExclusivityAgreement]:
    """Build Prompt 8C deliverable 6: finds ends_at < now() AND
    status = 'active', flips them to 'expired', and returns the rows
    that were actually transitioned (an empty list on a second run
    against the same agreements -- the WHERE status = 'active' guard
    means nothing matches the second time, giving the idempotency the
    acceptance criteria ask for: "running the job twice ... produces
    one log entry")."""
    rows = await conn.fetch(
        f"""
        UPDATE public.category_exclusivity_agreements
        SET status = 'expired'
        WHERE status = 'active' AND ends_at < $1
        RETURNING {_COLUMNS}
        """,
        now,
    )
    return [ExclusivityAgreement.from_row(r) for r in rows]


async def cancel(
    conn: asyncpg.Connection,
    agreement_id: str,
    *,
    cancellation_reason: str,
    refund_cents: int,
    at: datetime,
) -> ExclusivityAgreement | None:
    row = await conn.fetchrow(
        f"""
        UPDATE public.category_exclusivity_agreements
        SET status = 'cancelled', cancelled_at = $2, cancellation_reason = $3, refund_cents = $4,
            payment_status = CASE WHEN $4 >= fee_cents THEN 'refunded' ELSE 'partially_refunded' END
        WHERE id = $1
        RETURNING {_COLUMNS}
        """,
        agreement_id,
        at,
        cancellation_reason,
        refund_cents,
    )
    return ExclusivityAgreement.from_row(row) if row is not None else None


async def revenue_analytics(conn: asyncpg.Connection) -> dict:
    total_row = await conn.fetchrow(
        "SELECT COALESCE(SUM(fee_cents), 0) AS total_revenue_cents, COUNT(*) AS paid_count "
        "FROM public.category_exclusivity_agreements WHERE payment_status = 'paid'"
    )
    active_count = await conn.fetchval(
        "SELECT COUNT(*) FROM public.category_exclusivity_agreements WHERE status = 'active'"
    )
    category_rows = await conn.fetch(
        "SELECT category, COUNT(*) AS purchase_count FROM public.category_exclusivity_agreements "
        "GROUP BY category ORDER BY purchase_count DESC, category ASC"
    )
    avg_days = await conn.fetchval(
        "SELECT AVG(EXTRACT(EPOCH FROM (ends_at - starts_at)) / 86400.0) FROM public.category_exclusivity_agreements"
    )
    return {
        "total_revenue_cents": int(total_row["total_revenue_cents"]),
        "active_count": int(active_count or 0),
        "categories_by_purchase_frequency": [
            {"category": r["category"], "purchase_count": int(r["purchase_count"])} for r in category_rows
        ],
        "average_agreement_length_days": float(avg_days) if avg_days is not None else 0.0,
    }
