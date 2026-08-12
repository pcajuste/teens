"""asyncpg connection pool.

Connects via DATABASE_URL — a direct Postgres connection that
intentionally bypasses RLS (see .env.example's DATABASE_URL comment).
Authorization is enforced in application code (app/core/security.py's
role/account-status dependencies), not by RLS, at this layer.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

import asyncpg

from app.core.config import Settings

_pool: asyncpg.Pool | None = None


async def init_pool(settings: Settings) -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(dsn=settings.database_url, min_size=1, max_size=10)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized — init_pool() must run at app startup.")
    return _pool


async def get_connection() -> AsyncIterator[asyncpg.Connection]:
    pool = get_pool()
    async with pool.acquire() as conn:
        yield conn
