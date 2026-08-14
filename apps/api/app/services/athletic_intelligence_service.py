"""Athletic Intelligence Layer write path (ATHLETICS-8): turns
athletic_seasons rows that have reached 'attested'/'verified' into
fully anonymized public.intelligence_events_anonymized rows, track='athletics'.

Mirrors app/services/intelligence_service.py's shape exactly -- this is
the ONLY place PII is stripped for the athletic intelligence pipeline.
Explicitly enumerated fields that never reach
intelligence_events_anonymized: talent_id, talent display_name,
coach_name/coach_email, team_name, individual-level sport_stats.

category = sport name (not a brand campaign category) -- the `track`
discriminator on intelligence_events_anonymized makes this semantic
difference structurally enforceable (see migration
20260828090000_add_track_to_intelligence_events_anonymized.sql)."""
from __future__ import annotations

from datetime import datetime, timezone

import asyncpg

from app.repositories.athletic_seasons_repository import (
    PendingAthleticIntelligenceSource,
    list_pending_intelligence_events,
    mark_intelligence_written,
)
from app.repositories.intelligence_repository import AnonymizedEvent, insert_events


def _school_type_bucket(school_type: str | None) -> str:
    """null source school_type -> explicit 'unspecified' bucket, same
    convention as the brand pipeline's _school_type_bucket."""
    return school_type or "unspecified"


def _time_period_bucket(at: datetime) -> str:
    quarter = (at.month - 1) // 3 + 1
    return f"{at.year}-Q{quarter}"


def anonymize_athletic_event(source: PendingAthleticIntelligenceSource) -> AnonymizedEvent:
    """One AnonymizedEvent per attested/verified season -- unlike the
    brand pipeline (which fans out per target_categories), an athletic
    season has exactly one sport, so this is a 1:1 mapping. payout_bucket
    is 'unspecified' for every athletic event -- the athletic track has
    no monetary component at MVP."""
    return AnonymizedEvent(
        category=source.sport,
        city=source.talent_city,
        state=source.talent_state,
        school_type=_school_type_bucket(source.talent_school_type),
        time_period_bucket=_time_period_bucket(source.created_at),
        status=source.status,
        payout_bucket="unspecified",
        track="athletics",
    )


async def write_athletic_intelligence_events(conn: asyncpg.Connection) -> int:
    """Reads every attested/verified athletic_season with
    intelligence_event_written_at IS NULL, writes one anonymized event
    each, and marks them written. Returns the count written -- the job
    runner reports {"events_written": int}. Idempotent via the same
    intelligence_event_written_at gate the brand pipeline uses."""
    pending = await list_pending_intelligence_events(conn)
    if not pending:
        return 0
    events = [anonymize_athletic_event(source) for source in pending]
    await insert_events(conn, events)
    await mark_intelligence_written(conn, [source.athletic_season_id for source in pending], at=datetime.now(timezone.utc))
    return len(pending)
