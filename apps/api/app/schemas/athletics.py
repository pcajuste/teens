"""Athletic track API schemas (ATHLETICS-1, per D1-D10 decisions in
teenure_athletics_playbook.md).

No `AthleticAchievementCreateRequest/Response` (D9 decision --
achievements are JSONB within sport_stats at MVP, not a separate
table).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, field_validator

from app.core.sport_stats_schemas import SportStatsValidationError, validate_sport_stats
from app.core.sports import SEASON_LEVELS, SEASON_TYPES, SUPPORTED_SPORTS


class EnableAthleticTrackResponse(BaseModel):
    """POST /talents/athletics/enable response."""
    enabled_tracks: list[str]


class SportProfileUpdateRequest(BaseModel):
    sport: str
    positions: list[str] = []
    gpa: float | None = None
    hudl_url: str | None = None
    maxpreps_url: str | None = None

    @field_validator("sport")
    @classmethod
    def _valid_sport(cls, value: str) -> str:
        if value not in SUPPORTED_SPORTS:
            raise ValueError(f"Unsupported sport. Valid: {sorted(SUPPORTED_SPORTS)}")
        return value

    @field_validator("gpa")
    @classmethod
    def _valid_gpa(cls, value: float | None) -> float | None:
        if value is not None and not (0.0 <= value <= 4.0):
            raise ValueError("GPA must be between 0.0 and 4.0")
        return value


class SportProfileResponse(BaseModel):
    id: str
    sport: str
    positions: list[str]
    gpa: float | None
    hudl_url: str | None
    maxpreps_url: str | None
    created_at: datetime
    updated_at: datetime


class CreateAthleticSeasonRequest(BaseModel):
    sport: str
    season_year: int
    season_type: str
    team_name: str
    level: str
    sport_stats: dict[str, Any] = {}
    coach_name: str | None = None
    coach_email: str | None = None

    @field_validator("sport")
    @classmethod
    def _valid_sport(cls, value: str) -> str:
        if value not in SUPPORTED_SPORTS:
            raise ValueError("Unsupported sport")
        return value

    @field_validator("season_type")
    @classmethod
    def _valid_season_type(cls, value: str) -> str:
        if value not in SEASON_TYPES:
            raise ValueError("Invalid season_type")
        return value

    @field_validator("level")
    @classmethod
    def _valid_level(cls, value: str) -> str:
        if value not in SEASON_LEVELS:
            raise ValueError("Invalid level")
        return value

    @field_validator("sport_stats")
    @classmethod
    def _valid_stats(cls, value: dict, info) -> dict:
        sport = info.data.get("sport")
        if sport:
            try:
                validate_sport_stats(sport, value)
            except SportStatsValidationError as e:
                raise ValueError(str(e))
        return value

    @field_validator("season_year")
    @classmethod
    def _valid_year(cls, value: int) -> int:
        if not (2015 <= value <= 2035):
            raise ValueError("season_year must be between 2015 and 2035")
        return value


class AthleticSeasonResponse(BaseModel):
    id: str
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
    status: str
    created_at: datetime
    updated_at: datetime


class RequestCoachAttestationResponse(BaseModel):
    """POST /talents/athletics/seasons/:id/request-attestation response.
    D8: rate_limited=True when the 48h resend minimum has not elapsed."""
    success: bool
    rate_limited: bool = False
    hours_until_resend_allowed: float | None = None
    message: str


class CoachAttestationTokenResponse(BaseModel):
    """GET /athletics/attest/:token response. Always 200 -- valid=False
    with a reason instead of 404, to avoid token-enumeration timing
    attacks. Never includes talent PII beyond display_name (no
    school_name, city, state, or graduation_year)."""
    valid: bool
    reason: str | None = None
    talent_display_name: str | None = None
    sport: str | None = None
    season_year: int | None = None
    team_name: str | None = None
    level: str | None = None
    sport_stats: dict[str, Any] | None = None
    coach_name: str | None = None


class CoachAttestationDecisionResponse(BaseModel):
    """POST /athletics/attest/:token/confirm and /decline response.
    Always 200 -- success=False with a reason instead of 404/409."""
    success: bool
    reason: str | None = None
    sport: str | None = None
    season_year: int | None = None
    team_name: str | None = None


class NilEligibilityResponse(BaseModel):
    state: str
    nil_eligible_in_state: bool
    school_association_rules_acknowledged: bool
    acknowledged_at: datetime | None
    notes: str | None = None


class PublicNilStateRuleResponse(BaseModel):
    """GET /public/nil-rules item. last_updated_at is deliberately
    omitted -- internal admin field, not for the public marketing site."""
    state: str
    nil_eligible: bool
    notes: str | None
    effective_date: date


class AdminUpdateNilStateRuleRequest(BaseModel):
    nil_eligible: bool
    notes: str | None = None
    effective_date: date


class AdminUpdateNilStateRuleResponse(BaseModel):
    state: str
    updated: bool
    talents_affected: int


class AthleticProfileSummaryResponse(BaseModel):
    """GET /talents/me/athletic-summary -- the complete athletic profile
    for the talent's own dashboard view. Parallel to TalentProfileResponse
    for the brand track."""
    enabled_tracks: list[str]
    athletic_seasons_completed: int
    athletic_completeness_score: int
    athletic_recruiter_interest_count: int  # D2: engagement signal
    sport_profiles: list[SportProfileResponse]
    recent_seasons: list[AthleticSeasonResponse]  # last 3 seasons
    nil_eligibility: NilEligibilityResponse | None
