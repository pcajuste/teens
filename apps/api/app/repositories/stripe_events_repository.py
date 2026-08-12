"""Webhook idempotency (Build Prompt 10 acceptance criterion: "Same
webhook payload twice -> no duplicate side effects"). One row per
processed Stripe event id -- see supabase/migrations/20260815090000_stripe_events_table.sql.
"""
from __future__ import annotations

import asyncpg


async def record_if_new(conn: asyncpg.Connection, *, event_id: str, event_type: str) -> bool:
    """Inserts the event id if not already seen. Returns True the first
    time (caller should dispatch), False on a retry (caller should
    return 200 without re-running any handler) -- ON CONFLICT DO NOTHING
    makes this atomic against concurrent delivery of the same event."""
    result = await conn.execute(
        "INSERT INTO public.stripe_events (event_id, event_type) VALUES ($1, $2) ON CONFLICT (event_id) DO NOTHING",
        event_id,
        event_type,
    )
    return result == "INSERT 0 1"
