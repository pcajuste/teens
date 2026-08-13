from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, field_validator

from app.core.categories import ALL_VALUES_FILTER_CATEGORIES


class RequestLinkRequest(BaseModel):
    parent_email: EmailStr


class RequestLinkResponse(BaseModel):
    status: Literal["sent"]


class VerifyResponse(BaseModel):
    session_token: str
    expires_at: datetime


class ChallengeActivitySubmissionEntry(BaseModel):
    challenge_title: str
    submitted_at: datetime
    status: Literal["submitted", "converted"]
    bonus_earned_cents: int | None = None


class ChallengeActivityResponse(BaseModel):
    total_submitted: int
    total_converted: int
    total_bonus_earned_cents: int
    recent_submissions: list[ChallengeActivitySubmissionEntry]


class ModuleActivityBadgeEntry(BaseModel):
    badge_title: str
    earned_at: str


class ModuleActivityResponse(BaseModel):
    """Parent dashboard addition (Build Prompt 8H deliverable 8) --
    deliberately no quiz_score or wrong-answer fields anywhere in this
    schema. Parents see completion status and badges earned, not the
    struggle."""

    total_started: int
    total_passed: int
    total_failed: int
    badges_earned: list[ModuleActivityBadgeEntry]
    ftc_module_passed: bool


class DashboardResponse(BaseModel):
    display_name: str
    school_name: str
    graduation_year: int
    categories: list[str]
    profile_completeness_score: int
    total_earnings_cents: int
    total_campaigns_completed: int
    challenge_activity: ChallengeActivityResponse
    module_activity: ModuleActivityResponse


class PendingCampaignResponse(BaseModel):
    campaign_id: str
    brand_name: str
    title: str
    product_name: str
    campaign_goal: str
    key_messaging: str
    prohibited_content: str | None
    deliverables_description: str
    payout_per_talent_cents: int | None
    start_date: str
    end_date: str
    requires_in_person_activation: bool
    parent_approval_deadline: datetime | None


class CampaignDecisionResponse(BaseModel):
    campaign_id: str
    parent_approval_status: Literal["approved", "blocked"]


class SettingsResponse(BaseModel):
    values_filters: list[str]
    campaign_approval_required: bool
    digest_enabled: bool


class ValuesFiltersRequest(BaseModel):
    values_filters: list[str]

    @field_validator("values_filters")
    @classmethod
    def _valid_categories(cls, value: list[str]) -> list[str]:
        invalid = sorted(set(value) - ALL_VALUES_FILTER_CATEGORIES)
        if invalid:
            raise ValueError(f"invalid category values: {invalid}")
        return value


class ApprovalRequiredRequest(BaseModel):
    enabled: bool


class DigestSettingRequest(BaseModel):
    enabled: bool


class DigestPreviewResponse(BaseModel):
    campaigns_completed_this_month: int
    earnings_this_month_cents: int
    lifetime_earnings_cents: int
    profile_completeness_score: int
    profile_completeness_change: int | None
    active_categories: list[str]


class AccountControlResponse(BaseModel):
    account_status: str
