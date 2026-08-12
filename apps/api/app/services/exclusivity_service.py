"""Category Exclusivity conflict detection (Build Prompt 8C).

The one function that matters: check_exclusivity_conflict. Every
campaign creation, every campaign activation, and every exclusivity
purchase runs it inside the SAME database transaction as the write it
gates (Section 8C: "this function must be called within the same
database transaction as campaign creation"). Concurrency safety comes
from two things acting together, not the SELECT alone:

  1. SELECT ... FOR UPDATE SKIP LOCKED on the candidate row(s) in
     category_exclusivity_agreements (see
     exclusivity_repository.check_conflict_for_update) -- this makes a
     concurrently-committing exclusivity purchase for the same
     category/city visible-or-not in a race-safe way rather than
     reading a half-committed row.
  2. The caller's own INSERT/UPDATE happening inside that same
     transaction, so if a competing transaction commits a new
     exclusivity agreement (or a competing campaign) between this
     check and the caller's write, Postgres's normal MVCC/row-locking
     semantics -- plus, for campaign creation, the documented one-retry
     -- resolve the race deterministically: exactly one of two
     concurrent writers ends up conflicting against a *committed* row
     while the other doesn't.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

import asyncpg

from app.repositories import exclusivity_repository


async def check_exclusivity_conflict(
    conn: asyncpg.Connection,
    *,
    category: str,
    city: str | None,
    starts_at: datetime,
    ends_at: datetime,
    exclude_brand_id: str | UUID | None = None,
) -> str | None:
    """Returns the conflicting brand's id (str) if any OTHER brand holds
    an active, paid exclusivity agreement overlapping
    [starts_at, ends_at) for `category` at `city` or platform-wide
    (city IS NULL on the agreement), else None. Only the brand_id is
    ever returned -- never agreement details -- so a caller-facing
    response built from this can never leak which agreement or its
    dates/price to the checking brand (Section 8C: "Returns the
    brand_id rather than the agreement details to avoid leaking
    competitive intelligence")."""
    exclude = str(exclude_brand_id) if exclude_brand_id is not None else None
    return await exclusivity_repository.check_conflict_for_update(
        conn,
        category=category,
        city=city,
        starts_at=starts_at,
        ends_at=ends_at,
        exclude_brand_id=exclude,
    )
