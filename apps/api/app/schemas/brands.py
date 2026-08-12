from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, field_validator

from app.core.categories import BASE_CATEGORIES

CampaignStatus = Literal["draft", "pending_payment", "payment_failed", "active", "paused", "completed", "cancelled"]
PaymentType = Literal["flat", "milestone"]
VerificationMethod = Literal["brand_confirmation", "rep_submission"]

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


class MilestoneResponse(BaseModel):
    id: str
    milestone_number: int
    title: str
    description: str | None
    verification_method: VerificationMethod
    payout_percentage: int
    sequence_required: bool


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


class CampaignBriefRequest(BaseModel):
    """POST /brands/campaigns body -- exact field set from Section 8's
    documented request body, plus max_reps validated > 0 here (the
    'max_reps > 0' acceptance criterion is enforced again server-side
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
    max_reps: int
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

    @field_validator("max_reps")
    @classmethod
    def _positive_max_reps(cls, value: int) -> int:
        if value < _MIN_MAX_REPS:
            raise ValueError("max_reps must be >= 1")
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
    max_reps: int
    reps_accepted_count: int
    budget_cents: int
    platform_fee_cents: int
    rep_pool_cents: int
    payout_per_rep_cents: int | None
    start_date: date
    end_date: date
    payment_type: PaymentType
    created_at: datetime
    updated_at: datetime


class MilestoneProgressResponse(BaseModel):
    """GET /brands/campaigns/:id/reps/:rep_id/milestones -- brand's
    per-rep milestone progress view (Build Prompt 8B frontend note:
    "milestone progress view -- which milestones are pending, submitted,
    or confirmed per rep")."""

    id: str
    campaign_milestone_id: str
    milestone_number: int
    title: str
    verification_method: VerificationMethod
    payout_percentage: int
    status: str
    rep_submission_text: str | None
    rep_submission_file_urls: list[str]
    payout_cents: int | None
    payout_status: str
    dispute_flag: bool
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


class RepBrowseCardResponse(BaseModel):
    """GET /brands/campaigns/:id/reps/browse -- see
    rep_profiles_repository.RepBrowseCard's docstring for exactly why
    this field set and not the fuller RepProfilePreviewResponse."""

    rep_id: str
    city: str
    state: str
    graduation_year: int
    school_type: str | None
    categories: list[str]
    profile_completeness_score: int
    average_rating: float | None
    total_campaigns_completed: int


class InviteRepsRequest(BaseModel):
    rep_ids: list[str]


class InviteResultResponse(BaseModel):
    rep_id: str
    campaign_rep_id: str | None
    status: Literal["invited", "already_invited", "campaign_full", "rep_not_found"]


class CampaignRepResponse(BaseModel):
    """GET /brands/campaigns/:id/reps -- brand's own view of a
    campaign_reps row. Distinct from reps.py's CampaignParticipationResponse
    only in that this is explicitly the brand-facing shape (same
    underlying fields today, but kept as its own schema so the two can
    diverge -- e.g. if a brand-only internal note field is ever added --
    without a rep-facing response accidentally inheriting it)."""

    id: str
    rep_id: str
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
    """GET .../reps/:rep_id/submission -- deliberately narrower than
    CampaignRepResponse: only what a brand needs to review a submission,
    not the full participation row."""

    campaign_rep_id: str
    rep_id: str
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
