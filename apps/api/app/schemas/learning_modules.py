from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator

ContentBlockType = Literal["text", "video_url", "image_url", "quiz"]
ModuleStatus = Literal["draft", "active", "archived"]
CompletionStatus = Literal["in_progress", "passed", "failed"]


class QuizQuestionInput(BaseModel):
    """Admin-authored quiz question -- correct_index is write-only:
    accepted here, stored, but never present on any response  schema in
    this file."""

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


class ContentBlockInput(BaseModel):
    type: ContentBlockType
    # str for text/video_url/image_url, list[QuizQuestionInput] for quiz.
    # Kept loosely typed (not a discriminated union) to match the jsonb
    # column's own shape -- validated explicitly in the router instead.
    content: object

    @field_validator("content")
    @classmethod
    def _validate_shape(cls, value: object, info) -> object:
        block_type = info.data.get("type")
        if block_type == "quiz":
            if not isinstance(value, list) or not value:
                raise ValueError("quiz blocks require a non-empty list of questions")
            # Validate each question via QuizQuestionInput, return dicts.
            return [QuizQuestionInput(**q).model_dump() for q in value]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{block_type} blocks require non-empty string content")
        return value


class ModuleCreateRequest(BaseModel):
    title: str
    description: str
    category: str | None = None
    estimated_minutes: int
    badge_title: str
    badge_description: str
    badge_color: str
    badge_icon: str | None = None
    content_blocks: list[ContentBlockInput]
    passing_score: int | None = None

    @field_validator("content_blocks")
    @classmethod
    def _at_least_one_block(cls, value: list[ContentBlockInput]) -> list[ContentBlockInput]:
        if not value:
            raise ValueError("content_blocks must contain at least one block")
        return value

    @field_validator("estimated_minutes")
    @classmethod
    def _positive_minutes(cls, value: int) -> int:
        if value < 1:
            raise ValueError("estimated_minutes must be >= 1")
        return value

    @field_validator("passing_score")
    @classmethod
    def _valid_passing_score(cls, value: int | None) -> int | None:
        if value is not None and not (1 <= value <= 100):
            raise ValueError("passing_score must be between 1 and 100 when provided")
        return value


class ModuleAdminResponse(BaseModel):
    """Write-only-answers response  for admin create/update/get/list --
    content_blocks here NEVER contains correct_index (see
    ModulePublicSerializer / strip_correct_index)."""

    id: str
    title: str
    description: str
    category: str | None
    content_blocks: list[dict]
    passing_score: int | None
    badge_title: str
    badge_description: str
    badge_color: str
    badge_icon: str | None
    estimated_minutes: int
    status: ModuleStatus
    created_at: datetime
    updated_at: datetime
    # Admin list/detail quality signals (spec deliverable 1).
    completion_count: int = 0
    pass_rate: float | None = None
    average_attempts: float | None = None
    in_progress_count: int = 0


class TalentProgressResponse(BaseModel):
    status: CompletionStatus
    attempts: int
    quiz_score: int | None
    last_attempt_at: datetime | None


class ModuleAvailableResponse(BaseModel):
    """GET /talents/modules/available entries."""

    id: str
    title: str
    description: str
    category: str | None
    badge_title: str
    badge_description: str
    badge_color: str
    badge_icon: str | None
    estimated_minutes: int
    passing_score: int | None
    talent_progress: TalentProgressResponse | None


class ModuleCompletedResponse(BaseModel):
    """GET /talents/modules/completed entries -- source of truth for badge
    history."""

    module_id: str
    title: str
    category: str | None
    badge_title: str
    badge_description: str
    badge_color: str
    badge_icon: str | None
    passed_at: datetime | None
    quiz_score: int | None


class ModuleContentResponse(BaseModel):
    """GET /talents/modules/:id and POST /talents/modules/:id/start's module
    portion -- content_blocks NEVER contains correct_index."""

    id: str
    title: str
    description: str
    category: str | None
    content_blocks: list[dict]
    passing_score: int | None
    badge_title: str
    badge_description: str
    badge_color: str
    badge_icon: str | None
    estimated_minutes: int
    status: ModuleStatus


class ModuleStartRequest(BaseModel):
    disclosure_acknowledged: bool = False


class ModuleStartResponse(BaseModel):
    module: ModuleContentResponse
    completion: TalentProgressResponse


class ModuleCompleteRequest(BaseModel):
    answers: list[int] = []


class WrongAnswerEntry(BaseModel):
    question_index: int
    correct_index: int
    talent_answer_index: int


class BadgeSummary(BaseModel):
    badge_title: str
    badge_description: str
    badge_color: str
    badge_icon: str | None


class ModuleCompleteResponse(BaseModel):
    passed: bool
    quiz_score: int | None
    passing_score: int | None = None
    badge: BadgeSummary | None = None
    profile_completeness_score: int | None = None
    correct_answers: list[WrongAnswerEntry] | None = None


class AdminModuleAnalyticsPerModuleEntry(BaseModel):
    module_id: str
    title: str
    category: str | None
    completion_count: int
    pass_rate: float | None
    average_attempts: float | None


class AdminModuleAnalyticsBadgeEntry(BaseModel):
    badge_title: str
    category: str | None
    earned_count: int


class FtcModuleReadinessResponse(BaseModel):
    attempted_reps: int
    passed_reps: int
    pass_percentage: float | None


class AdminModuleAnalyticsResponse(BaseModel):
    total_modules: int
    draft_modules: int
    active_modules: int
    archived_modules: int
    completions_in_progress: int
    completions_passed: int
    completions_failed: int
    per_module: list[AdminModuleAnalyticsPerModuleEntry]
    modules_flagged_low_pass_rate: list[str]
    modules_flagged_high_attempts: list[str]
    badge_distribution: list[AdminModuleAnalyticsBadgeEntry]
    ftc_module_readiness: FtcModuleReadinessResponse | None


class ModuleActivityBadgeEntry(BaseModel):
    badge_title: str
    earned_at: str


class ModuleActivityResponse(BaseModel):
    """Parent dashboard addition (spec deliverable 8) -- no quiz_score,
    no wrong-answer detail. Parents see the outcome, not the struggle."""

    total_started: int
    total_passed: int
    total_failed: int
    badges_earned: list[ModuleActivityBadgeEntry]
    ftc_module_passed: bool
