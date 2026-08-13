from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator

from app.core.categories import BASE_CATEGORIES

SubmissionFormat = Literal["text", "file", "both"]
ChallengeStatus = Literal["draft", "active", "closed"]


class QuizQuestionInput(BaseModel):
    """Brand-authored quiz question (issue #51) -- correct_index is
    write-only: accepted here, stored, but never present on any
    response  schema in this file. Same shape/validation as
    learning_modules.QuizQuestionInput."""

    question: str
    options: list[str]
    correct_index: int

    @field_validator("options")
    @classmethod
    def _exactly_four_options(cls, value: list[str]) -> list[str]:
        if len(value) != 4:
            raise ValueError("quiz questions must have exactly 4 options")
        return value

    @field_validator("correct_index")
    @classmethod
    def _valid_index(cls, value: int) -> int:
        if not (0 <= value <= 3):
            raise ValueError("correct_index must be between 0 and 3")
        return value


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
    # Build Prompt 8I content layer
    goal_text: str | None = None
    rules_text: str | None = None
    judging_criteria: str | None = None
    prize_reward_text: str | None = None
    why_text: str | None = None
    moderation_status: str = "draft"
    rejection_reason: str | None = None
    # Stripped (never includes correct_index) -- see
    # Challenge.public_quiz_questions / strip_quiz_answer_keys.
    quiz_questions: list[dict] = []


class ChallengeContentLayerUpdateRequest(BaseModel):
    """PUT /brands/challenges/:id/content -- Build Prompt 8I's added
    fields, kept separate from ChallengeCreateRequest (Prompt 8G) since
    only why_text is required here. quiz_questions (issue #51) is
    optional and, per Section 5's "highest-scrutiny" requirement, still
    rides through the same why_text-gated moderation queue as the rest
    of the content layer -- omitted entirely means "leave the existing
    quiz unchanged," not "clear it" (see
    challenges_repository.update_content_layer)."""

    goal_text: str | None = None
    rules_text: str | None = None
    judging_criteria: str | None = None
    prize_reward_text: str | None = None
    why_text: str
    quiz_questions: list[QuizQuestionInput] | None = None

    @field_validator("why_text")
    @classmethod
    def _why_text_length(cls, value: str) -> str:
        words = value.split()
        if len(words) > 150:
            raise ValueError(f"why_text must be at most 150 words (got {len(words)})")
        return value

    @field_validator("quiz_questions")
    @classmethod
    def _quiz_length(cls, value: list[QuizQuestionInput] | None) -> list[QuizQuestionInput] | None:
        if value is not None and not 1 <= len(value) <= 10:
            raise ValueError("quiz_questions must have between 1 and 10 questions")
        return value


class SubmitQuizRequest(BaseModel):
    """POST /talents/challenges/:id/quiz/submit -- one answer index per
    quiz_questions entry, in order."""

    answers: list[int]


class QuizWrongAnswerEntry(BaseModel):
    """Reveals correct_index only for questions the talent already
    answered wrong, and only after the one-time attempt is scored --
    same disclosure shape as learning_modules' WrongAnswerEntry. This
    is the ONLY response  model in this file allowed to carry
    correct_index."""

    question_index: int
    correct_index: int
    talent_answer_index: int


class QuizResultResponse(BaseModel):
    challenge_id: str
    score: int
    total: int
    passed: bool
    wrong_answers: list[QuizWrongAnswerEntry]


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
    # Stripped -- never includes correct_index (issue #51). Safe to
    # show up front since taking the quiz is gated on having an
    # existing submission, not on not having seen the questions.
    quiz_questions: list[dict] = []


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
