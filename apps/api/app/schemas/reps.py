from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, field_validator

from app.core.categories import BASE_CATEGORIES

SchoolType = Literal["public", "private", "charter", "homeschool"]

_MIN_GRAD_YEAR = 2024
_MAX_GRAD_YEAR = 2035


class RepProfileUpdateRequest(BaseModel):
    """PUT /reps/me body. Only rep-writable fields -- cached/computed
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
        # Reps self-select only from the base category set -- never the
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


class RepProfileResponse(BaseModel):
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


class RepProfilePreviewResponse(BaseModel):
    """Exactly what a brand or recruiter sees (GET /reps/me/profile-
    preview) -- shares field selection with RepProfileResponse rather
    than maintaining a second list that can drift, per Build Prompt 5
    deliverable 2. Deliberately excludes nothing else beyond what's
    already absent from rep_profiles: no contact info, no profile photo
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


class CampaignSummaryResponse(BaseModel):
    id: str
    title: str
    product_name: str
    campaign_goal: str
    deliverables_description: str
    target_categories: list[str]
    target_cities: list[str]
    payout_per_rep_cents: int | None
    start_date: date
    end_date: date


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


class AcceptCampaignRequest(BaseModel):
    ftc_disclosure_accepted: bool = False


class SubmitCampaignRequest(BaseModel):
    submission_text: str
    submission_file_urls: list[str] = []


class EarningsResponse(BaseModel):
    pending_cents: int
    confirmed_cents: int
    paid_cents: int
    lifetime_paid_cents: int


class StripeOnboardingResponse(BaseModel):
    """POST /reps/stripe/onboarding response. `url` is single-use and
    short-lived (Stripe's default Account Link expiry) -- callers must
    request a fresh one rather than caching this, which is also why
    this is a POST, not a GET."""

    url: str
