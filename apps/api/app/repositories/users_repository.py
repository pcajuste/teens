"""Data access for public.users.

Every function takes an explicit asyncpg connection (acquired from the
pool by the caller, typically a single connection per request via
app/db/pool.py) rather than reaching for a pool/global — keeps queries
transaction-friendly and easy to unit test against a real connection.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import asyncpg


@dataclass(frozen=True, slots=True)
class UserRecord:
    id: str
    email: str
    role: str
    account_status: str
    date_of_birth: date
    parent_email: str | None
    parent_verified_at: datetime | None
    consent_token: str | None
    consent_token_issued_at: datetime | None
    consent_email_last_sent_at: datetime | None

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "UserRecord":
        return cls(
            id=str(row["id"]),
            email=row["email"],
            role=row["role"],
            account_status=row["account_status"],
            date_of_birth=row["date_of_birth"],
            parent_email=row["parent_email"],
            parent_verified_at=row["parent_verified_at"],
            consent_token=row["consent_token"],
            consent_token_issued_at=row["consent_token_issued_at"],
            consent_email_last_sent_at=row["consent_email_last_sent_at"],
        )


_COLUMNS = (
    "id, email, role, account_status, date_of_birth, parent_email, "
    "parent_verified_at, consent_token, consent_token_issued_at, consent_email_last_sent_at"
)


async def create_user(
    conn: asyncpg.Connection,
    *,
    user_id: str,
    email: str,
    role: str,
    account_status: str,
    date_of_birth: date,
    parent_email: str | None,
    consent_token: str | None,
    consent_token_issued_at: datetime | None,
) -> UserRecord:
    row = await conn.fetchrow(
        f"""
        INSERT INTO public.users
            (id, email, role, account_status, date_of_birth, parent_email,
             consent_token, consent_token_issued_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING {_COLUMNS}
        """,
        user_id,
        email,
        role,
        account_status,
        date_of_birth,
        parent_email,
        consent_token,
        consent_token_issued_at,
    )
    return UserRecord.from_row(row)


async def get_user_by_id(conn: asyncpg.Connection, user_id: str) -> UserRecord | None:
    row = await conn.fetchrow(f"SELECT {_COLUMNS} FROM public.users WHERE id = $1", user_id)
    return UserRecord.from_row(row) if row else None


async def get_user_by_email(conn: asyncpg.Connection, email: str) -> UserRecord | None:
    row = await conn.fetchrow(f"SELECT {_COLUMNS} FROM public.users WHERE email = $1", email)
    return UserRecord.from_row(row) if row else None


async def get_user_by_consent_token(conn: asyncpg.Connection, consent_token: str) -> UserRecord | None:
    row = await conn.fetchrow(
        f"SELECT {_COLUMNS} FROM public.users WHERE consent_token = $1", consent_token
    )
    return UserRecord.from_row(row) if row else None


async def set_consent_token(
    conn: asyncpg.Connection,
    user_id: str,
    *,
    consent_token: str,
    issued_at: datetime,
) -> UserRecord:
    row = await conn.fetchrow(
        f"""
        UPDATE public.users
        SET consent_token = $2, consent_token_issued_at = $3, updated_at = now()
        WHERE id = $1
        RETURNING {_COLUMNS}
        """,
        user_id,
        consent_token,
        issued_at,
    )
    return UserRecord.from_row(row)


async def mark_consent_email_sent(conn: asyncpg.Connection, user_id: str, *, sent_at: datetime) -> None:
    await conn.execute(
        "UPDATE public.users SET consent_email_last_sent_at = $2, updated_at = now() WHERE id = $1",
        user_id,
        sent_at,
    )


async def set_account_status(conn: asyncpg.Connection, user_id: str, status: str) -> UserRecord:
    row = await conn.fetchrow(
        f"""
        UPDATE public.users
        SET account_status = $2, updated_at = now()
        WHERE id = $1
        RETURNING {_COLUMNS}
        """,
        user_id,
        status,
    )
    return UserRecord.from_row(row)


async def mark_parent_verified_and_activate(conn: asyncpg.Connection, user_id: str, *, verified_at: datetime) -> UserRecord:
    row = await conn.fetchrow(
        f"""
        UPDATE public.users
        SET parent_verified_at = $2, account_status = 'active', updated_at = now()
        WHERE id = $1
        RETURNING {_COLUMNS}
        """,
        user_id,
        verified_at,
    )
    return UserRecord.from_row(row)
