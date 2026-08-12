"""Data access for public.parent_records, joined with rep_profiles/users
where a parent-portal operation needs rep context (age, earnings,
profile fields) in the same query."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime

import asyncpg

_PARENT_COLUMNS = (
    "parent_id, rep_id, parent_email, campaign_approval_required, values_filters, "
    "digest_enabled, portal_expires_at, suspended_by_parent_at, "
    "magic_link_last_requested_at, digest_last_sent_at, last_digest_profile_completeness_score"
)


@dataclass(frozen=True, slots=True)
class ParentRecord:
    parent_id: str
    rep_id: str
    parent_email: str
    campaign_approval_required: bool
    values_filters: list[str]
    digest_enabled: bool
    portal_expires_at: datetime
    suspended_by_parent_at: datetime | None
    magic_link_last_requested_at: datetime | None
    digest_last_sent_at: datetime | None
    last_digest_profile_completeness_score: int | None

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "ParentRecord":
        return cls(
            parent_id=str(row["parent_id"]),
            rep_id=str(row["rep_id"]),
            parent_email=row["parent_email"],
            campaign_approval_required=row["campaign_approval_required"],
            values_filters=json.loads(row["values_filters"]) if row["values_filters"] else [],
            digest_enabled=row["digest_enabled"],
            portal_expires_at=row["portal_expires_at"],
            suspended_by_parent_at=row["suspended_by_parent_at"],
            magic_link_last_requested_at=row["magic_link_last_requested_at"],
            digest_last_sent_at=row["digest_last_sent_at"],
            last_digest_profile_completeness_score=row["last_digest_profile_completeness_score"],
        )


@dataclass(frozen=True, slots=True)
class RepContext:
    """Rep-side fields a parent-portal operation commonly needs
    alongside the parent_records row."""

    rep_user_id: str
    rep_email: str
    rep_account_status: str
    date_of_birth: date
    display_name: str
    school_name: str
    graduation_year: int
    categories: list[str]
    profile_completeness_score: int
    total_earnings_cents: int
    total_campaigns_completed: int


async def create_parent_record(
    conn: asyncpg.Connection,
    *,
    rep_id: str,
    parent_email: str,
    campaign_approval_required: bool = True,
    digest_enabled: bool = True,
    portal_expires_at: datetime,
) -> ParentRecord:
    """Prompt 5: created at the moment rep_profiles is first created
    during onboarding, only for reps whose public.users.parent_verified_at
    IS NOT NULL (the under-16 consent-flow path) -- see
    docs/parent_records_creation_timing.md. Always called inside the
    same transaction as the rep_profiles insert."""
    row = await conn.fetchrow(
        f"""
        INSERT INTO public.parent_records
            (rep_id, parent_email, campaign_approval_required, values_filters,
             digest_enabled, portal_expires_at)
        VALUES ($1, $2, $3, '[]'::jsonb, $4, $5)
        RETURNING {_PARENT_COLUMNS}
        """,
        rep_id,
        parent_email,
        campaign_approval_required,
        digest_enabled,
        portal_expires_at,
    )
    return ParentRecord.from_row(row)


async def get_parent_by_id(conn: asyncpg.Connection, parent_id: str) -> ParentRecord | None:
    row = await conn.fetchrow(
        f"SELECT {_PARENT_COLUMNS} FROM public.parent_records WHERE parent_id = $1", parent_id
    )
    return ParentRecord.from_row(row) if row else None


async def get_parent_by_rep_id(conn: asyncpg.Connection, rep_id: str) -> ParentRecord | None:
    row = await conn.fetchrow(
        f"SELECT {_PARENT_COLUMNS} FROM public.parent_records WHERE rep_id = $1", rep_id
    )
    return ParentRecord.from_row(row) if row else None


async def get_most_recent_parent_by_email(conn: asyncpg.Connection, parent_email: str) -> ParentRecord | None:
    row = await conn.fetchrow(
        f"""
        SELECT {_PARENT_COLUMNS} FROM public.parent_records
        WHERE parent_email = $1
        ORDER BY created_at DESC
        LIMIT 1
        """,
        parent_email,
    )
    return ParentRecord.from_row(row) if row else None


async def get_rep_context(conn: asyncpg.Connection, rep_id: str) -> RepContext | None:
    row = await conn.fetchrow(
        """
        SELECT
            u.id AS rep_user_id, u.email AS rep_email, u.account_status AS rep_account_status,
            u.date_of_birth,
            rp.display_name, rp.school_name, rp.graduation_year, rp.categories,
            rp.profile_completeness_score, rp.total_earnings_cents, rp.total_campaigns_completed
        FROM public.rep_profiles rp
        JOIN public.users u ON u.id = rp.user_id
        WHERE rp.id = $1
        """,
        rep_id,
    )
    if row is None:
        return None
    return RepContext(
        rep_user_id=str(row["rep_user_id"]),
        rep_email=row["rep_email"],
        rep_account_status=row["rep_account_status"],
        date_of_birth=row["date_of_birth"],
        display_name=row["display_name"],
        school_name=row["school_name"],
        graduation_year=row["graduation_year"],
        categories=list(row["categories"] or []),
        profile_completeness_score=row["profile_completeness_score"],
        total_earnings_cents=row["total_earnings_cents"],
        total_campaigns_completed=row["total_campaigns_completed"],
    )


async def create_parent_record(
    conn: asyncpg.Connection,
    *,
    rep_id: str,
    parent_email: str,
    portal_expires_at: datetime,
    campaign_approval_required: bool = True,
    digest_enabled: bool = True,
) -> ParentRecord:
    """Creates the parent_records row at rep onboarding time (Prompt 5,
    PUT /reps/me creating rep_profiles for the first time), ONLY for
    reps who went through the under-16 consent flow
    (public.users.parent_verified_at IS NOT NULL) -- see
    docs/parent_records_creation_timing.md for the full design note.
    Callers are expected to run this inside the same transaction as the
    rep_profiles insert it depends on (parent_records.rep_id is a
    NOT NULL UNIQUE FK to rep_profiles.id)."""
    row = await conn.fetchrow(
        f"""
        INSERT INTO public.parent_records
            (rep_id, parent_email, campaign_approval_required, values_filters,
             digest_enabled, portal_expires_at)
        VALUES ($1, $2, $3, '[]'::jsonb, $4, $5)
        RETURNING {_PARENT_COLUMNS}
        """,
        rep_id,
        parent_email,
        campaign_approval_required,
        digest_enabled,
        portal_expires_at,
    )
    return ParentRecord.from_row(row)


async def update_magic_link_last_requested_at(conn: asyncpg.Connection, parent_id: str, *, at: datetime) -> None:
    await conn.execute(
        "UPDATE public.parent_records SET magic_link_last_requested_at = $2, updated_at = now() WHERE parent_id = $1",
        parent_id,
        at,
    )


async def update_values_filters(conn: asyncpg.Connection, parent_id: str, values_filters: list[str]) -> ParentRecord:
    row = await conn.fetchrow(
        f"""
        UPDATE public.parent_records SET values_filters = $2::jsonb, updated_at = now()
        WHERE parent_id = $1
        RETURNING {_PARENT_COLUMNS}
        """,
        parent_id,
        json.dumps(values_filters),
    )
    return ParentRecord.from_row(row)


async def update_campaign_approval_required(conn: asyncpg.Connection, parent_id: str, enabled: bool) -> ParentRecord:
    row = await conn.fetchrow(
        f"""
        UPDATE public.parent_records SET campaign_approval_required = $2, updated_at = now()
        WHERE parent_id = $1
        RETURNING {_PARENT_COLUMNS}
        """,
        parent_id,
        enabled,
    )
    return ParentRecord.from_row(row)


async def update_digest_enabled(conn: asyncpg.Connection, parent_id: str, enabled: bool) -> ParentRecord:
    row = await conn.fetchrow(
        f"""
        UPDATE public.parent_records SET digest_enabled = $2, updated_at = now()
        WHERE parent_id = $1
        RETURNING {_PARENT_COLUMNS}
        """,
        parent_id,
        enabled,
    )
    return ParentRecord.from_row(row)


async def set_suspended_by_parent(conn: asyncpg.Connection, parent_id: str, *, at: datetime | None) -> None:
    await conn.execute(
        "UPDATE public.parent_records SET suspended_by_parent_at = $2, updated_at = now() WHERE parent_id = $1",
        parent_id,
        at,
    )


async def update_digest_snapshot(conn: asyncpg.Connection, parent_id: str, *, sent_at: datetime, score: int) -> None:
    await conn.execute(
        """
        UPDATE public.parent_records
        SET digest_last_sent_at = $2, last_digest_profile_completeness_score = $3, updated_at = now()
        WHERE parent_id = $1
        """,
        parent_id,
        sent_at,
        score,
    )


async def list_digest_enabled(conn: asyncpg.Connection) -> list[ParentRecord]:
    rows = await conn.fetch(f"SELECT {_PARENT_COLUMNS} FROM public.parent_records WHERE digest_enabled = TRUE")
    return [ParentRecord.from_row(row) for row in rows]
