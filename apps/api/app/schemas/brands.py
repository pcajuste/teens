from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, field_validator

from app.core.categories import BASE_CATEGORIES

CampaignStatus = Literal["draft", "pending_payment", "payment_failed", "active", "paused", "completed", "cancelled"]
PaymentType = Literal["flat", "milestone"]
VerificationMethod = Literal["brand_confirmation", "talent_submission"]

_MIN_MAX_REPS = 1


class MilestoneRequest(BaseModel):
    """One entry of POST /brands/campaigns's `milestones` array when
    payment_type='milestone' (Build Prompt 8B deliverable 1). Field-
    level shape only -- the cross-milestone business rules (percentages
    sum to 100, sequential numbering, at least one sequence_required,
    non-sequential only trailing) are checked by
    app/services/campaign_service.validate_milestones against the whole
    list, not per-field here."""

    milestone_number: int
    title: str
    description: str | None = None
    verification_method: VerificationMethod
    payout_percentage: int
    sequence_required: bool = True
    threshold_count: int | None = None
    """Optional count-based milestone support (fills the 8B FRONTEND
    ADDITIONS > UX guidance gap: 'publish 3 pieces of content' should
    show '2 of 3' progress, not a flat pending/done state). Only
    meaningful for milestones the talent completes by repeated submission
    -- most milestones leave this unset, and an unset threshold_count
    behaves identically to how every milestone worked before this was
    added."""

    @field_validator("payout_percentage")
    @classmethod
    def _in_range(cls, value: int) -> int:
        if not (1 <= value <= 100):
            raise ValueError("payout_percentage must be between 1 and 100")
        return value

    @field_validator("milestone_number")
    @classmethod
    def _positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("milestone_number must be >= 1")
        return value

    @field_validator("threshold_count")
    @classmethod
    def _positive_threshold(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("threshold_count must be >= 1 when provided")
        return value


class MilestoneResponse(BaseModel):
    id: str
    milestone_number: int
    title: str
    description: str | None
    verification_method: VerificationMethod
    payout_percentage: int
    sequence_required: bool
    threshold_count: int | None = None


class BrandProfileUpdateRequest(BaseModel):
    """PUT /brands/me body. `ein` is plaintext in the request (the only
    place it's ever plaintext outside Stripe/legal review) -- the router
    encrypts it before it ever reaches brand_profiles_repository."""

    company_name: str
    website: str | None = None
    ein: str | None = None
    industry: str | None = None
    target_categories: list[str] = []

    @field_validator("target_categories")
    @classmethod
    def _valid_categories(cls, value: list[str]) -> list[str]:
        invalid = sorted(set(value) - BASE_CATEGORIES)
        if invalid:
            raise ValueError(f"invalid category values: {invalid}")
        return value


class BrandProfileResponse(BaseModel):
    id: str
    company_name: str
    website: str | None
    has_ein_on_file: bool
    industry: str | None
    target_categories: list[str]
    verified: bool
    account_status_note: str | None = None


def _word_count_at_most(value: str, max_words: int, field_name: str) -> str:
    words = value.split()
    if len(words) > max_words:
        raise ValueError(f"{field_name} must be at most {max_words} words (got {len(words)})")
    return value


class CompanyProfileUpdateRequest(BaseModel):
    """PUT /brands/me/company-profile -- Build Prompt 8I template 1,
    required before any other template can go live."""

    logo_url: str | None = None
    brand_color_primary: str | None = None
    about_text: str
    why_on_teenure_text: str

    @field_validator("about_text")
    @classmethod
    def _about_text_length(cls, value: str) -> str:
        return _word_count_at_most(value, 150, "about_text")

    @field_validator("why_on_teenure_text")
    @classmethod
    def _why_text_length(cls, value: str) -> str:
        return _word_count_at_most(value, 100, "why_on_teenure_text")


class CompanyProfileResponse(BaseModel):
    logo_url: str | None
    brand_color_primary: str | None
    about_text: str | None
    why_on_teenure_text: str | None
    complete: bool


class CampaignBriefRequest(BaseModel):
    """POST /brands/campaigns body -- exact field set from Section 8's
    documented request body, plus max_talents validated > 0 here (the
    'max_talents > 0' acceptance criterion is enforced again server-side
    at /activate, not just here, since a draft can be created then later
    validated at activation time per deliverable 4)."""

    title: str
    product_name: str
    campaign_goal: str
    key_messaging: str
    prohibited_content: str | None = None
    deliverables_description: str
    target_categories: list[str]
    target_cities: list[str] = []
    max_talents: int
    budget_cents: int
    start_date: date
    end_date: date
    payment_type: PaymentType = "flat"
    milestones: list[MilestoneRequest] = []

    @field_validator("target_categories")
    @classmethod
    def _valid_categories(cls, value: list[str]) -> list[str]:
        invalid = sorted(set(value) - BASE_CATEGORIES)
        if invalid:
            raise ValueError(f"invalid category values: {invalid}")
        return value

    @field_validator("max_talents")
    @classmethod
    def _positive_max_reps(cls, value: int) -> int:
        if value < _MIN_MAX_REPS:
            raise ValueError("max_talents must be >= 1")
        return value

    @field_validator("budget_cents")
    @classmethod
    def _positive_budget(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("budget_cents must be > 0")
        return value


class CampaignResponse(BaseModel):
    id: str
    title: str
    status: CampaignStatus
    product_name: str
    campaign_goal: str
    key_messaging: str
    prohibited_content: str | None
    deliverables_description: str
    target_categories: list[str]
    target_cities: list[str]
    max_talents: int
    talents_accepted_count: int
    budget_cents: int
    platform_fee_cents: int
    talent_pool_cents: int
    payout_per_talent_cents: int | None
    start_date: date
    end_date: date
    payment_type: PaymentType
    created_at: datetime
    updated_at: datetime


class MilestoneProgressResponse(BaseModel):
    """GET /brands/campaigns/:id/talents/:talent_id/milestones -- brand's
    per-talent milestone progress view (Build Prompt 8B frontend note:
    "milestone progress view -- which milestones are pending, submitted,
    or confirmed per talent")."""

    id: str
    campaign_milestone_id: str
    milestone_number: int
    title: str
    verification_method: VerificationMethod
    payout_percentage: int
    status: str
    talent_submission_text: str | None
    talent_submission_file_urls: list[str]
    payout_cents: int | None
    payout_status: str
    dispute_flag: bool
    threshold_count: int | None = None
    current_count: int = 0
    submitted_at: datetime | None
    confirmed_at: datetime | None
    paid_at: datetime | None


class MilestoneDisputeRequest(BaseModel):
    reason: str | None = None


class ActivateCampaignResponse(BaseModel):
    id: str
    status: CampaignStatus
    stripe_payment_intent_client_secret: str


class CancelCampaignResponse(BaseModel):
    id: str
    status: CampaignStatus
    refund_pending: bool
    refund_amount_cents: int = 0


class ReceiptResponse(BaseModel):
    receipt_url: str | None


class TalentBrowseCardResponse(BaseModel):
    """GET /brands/campaigns/:id/talents/browse -- see
    talent_profiles_repository.TalentBrowseCard's docstring for exactly why
    this field set and not the fuller TalentProfilePreviewResponse."""

    talent_id: str
    city: str
    state: str
    graduation_year: int
    school_type: str | None
    categories: list[str]
    profile_completeness_score: int
    brand_average_rating: float | None
    brand_campaigns_completed: int
    challenges_converted_count: int = 0
    challenge_conversion_rate: float | None = None
    badge_count: int = 0
    badge_titles: list[str] = []


class InviteRepsRequest(BaseModel):
    talent_ids: list[str]


class InviteResultResponse(BaseModel):
    talent_id: str
    campaign_talent_id: str | None
    status: Literal["invited", "already_invited", "campaign_full", "talent_not_found"]


class CampaignRepResponse(BaseModel):
    """GET /brands/campaigns/:id/talents -- brand's own view of a
    campaign_talents row. Distinct from talents.py's CampaignParticipationResponse
    only in that this is explicitly the brand-facing shape (same
    underlying fields today, but kept as its own schema so the two can
    diverge -- e.g. if a brand-only internal note field is ever added --
    without a talent-facing response  accidentally inheriting it)."""

    id: str
    talent_id: str
    status: str
    ftc_disclosure_accepted: bool
    parent_approval_status: str
    submission_text: str | None
    submission_file_urls: list[str]
    revision_note: str | None
    brand_rating: int | None
    brand_rating_note: str | None
    payout_cents: int | None
    payout_status: str | None
    invited_at: datetime
    accepted_at: datetime | None
    submitted_at: datetime | None
    confirmed_at: datetime | None
    paid_at: datetime | None
    milestones_completed_count: int = 0
    total_milestone_payout_cents: int = 0


class SubmissionResponse(BaseModel):
    """GET .../talents/:talent_id/submission -- deliberately narrower than
    CampaignRepResponse: only what a brand needs to review a submission,
    not the full participation row."""

    campaign_talent_id: str
    talent_id: str
    status: str
    submission_text: str | None
    submission_file_urls: list[str]
    submitted_at: datetime | None


class RevisionRequest(BaseModel):
    note: str


class RateRequest(BaseModel):
    brand_rating: int
    brand_rating_note: str | None = None

    @field_validator("brand_rating")
    @classmethod
    def _in_range(cls, value: int) -> int:
        if not (1 <= value <= 5):
            raise ValueError("brand_rating must be between 1 and 5")
        return value
