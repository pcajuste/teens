from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, field_validator

from app.core.categories import BASE_CATEGORIES

SchoolType = Literal["public", "private", "charter", "homeschool"]

_MIN_GRAD_YEAR = 2024
_MAX_GRAD_YEAR = 2035


class TalentProfileUpdateRequest(BaseModel):
    """PUT /talents/me body. Only talent-writable fields -- cached/computed
    fields (total_campaigns_completed, total_earnings_cents,
    average_rating, profile_completeness_score, recruiter_visible) are
    absent on purpose; they cannot be set by this request at all, not
    even ignored silently -- there is no field here to send them in."""

    display_name: str
    school_name: str
    school_type: SchoolType | None = None
    city: str
    state: str
    graduation_year: int
    bio: str | None = None
    categories: list[str]
    instagram_handle: str | None = None
    tiktok_handle: str | None = None

    @field_validator("categories")
    @classmethod
    def _valid_categories(cls, value: list[str]) -> list[str]:
        # Talents self-select only from the base category set -- never the
        # parent-only-blockable categories (Section 7 / Build Prompt 5
        # design constraint).
        invalid = sorted(set(value) - BASE_CATEGORIES)
        if invalid:
            raise ValueError(f"invalid category values: {invalid}")
        return value

    @field_validator("graduation_year")
    @classmethod
    def _valid_grad_year(cls, value: int) -> int:
        if not (_MIN_GRAD_YEAR <= value <= _MAX_GRAD_YEAR):
            raise ValueError(f"graduation_year must be between {_MIN_GRAD_YEAR} and {_MAX_GRAD_YEAR}")
        return value


class TalentProfileResponse(BaseModel):
    id: str
    display_name: str
    school_name: str
    school_type: str | None
    city: str
    state: str
    graduation_year: int
    bio: str | None
    categories: list[str]
    instagram_handle: str | None
    tiktok_handle: str | None
    recruiter_visible: bool
    total_campaigns_completed: int
    total_earnings_cents: int
    average_rating: float | None
    profile_completeness_score: int
    stripe_onboarding_complete: bool
    challenges_submitted_count: int = 0
    challenges_converted_count: int = 0
    challenge_conversion_rate: float | None = None
    badges: list[dict] = []
    badges_earned_count: int = 0


class TalentProfilePreviewResponse(BaseModel):
    """Exactly what a brand or recruiter sees (GET /talents/me/profile-
    preview) -- shares field selection with TalentProfileResponse rather
    than maintaining a second list that can drift, per Build Prompt 5
    deliverable 2. Deliberately excludes nothing else beyond what's
    already absent from talent_profiles: no contact info, no profile photo
    (Section 1A content policy -- Teenure never collects one)."""

    display_name: str
    school_name: str
    school_type: str | None
    city: str
    state: str
    graduation_year: int
    bio: str | None
    categories: list[str]
    instagram_handle: str | None
    tiktok_handle: str | None
    total_campaigns_completed: int
    average_rating: float | None
    profile_completeness_score: int
    challenges_submitted_count: int = 0
    challenges_converted_count: int = 0
    challenge_conversion_rate: float | None = None
    badges: list[dict] = []
    badges_earned_count: int = 0


class AchievementRecordResponse(BaseModel):
    """GET /talents/me/achievement-record -- a downloadable "Teenure
    Achievement Record" document. Wraps TalentProfilePreviewResponse
    rather than repeating its fields, so the record can never drift
    from what a brand/recruiter already sees via GET
    /talents/me/profile-preview (same rule as that endpoint's own
    docstring). generated_at is the only field added on top, purely
    for display on the printable page -- it is not persisted."""

    generated_at: datetime
    record: TalentProfilePreviewResponse


class CampaignSummaryResponse(BaseModel):
    id: str
    title: str
    product_name: str
    campaign_goal: str
    deliverables_description: str
    target_categories: list[str]
    target_cities: list[str]
    payout_per_talent_cents: int | None
    start_date: date
    end_date: date


class MilestoneParticipationResponse(BaseModel):
    """Per-milestone entry within GET /talents/campaigns/active for a
    milestone campaign (Build Prompt 8B deliverable 3). `actionable`
    is server-computed sequence awareness -- true for a sequence_required
    milestone once every prior sequence_required milestone is
    confirmed-or-later, or for any non-sequential milestone once all
    sequence_required milestones are confirmed-or-later -- so a talent is
    never confused about which milestone to work on next."""

    id: str
    campaign_milestone_id: str
    milestone_number: int
    title: str
    description: str | None
    verification_method: str
    payout_percentage: int
    sequence_required: bool
    status: str
    actionable: bool
    payout_cents: int | None
    payout_status: str
    threshold_count: int | None = None
    current_count: int = 0
    submitted_at: datetime | None
    confirmed_at: datetime | None
    paid_at: datetime | None


class CampaignParticipationResponse(BaseModel):
    campaign_id: str
    status: str
    ftc_disclosure_accepted: bool
    parent_approval_status: str
    parent_approval_deadline: datetime | None
    submission_text: str | None
    submission_file_urls: list[str]
    revision_note: str | None
    payout_cents: int | None
    payout_status: str | None
    invited_at: datetime
    accepted_at: datetime | None
    submitted_at: datetime | None
    confirmed_at: datetime | None
    paid_at: datetime | None
    payment_type: str = "flat"
    milestones: list[MilestoneParticipationResponse] = []
    milestones_completed_count: int = 0
    total_milestone_payout_cents: int = 0


class AcceptCampaignRequest(BaseModel):
    ftc_disclosure_accepted: bool = False


class SubmitCampaignRequest(BaseModel):
    submission_text: str
    submission_file_urls: list[str] = []


class SubmitMilestoneRequest(BaseModel):
    submission_text: str
    submission_file_urls: list[str] = []


class MilestoneEarningsEntry(BaseModel):
    """One campaign's milestone-level earnings detail within GET
    /talents/earnings (Build Prompt 8B deliverable 10): "which milestones
    are pending, which are paid, what amount each released." """

    campaign_id: str
    campaign_title: str
    payout_per_talent_cents: int | None
    milestones_completed_count: int
    total_milestone_payout_cents: int
    milestones: list[MilestoneParticipationResponse]


class EarningsResponse(BaseModel):
    pending_cents: int
    confirmed_cents: int
    paid_cents: int
    lifetime_paid_cents: int
    milestone_campaigns: list[MilestoneEarningsEntry] = []


class StripeOnboardingResponse(BaseModel):
    """POST /talents/stripe/onboarding response . `url` is single-use and
    short-lived (Stripe's default Account Link expiry) -- callers must
    request a fresh one rather than caching this, which is also why
    this is a POST, not a GET."""

    url: str


# ── Living Achievement Link (Build Prompt 5 deliverable 12) ─────────


class AchievementLinkResponse(BaseModel):
    url: str
    token: str
    verified_profile_public: bool
    earnings_visible_on_public_profile: bool


class AchievementLinkVisibilityUpdateRequest(BaseModel):
    verified_profile_public: bool
    earnings_visible_on_public_profile: bool


class PublicVerifiedProfileResponse(BaseModel):
    """GET /verified/:token -- public, unauthenticated. `public` is False
    when the token is valid but the talent has verified_profile_public
    turned off; every field below it is then null rather than omitted,
    so the frontend can render a single response  shape either way."""

    public: bool
    display_name: str | None = None
    school_name: str | None = None
    graduation_year: int | None = None
    city: str | None = None
    categories: list[str] | None = None
    badges: list[dict] | None = None
    total_campaigns_completed: int | None = None
    average_rating: float | None = None
    total_earnings_cents: int | None = None
    last_updated: datetime | None = None


# ── Goal Setting and Progress Tracking (Build Prompt 5 deliverable 13) ─

GoalType = Literal["campaigns_completed", "earnings_total", "categories_active", "badges_earned", "profile_completeness"]

_GOAL_MIN_TARGETS: dict[str, int] = {
    "campaigns_completed": 1,
    "earnings_total": 1000,  # $10 minimum, spec deliverable 13
    "categories_active": 1,
    "badges_earned": 1,
    "profile_completeness": 1,
}
_GOAL_MAX_TARGETS: dict[str, int] = {
    "profile_completeness": 100,
}


class CreateGoalRequest(BaseModel):
    goal_type: GoalType
    target_value: int
    target_date: date | None = None

    @field_validator("target_value")
    @classmethod
    def _target_value_in_range(cls, value: int, info) -> int:
        goal_type = info.data.get("goal_type")
        if goal_type is None:
            return value
        minimum = _GOAL_MIN_TARGETS.get(goal_type, 1)
        if value < minimum:
            raise ValueError(f"target_value for {goal_type} must be >= {minimum}")
        maximum = _GOAL_MAX_TARGETS.get(goal_type)
        if maximum is not None and value > maximum:
            raise ValueError(f"target_value for {goal_type} must be <= {maximum}")
        return value


class GoalResponse(BaseModel):
    id: str
    goal_type: GoalType
    target_value: int
    target_date: date | None
    current_value: int
    progress_percentage: int
    status: Literal["active", "completed", "abandoned"]
    completed_at: datetime | None
    created_at: datetime
    projected_completion_date: date | None = None


class GoalSuggestion(BaseModel):
    goal_type: GoalType
    label: str
    suggested_target_value: int
