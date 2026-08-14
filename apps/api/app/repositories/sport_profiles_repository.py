"""Data access for public.sport_profiles.

Sport-specific talent profile: one row per (talent_id, sport) pair
(UNIQUE constraint from Migration C). `sport` is validated against
app.core.sports.SUPPORTED_SPORTS server-side here -- the same
belt-and-suspenders pattern SportProfileUpdateRequest's field_validator
uses at the schema layer (Pydantic rejects it before the request body
is even fully parsed in the normal request path; this repository-level
check exists for any caller that doesn't go through that schema, e.g.
a future admin/backfill script).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import asyncpg

from app.core.sports import SUPPORTED_SPORTS

_COLUMNS = "id, talent_id, sport, positions, gpa, hudl_url, maxpreps_url, created_at, updated_at"


@dataclass(frozen=True, slots=True)
class SportProfile:
    id: str
    talent_id: str
    sport: str
    positions: list[str]
    gpa: float | None
    hudl_url: str | None
    maxpreps_url: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "SportProfile":
        return cls(
            id=str(row["id"]),
            talent_id=str(row["talent_id"]),
            sport=row["sport"],
            positions=list(row["positions"] or []),
            gpa=float(row["gpa"]) if row["gpa"] is not None else None,
            hudl_url=row["hudl_url"],
            maxpreps_url=row["maxpreps_url"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


async def upsert_sport_profile(
    conn: asyncpg.Connection,
    talent_id: str,
    *,
    sport: str,
    positions: list[str],
    gpa: float | None = None,
    hudl_url: str | None = None,
    maxpreps_url: str | None = None,
) -> SportProfile:
    if sport not in SUPPORTED_SPORTS:
        raise ValueError(f"Unsupported sport: {sport!r}. Valid: {sorted(SUPPORTED_SPORTS)}")
    row = await conn.fetchrow(
        f"""
        INSERT INTO public.sport_profiles (talent_id, sport, positions, gpa, hudl_url, maxpreps_url)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (talent_id, sport) DO UPDATE
        SET positions = EXCLUDED.positions,
            gpa = EXCLUDED.gpa,
            hudl_url = EXCLUDED.hudl_url,
            maxpreps_url = EXCLUDED.maxpreps_url,
            updated_at = now()
        RETURNING {_COLUMNS}
        """,
        talent_id,
        sport,
        positions,
        gpa,
        hudl_url,
        maxpreps_url,
    )
    return SportProfile.from_row(row)


async def list_for_talent(conn: asyncpg.Connection, talent_id: str) -> list[SportProfile]:
    rows = await conn.fetch(
        f"SELECT {_COLUMNS} FROM public.sport_profiles WHERE talent_id = $1 ORDER BY sport ASC",
        talent_id,
    )
    return [SportProfile.from_row(r) for r in rows]


async def get_by_talent_and_sport(conn: asyncpg.Connection, talent_id: str, sport: str) -> SportProfile | None:
    row = await conn.fetchrow(
        f"SELECT {_COLUMNS} FROM public.sport_profiles WHERE talent_id = $1 AND sport = $2",
        talent_id,
        sport,
    )
    return SportProfile.from_row(row) if row else None
