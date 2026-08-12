"""Learning Modules and Verified Badges (Build Prompt 8H): admin-curated
educational content reps complete to earn verified profile badges, plus
the mandatory FTC Disclosure Essentials gate on campaign acceptance.

Three routers, matching this codebase's existing split by URL prefix:
`admin_modules_router` (mounted under app.routers.admin's existing
/admin prefix pattern, but kept in its own module here since 8H is a
big enough addition to warrant one), `reps_modules_router`
(`/reps/modules/...`), and a small helper used by app/routers/reps.py
to gate POST /campaigns/:id/accept.

SECURITY: `correct_index` must never appear in any client-facing
response, including admin preview. Every response in this file that
carries content_blocks routes through
learning_modules_repository.strip_correct_index (or a module's own
`.public_content_blocks` property, which calls the same function) --
never through raw `.content_blocks`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.core.profile_score import compute_profile_completeness_score
from app.core.security import AuthenticatedUser, require_role
from app.db.pool import get_connection
from app.repositories import learning_modules_repository, rep_profiles_repository
from app.schemas.learning_modules import (
    AdminModuleAnalyticsResponse,
    BadgeSummary,
    ModuleAdminResponse,
    ModuleAvailableResponse,
    ModuleCompletedResponse,
    ModuleCompleteRequest,
    ModuleCompleteResponse,
    ModuleContentResponse,
    ModuleCreateRequest,
    ModuleStartRequest,
    ModuleStartResponse,
    RepProgressResponse,
    WrongAnswerEntry,
)

logger = logging.getLogger(__name__)

admin_modules_router = APIRouter(prefix="/admin/modules", tags=["admin", "learning-modules"], dependencies=[Depends(require_role("admin"))])
admin_module_analytics_router = APIRouter(prefix="/admin/analytics", tags=["admin", "learning-modules"], dependencies=[Depends(require_role("admin"))])
reps_modules_router = APIRouter(prefix="/reps/modules", tags=["reps", "learning-modules"])

RETAKE_COOLDOWN = timedelta(hours=24)


# ══════════════════════════════════════════════════════════════════
# Shared serialization helpers
# ══════════════════════════════════════════════════════════════════


def _to_content_response(m: learning_modules_repository.LearningModule) -> ModuleContentResponse:
    return ModuleContentResponse(
        id=m.id,
        title=m.title,
        description=m.description,
        category=m.category,
        content_blocks=m.public_content_blocks,
        passing_score=m.passing_score,
        badge_title=m.badge_title,
        badge_description=m.badge_description,
        badge_color=m.badge_color,
        badge_icon=m.badge_icon,
        estimated_minutes=m.estimated_minutes,
        status=m.status,
    )


def _quiz_question_count(content_blocks: list[dict]) -> int:
    return sum(len(b.get("content") or []) for b in content_blocks if b.get("type") == "quiz")


# ══════════════════════════════════════════════════════════════════
# Admin module management (spec deliverable 1)
# ══════════════════════════════════════════════════════════════════


def _validate_quiz_consistency(body: ModuleCreateRequest) -> None:
    has_quiz = any(b.type == "quiz" for b in body.content_blocks)
    if has_quiz and body.passing_score is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "passing_score_required", "message": "passing_score (1-100) is required when content_blocks includes a quiz."},
        )
    if not has_quiz and body.passing_score is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "passing_score_not_allowed", "message": "passing_score must be null when there are no quiz blocks."},
        )


async def _to_admin_response(conn: asyncpg.Connection, m: learning_modules_repository.LearningModule) -> ModuleAdminResponse:
    stats_by_id = await learning_modules_repository.admin_module_stats(conn)
    stats = stats_by_id.get(m.id, {"completion_count": 0, "pass_rate": None, "average_attempts": None, "in_progress_count": 0})
    return ModuleAdminResponse(
        id=m.id,
        title=m.title,
        description=m.description,
        category=m.category,
        content_blocks=m.public_content_blocks,
        passing_score=m.passing_score,
        badge_title=m.badge_title,
        badge_description=m.badge_description,
        badge_color=m.badge_color,
        badge_icon=m.badge_icon,
        estimated_minutes=m.estimated_minutes,
        status=m.status,
        created_at=m.created_at,
        updated_at=m.updated_at,
        **stats,
    )


@admin_modules_router.post("", response_model=ModuleAdminResponse, status_code=status.HTTP_201_CREATED)
async def create_module(
    body: ModuleCreateRequest,
    conn: asyncpg.Connection = Depends(get_connection),
) -> ModuleAdminResponse:
    _validate_quiz_consistency(body)
    created = await learning_modules_repository.create_module(
        conn,
        title=body.title,
        description=body.description,
        category=body.category,
        content_blocks=[b.model_dump() for b in body.content_blocks],
        passing_score=body.passing_score,
        badge_title=body.badge_title,
        badge_description=body.badge_description,
        badge_color=body.badge_color,
        badge_icon=body.badge_icon,
        estimated_minutes=body.estimated_minutes,
    )
    return await _to_admin_response(conn, created)


@admin_modules_router.get("", response_model=list[ModuleAdminResponse])
async def list_modules(conn: asyncpg.Connection = Depends(get_connection)) -> list[ModuleAdminResponse]:
    modules = await learning_modules_repository.list_all(conn)
    return [await _to_admin_response(conn, m) for m in modules]


async def _require_module(conn: asyncpg.Connection, module_id: str) -> learning_modules_repository.LearningModule:
    module = await learning_modules_repository.get_by_id(conn, module_id)
    if module is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "module_not_found", "message": "No module found for that id."})
    return module


@admin_modules_router.get("/{module_id}", response_model=ModuleAdminResponse)
async def get_module(module_id: str, conn: asyncpg.Connection = Depends(get_connection)) -> ModuleAdminResponse:
    module = await _require_module(conn, module_id)
    return await _to_admin_response(conn, module)


@admin_modules_router.put("/{module_id}", response_model=ModuleAdminResponse)
async def update_module(
    module_id: str,
    body: ModuleCreateRequest,
    conn: asyncpg.Connection = Depends(get_connection),
) -> ModuleAdminResponse:
    _validate_quiz_consistency(body)
    await _require_module(conn, module_id)  # 404 regardless of status
    updated = await learning_modules_repository.update_module(
        conn,
        module_id,
        title=body.title,
        description=body.description,
        category=body.category,
        content_blocks=[b.model_dump() for b in body.content_blocks],
        passing_score=body.passing_score,
        badge_title=body.badge_title,
        badge_description=body.badge_description,
        badge_color=body.badge_color,
        badge_icon=body.badge_icon,
        estimated_minutes=body.estimated_minutes,
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "module_not_editable",
                "message": "Active modules cannot be edited. Archive this module and create a new one to preserve the integrity of existing badges.",
            },
        )
    return await _to_admin_response(conn, updated)


@admin_modules_router.post("/{module_id}/activate", response_model=ModuleAdminResponse)
async def activate_module(module_id: str, conn: asyncpg.Connection = Depends(get_connection)) -> ModuleAdminResponse:
    module = await _require_module(conn, module_id)
    if module.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "illegal_transition", "message": f"Cannot activate from status '{module.status}'."},
        )
    if not module.content_blocks:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "incomplete_module", "message": "content_blocks must be non-empty to activate."})
    has_quiz = any(b.get("type") == "quiz" for b in module.content_blocks)
    if has_quiz and module.passing_score is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "passing_score_required", "message": "passing_score is required when content_blocks includes a quiz."})
    if not has_quiz and module.passing_score is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "passing_score_not_allowed", "message": "passing_score must be null when there are no quiz blocks."})
    updated = await learning_modules_repository.activate(conn, module_id)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "illegal_transition", "message": "Module status changed before activation completed."})
    return await _to_admin_response(conn, updated)


@admin_modules_router.post("/{module_id}/archive", response_model=ModuleAdminResponse)
async def archive_module(module_id: str, conn: asyncpg.Connection = Depends(get_connection)) -> ModuleAdminResponse:
    module = await _require_module(conn, module_id)
    updated = await learning_modules_repository.archive(conn, module_id)
    if updated is None:
        if module.status == "archived":
            return await _to_admin_response(conn, module)  # idempotent
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "illegal_transition", "message": f"Cannot archive from status '{module.status}'."})
    return await _to_admin_response(conn, updated)


# ══════════════════════════════════════════════════════════════════
# Admin analytics (spec deliverable 9)
# ══════════════════════════════════════════════════════════════════


@admin_module_analytics_router.get("/modules", response_model=AdminModuleAnalyticsResponse)
async def analytics_modules(
    conn: asyncpg.Connection = Depends(get_connection),
    settings: Settings = Depends(get_settings),
) -> AdminModuleAnalyticsResponse:
    result = await learning_modules_repository.admin_analytics(conn, ftc_module_id=settings.ftc_module_id or None)
    return AdminModuleAnalyticsResponse(**result)


# ══════════════════════════════════════════════════════════════════
# Rep module discovery + progress (spec deliverable 3)
# ══════════════════════════════════════════════════════════════════


async def _get_own_rep_profile(conn: asyncpg.Connection, user: AuthenticatedUser) -> rep_profiles_repository.RepProfile:
    profile = await rep_profiles_repository.get_by_user_id(conn, user.id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "rep_profile_not_found", "message": "Complete onboarding via PUT /reps/me first."})
    return profile


@reps_modules_router.get("/available", response_model=list[ModuleAvailableResponse])
async def available_modules(
    user: AuthenticatedUser = Depends(require_role("rep")),
    conn: asyncpg.Connection = Depends(get_connection),
    settings: Settings = Depends(get_settings),
) -> list[ModuleAvailableResponse]:
    profile = await _get_own_rep_profile(conn, user)
    modules = await learning_modules_repository.list_active(conn)
    completions = {c.module_id: c for c in await learning_modules_repository.list_for_rep(conn, profile.id)}

    def _sort_key(m: learning_modules_repository.LearningModule) -> tuple[int, int, str]:
        is_ftc = 0 if (settings.ftc_module_id and m.id == settings.ftc_module_id) else 1
        is_category_match = 0 if (m.category and m.category in profile.categories) else 1
        return (is_ftc, is_category_match, m.title)

    result: list[ModuleAvailableResponse] = []
    for m in sorted(modules, key=_sort_key):
        completion = completions.get(m.id)
        if completion is not None and completion.status == "passed":
            continue  # already passed -- not "available"
        rep_progress = (
            RepProgressResponse(
                status=completion.status,
                attempts=completion.attempts,
                quiz_score=completion.quiz_score,
                last_attempt_at=completion.last_attempt_at,
            )
            if completion is not None
            else None
        )
        result.append(
            ModuleAvailableResponse(
                id=m.id,
                title=m.title,
                description=m.description,
                category=m.category,
                badge_title=m.badge_title,
                badge_description=m.badge_description,
                badge_color=m.badge_color,
                badge_icon=m.badge_icon,
                estimated_minutes=m.estimated_minutes,
                passing_score=m.passing_score,
                rep_progress=rep_progress,
            )
        )
    return result


@reps_modules_router.get("/completed", response_model=list[ModuleCompletedResponse])
async def completed_modules(
    user: AuthenticatedUser = Depends(require_role("rep")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[ModuleCompletedResponse]:
    profile = await _get_own_rep_profile(conn, user)
    completions = [c for c in await learning_modules_repository.list_for_rep(conn, profile.id) if c.status == "passed"]
    result: list[ModuleCompletedResponse] = []
    for c in completions:
        module = await learning_modules_repository.get_by_id(conn, c.module_id)
        if module is None:
            continue
        result.append(
            ModuleCompletedResponse(
                module_id=module.id,
                title=module.title,
                category=module.category,
                badge_title=module.badge_title,
                badge_description=module.badge_description,
                badge_color=module.badge_color,
                badge_icon=module.badge_icon,
                passed_at=c.passed_at,
                quiz_score=c.quiz_score,
            )
        )
    return result


@reps_modules_router.get("/{module_id}", response_model=ModuleContentResponse)
async def get_module_content(
    module_id: str,
    user: AuthenticatedUser = Depends(require_role("rep")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> ModuleContentResponse:
    await _get_own_rep_profile(conn, user)
    module = await learning_modules_repository.get_by_id(conn, module_id)
    if module is None or module.status == "draft":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "module_not_found", "message": "No module found for that id."})
    return _to_content_response(module)


# ══════════════════════════════════════════════════════════════════
# Module start (spec deliverable 4)
# ══════════════════════════════════════════════════════════════════


@reps_modules_router.post("/{module_id}/start", response_model=ModuleStartResponse)
async def start_module(
    module_id: str,
    body: ModuleStartRequest,
    user: AuthenticatedUser = Depends(require_role("rep")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> ModuleStartResponse:
    profile = await _get_own_rep_profile(conn, user)

    if not body.disclosure_acknowledged:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "disclosure_acknowledgment_required",
                "message": (
                    "Module disclosure acknowledgment required. This module is unpaid. Completing it "
                    "earns a verified badge on your profile. Your school district may offer a completion "
                    "stipend — check with your school counselor."
                ),
            },
        )

    module = await _require_module(conn, module_id)
    if module.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "module_not_active", "message": "This module is not currently available to start."})

    existing = await learning_modules_repository.get_for_rep_and_module(conn, profile.id, module_id)
    if existing is not None and existing.status == "passed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "already_completed", "message": "You have already completed this module."})

    now = datetime.now(timezone.utc)
    if existing is not None and existing.status == "failed":
        if existing.last_attempt_at is not None and (now - existing.last_attempt_at) < RETAKE_COOLDOWN:
            available_at = existing.last_attempt_at + RETAKE_COOLDOWN
            remaining = available_at - now
            hours, remainder = divmod(int(remaining.total_seconds()), 3600)
            minutes = remainder // 60
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "retake_cooldown",
                    "message": f"You can retake this module in {hours} hours and {minutes} minutes.",
                    "available_at": available_at.isoformat(),
                },
            )
        completion = await learning_modules_repository.start_retake(conn, rep_id=profile.id, module_id=module_id, at=now)
    elif existing is not None:
        # in_progress -- re-acknowledging the disclosure and resuming is
        # fine; treat as idempotent re-start rather than an error (the
        # rep may have closed the tab mid-module). Row is left as-is.
        completion = existing
    else:
        completion = await learning_modules_repository.start_new(conn, rep_id=profile.id, module_id=module_id, at=now)

    if completion is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "illegal_transition", "message": "Completion state changed before start completed."})

    return ModuleStartResponse(
        module=_to_content_response(module),
        completion=RepProgressResponse(
            status=completion.status,
            attempts=completion.attempts,
            quiz_score=completion.quiz_score,
            last_attempt_at=completion.last_attempt_at,
        ),
    )


# ══════════════════════════════════════════════════════════════════
# Module completion (spec deliverable 5)
# ══════════════════════════════════════════════════════════════════


@reps_modules_router.post("/{module_id}/complete", response_model=ModuleCompleteResponse)
async def complete_module(
    module_id: str,
    body: ModuleCompleteRequest,
    user: AuthenticatedUser = Depends(require_role("rep")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> ModuleCompleteResponse:
    profile = await _get_own_rep_profile(conn, user)

    completion = await learning_modules_repository.get_for_rep_and_module(conn, profile.id, module_id)
    if completion is None or completion.status != "in_progress":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "not_started", "message": "You must start this module before completing it."})

    module = await _require_module(conn, module_id)
    if module.status == "archived":
        raise HTTPException(status_code=status.HTTP_410_GONE, detail={"code": "module_archived", "message": "This module is no longer available."})

    # (c) Fetch content_blocks WITH correct_index -- server-side only,
    # never derived from anything the client submitted. `module` here
    # came straight from the repository's raw row, not a stripped
    # response, so module.content_blocks (not .public_content_blocks)
    # is safe to score against.
    quiz_questions: list[dict] = []
    for block in module.content_blocks:
        if block.get("type") == "quiz":
            quiz_questions.extend(block.get("content") or [])

    now = datetime.now(timezone.utc)

    if not quiz_questions:
        quiz_score = None
        passed = module.passing_score is None
        wrong_answers: list[WrongAnswerEntry] = []
    else:
        correct_count = 0
        wrong_answers = []
        for idx, q in enumerate(quiz_questions):
            rep_answer = body.answers[idx] if idx < len(body.answers) else -1
            correct_index = q["correct_index"]
            if rep_answer == correct_index:
                correct_count += 1
            else:
                wrong_answers.append(WrongAnswerEntry(question_index=idx, correct_index=correct_index, rep_answer_index=rep_answer))
        quiz_score = round((correct_count / len(quiz_questions)) * 100)
        passed = module.passing_score is not None and quiz_score >= module.passing_score

    if passed:
        async with conn.transaction():
            updated_completion = await learning_modules_repository.mark_passed(conn, completion.id, quiz_score=quiz_score, at=now)
            if updated_completion is None:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "illegal_transition", "message": "Completion state changed mid-request."})

            badge = {
                "module_id": module.id,
                "badge_title": module.badge_title,
                "badge_description": module.badge_description,
                "badge_color": module.badge_color,
                "badge_icon": module.badge_icon,
                "earned_at": now.isoformat(),
            }
            new_score = compute_profile_completeness_score(
                bio=profile.bio,
                categories=profile.categories,
                school_type=profile.school_type,
                instagram_handle=profile.instagram_handle,
                tiktok_handle=profile.tiktok_handle,
                total_campaigns_completed=profile.total_campaigns_completed,
                badges_earned_count=profile.badges_earned_count + 1,
            )
            updated_profile = await rep_profiles_repository.append_badge_and_recompute_score(conn, profile.id, badge=badge, new_score=new_score)
            if updated_profile is None:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"code": "badge_issuance_failed", "message": "Could not issue badge."})

        return ModuleCompleteResponse(
            passed=True,
            quiz_score=quiz_score,
            badge=BadgeSummary(
                badge_title=module.badge_title,
                badge_description=module.badge_description,
                badge_color=module.badge_color,
                badge_icon=module.badge_icon,
            ),
            profile_completeness_score=new_score,
        )

    updated_completion = await learning_modules_repository.mark_failed(conn, completion.id, quiz_score=quiz_score, at=now)
    if updated_completion is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "illegal_transition", "message": "Completion state changed mid-request."})
    return ModuleCompleteResponse(
        passed=False,
        quiz_score=quiz_score,
        passing_score=module.passing_score,
        correct_answers=wrong_answers,
    )


# ══════════════════════════════════════════════════════════════════
# FTC gate helper -- used by app/routers/reps.py's accept_campaign
# ══════════════════════════════════════════════════════════════════


async def enforce_ftc_gate(conn: asyncpg.Connection, settings: Settings, rep_id: str) -> None:
    """Raises HTTPException(403) if FTC_MODULE_ID is configured and the
    rep has no 'passed' completion row for it. No-op (with a warning
    log) if FTC_MODULE_ID is unset -- spec deliverable 2."""
    if not settings.ftc_module_id:
        logger.warning("FTC_MODULE_ID not configured. FTC gate skipped.")
        return
    passed = await learning_modules_repository.has_passed(conn, rep_id, settings.ftc_module_id)
    if not passed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ftc_module_required",
                "message": (
                    "Complete the FTC Disclosure Essentials module before accepting campaigns. It takes "
                    "about 5 minutes and is required to ensure you understand sponsored content disclosure rules."
                ),
                "module_id": settings.ftc_module_id,
            },
        )
