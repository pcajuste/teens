"""Data access for public.recruiter_profiles (Build Prompt 11). Same
shape as brand_profiles_repository.py/talent_profiles_repository.py:
every function takes an explicit asyncpg connection, frozen/slots
dataclass with `from_row`.

Credit deduction (GET /recruiters/talents/:id, POST .../contact) uses a
single atomic conditional UPDATE with a WHERE-clause precondition and
RETURNING -- the same pattern as campaigns_repository.set_pending_payment
-- rather than an explicit transaction/row lock. A single UPDATE
statement's WHERE clause is re-evaluated per-row inside the same
statement and concurrent UPDATEs to the same row serialize under
Postgres's MVCC, so "concurrent requests with exactly 1 credit
remaining -> exactly one success" holds with no extra locking
machinery, matching this codebase's existing style."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import asyncpg

_COLUMNS = (
    "id, user_id, institution_name, institution_type, website, verified, "
    "contact_credits_remaining, credits_reset_date, stripe_customer_id, "
    "stripe_subscription_id, created_at, updated_at"
)


@dataclass(frozen=True, slots=True)
class RecruiterProfile:
    id: str
    user_id: str
    institution_name: str
    institution_type: str
    website: str | None
    verified: bool
    contact_credits_remaining: int
    credits_reset_date: date | None
    stripe_customer_id: str | None
    stripe_subscription_id: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "RecruiterProfile":
        return cls(
            id=str(row["id"]),
            user_id=str(row["user_id"]),
            institution_name=row["institution_name"],
            institution_type=row["institution_type"],
            website=row["website"],
            verified=row["verified"],
            contact_credits_remaining=row["contact_credits_remaining"],
            credits_reset_date=row["credits_reset_date"],
            stripe_customer_id=row["stripe_customer_id"],
            stripe_subscription_id=row["stripe_subscription_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


async def get_by_id(conn: asyncpg.Connection, recruiter_id: str) -> RecruiterProfile | None:
    row = await conn.fetchrow(f"SELECT {_COLUMNS} FROM public.recruiter_profiles WHERE id = $1", recruiter_id)
    return RecruiterProfile.from_row(row) if row else None


async def get_by_user_id(conn: asyncpg.Connection, user_id: str) -> RecruiterProfile | None:
    row = await conn.fetchrow(f"SELECT {_COLUMNS} FROM public.recruiter_profiles WHERE user_id = $1", user_id)
    return RecruiterProfile.from_row(row) if row else None


async def get_by_stripe_customer_id(conn: asyncpg.Connection, stripe_customer_id: str) -> RecruiterProfile | None:
    row = await conn.fetchrow(
        f"SELECT {_COLUMNS} FROM public.recruiter_profiles WHERE stripe_customer_id = $1", stripe_customer_id
    )
    return RecruiterProfile.from_row(row) if row else None


async def get_by_stripe_subscription_id(conn: asyncpg.Connection, stripe_subscription_id: str) -> RecruiterProfile | None:
    row = await conn.fetchrow(
        f"SELECT {_COLUMNS} FROM public.recruiter_profiles WHERE stripe_subscription_id = $1", stripe_subscription_id
    )
    return RecruiterProfile.from_row(row) if row else None


async def create_recruiter_profile(
    conn: asyncpg.Connection,
    *,
    user_id: str,
    institution_name: str,
    institution_type: str,
    website: str | None,
) -> RecruiterProfile:
    row = await conn.fetchrow(
        f"""
        INSERT INTO public.recruiter_profiles (user_id, institution_name, institution_type, website)
        VALUES ($1, $2, $3, $4)
        RETURNING {_COLUMNS}
        """,
        user_id,
        institution_name,
        institution_type,
        website,
    )
    return RecruiterProfile.from_row(row)


async def update_recruiter_profile(
    conn: asyncpg.Connection,
    recruiter_id: str,
    *,
    institution_name: str,
    institution_type: str,
    website: str | None,
) -> RecruiterProfile:
    row = await conn.fetchrow(
        f"""
        UPDATE public.recruiter_profiles
        SET institution_name = $2, institution_type = $3, website = $4, updated_at = now()
        WHERE id = $1
        RETURNING {_COLUMNS}
        """,
        recruiter_id,
        institution_name,
        institution_type,
        website,
    )
    return RecruiterProfile.from_row(row)


async def set_stripe_customer_id(conn: asyncpg.Connection, recruiter_id: str, stripe_customer_id: str) -> None:
    await conn.execute(
        "UPDATE public.recruiter_profiles SET stripe_customer_id = $2, updated_at = now() WHERE id = $1",
        recruiter_id,
        stripe_customer_id,
    )


async def decrement_credit(conn: asyncpg.Connection, recruiter_id: str) -> RecruiterProfile | None:
    """Atomic "spend 1 credit if any remain" -- returns the updated row,
    or None if the recruiter had 0 credits (caller raises 402). See
    module docstring for why this single UPDATE is concurrency-safe
    without an explicit transaction/lock."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.recruiter_profiles
        SET contact_credits_remaining = contact_credits_remaining - 1, updated_at = now()
        WHERE id = $1 AND contact_credits_remaining > 0
        RETURNING {_COLUMNS}
        """,
        recruiter_id,
    )
    return RecruiterProfile.from_row(row) if row else None


async def activate_subscription(
    conn: asyncpg.Connection,
    recruiter_id: str,
    *,
    stripe_subscription_id: str,
    credits_allotment: int,
    credits_reset_date: date,
) -> RecruiterProfile | None:
    """customer.subscription.created webhook -- sets the recruiter's
    subscription id and starting credit balance. Does NOT flip
    public.users.account_status itself (that's the dual-gate: admin
    approval AND subscription creation both required, Build Prompt 11
    deliverable 8) -- the webhook handler does that separately via
    users_repository so this function stays a pure recruiter_profiles
    write."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.recruiter_profiles
        SET stripe_subscription_id = $2, contact_credits_remaining = $3, credits_reset_date = $4, updated_at = now()
        WHERE id = $1
        RETURNING {_COLUMNS}
        """,
        recruiter_id,
        stripe_subscription_id,
        credits_allotment,
        credits_reset_date,
    )
    return RecruiterProfile.from_row(row) if row else None


async def reset_credits(
    conn: asyncpg.Connection, recruiter_id: str, *, credits_allotment: int, credits_reset_date: date
) -> RecruiterProfile | None:
    """customer.subscription.updated (renewal) webhook -- credits do NOT
    roll over, unused credits are lost (explicit MVP decision, Build
    Prompt 11 deliverable 8)."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.recruiter_profiles
        SET contact_credits_remaining = $2, credits_reset_date = $3, updated_at = now()
        WHERE id = $1
        RETURNING {_COLUMNS}
        """,
        recruiter_id,
        credits_allotment,
        credits_reset_date,
    )
    return RecruiterProfile.from_row(row) if row else None


async def clear_subscription(conn: asyncpg.Connection, recruiter_id: str) -> RecruiterProfile | None:
    """customer.subscription.deleted webhook -- clears the subscription
    id (the signal recruiters.py's _require_subscription_active checks)
    and zeroes the remaining balance; existing saved profiles and
    message history are untouched (deliverable 8: nothing here deletes
    from recruiter_saved_profiles/recruiter_contacts)."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.recruiter_profiles
        SET stripe_subscription_id = NULL, contact_credits_remaining = 0, credits_reset_date = NULL, updated_at = now()
        WHERE id = $1
        RETURNING {_COLUMNS}
        """,
        recruiter_id,
    )
    return RecruiterProfile.from_row(row) if row else None


async def add_credits(conn: asyncpg.Connection, recruiter_id: str, *, credits: int) -> RecruiterProfile | None:
    """Stripe one-time credit top-up webhook -- increments (not rest)
    the balance, distinct from reset_credits."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.recruiter_profiles
        SET contact_credits_remaining = contact_credits_remaining + $2, updated_at = now()
        WHERE id = $1
        RETURNING {_COLUMNS}
        """,
        recruiter_id,
        credits,
    )
    return RecruiterProfile.from_row(row) if row else None
