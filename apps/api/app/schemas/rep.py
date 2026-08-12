from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.constants import CATEGORIES, GRADUATION_YEAR_MAX, GRADUATION_YEAR_MIN


class RepProfile(BaseModel):
    id: str
    user_id: str
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


class RepProfileUpdate(BaseModel):
    # extra="forbid" is the technical enforcement for deliverable 1's
    # "rejects any attempt to write the cached/computed fields
    # directly" -- those fields (total_campaigns_completed,
    # total_earnings_cents, average_rating, profile_completeness_score)
    # simply have no field on this model, so submitting them in the
    # request body is a 422, not a silently-ignored no-op.
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = None
    school_name: str | None = None
    school_type: str | None = None
    city: str | None = None
    state: str | None = None
    graduation_year: int | None = None
    bio: str | None = None
    categories: list[str] | None = None
    instagram_handle: str | None = None
    tiktok_handle: str | None = None
    recruiter_visible: bool | None = None

    @field_validator("categories")
    @classmethod
    def validate_categories(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        invalid = sorted(set(v) - set(CATEGORIES))
        if invalid:
            raise ValueError(f"Invalid categories {invalid}; allowed: {CATEGORIES}")
        return v

    @field_validator("graduation_year")
    @classmethod
    def validate_graduation_year(cls, v: int | None) -> int | None:
        if v is None:
            return v
        if not (GRADUATION_YEAR_MIN <= v <= GRADUATION_YEAR_MAX):
            raise ValueError(f"graduation_year must be between {GRADUATION_YEAR_MIN} and {GRADUATION_YEAR_MAX}")
        return v


class ProfilePreview(BaseModel):
    """Exactly what a brand/recruiter sees (deliverable 2) -- no PII beyond
    what Section 5's rep-card/profile-view spec exposes at browse stage.
    """

    display_name: str
    school_name: str
    city: str
    state: str
    graduation_year: int
    bio: str | None
    categories: list[str]
    instagram_handle: str | None
    tiktok_handle: str | None
    total_campaigns_completed: int
    average_rating: float | None


class CampaignSummary(BaseModel):
    campaign_reps_id: str
    campaign_id: str
    title: str
    status: str
    product_name: str
    deliverables_description: str
    payout_cents: int | None
    invite_expires_at: str | None = None
    start_date: str
    end_date: str
    parent_approval_status: str = "not_required"


class EarningsBreakdown(BaseModel):
    pending_cents: int
    confirmed_cents: int
    paid_cents: int
    lifetime_total_cents: int


class SubmitRequest(BaseModel):
    submission_text: str
    submission_file_urls: list[str] = []


class AcceptRequest(BaseModel):
    ftc_disclosure_accepted: bool
