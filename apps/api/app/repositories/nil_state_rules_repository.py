"""Data access for public.nil_state_rules (admin-managed table).

Read-only for the application. Admin updates via SQL or a future
admin UI endpoint when state laws change. The full state-eligibility
map is seeded in Migration C.

Industry reference: Opendorse's compliance database pattern -- human
team maintains the compliance table, application reads it. Not a
live external API (laws change at the legislative level, not in
real-time).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import asyncpg


@dataclass(frozen=True, slots=True)
class NilStateRule:
    state: str
    nil_eligible: bool
    notes: str | None
    effective_date: date
    last_updated_at: datetime


async def get_by_state(
    conn: asyncpg.Connection, state: str
) -> NilStateRule | None:
    row = await conn.fetchrow(
        "SELECT state, nil_eligible, notes, effective_date, last_updated_at "
        "FROM public.nil_state_rules WHERE state = $1",
        state.upper(),
    )
    if not row:
        return None
    return NilStateRule(
        state=row["state"],
        nil_eligible=row["nil_eligible"],
        notes=row["notes"],
        effective_date=row["effective_date"],
        last_updated_at=row["last_updated_at"],
    )


async def list_all(conn: asyncpg.Connection) -> list[NilStateRule]:
    rows = await conn.fetch(
        "SELECT state, nil_eligible, notes, effective_date, last_updated_at "
        "FROM public.nil_state_rules ORDER BY state"
    )
    return [
        NilStateRule(
            state=r["state"],
            nil_eligible=r["nil_eligible"],
            notes=r["notes"],
            effective_date=r["effective_date"],
            last_updated_at=r["last_updated_at"],
        )
        for r in rows
    ]
