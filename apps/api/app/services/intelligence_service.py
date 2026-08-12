"""Intelligence Layer write path (Build Prompt 14): turns
campaign_reps rows that have reached 'confirmed'/'paid' into fully
anonymized public.intelligence_events_anonymized rows.

This module is the ONLY place PII is stripped for the intelligence
pipeline -- app/repositories/intelligence_repository.list_pending_events
reads identifying fields (campaign_rep_id, target_categories,
rep_city/state/school_type) precisely so this function can drop every
one of them before anything is written. Explicitly enumerated fields
that never reach intelligence_events_anonymized, per the build prompt:
rep_id, rep display_name, school_name, instagram_handle, tiktok_handle,
individual-level city (this schema has no location field finer than
city -- see the migration header comment), campaign_id, brand_id, and
payout_cents (replaced by a bucket -- see _payout_bucket below).
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.repositories.intelligence_repository import AnonymizedEvent, PendingIntelligenceSource

_PAYOUT_BUCKETS: tuple[tuple[int, str], ...] = (
    (5_000, "under_50"),
    (15_000, "50_150"),
    (30_000, "150_300"),
    (50_000, "300_500"),
)
_PAYOUT_BUCKET_TOP = "500_plus"


def _payout_bucket(payout_cents: int | None) -> str:
    if payout_cents is None:
        return "unspecified"
    for ceiling, label in _PAYOUT_BUCKETS:
        if payout_cents < ceiling:
            return label
    return _PAYOUT_BUCKET_TOP


def _school_type_bucket(school_type: str | None) -> str:
    """null source school_type -> explicit 'unspecified' bucket, never
    silently dropped (build prompt deliverable 1)."""
    return school_type or "unspecified"


def _time_period_bucket(at: datetime) -> str:
    quarter = (at.month - 1) // 3 + 1
    return f"{at.year}-Q{quarter}"


def anonymize(source: PendingIntelligenceSource) -> list[AnonymizedEvent]:
    """One AnonymizedEvent per category the source campaign targeted
    (campaigns.target_categories is an array -- see the migration
    header comment for why this fans out rather than collapsing to a
    single column). Returns an empty list only if the campaign somehow
    targeted zero categories, which campaigns_repository's creation
    path never allows -- there is nothing to silently drop here."""
    transition_at = source.paid_at if source.status == "paid" else source.confirmed_at
    if transition_at is None:
        transition_at = datetime.now(timezone.utc)

    time_period_bucket = _time_period_bucket(transition_at)
    school_type = _school_type_bucket(source.rep_school_type)
    payout_bucket = _payout_bucket(source.payout_cents)

    return [
        AnonymizedEvent(
            category=category,
            city=source.rep_city,
            state=source.rep_state,
            school_type=school_type,
            time_period_bucket=time_period_bucket,
            status=source.status,
            payout_bucket=payout_bucket,
        )
        for category in source.target_categories
    ]
