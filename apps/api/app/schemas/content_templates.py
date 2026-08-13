"""Request/response  models for Build Prompt 8I's Scholarship and
Insight & Feedback templates. Company Profile lives in schemas/brands.py
(it's a brand_profiles field group, not its own entity) and the Skills
Challenge template's new fields live in schemas/challenges.py alongside
the Prompt 8G models it extends."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator, model_validator


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


class QAQuestion(BaseModel):
    id: str
    prompt: str

    @field_validator("prompt")
    @classmethod
    def _prompt_length(cls, value: str) -> str:
        if len(value) > 300:
            raise ValueError("prompt must be at most 300 characters")
        return value


class InsightCampaignCreateRequest(BaseModel):
    title: str
    material_url: str
    business_question: str
    feedback_format: str = "rating_scale"
    qa_questions: list[QAQuestion] = []
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

    @field_validator("feedback_format")
    @classmethod
    def _known_format(cls, value: str) -> str:
        if value not in ("rating_scale", "structured_qa"):
            raise ValueError("feedback_format must be one of: rating_scale, structured_qa")
        return value

    @model_validator(mode="after")
    def _qa_questions_match_format(self) -> "InsightCampaignCreateRequest":
        if self.feedback_format == "structured_qa":
            if not 1 <= len(self.qa_questions) <= 8:
                raise ValueError("structured_qa campaigns need between 1 and 8 qa_questions")
            ids = [q.id for q in self.qa_questions]
            if len(ids) != len(set(ids)):
                raise ValueError("qa_questions ids must be unique")
        elif self.qa_questions:
            raise ValueError("qa_questions is only valid when feedback_format is structured_qa")
        return self


class InsightCampaignResponse(BaseModel):
    id: str
    title: str
    material_url: str
    business_question: str
    feedback_format: str
    qa_questions: list[QAQuestion]
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
    feedback_format: str
    qa_questions: list[QAQuestion]
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


class QAAnswer(BaseModel):
    question_id: str
    answer_text: str

    @field_validator("answer_text")
    @classmethod
    def _answer_length(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("answer_text must not be empty")
        if len(value) > 500:
            raise ValueError("answer_text must be at most 500 characters")
        return value


class InsightResponseSubmitRequest(BaseModel):
    ratings: list[RatingAnswer] | None = None
    qa_answers: list[QAAnswer] | None = None

    @model_validator(mode="after")
    def _exactly_one_populated(self) -> "InsightResponseSubmitRequest":
        if bool(self.ratings) == bool(self.qa_answers):
            raise ValueError("submit exactly one of: ratings, qa_answers")
        return self


class InsightResponseAck(BaseModel):
    panel_member_id: str
    submitted_at: datetime


class InsightBrandResultResponse(BaseModel):
    """Brand-facing aggregated results -- pseudonym handle only, no
    talent_id/display_name field exists on this model at all."""

    pseudonym_handle: str
    feedback_format: str
    ratings: list[dict] | None
    qa_answers: list[dict] | None
    submitted_at: datetime


class InsightBrandResultsResponse(BaseModel):
    """Wraps per-response results with the campaign's release state.
    For structured_qa, results stays [] and released=False until every
    panel_size response has been submitted *and* moderator-approved
    (issue #52's k-anonymity gate) -- rating_scale is always released
    per-response, matching its pre-existing behavior."""

    feedback_format: str
    released: bool
    responses_submitted: int
    responses_required: int
    results: list[InsightBrandResultResponse]


# ──────────────────────────────────────────────────────────────────
# Internship / Apprenticeship template (issue #50)
# ──────────────────────────────────────────────────────────────────


class InternshipCreateRequest(BaseModel):
    role_title: str
    description: str
    time_commitment: str
    compensation_type: str
    compensation_why: str
    requirements_text: str
    application_process_text: str
    why_text: str
    deadline: datetime

    @field_validator("compensation_type")
    @classmethod
    def _known_compensation_type(cls, value: str) -> str:
        if value not in ("paid", "stipend", "unpaid"):
            raise ValueError("compensation_type must be one of: paid, stipend, unpaid")
        return value

    @field_validator("compensation_why")
    @classmethod
    def _compensation_why_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("compensation_why must not be empty")
        return value

    @field_validator("why_text")
    @classmethod
    def _why_text_length(cls, value: str) -> str:
        return _word_count_at_most(value, 150, "why_text")


class InternshipResponse(BaseModel):
    id: str
    role_title: str
    description: str
    time_commitment: str
    compensation_type: str
    compensation_why: str
    requirements_text: str
    application_process_text: str
    why_text: str
    deadline: datetime
    moderation_status: str
    rejection_reason: str | None
    status: str
    created_at: datetime


class InternshipApplyRequest(BaseModel):
    response_text: str

    @field_validator("response_text")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("response_text must not be empty")
        return value


class InternshipApplicationResponse(BaseModel):
    id: str
    internship_id: str
    response_text: str
    status: str
    submitted_at: datetime
    reviewed_at: datetime | None


class InternshipApplicationBrandView(BaseModel):
    """Brand-facing application list -- same non-pseudonymous shape as
    ScholarshipApplicationBrandView; internship applicants are
    on-platform Talent accounts with a name attached, not pseudonymous
    panelists (8I's pseudonym requirement is scoped to Insight &
    Feedback only)."""

    id: str
    talent_id: str
    response_text: str
    status: str
    submitted_at: datetime


class InsightResponseModerationItem(BaseModel):
    """Admin-facing queue item for a pending structured_qa response.
    Pseudonymous like every other brand/admin-adjacent Insight &
    Feedback surface -- a human reviewer moderating text still doesn't
    need the talent's real identity to do their job."""

    id: str
    campaign_id: str
    campaign_title: str
    pseudonym_handle: str
    qa_answers: list[dict]
    scrub_flags: list[dict]
    submitted_at: datetime
