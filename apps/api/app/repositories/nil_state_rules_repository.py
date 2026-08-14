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


async def get_by_talent_state(conn: asyncpg.Connection, talent_id: str) -> NilStateRule | None:
    """Joins talent_profiles.state with nil_state_rules -- returns the
    rule for the talent's own state. None only if the talent's state
    is not in nil_state_rules (should not happen after the seed)."""
    row = await conn.fetchrow(
        """
        SELECT r.state, r.nil_eligible, r.notes, r.effective_date, r.last_updated_at
        FROM public.nil_state_rules r
        JOIN public.talent_profiles t ON t.state = r.state
        WHERE t.id = $1
        """,
        talent_id,
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


async def update_rule(
    conn: asyncpg.Connection, state: str, *, nil_eligible: bool, notes: str | None, effective_date: date
) -> NilStateRule | None:
    """Admin-only update (ATHLETICS-3). Caller is responsible for
    revoking any now-invalid nil_eligibility_records acknowledgments
    (see admin.py's PUT /admin/nil-rules/:state)."""
    row = await conn.fetchrow(
        """
        UPDATE public.nil_state_rules
        SET nil_eligible = $2, notes = $3, effective_date = $4, last_updated_at = now()
        WHERE state = $1
        RETURNING state, nil_eligible, notes, effective_date, last_updated_at
        """,
        state.upper(),
        nil_eligible,
        notes,
        effective_date,
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


async def revoke_acknowledgments_for_state(conn: asyncpg.Connection, state: str) -> int:
    """When a state flips eligible -> ineligible, existing acknowledgments
    are no longer valid -- policy reversals are not grandfathered.
    Returns the number of talent records affected."""
    result = await conn.execute(
        """
        UPDATE public.nil_eligibility_records
        SET school_association_rules_acknowledged = FALSE, acknowledged_at = NULL, nil_eligible_in_state = FALSE
        WHERE state = $1 AND nil_eligible_in_state = TRUE
        """,
        state.upper(),
    )
    return int(result.split(" ")[-1])


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
