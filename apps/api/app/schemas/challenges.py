from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator

from app.core.categories import BASE_CATEGORIES

SubmissionFormat = Literal["text", "file", "both"]
ChallengeStatus = Literal["draft", "active", "closed"]


class ChallengeCreateRequest(BaseModel):
    title: str
    brief: str
    category: str
    submission_format: SubmissionFormat = "both"
    submission_prompt: str
    target_cities: list[str] = []
    max_submissions: int | None = None
    opens_at: datetime | None = None
    closes_at: datetime | None = None

    @field_validator("category")
    @classmethod
    def _valid_category(cls, value: str) -> str:
        if value not in BASE_CATEGORIES:
            raise ValueError(f"invalid category value: {value}")
        return value

    @field_validator("max_submissions")
    @classmethod
    def _positive(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("max_submissions must be >= 1 when provided")
        return value


class ChallengeResponse(BaseModel):
    id: str
    brand_id: str
    title: str
    brief: str
    category: str
    target_cities: list[str]
    submission_format: SubmissionFormat
    submission_prompt: str
    status: ChallengeStatus
    max_submissions: int | None
    submissions_count: int
    conversion_count: int
    conversion_rate: float | None
    opens_at: datetime | None
    closes_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ChallengeSubmissionTalentCardResponse(BaseModel):
    """GET /brands/challenges/:id/submissions per-submission talent card --
    no PII beyond display_name/city (spec deliverable 2: warm discovery,
    the talent initiated contact by submitting -- see the router's own
    docstring). Never includes Instagram/TikTok handles, school name,
    or date of birth."""

    talent_id: str
    display_name: str
    city: str
    categories: list[str]
    profile_completeness_score: int
    campaigns_completed: int
    average_rating: float | None
    challenges_converted_count: int
    challenge_conversion_rate: float | None


class BrandSubmissionResponse(BaseModel):
    """Brand's own view of a submission. status is remapped so
    'declined' never appears here either (spec deliverable 2: "declined
    submissions show as 'reviewed' from the brand's list perspective --
    the decline was their action") -- never brand_note echoed back
    beyond what the brand itself just wrote (brand_note IS included
    here; this is the brand's own internal note, not talent-facing)."""

    id: str
    challenge_id: str
    talent: ChallengeSubmissionTalentCardResponse
    submission_text: str | None
    submission_file_urls: list[str]
    status: Literal["submitted", "reviewed", "converted"]
    brand_note: str | None
    submitted_at: datetime
    converted_to_campaign_id: str | None
    payout_cents: int | None
    payout_status: str | None


class ReviewSubmissionRequest(BaseModel):
    brand_note: str | None = None


class ConvertSubmissionRequest(BaseModel):
    campaign_id: str


class ConvertSubmissionResponse(BaseModel):
    id: str
    status: Literal["converted"]
    converted_to_campaign_id: str
    payout_cents: int
    payout_status: str | None
    stripe_transfer_id: str | None


class TalentChallengeAvailableResponse(BaseModel):
    """GET /talents/challenges/available."""

    id: str
    title: str
    brief: str
    category: str
    submission_format: SubmissionFormat
    submission_prompt: str
    target_cities: list[str]
    closes_at: datetime | None


class TalentChallengeSubmittedResponse(BaseModel):
    """GET /talents/challenges/submitted. status is remapped per the spec:
    'submitted'/'reviewed' both surface as 'submitted' -- a talent sees no
    difference between reviewed and unreviewed (intentional); 'declined'
    rows are excluded entirely by the router before this is ever built."""

    challenge_id: str
    challenge_title: str
    category: str
    submitted_at: datetime
    status: Literal["submitted", "converted"]
    campaign_id: str | None = None
    campaign_title: str | None = None
    payout_per_talent_cents: int | None = None
    bonus_cents: int | None = None


class SubmitChallengeRequest(BaseModel):
    submission_text: str | None = None
    submission_file_urls: list[str] = []
    disclosure_acknowledged: bool = False


class TalentChallengeSubmissionResponse(BaseModel):
    id: str
    challenge_id: str
    status: Literal["submitted"]
    submitted_at: datetime


class AdminChallengeAnalyticsCategoryEntry(BaseModel):
    category: str
    submissions_count: int


class AdminChallengeAnalyticsBrandEntry(BaseModel):
    brand_id: str
    company_name: str
    submissions_count: int
    conversion_count: int
    conversion_rate: float | None


class AdminChallengeAnalyticsResponse(BaseModel):
    total_challenges: int
    active_challenges: int
    closed_challenges: int
    total_submissions: int
    platform_conversion_rate: float | None
    conversion_bonus_total_paid_cents: int
    top_categories: list[AdminChallengeAnalyticsCategoryEntry]
    top_converting_brands: list[AdminChallengeAnalyticsBrandEntry]
    zero_conversion_brands: list[AdminChallengeAnalyticsBrandEntry]
