"""Request/response  models for Build Prompt 8I's Scholarship and
Insight & Feedback templates. Company Profile lives in schemas/brands.py
(it's a brand_profiles field group, not its own entity) and the Skills
Challenge template's new fields live in schemas/challenges.py alongside
the Prompt 8G models it extends."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


def _word_count_at_most(value: str, max_words: int, field_name: str) -> str:
    words = value.split()
    if len(words) > max_words:
        raise ValueError(f"{field_name} must be at most {max_words} words (got {len(words)})")
    return value


# ──────────────────────────────────────────────────────────────────
# Scholarship template
# ──────────────────────────────────────────────────────────────────


class EligibilityCriterion(BaseModel):
    label: str
    required: bool = True


class ScholarshipCreateRequest(BaseModel):
    title: str
    award_amount_cents: int
    number_of_awards: int = 1
    eligibility_criteria: list[EligibilityCriterion] = []
    application_requirements: str
    why_text: str
    image_url: str | None = None
    video_url: str | None = None
    deadline: datetime

    @field_validator("why_text")
    @classmethod
    def _why_text_length(cls, value: str) -> str:
        return _word_count_at_most(value, 150, "why_text")

    @field_validator("award_amount_cents")
    @classmethod
    def _positive_award(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("award_amount_cents must be > 0")
        return value

    @field_validator("number_of_awards")
    @classmethod
    def _positive_awards_count(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("number_of_awards must be > 0")
        return value


class ScholarshipResponse(BaseModel):
    id: str
    title: str
    award_amount_cents: int
    number_of_awards: int
    eligibility_criteria: list[dict]
    application_requirements: str
    why_text: str
    image_url: str | None
    video_url: str | None
    deadline: datetime
    moderation_status: str
    rejection_reason: str | None
    status: str
    created_at: datetime


class ScholarshipApplyRequest(BaseModel):
    response_text: str

    @field_validator("response_text")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("response_text must not be empty")
        return value


class ScholarshipApplicationResponse(BaseModel):
    id: str
    scholarship_id: str
    response_text: str
    status: str
    submitted_at: datetime
    reviewed_at: datetime | None


class ScholarshipApplicationBrandView(BaseModel):
    """Brand-facing application list -- deliberately no talent identity
    field beyond the applicant's response text; the brand awards/
    declines through campaign_talents-style identity disclosure that
    happens only once a talent is already an on-platform applicant with
    a name attached to their Teenure account (unlike Insight & Feedback,
    Scholarship applications are not pseudonymous -- 8I's pseudonym
    requirement is scoped to the Insight & Feedback template only)."""

    id: str
    talent_id: str
    response_text: str
    status: str
    submitted_at: datetime


# ──────────────────────────────────────────────────────────────────
# Insight & Feedback template
# ──────────────────────────────────────────────────────────────────


class InsightEligibilityUpdateRequest(BaseModel):
    legal_entity_verified: bool = False
    named_contact_verified: bool = False
    business_presence_verified: bool = False
    funding_confirmed: bool = False
    content_agreement_signed: bool = False
    is_early_stage_startup: bool = False
    incorporated_3mo_or_backed: bool = False
    has_real_product: bool = False


class InsightEligibilityResponse(BaseModel):
    legal_entity_verified: bool
    named_contact_verified: bool
    business_presence_verified: bool
    funding_confirmed: bool
    content_agreement_signed: bool
    is_early_stage_startup: bool
    incorporated_3mo_or_backed: bool
    has_real_product: bool
    eligible: bool
    manually_reviewed_at: datetime | None


class InsightCampaignCreateRequest(BaseModel):
    title: str
    material_url: str
    business_question: str
    panel_size: int
    panel_criteria: dict = {}
    compensation_cents: int
    confidentiality_terms: str
    is_startup_validation: bool = False
    opens_at: datetime | None = None
    closes_at: datetime | None = None

    @field_validator("panel_size")
    @classmethod
    def _positive_panel(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("panel_size must be > 0")
        return value

    @field_validator("compensation_cents")
    @classmethod
    def _non_negative_comp(cls, value: int) -> int:
        if value < 0:
            raise ValueError("compensation_cents must be >= 0")
        return value


class InsightCampaignResponse(BaseModel):
    id: str
    title: str
    material_url: str
    business_question: str
    feedback_format: str
    panel_size: int
    panel_criteria: dict
    compensation_cents: int
    confidentiality_terms: str
    is_startup_validation: bool
    moderation_status: str
    rejection_reason: str | None
    status: str
    created_at: datetime


class InsightInvitationResponse(BaseModel):
    """Talent-facing -- their own panel invitation. Shows the real
    campaign/brand context, since the teen always knows it's them; only
    the brand's *view of the teen* is pseudonymous."""

    panel_member_id: str
    campaign_id: str
    campaign_title: str
    business_question: str
    confidentiality_terms: str
    compensation_cents: int
    invited_at: datetime
    responded_at: datetime | None


class RatingAnswer(BaseModel):
    question: str
    score: int

    @field_validator("score")
    @classmethod
    def _score_range(cls, value: int) -> int:
        if not 1 <= value <= 5:
            raise ValueError("score must be between 1 and 5")
        return value


class InsightResponseSubmitRequest(BaseModel):
    ratings: list[RatingAnswer]

    @field_validator("ratings")
    @classmethod
    def _non_empty_ratings(cls, value: list[RatingAnswer]) -> list[RatingAnswer]:
        if not value:
            raise ValueError("ratings must not be empty")
        return value


class InsightResponseAck(BaseModel):
    panel_member_id: str
    submitted_at: datetime


class InsightBrandResultResponse(BaseModel):
    """Brand-facing aggregated results -- pseudonym handle only, no
    talent_id/display_name field exists on this model at all."""

    pseudonym_handle: str
    ratings: list[dict]
    submitted_at: datetime
