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


@dataclass(frozen=True, slots=True)
class RecruiterContactWithRepName:
    """list_for_recruiter's row shape: a RecruiterContact plus the rep's
    display_name. Joining in the name here isn't a new PII disclosure --
    the recruiter already paid the credit that revealed it when they sent
    this message (get_rep_detail/contact_rep both require and charge for
    that view first) -- it just saves the frontend a second per-row
    credit-free lookup against a rep_profiles read path that doesn't
    otherwise exist for recruiters outside the credit-gated routes."""

    contact: RecruiterContact
    rep_display_name: str


async def list_for_recruiter(conn: asyncpg.Connection, recruiter_id: str) -> list[RecruiterContactWithRepName]:
    """Build Prompt 12 deliverable 4 ("Messaging UI: ... read-receipt
    display") -- the recruiter-facing counterpart to list_for_rep, newest
    first, so a recruiter can see whether/when each message they sent
    was read. No message content beyond what the recruiter themselves
    wrote is exposed here (one-directional messaging, no reply)."""
    rows = await conn.fetch(
        f"""
        SELECT c.id, c.recruiter_id, c.rep_id, c.message_text, c.read_at, c.messaged_at, r.display_name
        FROM public.recruiter_contacts c
        JOIN public.rep_profiles r ON r.id = c.rep_id
        WHERE c.recruiter_id = $1
        ORDER BY c.messaged_at DESC
        """,
        recruiter_id,
    )
    return [RecruiterContactWithRepName(contact=RecruiterContact.from_row(row), rep_display_name=row["display_name"]) for row in rows]


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
