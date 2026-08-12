"""Data access for public.parent_auth_tokens -- the magic-link tokens
themselves (distinct from the parent session JWT issued after a
successful verify; see app/core/security.py's module docstring).

Tokens are stored hashed (schema comment: "store a hash, never the raw
token"). SHA-256 of the raw token is sufficient here -- unlike a
password, this is a single-use, high-entropy (32 bytes,
secrets.token_urlsafe) random value with no attacker-guessable
structure, so a slow KDF (bcrypt/scrypt) buys nothing a fast hash
doesn't already provide against brute force.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import asyncpg


@dataclass(frozen=True, slots=True)
class ParentAuthToken:
    id: str
    parent_record_id: str
    expires_at: datetime
    used_at: datetime | None


async def create_token(
    conn: asyncpg.Connection, *, parent_record_id: str, token_hash: str, expires_at: datetime
) -> None:
    await conn.execute(
        "INSERT INTO public.parent_auth_tokens (parent_record_id, token_hash, expires_at) VALUES ($1, $2, $3)",
        parent_record_id,
        token_hash,
        expires_at,
    )


async def get_by_token_hash(conn: asyncpg.Connection, token_hash: str) -> ParentAuthToken | None:
    row = await conn.fetchrow(
        "SELECT id, parent_record_id, expires_at, used_at FROM public.parent_auth_tokens WHERE token_hash = $1",
        token_hash,
    )
    if row is None:
        return None
    return ParentAuthToken(
        id=str(row["id"]),
        parent_record_id=str(row["parent_record_id"]),
        expires_at=row["expires_at"],
        used_at=row["used_at"],
    )


async def mark_used(conn: asyncpg.Connection, token_id: str, *, used_at: datetime) -> None:
    await conn.execute("UPDATE public.parent_auth_tokens SET used_at = $2 WHERE id = $1", token_id, used_at)
