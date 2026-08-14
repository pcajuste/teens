"""Data access for public.recruiter_saved_profiles (Build Prompt 11
deliverable 5). Composite PK (recruiter_id, talent_id) -- a recruiter can
save a talent to at most one row, list_name is just a label on that row,
not a separate list membership table."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import asyncpg

_COLUMNS = "recruiter_id, talent_id, saved_at, list_name"


@dataclass(frozen=True, slots=True)
class SavedProfile:
    recruiter_id: str
    talent_id: str
    saved_at: datetime
    list_name: str | None

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "SavedProfile":
        return cls(
            recruiter_id=str(row["recruiter_id"]),
            talent_id=str(row["talent_id"]),
            saved_at=row["saved_at"],
            list_name=row["list_name"],
        )


async def save(conn: asyncpg.Connection, *, recruiter_id: str, talent_id: str, list_name: str | None) -> SavedProfile:
    """Upsert -- saving an already-saved talent just updates list_name
    rather than erroring, since re-saving to move a talent between lists
    is the expected use of list_name."""
    row = await conn.fetchrow(
        f"""
        INSERT INTO public.recruiter_saved_profiles (recruiter_id, talent_id, list_name)
        VALUES ($1, $2, COALESCE($3, 'Default'))
        ON CONFLICT (recruiter_id, talent_id) DO UPDATE SET list_name = COALESCE($3, public.recruiter_saved_profiles.list_name)
        RETURNING {_COLUMNS}
        """,
        recruiter_id,
        talent_id,
        list_name,
    )
    return SavedProfile.from_row(row)


async def unsave(conn: asyncpg.Connection, *, recruiter_id: str, talent_id: str) -> bool:
    result = await conn.execute(
        "DELETE FROM public.recruiter_saved_profiles WHERE recruiter_id = $1 AND talent_id = $2",
        recruiter_id,
        talent_id,
    )
    return result != "DELETE 0"


async def list_for_recruiter(conn: asyncpg.Connection, recruiter_id: str, *, track: str | None = None) -> list[SavedProfile]:
    """track filters against talent_profiles.enabled_tracks -- 'athletics'
    or 'brand' (ATHLETICS-7 deliverable 3). None returns everything."""
    if track is None:
        rows = await conn.fetch(
            f"SELECT {_COLUMNS} FROM public.recruiter_saved_profiles WHERE recruiter_id = $1 ORDER BY saved_at DESC",
            recruiter_id,
        )
        return [SavedProfile.from_row(row) for row in rows]

    prefixed_columns = ", ".join(f"sp.{c.strip()}" for c in _COLUMNS.split(","))
    rows = await conn.fetch(
        f"""
        SELECT {prefixed_columns}
        FROM public.recruiter_saved_profiles sp
        JOIN public.talent_profiles tp ON tp.id = sp.talent_id
        WHERE sp.recruiter_id = $1 AND $2 = ANY(tp.enabled_tracks)
        ORDER BY sp.saved_at DESC
        """,
        recruiter_id,
        track,
    )
    return [SavedProfile.from_row(row) for row in rows]
