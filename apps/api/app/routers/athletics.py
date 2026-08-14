"""Athletic track backend (ATHLETICS-1): track enable/sport-profile stub
endpoints plus the full athletic season CRUD + state machine.

Every route requires an active talent account
(app.core.security.require_role("talent")); a talent's own
talent_profiles row is looked up from the authenticated user's id on
every request rather than trusting a talent_id from the URL/body --
same pattern as app/routers/talents.py's `_get_own_profile`.

Architectural rule 2 (Teenure_Prompts_Athletics.md Section 0): every
athletic endpoint except POST /talents/athletics/enable itself checks
'athletics' in talent.enabled_tracks before returning athletic data --
a talent who has not enabled the athletic track cannot post seasons or
manage sport profiles.
"""
from __future__ import annotations

from datetime import datetime, timezone

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import AuthenticatedUser, require_role
from app.core.sport_stats_schemas import SportStatsValidationError, validate_sport_stats
from app.core.sports import SUPPORTED_SPORTS
from app.core.profile_score import compute_athletic_completeness_score, compute_cross_track_score
from app.db.pool import get_connection
from app.repositories import (
    athletic_seasons_repository,
    coach_attestation_tokens_repository,
    sport_profiles_repository,
    talent_profiles_repository,
)
from app.schemas.athletics import (
    AthleticSeasonResponse,
    CreateAthleticSeasonRequest,
    EnableAthleticTrackResponse,
    RequestCoachAttestationResponse,
    SportProfileResponse,
    SportProfileUpdateRequest,
)

athletics_router = APIRouter(prefix="/talents/athletics", tags=["athletics"])


def _require_talent_profile_row(row) -> talent_profiles_repository.TalentProfile:
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "talent_profile_not_found", "message": "Complete onboarding via PUT /talents/me first."},
        )
    return row


async def _get_own_profile(
    conn: asyncpg.Connection, user: AuthenticatedUser
) -> talent_profiles_repository.TalentProfile:
    profile = await talent_profiles_repository.get_by_user_id(conn, user.id)
    return _require_talent_profile_row(profile)


def _require_athletics_enabled(profile: talent_profiles_repository.TalentProfile) -> None:
    if "athletics" not in profile.enabled_tracks:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "athletics_not_enabled",
                "message": "Enable the athletic track first via POST /talents/athletics/enable.",
            },
        )


def _to_sport_profile_response(sp: sport_profiles_repository.SportProfile) -> SportProfileResponse:
    return SportProfileResponse(
        id=sp.id,
        sport=sp.sport,
        positions=sp.positions,
        gpa=sp.gpa,
        hudl_url=sp.hudl_url,
        maxpreps_url=sp.maxpreps_url,
        created_at=sp.created_at,
        updated_at=sp.updated_at,
    )


def _to_season_response(s: athletic_seasons_repository.AthleticSeason) -> AthleticSeasonResponse:
    return AthleticSeasonResponse(
        id=s.id,
        sport=s.sport,
        season_year=s.season_year,
        season_type=s.season_type,
        team_name=s.team_name,
        level=s.level,
        sport_stats=s.sport_stats,
        coach_name=s.coach_name,
        coach_email=s.coach_email,
        coach_attestation_status=s.coach_attestation_status,
        coach_attested_at=s.coach_attested_at,
        admin_verified=s.admin_verified,
        admin_verified_at=s.admin_verified_at,
        status=s.status,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


async def _require_own_season(
    conn: asyncpg.Connection, season_id: str, talent_id: str
) -> athletic_seasons_repository.AthleticSeason:
    """404 -- never 403 -- whether the season doesn't exist or belongs to
    another talent (ATHLETICS-1 acceptance criterion: ownership checks
    never confirm existence to a non-owner)."""
    season = await athletic_seasons_repository.get_by_id_and_talent(conn, season_id, talent_id)
    if season is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "athletic_season_not_found", "message": "No season found for that id."},
        )
    return season


# ══════════════════════════════════════════════════════════════════
# Track enable + sport profiles (stub endpoints extended per ATHLETICS-1)
# ══════════════════════════════════════════════════════════════════


@athletics_router.post("/enable", response_model=EnableAthleticTrackResponse)
async def enable_athletics(
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> EnableAthleticTrackResponse:
    """Idempotent: adds 'athletics' to enabled_tracks if not already
    present. No track-gate check here -- this IS the gate."""
    profile = await _get_own_profile(conn, user)
    updated = await talent_profiles_repository.enable_athletic_track(conn, profile.id)
    return EnableAthleticTrackResponse(enabled_tracks=updated.enabled_tracks)


@athletics_router.get("/sports", response_model=list[SportProfileResponse])
async def list_sport_profiles(
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[SportProfileResponse]:
    profile = await _get_own_profile(conn, user)
    _require_athletics_enabled(profile)
    sport_profiles = await sport_profiles_repository.list_for_talent(conn, profile.id)
    return [_to_sport_profile_response(sp) for sp in sport_profiles]


@athletics_router.put("/sports/{sport}", response_model=SportProfileResponse)
async def upsert_sport_profile(
    sport: str,
    body: SportProfileUpdateRequest,
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> SportProfileResponse:
    profile = await _get_own_profile(conn, user)
    _require_athletics_enabled(profile)
    if sport not in SUPPORTED_SPORTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "unsupported_sport", "message": f"Unsupported sport. Valid: {sorted(SUPPORTED_SPORTS)}"},
        )
    if sport != body.sport:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "sport_mismatch", "message": "URL sport and body sport must match."},
        )

    sport_profile = await sport_profiles_repository.upsert_sport_profile(
        conn,
        profile.id,
        sport=body.sport,
        positions=body.positions,
        gpa=body.gpa,
        hudl_url=body.hudl_url,
        maxpreps_url=body.maxpreps_url,
    )

    # D1: a sport_profile upsert is one of the athletic completeness
    # weighted factors -- recompute inline rather than waiting on
    # ATHLETICS-4's trigger wiring (that ticket wires the
    # coach-attestation-driven recompute; this one is triggered by the
    # sport_profile write itself, which ATHLETICS-1 owns).
    all_sport_profiles = await sport_profiles_repository.list_for_talent(conn, profile.id)
    has_gpa = any(sp.gpa is not None for sp in all_sport_profiles)
    has_film_url = any(sp.hudl_url or sp.maxpreps_url for sp in all_sport_profiles)
    seasons = await athletic_seasons_repository.list_for_talent(conn, profile.id)
    has_attested_season = any(s.status in ("attested", "verified") for s in seasons)

    athletic_score = compute_athletic_completeness_score(
        has_sport_profile=True,
        has_gpa=has_gpa,
        has_attested_season=has_attested_season,
        has_film_url=has_film_url,
        nil_acknowledged=False,  # ATHLETICS-3 owns NIL acknowledgment wiring
    )
    await talent_profiles_repository.update_athletic_completeness_score(conn, profile.id, athletic_score)

    return _to_sport_profile_response(sport_profile)


# ══════════════════════════════════════════════════════════════════
# Athletic season CRUD + state machine (ATHLETICS-1)
# ══════════════════════════════════════════════════════════════════


@athletics_router.post("/seasons", response_model=AthleticSeasonResponse, status_code=status.HTTP_201_CREATED)
async def create_season(
    body: CreateAthleticSeasonRequest,
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> AthleticSeasonResponse:
    profile = await _get_own_profile(conn, user)
    _require_athletics_enabled(profile)

    try:
        season = await athletic_seasons_repository.create_season(
            conn,
            profile.id,
            sport=body.sport,
            season_year=body.season_year,
            season_type=body.season_type,
            team_name=body.team_name,
            level=body.level,
            sport_stats=body.sport_stats,
            coach_name=body.coach_name,
            coach_email=body.coach_email,
        )
    except SportStatsValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_sport_stats", "message": str(e)},
        ) from e
    return _to_season_response(season)


@athletics_router.get("/seasons", response_model=list[AthleticSeasonResponse])
async def list_seasons(
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[AthleticSeasonResponse]:
    profile = await _get_own_profile(conn, user)
    _require_athletics_enabled(profile)
    seasons = await athletic_seasons_repository.list_for_talent(conn, profile.id)
    return [_to_season_response(s) for s in seasons]


@athletics_router.get("/seasons/{season_id}", response_model=AthleticSeasonResponse)
async def get_season(
    season_id: str,
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> AthleticSeasonResponse:
    profile = await _get_own_profile(conn, user)
    _require_athletics_enabled(profile)
    season = await _require_own_season(conn, season_id, profile.id)
    return _to_season_response(season)


@athletics_router.put("/seasons/{season_id}", response_model=AthleticSeasonResponse)
async def update_season(
    season_id: str,
    body: CreateAthleticSeasonRequest,
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> AthleticSeasonResponse:
    profile = await _get_own_profile(conn, user)
    _require_athletics_enabled(profile)
    season = await _require_own_season(conn, season_id, profile.id)

    if season.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "season_not_editable", "message": "Season can only be edited in draft status."},
        )

    try:
        updated = await athletic_seasons_repository.update_season(
            conn,
            season_id,
            sport=body.sport,
            season_year=body.season_year,
            season_type=body.season_type,
            team_name=body.team_name,
            level=body.level,
            sport_stats=body.sport_stats,
            coach_name=body.coach_name,
            coach_email=body.coach_email,
        )
    except SportStatsValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_sport_stats", "message": str(e)},
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "season_not_editable", "message": str(e)},
        ) from e
    return _to_season_response(updated)


@athletics_router.delete("/seasons/{season_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_season(
    season_id: str,
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> None:
    profile = await _get_own_profile(conn, user)
    _require_athletics_enabled(profile)
    season = await _require_own_season(conn, season_id, profile.id)

    if season.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "season_not_editable", "message": "Season can only be deleted in draft status."},
        )

    deleted = await athletic_seasons_repository.delete_season(conn, season_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "season_not_editable", "message": "Season can only be deleted in draft status."},
        )


@athletics_router.post("/seasons/{season_id}/request-attestation", response_model=RequestCoachAttestationResponse)
async def request_attestation(
    season_id: str,
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> RequestCoachAttestationResponse:
    profile = await _get_own_profile(conn, user)
    _require_athletics_enabled(profile)
    season = await _require_own_season(conn, season_id, profile.id)

    if season.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "season_not_editable", "message": "Attestation can only be requested from draft status."},
        )
    if not season.coach_email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "coach_email_required",
                "message": "Set a coach email on the season before requesting attestation.",
            },
        )
    if not season.coach_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "coach_name_required",
                "message": "Set a coach name on the season before requesting attestation.",
            },
        )

    # D8: rate limit check -- at most one fresh link per 48h.
    hours_since = await coach_attestation_tokens_repository.hours_since_last_token(conn, season_id)
    if hours_since is not None and hours_since < coach_attestation_tokens_repository.MIN_HOURS_BEFORE_RESEND:
        hours_remaining = coach_attestation_tokens_repository.MIN_HOURS_BEFORE_RESEND - hours_since
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "rate_limited",
                "message": "Wait 48 hours between attestation requests.",
                "hours_until_resend_allowed": round(hours_remaining, 2),
            },
        )

    updated = await athletic_seasons_repository.transition_to_pending_attestation(conn, season_id)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "illegal_transition", "message": "Cannot request attestation from the current status."},
        )

    await coach_attestation_tokens_repository.issue_token(conn, season_id, season.coach_email)
    # ATHLETICS-2: send_coach_attestation_email()

    return RequestCoachAttestationResponse(
        success=True,
        rate_limited=False,
        hours_until_resend_allowed=None,
        message="Coach attestation requested.",
    )


@athletics_router.post("/seasons/{season_id}/withdraw-attestation", response_model=AthleticSeasonResponse)
async def withdraw_attestation(
    season_id: str,
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> AthleticSeasonResponse:
    profile = await _get_own_profile(conn, user)
    _require_athletics_enabled(profile)
    season = await _require_own_season(conn, season_id, profile.id)

    if season.status != "pending_attestation":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "illegal_transition",
                "message": "Attestation can only be withdrawn from pending_attestation status.",
            },
        )

    updated = await athletic_seasons_repository.withdraw_attestation_request(conn, season_id)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "illegal_transition", "message": "Cannot withdraw attestation from the current status."},
        )
    await coach_attestation_tokens_repository.supersede_all_for_season(conn, season_id)
    # ATHLETICS-4: recompute_athletic_cached_totals() called here
    # after attestation completes. Not called here -- attestation has not
    # happened yet at this transition (this route moves the season back
    # to 'draft', it never reaches 'attested').

    return _to_season_response(updated)
