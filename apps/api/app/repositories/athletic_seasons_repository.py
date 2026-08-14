"""Data access for public.athletic_seasons -- the athletic track's
"campaign" equivalent (ATHLETICS-1). State machine:

    draft -> pending_attestation -> attested -> verified

See Teenure_Prompts_Athletics.md's ATHLETICS-1 section for the full
transition table. Every transition function here returns None on an
illegal transition (wrong current status, or row not found) rather
than raising -- the router turns None into the appropriate 409/404,
matching this codebase's existing campaign_talents_repository pattern
(accept/decline/submit/withdraw all return None on an illegal
transition).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import asyncpg

from app.core.sport_stats_schemas import validate_sport_stats

_COLUMNS = (
    "id, talent_id, sport, season_year, season_type, team_name, level, sport_stats, "
    "coach_name, coach_email, coach_attestation_status, coach_attested_at, "
    "admin_verified, admin_verified_at, admin_verified_by, admin_flag_reason, "
    "intelligence_event_written_at, status, created_at, updated_at"
)


@dataclass(frozen=True, slots=True)
class AthleticSeason:
    id: str
    talent_id: str
    sport: str
    season_year: int
    season_type: str
    team_name: str
    level: str
    sport_stats: dict[str, Any]
    coach_name: str | None
    coach_email: str | None
    coach_attestation_status: str
    coach_attested_at: datetime | None
    admin_verified: bool
    admin_verified_at: datetime | None
    admin_verified_by: str | None
    admin_flag_reason: str | None
    intelligence_event_written_at: datetime | None
    status: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "AthleticSeason":
        stats = row["sport_stats"]
        return cls(
            id=str(row["id"]),
            talent_id=str(row["talent_id"]),
            sport=row["sport"],
            season_year=row["season_year"],
            season_type=row["season_type"],
            team_name=row["team_name"],
            level=row["level"],
            sport_stats=json.loads(stats) if isinstance(stats, str) else dict(stats or {}),
            coach_name=row["coach_name"],
            coach_email=row["coach_email"],
            coach_attestation_status=row["coach_attestation_status"],
            coach_attested_at=row["coach_attested_at"],
            admin_verified=row["admin_verified"],
            admin_verified_at=row["admin_verified_at"],
            admin_verified_by=row["admin_verified_by"],
            admin_flag_reason=row["admin_flag_reason"],
            intelligence_event_written_at=row["intelligence_event_written_at"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


async def get_by_id(conn: asyncpg.Connection, season_id: str) -> AthleticSeason | None:
    row = await conn.fetchrow(f"SELECT {_COLUMNS} FROM public.athletic_seasons WHERE id = $1", season_id)
    return AthleticSeason.from_row(row) if row else None


async def get_by_id_and_talent(conn: asyncpg.Connection, season_id: str, talent_id: str) -> AthleticSeason | None:
    """Ownership-scoped lookup -- use this in every talent-facing route
    so a season belonging to another talent behaves identically to a
    season that doesn't exist (404, never 403 -- ATHLETICS-1 acceptance
    criterion, same non-enumeration rule as campaign_talents_repository)."""
    row = await conn.fetchrow(
        f"SELECT {_COLUMNS} FROM public.athletic_seasons WHERE id = $1 AND talent_id = $2",
        season_id,
        talent_id,
    )
    return AthleticSeason.from_row(row) if row else None


async def list_for_talent(conn: asyncpg.Connection, talent_id: str) -> list[AthleticSeason]:
    rows = await conn.fetch(
        f"SELECT {_COLUMNS} FROM public.athletic_seasons "
        "WHERE talent_id = $1 ORDER BY season_year DESC, sport ASC",
        talent_id,
    )
    return [AthleticSeason.from_row(r) for r in rows]


async def create_season(
    conn: asyncpg.Connection,
    talent_id: str,
    *,
    sport: str,
    season_year: int,
    season_type: str,
    team_name: str,
    level: str,
    sport_stats: dict[str, Any],
    coach_name: str | None = None,
    coach_email: str | None = None,
) -> AthleticSeason:
    """Creates a season in 'draft' status. sport_stats is validated by
    the caller (schemas/athletics.py's field_validator) before this is
    reached, but validated again here defensively -- repository
    functions in this codebase never trust that the router already did
    the check (mirrors validate-at-every-layer elsewhere, e.g.
    sport_profiles_repository.upsert_sport_profile)."""
    validate_sport_stats(sport, sport_stats)
    row = await conn.fetchrow(
        f"""
        INSERT INTO public.athletic_seasons
            (talent_id, sport, season_year, season_type, team_name, level, sport_stats,
             coach_name, coach_email)
        VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9)
        RETURNING {_COLUMNS}
        """,
        talent_id,
        sport,
        season_year,
        season_type,
        team_name,
        level,
        json.dumps(sport_stats),
        coach_name,
        coach_email,
    )
    return AthleticSeason.from_row(row)


async def update_season(
    conn: asyncpg.Connection,
    season_id: str,
    *,
    sport: str,
    season_year: int,
    season_type: str,
    team_name: str,
    level: str,
    sport_stats: dict[str, Any],
    coach_name: str | None,
    coach_email: str | None,
) -> AthleticSeason:
    """Legal only from 'draft' -- raises ValueError if status != 'draft'.
    Validates sport_stats via validate_sport_stats() before writing."""
    validate_sport_stats(sport, sport_stats)
    current = await get_by_id(conn, season_id)
    if current is None or current.status != "draft":
        raise ValueError("Season can only be edited in draft status.")
    row = await conn.fetchrow(
        f"""
        UPDATE public.athletic_seasons
        SET sport = $2, season_year = $3, season_type = $4, team_name = $5, level = $6,
            sport_stats = $7::jsonb, coach_name = $8, coach_email = $9, updated_at = now()
        WHERE id = $1 AND status = 'draft'
        RETURNING {_COLUMNS}
        """,
        season_id,
        sport,
        season_year,
        season_type,
        team_name,
        level,
        json.dumps(sport_stats),
        coach_name,
        coach_email,
    )
    return AthleticSeason.from_row(row)


async def delete_season(conn: asyncpg.Connection, season_id: str) -> bool:
    """Legal only from 'draft'. Returns True if deleted, False if not
    found or wrong status. Hard delete -- no soft delete at MVP."""
    result = await conn.execute(
        "DELETE FROM public.athletic_seasons WHERE id = $1 AND status = 'draft'",
        season_id,
    )
    return result == "DELETE 1"


async def transition_to_pending_attestation(conn: asyncpg.Connection, season_id: str) -> AthleticSeason | None:
    """Sets status='pending_attestation', coach_attestation_status='requested'.
    Legal only from 'draft'. Returns None if transition is illegal (wrong
    status or season not found) -- caller raises the 409.
    Pre-condition: coach_email must be set on the season row (NOT NULL
    at this transition -- a season without a coach email cannot request
    attestation). Enforced here, not just at the route."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.athletic_seasons
        SET status = 'pending_attestation', coach_attestation_status = 'requested', updated_at = now()
        WHERE id = $1 AND status = 'draft' AND coach_email IS NOT NULL
        RETURNING {_COLUMNS}
        """,
        season_id,
    )
    return AthleticSeason.from_row(row) if row else None


async def withdraw_attestation_request(conn: asyncpg.Connection, season_id: str) -> AthleticSeason | None:
    """Sets status='draft', coach_attestation_status='not_requested'.
    Legal only from 'pending_attestation'. Callers must also call
    coach_attestation_tokens_repository.supersede_all_for_season() to
    invalidate the outstanding token -- not done here, since this
    repository has no reason to depend on the tokens repository."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.athletic_seasons
        SET status = 'draft', coach_attestation_status = 'not_requested', updated_at = now()
        WHERE id = $1 AND status = 'pending_attestation'
        RETURNING {_COLUMNS}
        """,
        season_id,
    )
    return AthleticSeason.from_row(row) if row else None


async def mark_attested(conn: asyncpg.Connection, season_id: str, *, at: datetime) -> AthleticSeason | None:
    """Sets status='attested', coach_attestation_status='attested',
    coach_attested_at=at. Legal only from 'pending_attestation'. Called
    by ATHLETICS-2's coach verification endpoint, not by talent-facing
    routes."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.athletic_seasons
        SET status = 'attested', coach_attestation_status = 'attested', coach_attested_at = $2, updated_at = now()
        WHERE id = $1 AND status = 'pending_attestation'
        RETURNING {_COLUMNS}
        """,
        season_id,
        at,
    )
    return AthleticSeason.from_row(row) if row else None


async def mark_attestation_declined(conn: asyncpg.Connection, season_id: str) -> AthleticSeason | None:
    """Sets coach_attestation_status='declined'. Does NOT change status
    from 'pending_attestation' -- the season remains pending until the
    talent manually withdraws or ATHLETICS-8's expiry job transitions it
    back to draft. Returns None if season not found or not in
    'pending_attestation'."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.athletic_seasons
        SET coach_attestation_status = 'declined', updated_at = now()
        WHERE id = $1 AND status = 'pending_attestation'
        RETURNING {_COLUMNS}
        """,
        season_id,
    )
    return AthleticSeason.from_row(row) if row else None


# ══════════════════════════════════════════════════════════════════
# Admin queue (ATHLETICS-8)
# ══════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class AdminAthleticSeasonRow:
    """GET /admin/athletics/seasons -- joins in the talent's
    display_name (admin-internal view only, never exposed elsewhere)."""

    id: str
    talent_id: str
    talent_display_name: str
    sport: str
    season_year: int
    team_name: str
    coach_attestation_status: str
    status: str
    admin_verified: bool
    admin_flag_reason: str | None
    created_at: datetime


async def list_for_admin(
    conn: asyncpg.Connection,
    *,
    status: str | None,
    sport: str | None,
    graduation_year: int | None,
    admin_verified: bool | None,
    limit: int,
    offset: int,
) -> list[AdminAthleticSeasonRow]:
    rows = await conn.fetch(
        """
        SELECT s.id, s.talent_id, tp.display_name AS talent_display_name, s.sport, s.season_year,
               s.team_name, s.coach_attestation_status, s.status, s.admin_verified, s.admin_flag_reason,
               s.created_at
        FROM public.athletic_seasons s
        JOIN public.talent_profiles tp ON tp.id = s.talent_id
        WHERE ($1::text IS NULL OR s.status = $1)
          AND ($2::text IS NULL OR s.sport = $2)
          AND ($3::int IS NULL OR tp.graduation_year = $3)
          AND ($4::bool IS NULL OR s.admin_verified = $4)
        ORDER BY s.created_at DESC
        LIMIT $5 OFFSET $6
        """,
        status,
        sport,
        graduation_year,
        admin_verified,
        limit,
        offset,
    )
    return [
        AdminAthleticSeasonRow(
            id=str(r["id"]),
            talent_id=str(r["talent_id"]),
            talent_display_name=r["talent_display_name"],
            sport=r["sport"],
            season_year=r["season_year"],
            team_name=r["team_name"],
            coach_attestation_status=r["coach_attestation_status"],
            status=r["status"],
            admin_verified=r["admin_verified"],
            admin_flag_reason=r["admin_flag_reason"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


async def list_pending_verification(conn: asyncpg.Connection) -> list[AdminAthleticSeasonRow]:
    """Shortcut for status='attested' AND admin_verified=FALSE -- coaches
    have confirmed these, admin has not yet elevated them."""
    rows = await conn.fetch(
        """
        SELECT s.id, s.talent_id, tp.display_name AS talent_display_name, s.sport, s.season_year,
               s.team_name, s.coach_attestation_status, s.status, s.admin_verified, s.admin_flag_reason,
               s.created_at
        FROM public.athletic_seasons s
        JOIN public.talent_profiles tp ON tp.id = s.talent_id
        WHERE s.status = 'attested' AND s.admin_verified = FALSE
        ORDER BY s.created_at DESC
        """
    )
    return [
        AdminAthleticSeasonRow(
            id=str(r["id"]),
            talent_id=str(r["talent_id"]),
            talent_display_name=r["talent_display_name"],
            sport=r["sport"],
            season_year=r["season_year"],
            team_name=r["team_name"],
            coach_attestation_status=r["coach_attestation_status"],
            status=r["status"],
            admin_verified=r["admin_verified"],
            admin_flag_reason=r["admin_flag_reason"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


async def admin_verify(conn: asyncpg.Connection, season_id: str, *, admin_id: str, at: datetime) -> AthleticSeason | None:
    """Sets admin_verified=TRUE, admin_verified_at, admin_verified_by,
    status='verified'. Legal only from 'attested' -- an admin cannot
    verify a season the coach hasn't confirmed yet."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.athletic_seasons
        SET admin_verified = TRUE, admin_verified_at = $2, admin_verified_by = $3,
            status = 'verified', updated_at = now()
        WHERE id = $1 AND status = 'attested'
        RETURNING {_COLUMNS}
        """,
        season_id,
        at,
        admin_id,
    )
    return AthleticSeason.from_row(row) if row else None


async def admin_flag(conn: asyncpg.Connection, season_id: str, *, reason: str) -> AthleticSeason | None:
    """Sets admin_flag_reason, reverts admin_verified to FALSE if it was
    TRUE. Does not change season.status -- flagging is an admin-internal
    note, not a state-machine transition. Talent is never notified."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.athletic_seasons
        SET admin_flag_reason = $2, admin_verified = FALSE, admin_verified_at = NULL,
            admin_verified_by = NULL, updated_at = now()
        WHERE id = $1
        RETURNING {_COLUMNS}
        """,
        season_id,
        reason,
    )
    return AthleticSeason.from_row(row) if row else None


# ══════════════════════════════════════════════════════════════════
# Coach attestation expiry sweep (ATHLETICS-8)
# ══════════════════════════════════════════════════════════════════


async def expire_stale_pending_attestations(conn: asyncpg.Connection) -> list[str]:
    """Finds pending_attestation seasons with no live (unused,
    unsuperseded, unexpired) coach_attestation_tokens row, and silently
    reverts them to draft/not_requested. Covers: token expired with no
    response, coach declined and talent never withdrew, or a superseded
    token's replacement also expired. Idempotent -- a season already
    reverted to 'draft' no longer matches the WHERE clause, so a second
    run is a no-op for it. Returns the ids of seasons actually
    transitioned, for the job to log."""
    rows = await conn.fetch(
        """
        UPDATE public.athletic_seasons
        SET status = 'draft', coach_attestation_status = 'not_requested', updated_at = now()
        WHERE status = 'pending_attestation'
          AND coach_attestation_status IN ('requested', 'declined')
          AND NOT EXISTS (
              SELECT 1 FROM public.coach_attestation_tokens t
              WHERE t.athletic_season_id = athletic_seasons.id
                AND t.used_at IS NULL
                AND t.superseded_at IS NULL
                AND t.expires_at > now()
          )
        RETURNING id
        """
    )
    return [str(r["id"]) for r in rows]


# ══════════════════════════════════════════════════════════════════
# Intelligence pipeline (ATHLETICS-8)
# ══════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class PendingAthleticIntelligenceSource:
    """One athletic_season row that has reached 'attested'/'verified'
    and hasn't been turned into an intelligence_events_anonymized row
    yet. Deliberately carries identifying fields (athletic_season_id,
    talent_id) -- this dataclass never itself gets written anywhere;
    the intelligence service strips it down before anything touches
    intelligence_events_anonymized."""

    athletic_season_id: str
    sport: str
    status: str
    created_at: datetime
    talent_city: str
    talent_state: str
    talent_school_type: str | None


async def list_pending_intelligence_events(conn: asyncpg.Connection) -> list[PendingAthleticIntelligenceSource]:
    rows = await conn.fetch(
        """
        SELECT s.id AS athletic_season_id, s.sport, s.status, s.created_at,
               tp.city AS talent_city, tp.state AS talent_state, tp.school_type AS talent_school_type
        FROM public.athletic_seasons s
        JOIN public.talent_profiles tp ON tp.id = s.talent_id
        WHERE s.status IN ('attested', 'verified') AND s.intelligence_event_written_at IS NULL
        """
    )
    return [
        PendingAthleticIntelligenceSource(
            athletic_season_id=str(r["athletic_season_id"]),
            sport=r["sport"],
            status=r["status"],
            created_at=r["created_at"],
            talent_city=r["talent_city"],
            talent_state=r["talent_state"],
            talent_school_type=r["talent_school_type"],
        )
        for r in rows
    ]


async def mark_intelligence_written(conn: asyncpg.Connection, season_ids: list[str], *, at: datetime) -> None:
    if not season_ids:
        return
    await conn.execute(
        "UPDATE public.athletic_seasons SET intelligence_event_written_at = $2 WHERE id = ANY($1::uuid[])",
        season_ids,
        at,
    )
