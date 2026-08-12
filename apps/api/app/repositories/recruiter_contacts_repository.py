"""Data access for public.recruiter_contacts (Build Prompt 11). One
row per recruiter->rep message, one-directional by design -- no reply
column, no reply endpoint (deliverable 4). The UNIQUE(recruiter_id,
rep_id) constraint enforces "you've already contacted this rep" on a
second contact attempt; create_contact surfaces that as a return of
None (caught via asyncpg.UniqueViolationError) rather than letting the
IntegrityError bubble up raw, matching this codebase's "None ->
caller raises HTTPException" convention used throughout
campaigns_repository/campaign_reps_repository."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import asyncpg

_COLUMNS = "id, recruiter_id, rep_id, message_text, read_at, messaged_at"


@dataclass(frozen=True, slots=True)
class RecruiterContact:
    id: str
    recruiter_id: str
    rep_id: str
    message_text: str
    read_at: datetime | None
    messaged_at: datetime

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "RecruiterContact":
        return cls(
            id=str(row["id"]),
            recruiter_id=str(row["recruiter_id"]),
            rep_id=str(row["rep_id"]),
            message_text=row["message_text"],
            read_at=row["read_at"],
            messaged_at=row["messaged_at"],
        )


async def get_for_recruiter_and_rep(conn: asyncpg.Connection, recruiter_id: str, rep_id: str) -> RecruiterContact | None:
    row = await conn.fetchrow(
        f"SELECT {_COLUMNS} FROM public.recruiter_contacts WHERE recruiter_id = $1 AND rep_id = $2",
        recruiter_id,
        rep_id,
    )
    return RecruiterContact.from_row(row) if row else None


async def create_contact(
    conn: asyncpg.Connection, *, recruiter_id: str, rep_id: str, message_text: str
) -> RecruiterContact | None:
    try:
        row = await conn.fetchrow(
            f"""
            INSERT INTO public.recruiter_contacts (recruiter_id, rep_id, message_text)
            VALUES ($1, $2, $3)
            RETURNING {_COLUMNS}
            """,
            recruiter_id,
            rep_id,
            message_text,
        )
    except asyncpg.UniqueViolationError:
        return None
    return RecruiterContact.from_row(row)


async def list_for_rep(conn: asyncpg.Connection, rep_id: str) -> list[RecruiterContact]:
    """GET /reps/inbox -- newest first."""
    rows = await conn.fetch(
        f"SELECT {_COLUMNS} FROM public.recruiter_contacts WHERE rep_id = $1 ORDER BY messaged_at DESC",
        rep_id,
    )
    return [RecruiterContact.from_row(row) for row in rows]


async def get_by_id_and_rep(conn: asyncpg.Connection, contact_id: str, rep_id: str) -> RecruiterContact | None:
    row = await conn.fetchrow(
        f"SELECT {_COLUMNS} FROM public.recruiter_contacts WHERE id = $1 AND rep_id = $2",
        contact_id,
        rep_id,
    )
    return RecruiterContact.from_row(row) if row else None


async def mark_read(conn: asyncpg.Connection, contact_id: str, rep_id: str) -> RecruiterContact | None:
    row = await conn.fetchrow(
        f"""
        UPDATE public.recruiter_contacts
        SET read_at = now()
        WHERE id = $1 AND rep_id = $2 AND read_at IS NULL
        RETURNING {_COLUMNS}
        """,
        contact_id,
        rep_id,
    )
    if row is not None:
        return RecruiterContact.from_row(row)
    # Idempotent: already-read or not-found are distinguished by the
    # caller via get_by_id_and_rep, not here -- this function only
    # reports whether *this call* performed the transition.
    return None
