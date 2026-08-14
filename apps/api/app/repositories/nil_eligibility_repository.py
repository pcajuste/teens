"""Data access for public.nil_eligibility_records (ATHLETICS-3).

A talent's NIL eligibility record is lazy-created on their first GET
/talents/athletics/nil call -- there is no row until the talent checks,
matching the playbook's D-decision to avoid pre-populating every talent
with a record they may never look at.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import asyncpg


@dataclass(frozen=True, slots=True)
class NilEligibilityRecord:
    id: str
    talent_id: str
    state: str
    nil_eligible_in_state: bool
    school_association_rules_acknowledged: bool
    acknowledged_at: datetime | None
    eligibility_checked_at: datetime

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "NilEligibilityRecord":
        return cls(
            id=str(row["id"]),
            talent_id=str(row["talent_id"]),
            state=row["state"],
            nil_eligible_in_state=row["nil_eligible_in_state"],
            school_association_rules_acknowledged=row["school_association_rules_acknowledged"],
            acknowledged_at=row["acknowledged_at"],
            eligibility_checked_at=row["eligibility_checked_at"],
        )


_COLUMNS = (
    "id, talent_id, state, nil_eligible_in_state, "
    "school_association_rules_acknowledged, acknowledged_at, eligibility_checked_at"
)


async def get_by_talent_id(conn: asyncpg.Connection, talent_id: str) -> NilEligibilityRecord | None:
    row = await conn.fetchrow(
        f"SELECT {_COLUMNS} FROM public.nil_eligibility_records WHERE talent_id = $1",
        talent_id,
    )
    return NilEligibilityRecord.from_row(row) if row else None


async def create_or_update(
    conn: asyncpg.Connection,
    talent_id: str,
    *,
    state: str,
    nil_eligible_in_state: bool,
    school_association_rules_acknowledged: bool = False,
    acknowledged_at: datetime | None = None,
) -> NilEligibilityRecord:
    row = await conn.fetchrow(
        f"""
        INSERT INTO public.nil_eligibility_records
            (talent_id, state, nil_eligible_in_state,
             school_association_rules_acknowledged, acknowledged_at)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (talent_id, state) DO UPDATE SET
            nil_eligible_in_state = EXCLUDED.nil_eligible_in_state,
            school_association_rules_acknowledged = EXCLUDED.school_association_rules_acknowledged,
            acknowledged_at = EXCLUDED.acknowledged_at,
            eligibility_checked_at = now()
        RETURNING {_COLUMNS}
        """,
        talent_id,
        state,
        nil_eligible_in_state,
        school_association_rules_acknowledged,
        acknowledged_at,
    )
    return NilEligibilityRecord.from_row(row)


async def mark_acknowledged(conn: asyncpg.Connection, talent_id: str, *, at: datetime) -> NilEligibilityRecord | None:
    """Legal only if nil_eligible_in_state=True on the existing record --
    a talent in an ineligible state cannot acknowledge rules that don't
    permit them to participate. Returns None if no record exists or the
    state is ineligible."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.nil_eligibility_records
        SET school_association_rules_acknowledged = TRUE, acknowledged_at = $2, eligibility_checked_at = now()
        WHERE talent_id = $1 AND nil_eligible_in_state = TRUE
        RETURNING {_COLUMNS}
        """,
        talent_id,
        at,
    )
    return NilEligibilityRecord.from_row(row) if row else None
