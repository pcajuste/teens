"""Talent portal backend (Build Prompt 5): own-profile CRUD, campaign
matching/participation state machine, earnings, and submission file
upload.

Two routers live in this module because Section 8 splits the URL
space: profile/listing endpoints hang off `/talents/...`, but campaign
*participation* actions are `/campaigns/:id/...` (no `/talents` prefix) --
`talents_router` and `campaigns_router` respectively, both included from
app/main.py.

Every route requires an active talent account
(app.core.security.require_role("talent")); a talent's own talent_profiles row
is looked up from the authenticated user's id on every request rather
than trusting a talent_id from the URL/body, so a talent can never read or
write another talent's campaign_talents rows (Build Prompt 5 acceptance
criterion).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.core.config import Settings, get_settings
from app.core.profile_score import compute_profile_completeness_score
from app.core.security import AuthenticatedUser, require_role
from app.db.pool import get_connection
from app.repositories import admin_repository
from app.repositories import (
    brand_profiles_repository,
    campaign_milestones_repository,
    campaign_talents_repository,
    campaigns_repository,
    parent_records_repository,
    recruiter_contacts_repository,
    talent_goals_repository,
    talent_profiles_repository,
    users_repository,
)
from app.routers.learning_modules import enforce_ftc_gate
from app.schemas.admin import SafetyReportCreateRequest, SafetyReportResponse
from app.schemas.recruiters import InboxMessageResponse
from app.schemas.talents import (
    AcceptCampaignRequest,
    AchievementLinkResponse,
    AchievementLinkVisibilityUpdateRequest,
    AchievementRecordResponse,
    CampaignParticipationResponse,
    CampaignSummaryResponse,
    CreateGoalRequest,
    EarningsResponse,
    GoalResponse,
    GoalSuggestion,
    MilestoneEarningsEntry,
    MilestoneParticipationResponse,
    TalentProfilePreviewResponse,
    TalentProfileResponse,
    TalentProfileUpdateRequest,
    StripeOnboardingResponse,
    SubmitCampaignRequest,
    SubmitMilestoneRequest,
)
from app.services import stripe_service
from app.services.email_service import send_goal_completed_email, send_milestone_submitted_email
from app.services.parent_service import apply_values_filter, determine_parent_approval, send_campaign_approval_request
from app.services.resend_client import ResendClient, resend_client_dependency
from app.services.storage_service import SubmissionUploadError, get_storage_client

talents_router = APIRouter(prefix="/talents", tags=["talents"])
campaigns_router = APIRouter(prefix="/campaigns", tags=["campaigns"])

# Scope decision (Build Prompt 5 deliverable 6): talent-facing "recruiters
# interested" signal is NOT built at MVP. Deliberate cut pending a
# product decision on count-only vs. identity-revealing display and
# whether a recruiter contact-credit is charged just to appear
# interested. Nothing in this router computes or exposes that signal.
# The 48h parent-approval window moved to
# app.services.parent_service.PARENT_APPROVAL_WINDOW_HOURS (Build
# Prompt 8) since it's now shared with the brand-invite path.


def _require_talent_profile_row(row) -> talent_profiles_repository.TalentProfile:
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "talent_profile_not_found", "message": "Complete onboarding via PUT /talents/me first."},
        )
    return row


async def _get_own_profile(
    conn: asyncpg.Connection, user: AuthenticatedUser
) -> talent_profiles_repository.TalentProfile:
    profile = await talent_profiles_repository.get_by_user_id(conn, user.id)
    return _require_talent_profile_row(profile)


def _eighteenth_birthday_utc(date_of_birth: date) -> datetime:
    """Server-computed only (Section 9: never trust a client-submitted
    date) -- Feb 29 birthdays fall back to Feb 28 in non-leap 18th-
    birthday years, matching how compute_age already treats month/day
    comparisons."""
    try:
        birthday = date_of_birth.replace(year=date_of_birth.year + 18)
    except ValueError:
        birthday = date_of_birth.replace(year=date_of_birth.year + 18, day=28)
    return datetime.combine(birthday, time.min, tzinfo=timezone.utc)


def _score(profile: talent_profiles_repository.TalentProfile) -> int:
    return compute_profile_completeness_score(
        bio=profile.bio,
        categories=profile.categories,
        school_type=profile.school_type,
        instagram_handle=profile.instagram_handle,
        tiktok_handle=profile.tiktok_handle,
        total_campaigns_completed=profile.total_campaigns_completed,
        badges_earned_count=profile.badges_earned_count,
    )


def _to_profile_response(p: talent_profiles_repository.TalentProfile) -> TalentProfileResponse:
    return TalentProfileResponse(
        id=p.id,
        display_name=p.display_name,
        school_name=p.school_name,
        school_type=p.school_type,
        city=p.city,
        state=p.state,
        graduation_year=p.graduation_year,
        bio=p.bio,
        categories=p.categories,
        instagram_handle=p.instagram_handle,
        tiktok_handle=p.tiktok_handle,
        recruiter_visible=p.recruiter_visible,
        total_campaigns_completed=p.total_campaigns_completed,
        total_earnings_cents=p.total_earnings_cents,
        average_rating=p.average_rating,
        profile_completeness_score=p.profile_completeness_score,
        stripe_onboarding_complete=p.stripe_onboarding_complete,
        challenges_submitted_count=p.challenges_submitted_count,
        challenges_converted_count=p.challenges_converted_count,
        challenge_conversion_rate=p.challenge_conversion_rate,
        badges=p.badges,
        badges_earned_count=p.badges_earned_count,
    )


def _to_preview_response(p: talent_profiles_repository.TalentProfile) -> TalentProfilePreviewResponse:
    """Shares the exact field set a brand/recruiter view will also use
    (Build Prompt 5 deliverable 2) -- both this function and any future
    brand/recruiter serializer should read from the same TalentProfile
    dataclass so the two field lists cannot drift independently."""
    return TalentProfilePreviewResponse(
        display_name=p.display_name,
        school_name=p.school_name,
        school_type=p.school_type,
        city=p.city,
        state=p.state,
        graduation_year=p.graduation_year,
        bio=p.bio,
        categories=p.categories,
        instagram_handle=p.instagram_handle,
        tiktok_handle=p.tiktok_handle,
        total_campaigns_completed=p.total_campaigns_completed,
        average_rating=p.average_rating,
        profile_completeness_score=p.profile_completeness_score,
        challenges_submitted_count=p.challenges_submitted_count,
        challenges_converted_count=p.challenges_converted_count,
        challenge_conversion_rate=p.challenge_conversion_rate,
        badges=p.badges,
        badges_earned_count=p.badges_earned_count,
    )


def _to_goal_response(g: talent_goals_repository.TalentGoal) -> GoalResponse:
    """Projected completion date is linear extrapolation from
    current_value/elapsed-time-since-created -- no historical progress
    snapshots exist to compute a real trend line, so "current pace"
    here means "average pace since the goal was created", not a
    recent-velocity estimate. None when there's no progress yet or the
    goal is already resolved (completed/abandoned) -- projecting a
    finished goal isn't meaningful."""
    projected: date | None = None
    if g.status == "active" and g.current_value > 0:
        elapsed_days = max((datetime.now(timezone.utc) - g.created_at).days, 1)
        rate_per_day = g.current_value / elapsed_days
        if rate_per_day > 0:
            remaining = max(g.target_value - g.current_value, 0)
            days_needed = remaining / rate_per_day
            projected = (datetime.now(timezone.utc) + timedelta(days=days_needed)).date()
    return GoalResponse(
        id=g.id,
        goal_type=g.goal_type,
        target_value=g.target_value,
        target_date=g.target_date,
        current_value=g.current_value,
        progress_percentage=g.progress_percentage,
        status=g.status,
        completed_at=g.completed_at,
        created_at=g.created_at,
        projected_completion_date=projected,
    )


def _to_participation_response(cr: campaign_talents_repository.CampaignTalent) -> CampaignParticipationResponse:
    return CampaignParticipationResponse(
        campaign_id=cr.campaign_id,
        status=cr.status,
        ftc_disclosure_accepted=cr.ftc_disclosure_accepted,
        parent_approval_status=cr.parent_approval_status,
        parent_approval_deadline=cr.parent_approval_deadline,
        submission_text=cr.submission_text,
        submission_file_urls=cr.submission_file_urls,
        revision_note=cr.revision_note,
        payout_cents=cr.payout_cents,
        payout_status=cr.payout_status,
        invited_at=cr.invited_at,
        accepted_at=cr.accepted_at,
        submitted_at=cr.submitted_at,
        confirmed_at=cr.confirmed_at,
        paid_at=cr.paid_at,
        milestones_completed_count=cr.milestones_completed_count,
        total_milestone_payout_cents=cr.total_milestone_payout_cents,
    )


def _compute_milestone_participation(
    milestone_defs: list[campaign_milestones_repository.CampaignMilestone],
    progress: list[campaign_milestones_repository.CampaignRepMilestone],
) -> list[MilestoneParticipationResponse]:
    """Build Prompt 8B deliverable 3's actionability rule: a
    sequence_required milestone is actionable once every PRIOR
    sequence_required milestone is confirmed-or-paid; a non-sequential
    milestone is actionable once every sequence_required milestone on
    the campaign is confirmed-or-paid (validate_milestones guarantees
    non-sequential milestones always trail every sequence_required one,
    so "all sequence_required milestones done" is exactly
    "all_prior_sequence_done" by the time we reach the first
    non-sequential entry in milestone_number order). Only a 'pending'
    milestone can ever be actionable -- one already submitted/confirmed/
    paid has nothing left for the talent to do."""
    progress_by_milestone_id = {p.campaign_milestone_id: p for p in progress}
    ordered = sorted(milestone_defs, key=lambda m: m.milestone_number)
    result: list[MilestoneParticipationResponse] = []
    all_prior_sequence_done = True
    for m in ordered:
        crm = progress_by_milestone_id.get(m.id)
        if crm is None:
            continue
        actionable = all_prior_sequence_done and crm.status == "pending"
        result.append(
            MilestoneParticipationResponse(
                id=crm.id,
                campaign_milestone_id=m.id,
                milestone_number=m.milestone_number,
                title=m.title,
                description=m.description,
                verification_method=m.verification_method,
                payout_percentage=m.payout_percentage,
                sequence_required=m.sequence_required,
                status=crm.status,
                actionable=actionable,
                payout_cents=crm.payout_cents,
                payout_status=crm.payout_status,
                threshold_count=m.threshold_count,
                current_count=crm.current_count,
                submitted_at=crm.submitted_at,
                confirmed_at=crm.confirmed_at,
                paid_at=crm.paid_at,
            )
        )
        if m.sequence_required and crm.status not in ("confirmed", "paid"):
            all_prior_sequence_done = False
    return result


async def _to_participation_response_with_milestones(
    conn: asyncpg.Connection, cr: campaign_talents_repository.CampaignTalent, campaign: campaigns_repository.Campaign
) -> CampaignParticipationResponse:
    """GET /talents/campaigns/active's per-row shape (Build Prompt 8B
    deliverable 3): every other participation-returning route
    (apply/accept/decline/submit/withdraw/history) uses the plain
    _to_participation_response above, which is fine there -- a talent
    already knows the milestone list for a campaign they just took an
    action on, and history is post-hoc. /active is the one place a talent
    is deciding what to do *next*, which is exactly what the milestone
    list + actionability flag exists to answer."""
    base = _to_participation_response(cr)
    if campaign.payment_type != "milestone":
        return base
    milestone_defs = await campaign_milestones_repository.list_for_campaign(conn, campaign.id)
    progress = await campaign_milestones_repository.list_for_campaign_rep(conn, cr.id)
    return base.model_copy(
        update={
            "payment_type": campaign.payment_type,
            "milestones": _compute_milestone_participation(milestone_defs, progress),
        }
    )


# ══════════════════════════════════════════════════════════════════
# /talents/*
# ══════════════════════════════════════════════════════════════════


@talents_router.get("/me", response_model=TalentProfileResponse)
async def get_me(
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> TalentProfileResponse:
    profile = await _get_own_profile(conn, user)
    return _to_profile_response(profile)


@talents_router.put("/me", response_model=TalentProfileResponse)
async def put_me(
    body: TalentProfileUpdateRequest,
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
    resend_client: ResendClient = Depends(resend_client_dependency),
) -> TalentProfileResponse:
    """Creates talent_profiles on first call (onboarding) or updates it on
    subsequent calls. On first creation only, also creates the linked
    parent_records row -- but only for talents whose
    public.users.parent_verified_at IS NOT NULL (the under-16
    consent-flow path); see docs/parent_records_creation_timing.md.
    Both inserts happen in one transaction so parent_records' FK to
    talent_profiles is never left in a half-created state."""
    existing = await talent_profiles_repository.get_by_user_id(conn, user.id)

    async with conn.transaction():
        if existing is None:
            db_user = await users_repository.get_user_by_id(conn, user.id)
            if db_user is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"code": "user_not_found", "message": "No user record found for this account."},
                )

            profile = await talent_profiles_repository.create_talent_profile(
                conn,
                user_id=user.id,
                display_name=body.display_name,
                school_name=body.school_name,
                school_type=body.school_type,
                city=body.city,
                state=body.state,
                graduation_year=body.graduation_year,
                bio=body.bio,
                categories=body.categories,
                instagram_handle=body.instagram_handle,
                tiktok_handle=body.tiktok_handle,
            )

            if db_user.parent_verified_at is not None:
                assert db_user.parent_email is not None
                await parent_records_repository.create_parent_record(
                    conn,
                    talent_id=profile.id,
                    parent_email=db_user.parent_email,
                    portal_expires_at=_eighteenth_birthday_utc(db_user.date_of_birth),
                    campaign_approval_required=True,
                    digest_enabled=True,
                )
        else:
            profile = await talent_profiles_repository.update_talent_profile(
                conn,
                existing.id,
                display_name=body.display_name,
                school_name=body.school_name,
                school_type=body.school_type,
                city=body.city,
                state=body.state,
                graduation_year=body.graduation_year,
                bio=body.bio,
                categories=body.categories,
                instagram_handle=body.instagram_handle,
                tiktok_handle=body.tiktok_handle,
            )

        new_score = _score(profile)
        newly_completed_goals: list[talent_goals_repository.TalentGoal] = []
        if new_score != profile.profile_completeness_score:
            await talent_profiles_repository.update_profile_completeness_score(conn, profile.id, new_score)
            profile = await talent_profiles_repository.get_by_id(conn, profile.id)
            # Build Prompt 5 deliverable 13: only profile_completeness
            # goals can move from this endpoint, but recompute_progress
            # is cheap and generic enough to just call outright rather
            # than special-casing a single-goal-type recompute.
            newly_completed_goals = await talent_goals_repository.recompute_progress(conn, profile.id)

    for goal in newly_completed_goals:
        await send_goal_completed_email(
            user.email,
            goal_description=talent_goals_repository.describe_goal(goal.goal_type, goal.target_value),
            client=resend_client,
        )

    return _to_profile_response(profile)


@talents_router.get("/me/profile-preview", response_model=TalentProfilePreviewResponse)
async def profile_preview(
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> TalentProfilePreviewResponse:
    profile = await _get_own_profile(conn, user)
    return _to_preview_response(profile)


@talents_router.get("/me/achievement-record", response_model=AchievementRecordResponse)
async def achievement_record(
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> AchievementRecordResponse:
    """Teenure Achievement Record export (Prompt 5 deliverable 9 gap
    fill, see Teenure_Build_Prompts.md section 18). Deliberately just
    wraps _to_preview_response's output -- exactly the same confirmed
    campaigns/categories/ratings a brand or recruiter already sees via
    GET /talents/me/profile-preview -- rather than assembling a second,
    driftable field list. No PDF library is added server-side for
    this: apps/api has no PDF dependency today (checked pyproject.toml)
    and this is a small MVP feature, so the frontend renders this JSON
    into a dedicated printable page and talents use the browser's native
    print-to-PDF instead of standing up a heavyweight rendering stack.
    Same auth pattern as every other /talents/me/* route: the talent is
    resolved from the authenticated user's own id, never from a
    client-supplied talent id, so a talent can never fetch another talent's
    record."""
    profile = await _get_own_profile(conn, user)
    return AchievementRecordResponse(
        generated_at=datetime.now(timezone.utc),
        record=_to_preview_response(profile),
    )


@talents_router.get("/me/achievement-link", response_model=AchievementLinkResponse)
async def get_achievement_link(
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
    settings: Settings = Depends(get_settings),
) -> AchievementLinkResponse:
    profile = await _get_own_profile(conn, user)
    token = await talent_profiles_repository.get_or_create_achievement_link_token(conn, profile.id)
    return AchievementLinkResponse(
        url=f"{settings.next_public_app_url}/verified/{token}",
        token=token,
        verified_profile_public=profile.verified_profile_public,
        earnings_visible_on_public_profile=profile.earnings_visible_on_public_profile,
    )


@talents_router.put("/me/achievement-link/visibility", response_model=AchievementLinkResponse)
async def update_achievement_link_visibility(
    body: AchievementLinkVisibilityUpdateRequest,
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
    settings: Settings = Depends(get_settings),
) -> AchievementLinkResponse:
    profile = await _get_own_profile(conn, user)
    token = await talent_profiles_repository.get_or_create_achievement_link_token(conn, profile.id)
    updated = await talent_profiles_repository.update_achievement_link_visibility(
        conn,
        profile.id,
        verified_profile_public=body.verified_profile_public,
        earnings_visible_on_public_profile=body.earnings_visible_on_public_profile,
    )
    return AchievementLinkResponse(
        url=f"{settings.next_public_app_url}/verified/{token}",
        token=token,
        verified_profile_public=updated.verified_profile_public,
        earnings_visible_on_public_profile=updated.earnings_visible_on_public_profile,
    )


@talents_router.post("/goals", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
async def create_goal(
    body: CreateGoalRequest,
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> GoalResponse:
    profile = await _get_own_profile(conn, user)
    active_count = await talent_goals_repository.count_active_goals(conn, profile.id)
    if active_count >= talent_goals_repository.MAX_ACTIVE_GOALS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "max_active_goals_exceeded",
                "message": "You already have 3 active goals. Abandon one before adding another.",
            },
        )
    goal = await talent_goals_repository.create_goal(
        conn, profile.id, goal_type=body.goal_type, target_value=body.target_value, target_date=body.target_date
    )
    return _to_goal_response(goal)


@talents_router.delete("/goals/{goal_id}", response_model=GoalResponse)
async def abandon_goal(
    goal_id: str,
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> GoalResponse:
    profile = await _get_own_profile(conn, user)
    goal = await talent_goals_repository.get_goal(conn, profile.id, goal_id)
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "goal_not_found", "message": "No goal with that id."})
    if goal.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "goal_already_completed", "message": "A completed goal cannot be abandoned."},
        )
    if goal.status == "abandoned":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "goal_already_abandoned", "message": "This goal was already abandoned."},
        )
    updated = await talent_goals_repository.abandon_goal(conn, goal_id)
    return _to_goal_response(updated)


@talents_router.get("/goals", response_model=list[GoalResponse])
async def list_goals(
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[GoalResponse]:
    profile = await _get_own_profile(conn, user)
    goals = await talent_goals_repository.list_goals(conn, profile.id)
    return [_to_goal_response(g) for g in goals]


@talents_router.get("/goals/suggestions", response_model=list[GoalSuggestion])
async def goal_suggestions(
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[GoalSuggestion]:
    """Stateless, rule-based (Build Prompt 5 deliverable 13) -- computed
    fresh on every request from the profile's current stats, not stored.
    Excludes goal_types the talent already has an active goal for, and
    returns at most 3."""
    profile = await _get_own_profile(conn, user)
    active_goals = await talent_goals_repository.list_goals(conn, profile.id)
    active_types = {g.goal_type for g in active_goals if g.status == "active"}

    candidates: list[GoalSuggestion] = []
    if profile.total_campaigns_completed < 5 and "campaigns_completed" not in active_types:
        candidates.append(GoalSuggestion(goal_type="campaigns_completed", label="Complete 5 campaigns", suggested_target_value=5))
    if profile.profile_completeness_score < 80 and "profile_completeness" not in active_types:
        candidates.append(GoalSuggestion(goal_type="profile_completeness", label="Reach 80% profile completeness", suggested_target_value=80))
    if profile.badges_earned_count == 0 and "badges_earned" not in active_types:
        candidates.append(GoalSuggestion(goal_type="badges_earned", label="Earn your first badge", suggested_target_value=1))
    categories_active = await talent_goals_repository.current_metric_values(conn, profile.id)
    if categories_active["categories_active"] < 2 and "categories_active" not in active_types:
        candidates.append(GoalSuggestion(goal_type="categories_active", label="Work in 2 categories", suggested_target_value=2))
    return candidates[:3]


@talents_router.get("/campaigns/available", response_model=list[CampaignSummaryResponse])
async def campaigns_available(
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[CampaignSummaryResponse]:
    profile = await _get_own_profile(conn, user)
    candidates = await campaigns_repository.list_available_for_rep(
        conn, talent_id=profile.id, categories=profile.categories, city=profile.city
    )

    # Values-filter exclusion is the enforcement point (Build Prompt 5
    # deliverable 3 / acceptance criterion) -- reused from
    # app.services.parent_service, not reimplemented. A campaign can
    # target multiple categories; it's excluded if ANY of its target
    # categories are blocked for this talent's parent, since the talent could
    # otherwise infer/participate in the blocked angle of the campaign.
    allowed: list[campaigns_repository.Campaign] = []
    for campaign in candidates:
        blocked = False
        for category in campaign.target_categories:
            if not await apply_values_filter(conn, talent_id=profile.id, campaign_category=category):
                blocked = True
                break
        if not blocked:
            allowed.append(campaign)

    return [
        CampaignSummaryResponse(
            id=c.id,
            title=c.title,
            product_name=c.product_name,
            campaign_goal=c.campaign_goal,
            deliverables_description=c.deliverables_description,
            target_categories=c.target_categories,
            target_cities=c.target_cities,
            payout_per_talent_cents=c.payout_per_talent_cents,
            start_date=c.start_date,
            end_date=c.end_date,
        )
        for c in allowed
    ]


@talents_router.get("/campaigns/active", response_model=list[CampaignParticipationResponse])
async def campaigns_active(
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[CampaignParticipationResponse]:
    """Build Prompt 8B deliverable 3: for milestone campaigns, each
    entry includes the milestone list (title/description/percentage/
    status/actionable) so a talent is never confused about what to work on
    next. campaigns_repository.get_by_id is looked up per row rather
    than batched -- list_active_for_rep is typically a handful of rows
    per talent, and this keeps the milestone-augmentation logic isolated
    to _to_participation_response_with_milestones rather than needing a
    second bulk-fetch path."""
    profile = await _get_own_profile(conn, user)
    rows = await campaign_talents_repository.list_active_for_rep(conn, profile.id)
    result: list[CampaignParticipationResponse] = []
    for r in rows:
        campaign = await campaigns_repository.get_by_id(conn, r.campaign_id)
        if campaign is None:
            result.append(_to_participation_response(r))
            continue
        result.append(await _to_participation_response_with_milestones(conn, r, campaign))
    return result


@talents_router.get("/campaigns/history", response_model=list[CampaignParticipationResponse])
async def campaigns_history(
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[CampaignParticipationResponse]:
    profile = await _get_own_profile(conn, user)
    rows = await campaign_talents_repository.list_history_for_rep(conn, profile.id)
    return [_to_participation_response(r) for r in rows]


@talents_router.get("/earnings", response_model=EarningsResponse)
async def earnings(
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> EarningsResponse:
    """Build Prompt 8B deliverable 10: pending/confirmed/paid totals
    stay flat-campaign-only (earnings_breakdown sums campaign_talents.
    payout_cents, which a milestone campaign never sets at the
    campaign_talents level -- see talent_profiles_repository.recompute_cached_totals's
    own note on why milestone earnings live on a separate column).
    milestone_campaigns adds the milestone-level detail the spec asks
    for ("which milestones are pending, which are paid, what amount
    each released") without changing what the flat totals above mean --
    the aggregate summary totals are deliberately left flat-only per the
    deliverable's own text ("Aggregate to the campaign level for the
    summary totals but expose milestone-level detail in the campaign
    earnings breakdown"); milestone_campaigns *is* that breakdown."""
    profile = await _get_own_profile(conn, user)
    breakdown = await campaign_talents_repository.earnings_breakdown(conn, profile.id)

    milestone_campaigns: list[MilestoneEarningsEntry] = []
    all_reps = await campaign_talents_repository.list_active_for_rep(conn, profile.id) + await campaign_talents_repository.list_history_for_rep(conn, profile.id)
    for cr in all_reps:
        campaign = await campaigns_repository.get_by_id(conn, cr.campaign_id)
        if campaign is None or campaign.payment_type != "milestone":
            continue
        milestone_defs = await campaign_milestones_repository.list_for_campaign(conn, campaign.id)
        progress = await campaign_milestones_repository.list_for_campaign_rep(conn, cr.id)
        milestone_campaigns.append(
            MilestoneEarningsEntry(
                campaign_id=campaign.id,
                campaign_title=campaign.title,
                payout_per_talent_cents=campaign.payout_per_talent_cents,
                milestones_completed_count=cr.milestones_completed_count,
                total_milestone_payout_cents=cr.total_milestone_payout_cents,
                milestones=_compute_milestone_participation(milestone_defs, progress),
            )
        )

    return EarningsResponse(
        pending_cents=breakdown["pending_cents"],
        confirmed_cents=breakdown["confirmed_cents"],
        paid_cents=breakdown["paid_cents"],
        lifetime_paid_cents=profile.total_earnings_cents,
        milestone_campaigns=milestone_campaigns,
    )


@talents_router.post("/stripe/onboarding", response_model=StripeOnboardingResponse)
async def stripe_onboarding(
    user: AuthenticatedUser = Depends(require_role("talent")),
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_connection),
) -> StripeOnboardingResponse:
    """Build Prompt 7 deliverable 3: creates a Stripe Connect Express
    account on first call, reuses the stored account id on every
    subsequent call (Stripe Account Links are single-use and
    short-lived, so "resuming" onboarding means requesting a fresh
    link for the same underlying account, not creating a new account).
    Onboarding completion is confirmed later via the account.updated
    webhook (app/routers/webhooks.py), never assumed from reaching
    return_url -- see docs/stripe-minors-policy.md for why Stripe's
    hosted onboarding, not this endpoint, is what handles the
    Representative/guardian requirement for talents under 18."""
    profile = await _get_own_profile(conn, user)

    account_id = profile.stripe_account_id
    if account_id is None:
        account_id = await stripe_service.create_connect_account(
            settings,
            email=user.email,
            metadata={"user_id": user.id, "talent_profile_id": profile.id},
        )
        await talent_profiles_repository.set_stripe_account_id(conn, profile.id, account_id)

    onboarding_url = f"{settings.next_public_app_url}/talent/onboarding/stripe"
    url = await stripe_service.create_connect_onboarding_link(
        settings,
        account_id=account_id,
        refresh_url=onboarding_url,
        return_url=onboarding_url,
    )
    return StripeOnboardingResponse(url=url)


@talents_router.get("/inbox", response_model=list[InboxMessageResponse])
async def inbox(
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[InboxMessageResponse]:
    """Build Prompt 11 deliverable 4: a talent's view of every recruiter
    who has contacted them. Not in Section 8's literal talent Routes list
    (added here per Prompt 11's own deliverable text, which calls for
    it explicitly) -- placed on talents_router alongside every other
    talent-facing GET, not on recruiters_router, since recruiter_contacts
    has no reply capability and this is read-only from the talent side."""
    profile = await _get_own_profile(conn, user)
    rows = await recruiter_contacts_repository.list_for_rep(conn, profile.id)
    return [InboxMessageResponse(id=r.id, message_text=r.message_text, read_at=r.read_at, messaged_at=r.messaged_at) for r in rows]


@talents_router.post("/inbox/{contact_id}/read", response_model=InboxMessageResponse)
async def mark_inbox_read(
    contact_id: str,
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> InboxMessageResponse:
    profile = await _get_own_profile(conn, user)
    existing = await recruiter_contacts_repository.get_by_id_and_rep(conn, contact_id, profile.id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "inbox_message_not_found", "message": "No message found for that id."},
        )
    updated = await recruiter_contacts_repository.mark_read(conn, contact_id, profile.id)
    result = updated or existing  # idempotent -- already-read is not an error
    return InboxMessageResponse(id=result.id, message_text=result.message_text, read_at=result.read_at, messaged_at=result.messaged_at)


# ══════════════════════════════════════════════════════════════════
# /campaigns/:id/* -- talent participation actions
# ══════════════════════════════════════════════════════════════════


async def _require_campaign(conn: asyncpg.Connection, campaign_id: str) -> campaigns_repository.Campaign:
    campaign = await campaigns_repository.get_by_id(conn, campaign_id)
    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "campaign_not_found", "message": "No campaign found for that id."},
        )
    return campaign


@campaigns_router.post("/{campaign_id}/apply", response_model=CampaignParticipationResponse, status_code=status.HTTP_201_CREATED)
async def apply_to_campaign(
    campaign_id: str,
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
    resend_client: ResendClient = Depends(resend_client_dependency),
) -> CampaignParticipationResponse:
    profile = await _get_own_profile(conn, user)
    await _require_campaign(conn, campaign_id)

    existing = await campaign_talents_repository.get_for_talent_and_campaign(conn, profile.id, campaign_id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "already_applied", "message": "A campaign_talents row already exists for this talent/campaign pair."},
        )

    parent_approval_status, parent_approval_deadline = await determine_parent_approval(conn, profile.id)

    created = await campaign_talents_repository.create_application(
        conn,
        talent_id=profile.id,
        campaign_id=campaign_id,
        parent_approval_status=parent_approval_status,
        parent_approval_deadline=parent_approval_deadline,
    )

    if parent_approval_status == "pending":
        # Pre-existing gap found while building Build Prompt 8's
        # brand-invite flow: parent_service.send_campaign_approval_request
        # already existed and was documented as "called by Prompt 5 when
        # a talent is invited/matched to a campaign," but nothing actually
        # called it -- a parent's approval queue would fill up with no
        # notification ever sent. Fixed here, and the same call is used
        # by the brand-invite endpoint (app/routers/brands.py) since
        # both paths create a 'pending' campaign_talents row identically.
        await send_campaign_approval_request(conn, resend_client, talent_id=profile.id, campaign_id=campaign_id)

    return _to_participation_response(created)


@campaigns_router.post("/{campaign_id}/accept", response_model=CampaignParticipationResponse)
async def accept_campaign(
    campaign_id: str,
    body: AcceptCampaignRequest = AcceptCampaignRequest(),
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
    settings: Settings = Depends(get_settings),
) -> CampaignParticipationResponse:
    profile = await _get_own_profile(conn, user)

    # Build Prompt 8H: FTC Disclosure Essentials module gate -- runs
    # before any other business logic in this handler (spec: "Add at
    # the start of the accept handler, before any other business
    # logic"). No-op with a warning log if FTC_MODULE_ID isn't
    # configured yet.
    await enforce_ftc_gate(conn, settings, profile.id)

    cr = await campaign_talents_repository.get_for_talent_and_campaign(conn, profile.id, campaign_id)
    if cr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "campaign_invitation_not_found", "message": "No invitation found for this campaign."},
        )

    # Parent approval gate -- distinct 403 code, not a generic error
    # (Section 8 / Build Prompt 5 acceptance criterion).
    if cr.parent_approval_status == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "awaiting_parent_approval", "message": "This campaign is awaiting parent approval."},
        )
    if cr.parent_approval_status == "blocked":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "parent_blocked", "message": "Your parent has blocked this campaign."},
        )

    campaign = await _require_campaign(conn, campaign_id)

    # Build Prompt 8B deliverable 2: campaign_talent_milestones rows are
    # created atomically with the accept itself -- "If any milestone row
    # fails to create, roll back the accept." A flat campaign has no
    # campaign_milestones rows, so initialize_for_accept is a no-op
    # ([]) for it; wrapping every accept in a transaction (not just
    # milestone ones) keeps this one code path uniform rather than
    # branching the whole function on payment_type.
    async with conn.transaction():
        updated = await campaign_talents_repository.accept(
            conn,
            profile.id,
            campaign_id,
            at=datetime.now(timezone.utc),
            ftc_disclosure_accepted=body.ftc_disclosure_accepted,
        )
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "illegal_transition", "message": f"Cannot accept from status '{cr.status}'."},
            )
        if campaign.payment_type == "milestone":
            await campaign_milestones_repository.initialize_for_accept(conn, updated.id, campaign_id)
    return _to_participation_response(updated)


@campaigns_router.post("/{campaign_id}/decline", response_model=CampaignParticipationResponse)
async def decline_campaign(
    campaign_id: str,
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> CampaignParticipationResponse:
    profile = await _get_own_profile(conn, user)
    cr = await campaign_talents_repository.get_for_talent_and_campaign(conn, profile.id, campaign_id)
    if cr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "campaign_invitation_not_found", "message": "No invitation found for this campaign."},
        )

    updated = await campaign_talents_repository.decline(conn, profile.id, campaign_id)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "illegal_transition", "message": f"Cannot decline from status '{cr.status}'."},
        )
    return _to_participation_response(updated)


@campaigns_router.post("/{campaign_id}/submit", response_model=CampaignParticipationResponse)
async def submit_campaign(
    campaign_id: str,
    body: SubmitCampaignRequest,
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> CampaignParticipationResponse:
    profile = await _get_own_profile(conn, user)
    cr = await campaign_talents_repository.get_for_talent_and_campaign(conn, profile.id, campaign_id)
    if cr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "campaign_invitation_not_found", "message": "No invitation found for this campaign."},
        )

    # FTC enforcement: this is the technical gate, not a UI hint
    # (Build Prompt 5 deliverable 8 / CLAUDE.md non-negotiable).
    if not cr.ftc_disclosure_accepted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ftc_disclosure_required",
                "message": "FTC sponsorship disclosure must be accepted before submitting.",
            },
        )

    updated = await campaign_talents_repository.submit(
        conn,
        profile.id,
        campaign_id,
        submission_text=body.submission_text,
        submission_file_urls=body.submission_file_urls,
        at=datetime.now(timezone.utc),
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "illegal_transition", "message": f"Cannot submit from status '{cr.status}'."},
        )
    return _to_participation_response(updated)


@campaigns_router.post(
    "/{campaign_id}/milestones/{milestone_id}/submit", response_model=MilestoneParticipationResponse
)
async def submit_milestone(
    campaign_id: str,
    milestone_id: str,
    body: SubmitMilestoneRequest,
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
    resend_client: ResendClient = Depends(resend_client_dependency),
) -> MilestoneParticipationResponse:
    """POST /campaigns/:campaign_id/milestones/:milestone_id/submit
    (Build Prompt 8B deliverable 4). Validates the campaign_rep exists
    and is 'accepted' (a milestone campaign's campaign_talents row stays
    'accepted' throughout -- see campaign_talents_repository.
    mark_confirmed_via_final_milestone's own note), and that the
    specific milestone is actionable for this talent right now (sequence
    gating -- the same rule GET /talents/campaigns/active surfaces via
    `actionable`, recomputed here server-side rather than trusted from
    a client that might be looking at a stale list). 'talent_submission'
    milestones rely on the milestone_auto_release job (every 30 min) to
    release payout after the 24h review window; 'brand_confirmation'
    milestones notify the brand immediately that a submission is
    waiting on them."""
    profile = await _get_own_profile(conn, user)
    cr = await campaign_talents_repository.get_for_talent_and_campaign(conn, profile.id, campaign_id)
    if cr is None or cr.status != "accepted":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "campaign_invitation_not_found", "message": "No active milestone campaign participation found."},
        )
    milestone = await campaign_milestones_repository.get_by_id_and_campaign(conn, milestone_id, campaign_id)
    if milestone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "milestone_not_found", "message": "No milestone found for that id on this campaign."},
        )

    milestone_defs = await campaign_milestones_repository.list_for_campaign(conn, campaign_id)
    progress = await campaign_milestones_repository.list_for_campaign_rep(conn, cr.id)
    actionable_by_id = {p.campaign_milestone_id: p.actionable for p in _compute_milestone_participation(milestone_defs, progress)}
    if not actionable_by_id.get(milestone_id, False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "milestone_not_actionable",
                "message": "This milestone isn't actionable yet -- prior sequence_required milestones must be confirmed first.",
            },
        )

    crm_id = next(p.id for p in progress if p.campaign_milestone_id == milestone_id)

    if milestone.threshold_count is not None:
        # Count-based milestone (Teenure_Build_Prompts.md 8B FRONTEND
        # ADDITIONS > UX guidance: "publish 3 pieces of content" should
        # show "2 of 3" progress). Each call is one increment, not a
        # full submission -- status only flips to 'submitted' (and the
        # usual brand_confirmation/talent_submission/auto-release flow
        # engages) once current_count reaches threshold_count.
        updated = await campaign_milestones_repository.submit_increment(
            conn,
            crm_id,
            threshold_count=milestone.threshold_count,
            submission_text=body.submission_text,
            submission_file_urls=body.submission_file_urls,
            at=datetime.now(timezone.utc),
        )
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "illegal_transition",
                    "message": "This milestone has already reached its threshold and been submitted.",
                },
            )
        reached_threshold = updated.current_count >= milestone.threshold_count
    else:
        updated = await campaign_milestones_repository.submit(
            conn,
            crm_id,
            submission_text=body.submission_text,
            submission_file_urls=body.submission_file_urls,
            at=datetime.now(timezone.utc),
        )
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "illegal_transition", "message": "This milestone has already been submitted."},
            )
        reached_threshold = True

    if reached_threshold and milestone.verification_method == "brand_confirmation":
        campaign = await campaigns_repository.get_by_id(conn, campaign_id)
        brand = await brand_profiles_repository.get_by_id(conn, campaign.brand_id) if campaign else None
        brand_user = await users_repository.get_user_by_id(conn, brand.user_id) if brand else None
        if brand_user is not None and campaign is not None:
            await send_milestone_submitted_email(
                brand_user.email, campaign_title=campaign.title, milestone_title=milestone.title, client=resend_client
            )
    # 'talent_submission' milestones need no immediate notification --
    # the 24h auto-release window is the brand's review period, and the
    # milestone_auto_release job (app/jobs/runner.py) is what acts on
    # it, not an email. Same for a threshold milestone that hasn't yet
    # reached its threshold -- there's nothing for the brand to review.

    refreshed = [_p for _p in _compute_milestone_participation(milestone_defs, [updated] + [p for p in progress if p.id != updated.id])]
    return next(p for p in refreshed if p.campaign_milestone_id == milestone_id)


@campaigns_router.post("/{campaign_id}/withdraw", response_model=CampaignParticipationResponse)
async def withdraw_campaign(
    campaign_id: str,
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> CampaignParticipationResponse:
    profile = await _get_own_profile(conn, user)
    cr = await campaign_talents_repository.get_for_talent_and_campaign(conn, profile.id, campaign_id)
    if cr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "campaign_invitation_not_found", "message": "No invitation found for this campaign."},
        )

    updated = await campaign_talents_repository.withdraw(conn, profile.id, campaign_id)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "illegal_transition",
                "message": f"Cannot withdraw from status '{cr.status}' -- already terminal.",
            },
        )
    return _to_participation_response(updated)


@campaigns_router.post("/{campaign_id}/submission-files", status_code=status.HTTP_201_CREATED)
async def upload_submission_file(
    campaign_id: str,
    file: UploadFile,
    user: AuthenticatedUser = Depends(require_role("talent")),
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_connection),
) -> dict:
    """Build Prompt 5 deliverable 11: Supabase Storage upload, scoped so
    only the talent and the relevant brand can read the file, and only
    accepted for campaigns the talent is actually invited to (a
    campaign_talents row must already exist -- any status is fine, since a
    talent may want to attach evidence before formally submitting)."""
    profile = await _get_own_profile(conn, user)
    cr = await campaign_talents_repository.get_for_talent_and_campaign(conn, profile.id, campaign_id)
    if cr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "campaign_invitation_not_found", "message": "You are not invited to this campaign."},
        )

    data = await file.read()
    storage = get_storage_client(settings)
    try:
        uploaded = await storage.upload(
            talent_id=profile.id,
            campaign_id=campaign_id,
            filename=file.filename or "upload",
            content_type=file.content_type or "application/octet-stream",
            data=data,
        )
    except SubmissionUploadError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": exc.code, "message": exc.message},
        ) from exc

    return {"url": uploaded.url, "storage_key": uploaded.storage_key}


@talents_router.post("/safety-reports", response_model=SafetyReportResponse, status_code=status.HTTP_201_CREATED)
async def file_safety_report(
    body: SafetyReportCreateRequest,
    user: AuthenticatedUser = Depends(require_role("talent")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> SafetyReportResponse:
    """One-tap report mechanism (Build Prompt 13 deliverable 7's
    upstream half): lets a talent flag a brand/campaign/interaction for
    admin review. Deliberately minimal -- a reason plus optional free
    text and campaign reference, no back-and-forth required to submit.
    Feeds admin.py's GET /admin/safety-reports queue, which the admin
    UI renders as its highest-priority lane."""
    profile = await _get_own_profile(conn, user)
    report = await admin_repository.create_safety_report(
        conn,
        reporter_talent_id=profile.id,
        campaign_id=body.campaign_id,
        reason=body.reason,
        description=body.description,
    )
    return SafetyReportResponse(
        id=report.id,
        reporter_talent_id=report.reporter_talent_id,
        reporter_display_name=report.reporter_display_name,
        campaign_id=report.campaign_id,
        reason=report.reason,
        description=report.description,
        status=report.status,
        created_at=report.created_at,
        resolved_at=report.resolved_at,
        resolution_note=report.resolution_note,
    )
