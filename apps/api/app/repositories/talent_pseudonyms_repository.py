"""Data access for public.talent_pseudonyms (Build Prompt 8I pseudonym
system). One persistent, never-regenerated handle per talent -- see
app/services/pseudonym_service.py for handle generation and the
no-de-anonymization guarantee this table exists to support."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import asyncpg


@dataclass(frozen=True, slots=True)
class TalentPseudonym:
    id: str
    talent_id: str
    handle: str
    created_at: datetime

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "TalentPseudonym":
        return cls(
            id=str(row["id"]),
            talent_id=str(row["talent_id"]),
            handle=row["handle"],
            created_at=row["created_at"],
        )


async def get_by_talent_id(conn: asyncpg.Connection, talent_id: str) -> TalentPseudonym | None:
    row = await conn.fetchrow(
        "SELECT id, talent_id, handle, created_at FROM public.talent_pseudonyms WHERE talent_id = $1", talent_id
    )
    return TalentPseudonym.from_row(row) if row else None


async def create(conn: asyncpg.Connection, *, talent_id: str, handle: str) -> TalentPseudonym:
    row = await conn.fetchrow(
        """
        INSERT INTO public.talent_pseudonyms (talent_id, handle)
        VALUES ($1, $2)
        RETURNING id, talent_id, handle, created_at
        """,
        talent_id,
        handle,
    )
    return TalentPseudonym.from_row(row)


async def handle_exists(conn: asyncpg.Connection, handle: str) -> bool:
    row = await conn.fetchrow("SELECT 1 FROM public.talent_pseudonyms WHERE handle = $1", handle)
    return row is not None
