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

import logging

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.core.security import AuthenticatedUser, require_role
from app.core.sport_stats_schemas import SportStatsValidationError, validate_sport_stats
from app.core.sports import SUPPORTED_SPORTS
from app.db.pool import get_connection
from app.repositories import (
    athletic_seasons_repository,
    coach_attestation_tokens_repository,
    nil_eligibility_repository,
    nil_state_rules_repository,
    sport_profiles_repository,
    talent_goals_repository,
    talent_profiles_repository,
    users_repository,
)
from app.schemas.athletics import (
    AthleticSeasonResponse,
    CoachAttestationDecisionResponse,
    CoachAttestationTokenResponse,
    CreateAthleticSeasonRequest,
    EnableAthleticTrackResponse,
    NilEligibilityResponse,
    RequestCoachAttestationResponse,
    SportProfileResponse,
    SportProfileUpdateRequest,
)
from app.services.email_service import (
    send_coach_attestation_email,
    send_goal_completed_email,
    send_talent_coach_attested_notification,
    send_talent_coach_declined_notification,
)
from app.services.resend_client import ResendClient
from app.services.resend_client import resend_client_dependency as _resend_client_dependency

logger = logging.getLogger(__name__)

athletics_router = APIRouter(prefix="/talents/athletics", tags=["athletics"])

# Public (unauthenticated) coach-attestation verification endpoints --
# ATHLETICS-2. Never behind require_role: a coach is never a platform
# user and clicks this link from an email, not a logged-in session.
athletics_public_router = APIRouter(prefix="/athletics", tags=["athletics-public"])


def _log_posthog_event(event: str, properties: dict) -> None:
    """No PostHog client exists anywhere in this codebase yet (verified
    via repo-wide search) -- this is a placeholder that logs instead of
    silently dropping the event, so the call site is ready to swap in a
    real client without touching callers once one is wired in."""
    logger.info("posthog_event", extra={"event": event, "properties": properties})


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
    # ATHLETICS-4: enabling the track can change profile_completeness_score
    # (the cross-track GREATEST) even though athletic_completeness_score
    # itself hasn't moved -- e.g. a talent with a pre-existing 0 athletic
    # score but who already has some athletic data seeded is an edge
    # case; recompute unconditionally rather than special-casing.
    await talent_profiles_repository.recompute_all_completeness_scores(conn, profile.id)
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

    # ATHLETICS-4: a sport_profile upsert is one of the athletic
    # completeness weighted factors -- recompute both track scores (and
    # the cross-track GREATEST) via the shared helper so this call site
    # never drifts from the NIL/attestation/enable trigger points.
    await talent_profiles_repository.recompute_all_completeness_scores(conn, profile.id)

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
    settings: Settings = Depends(get_settings),
    resend_client: ResendClient = Depends(_resend_client_dependency),
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

    token = await coach_attestation_tokens_repository.issue_token(conn, season_id, season.coach_email)

    # Email send failure never rolls back the state transition -- the
    # token exists and the coach can be re-sent via the rate-limited
    # re-request endpoint once resend is allowed again.
    try:
        attestation_url = f"{settings.next_public_app_url}/athletics/attest/{token.token}"
        await send_coach_attestation_email(
            coach_name=season.coach_name,
            coach_email=season.coach_email,
            talent_display_name=profile.display_name,
            sport=season.sport,
            season_year=season.season_year,
            team_name=season.team_name,
            level=season.level,
            sport_stats=season.sport_stats,
            attestation_url=attestation_url,
            client=resend_client,
        )
    except Exception:
        logger.exception("Failed to send coach attestation email for season %s", season_id)

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


# ══════════════════════════════════════════════════════════════════
# NIL compliance (ATHLETICS-3)
# ══════════════════════════════════════════════════════════════════


@athletics_router.get("/nil", response_model=NilEligibilityResponse)
async def get_nil_eligibility(
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> NilEligibilityResponse:
    profile = await _get_own_profile(conn, user)
    _require_athletics_enabled(profile)

    record = await nil_eligibility_repository.get_by_talent_id(conn, profile.id)
    if record is not None:
        return NilEligibilityResponse(
            state=record.state,
            nil_eligible_in_state=record.nil_eligible_in_state,
            school_association_rules_acknowledged=record.school_association_rules_acknowledged,
            acknowledged_at=record.acknowledged_at,
        )

    rule = await nil_state_rules_repository.get_by_talent_state(conn, profile.id)
    if rule is None:
        # Defensive: talent's state isn't in the seeded table yet.
        return NilEligibilityResponse(
            state=profile.state,
            nil_eligible_in_state=False,
            school_association_rules_acknowledged=False,
            acknowledged_at=None,
            notes="Your state's NIL policy is not yet confirmed. Check back soon.",
        )

    record = await nil_eligibility_repository.create_or_update(
        conn, profile.id, state=rule.state, nil_eligible_in_state=rule.nil_eligible
    )
    return NilEligibilityResponse(
        state=record.state,
        nil_eligible_in_state=record.nil_eligible_in_state,
        school_association_rules_acknowledged=record.school_association_rules_acknowledged,
        acknowledged_at=record.acknowledged_at,
    )


@athletics_router.post("/nil/acknowledge", response_model=NilEligibilityResponse)
async def acknowledge_nil_rules(
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> NilEligibilityResponse:
    profile = await _get_own_profile(conn, user)
    _require_athletics_enabled(profile)

    record = await nil_eligibility_repository.get_by_talent_id(conn, profile.id)
    if record is None:
        rule = await nil_state_rules_repository.get_by_talent_state(conn, profile.id)
        nil_eligible_in_state = rule.nil_eligible if rule is not None else False
        record = await nil_eligibility_repository.create_or_update(
            conn, profile.id, state=profile.state, nil_eligible_in_state=nil_eligible_in_state
        )

    if not record.nil_eligible_in_state:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "nil_not_eligible_in_state",
                "message": (
                    f"High school NIL activity is not currently permitted in {record.state}. "
                    "Platform rules cannot override state law. Your athletic profile can still "
                    "be built and discovered by college programs for recruiting purposes -- NIL "
                    "brand deals require state eligibility."
                ),
            },
        )

    if record.school_association_rules_acknowledged:
        # Idempotent -- already acknowledged, no-op.
        return NilEligibilityResponse(
            state=record.state,
            nil_eligible_in_state=record.nil_eligible_in_state,
            school_association_rules_acknowledged=record.school_association_rules_acknowledged,
            acknowledged_at=record.acknowledged_at,
        )

    updated = await nil_eligibility_repository.mark_acknowledged(conn, profile.id, at=datetime.now(timezone.utc))
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "nil_not_eligible_in_state",
                "message": f"High school NIL activity is not currently permitted in {record.state}.",
            },
        )
    await talent_profiles_repository.recompute_all_completeness_scores(conn, profile.id)
    return NilEligibilityResponse(
        state=updated.state,
        nil_eligible_in_state=updated.nil_eligible_in_state,
        school_association_rules_acknowledged=updated.school_association_rules_acknowledged,
        acknowledged_at=updated.acknowledged_at,
    )


# ══════════════════════════════════════════════════════════════════
# Public coach attestation verification (ATHLETICS-2)
# ══════════════════════════════════════════════════════════════════


@athletics_public_router.get("/attest/{token}", response_model=CoachAttestationTokenResponse)
async def get_attestation_token(
    token: str,
    conn: asyncpg.Connection = Depends(get_connection),
) -> CoachAttestationTokenResponse:
    """Always 200, never 404 -- prevents token-enumeration timing
    attacks (same rule as public.py's GET /verified/:token). Response
    never includes the talent's school_name, city, state, or
    graduation_year -- only what a coach needs to attest a record."""
    record = await coach_attestation_tokens_repository.get_by_token(conn, token)
    if record is None:
        return CoachAttestationTokenResponse(valid=False, reason="not_found")
    if record.used_at is not None:
        return CoachAttestationTokenResponse(valid=False, reason="already_used")
    if record.superseded_at is not None:
        return CoachAttestationTokenResponse(valid=False, reason="superseded")
    if record.expires_at <= datetime.now(timezone.utc):
        return CoachAttestationTokenResponse(valid=False, reason="expired")

    season = await athletic_seasons_repository.get_by_id(conn, record.athletic_season_id)
    if season is None:
        return CoachAttestationTokenResponse(valid=False, reason="not_found")
    profile = await talent_profiles_repository.get_by_id(conn, season.talent_id)
    if profile is None:
        return CoachAttestationTokenResponse(valid=False, reason="not_found")

    return CoachAttestationTokenResponse(
        valid=True,
        talent_display_name=profile.display_name,
        sport=season.sport,
        season_year=season.season_year,
        team_name=season.team_name,
        level=season.level,
        sport_stats=season.sport_stats,
        coach_name=season.coach_name,
    )


async def _validate_pending_token(
    conn: asyncpg.Connection, token: str
) -> tuple[coach_attestation_tokens_repository.CoachAttestationToken, athletic_seasons_repository.AthleticSeason] | None:
    """Shared validation for confirm/decline -- returns None (caller
    responds with success=False) on any invalid/expired/used/superseded
    token, or if the season has already left pending_attestation."""
    record = await coach_attestation_tokens_repository.get_by_token(conn, token)
    if record is None or record.used_at is not None or record.superseded_at is not None:
        return None
    if record.expires_at <= datetime.now(timezone.utc):
        return None
    season = await athletic_seasons_repository.get_by_id(conn, record.athletic_season_id)
    if season is None or season.status != "pending_attestation":
        return None
    return record, season


@athletics_public_router.post("/attest/{token}/confirm", response_model=CoachAttestationDecisionResponse)
async def confirm_attestation(
    token: str,
    conn: asyncpg.Connection = Depends(get_connection),
    resend_client: ResendClient = Depends(_resend_client_dependency),
) -> CoachAttestationDecisionResponse:
    validated = await _validate_pending_token(conn, token)
    if validated is None:
        return CoachAttestationDecisionResponse(success=False, reason="already_resolved")
    record, season = validated

    now = datetime.now(timezone.utc)
    async with conn.transaction():
        await coach_attestation_tokens_repository.consume_token(conn, record.id, at=now)
        updated = await athletic_seasons_repository.mark_attested(conn, season.id, at=now)

    # updated is None on a race (already attested by a concurrent
    # request) -- still return success, no double-processing.
    await talent_profiles_repository.recompute_athletic_cached_totals(conn, season.talent_id)
    await talent_profiles_repository.recompute_all_completeness_scores(conn, season.talent_id)
    newly_completed_goals = await talent_goals_repository.recompute_progress(conn, season.talent_id)

    profile = await talent_profiles_repository.get_by_id(conn, season.talent_id)
    if profile is not None:
        talent_user = await users_repository.get_user_by_id(conn, profile.user_id)
        if talent_user is not None:
            try:
                await send_talent_coach_attested_notification(
                    talent_email=talent_user.email,
                    talent_display_name=profile.display_name,
                    sport=season.sport,
                    season_year=season.season_year,
                    coach_name=season.coach_name or "Your coach",
                    client=resend_client,
                )
            except Exception:
                logger.exception("Failed to send coach-attested notification for season %s", season.id)
            for goal in newly_completed_goals:
                try:
                    await send_goal_completed_email(
                        talent_user.email,
                        goal_description=talent_goals_repository.describe_goal(goal.goal_type, goal.target_value),
                        client=resend_client,
                    )
                except Exception:
                    logger.exception("Failed to send goal-completed email for talent %s", season.talent_id)

    _log_posthog_event(
        "coach_attestation_confirmed",
        {"sport": season.sport, "season_year": season.season_year, "track": "athletics"},
    )

    return CoachAttestationDecisionResponse(
        success=True, sport=season.sport, season_year=season.season_year, team_name=season.team_name
    )


@athletics_public_router.post("/attest/{token}/decline", response_model=CoachAttestationDecisionResponse)
async def decline_attestation(
    token: str,
    conn: asyncpg.Connection = Depends(get_connection),
    resend_client: ResendClient = Depends(_resend_client_dependency),
) -> CoachAttestationDecisionResponse:
    validated = await _validate_pending_token(conn, token)
    if validated is None:
        return CoachAttestationDecisionResponse(success=False, reason="already_resolved")
    record, season = validated

    now = datetime.now(timezone.utc)
    async with conn.transaction():
        await coach_attestation_tokens_repository.consume_token(conn, record.id, at=now)
        await athletic_seasons_repository.mark_attestation_declined(conn, season.id)

    profile = await talent_profiles_repository.get_by_id(conn, season.talent_id)
    if profile is not None:
        talent_user = await users_repository.get_user_by_id(conn, profile.user_id)
        if talent_user is not None:
            try:
                await send_talent_coach_declined_notification(
                    talent_email=talent_user.email,
                    talent_display_name=profile.display_name,
                    sport=season.sport,
                    season_year=season.season_year,
                    client=resend_client,
                )
            except Exception:
                logger.exception("Failed to send coach-declined notification for season %s", season.id)

    return CoachAttestationDecisionResponse(success=True)
