"""Data access for the Intelligence Layer (Build Prompt 14).

Two distinct halves, deliberately kept in this one module since they
share the anonymization boundary as their organizing idea:

  - Write path: `list_pending_events` reads the *identifying* source
    tables (campaign_talents/campaigns/talent_profiles) -- that join is fine,
    it happens entirely server-side before anything is written anywhere
    -- and `insert_events`/`mark_written` write the anonymized rows and
    flip the source-table bookkeeping flag. See
    app/services/intelligence_service.py for the PII-stripping/bucketing
    logic that sits between the two.
  - Read path: `trend_by_category`/`trend_by_region`/`trend_by_school_type`
    query ONLY public.intelligence_events_anonymized -- no join, no
    identifying table referenced at all -- and enforce the
    minimum-group-size-of-10 gate (Section 9) before returning anything.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import asyncpg

MIN_GROUP_SIZE = 10
INSUFFICIENT_SAMPLE_SIZE: Literal["insufficient sample size"] = "insufficient sample size"


# ══════════════════════════════════════════════════════════════════
# Write path
# ══════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class PendingIntelligenceSource:
    """One campaign_talents row that has reached 'confirmed'/'paid' and
    hasn't been turned into intelligence_events_anonymized rows yet.
    Deliberately carries identifying fields (campaign_talent_id, talent_id,
    target_categories) -- this dataclass never itself gets written
    anywhere; app/services/intelligence_service.py strips it down to
    the anonymized columns before anything touches
    intelligence_events_anonymized."""

    campaign_talent_id: str
    status: str
    payout_cents: int | None
    confirmed_at: datetime | None
    paid_at: datetime | None
    target_categories: list[str]
    talent_city: str
    talent_state: str
    talent_school_type: str | None


_PENDING_QUERY = """
    SELECT
      cr.id AS campaign_talent_id, cr.status, cr.payout_cents, cr.confirmed_at, cr.paid_at,
      c.target_categories,
      rp.city AS talent_city, rp.state AS talent_state, rp.school_type AS talent_school_type
    FROM public.campaign_talents cr
    JOIN public.campaigns c ON c.id = cr.campaign_id
    JOIN public.talent_profiles rp ON rp.id = cr.talent_id
    WHERE cr.status IN ('confirmed', 'paid') AND cr.intelligence_event_written_at IS NULL
"""


async def list_pending_events(conn: asyncpg.Connection) -> list[PendingIntelligenceSource]:
    rows = await conn.fetch(_PENDING_QUERY)
    return [
        PendingIntelligenceSource(
            campaign_talent_id=str(r["campaign_talent_id"]),
            status=r["status"],
            payout_cents=r["payout_cents"],
            confirmed_at=r["confirmed_at"],
            paid_at=r["paid_at"],
            target_categories=list(r["target_categories"] or []),
            talent_city=r["talent_city"],
            talent_state=r["talent_state"],
            talent_school_type=r["talent_school_type"],
        )
        for r in rows
    ]


@dataclass(frozen=True, slots=True)
class AnonymizedEvent:
    category: str
    city: str
    state: str
    school_type: str
    time_period_bucket: str
    status: str
    payout_bucket: str
    track: str = "brand"


async def insert_events(conn: asyncpg.Connection, events: list[AnonymizedEvent]) -> None:
    if not events:
        return
    await conn.executemany(
        """
        INSERT INTO public.intelligence_events_anonymized
            (category, city, state, school_type, time_period_bucket, status, payout_bucket, track)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
        [
            (e.category, e.city, e.state, e.school_type, e.time_period_bucket, e.status, e.payout_bucket, e.track)
            for e in events
        ],
    )


async def mark_written(conn: asyncpg.Connection, campaign_talent_ids: list[str], *, at: datetime) -> None:
    if not campaign_talent_ids:
        return
    await conn.execute(
        "UPDATE public.campaign_talents SET intelligence_event_written_at = $2 WHERE id = ANY($1::uuid[])",
        campaign_talent_ids,
        at,
    )


# ══════════════════════════════════════════════════════════════════
# Read path -- trend reports (Section 3.5/9). Every query here targets
# public.intelligence_events_anonymized exclusively; none of these
# functions accept or construct a join to any other table.
# ══════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class TrendBucket:
    group: str
    sample_size: int | str
    completed_share: float | str


def _bucket_from_rows(rows: list[asyncpg.Record], *, group_key: str) -> list[TrendBucket]:
    buckets: list[TrendBucket] = []
    for r in rows:
        n = r["n"]
        if n < MIN_GROUP_SIZE:
            buckets.append(TrendBucket(group=r[group_key], sample_size=INSUFFICIENT_SAMPLE_SIZE, completed_share=INSUFFICIENT_SAMPLE_SIZE))
        else:
            buckets.append(TrendBucket(group=r[group_key], sample_size=n, completed_share=round(r["paid_n"] / n, 4)))
    return buckets


async def trend_by_category(conn: asyncpg.Connection) -> list[TrendBucket]:
    rows = await conn.fetch(
        """
        SELECT category AS grp, COUNT(*) AS n, COUNT(*) FILTER (WHERE status = 'paid') AS paid_n
        FROM public.intelligence_events_anonymized
        GROUP BY category
        ORDER BY category
        """
    )
    return _bucket_from_rows(rows, group_key="grp")


async def trend_by_region(conn: asyncpg.Connection) -> list[TrendBucket]:
    rows = await conn.fetch(
        """
        SELECT (city || ', ' || state) AS grp, COUNT(*) AS n, COUNT(*) FILTER (WHERE status = 'paid') AS paid_n
        FROM public.intelligence_events_anonymized
        GROUP BY city, state
        ORDER BY grp
        """
    )
    return _bucket_from_rows(rows, group_key="grp")


async def trend_by_school_type(conn: asyncpg.Connection) -> list[TrendBucket]:
    """Includes the 'unspecified' bucket (null source school_type,
    written as the literal string 'unspecified' by the write path) like
    any other school_type value -- it is not exempt from the
    minimum-group-size gate."""
    rows = await conn.fetch(
        """
        SELECT school_type AS grp, COUNT(*) AS n, COUNT(*) FILTER (WHERE status = 'paid') AS paid_n
        FROM public.intelligence_events_anonymized
        GROUP BY school_type
        ORDER BY school_type
        """
    )
    return _bucket_from_rows(rows, group_key="grp")
