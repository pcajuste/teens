"""Rep portal backend (Build Prompt 5): own-profile CRUD, campaign
matching/participation state machine, earnings, and submission file
upload.

Two routers live in this module because Section 8 splits the URL
space: profile/listing endpoints hang off `/reps/...`, but campaign
*participation* actions are `/campaigns/:id/...` (no `/reps` prefix) --
`reps_router` and `campaigns_router` respectively, both included from
app/main.py.

Every route requires an active rep account
(app.core.security.require_role("rep")); a rep's own rep_profiles row
is looked up from the authenticated user's id on every request rather
than trusting a rep_id from the URL/body, so a rep can never read or
write another rep's campaign_reps rows (Build Prompt 5 acceptance
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
from app.repositories import (
    campaign_reps_repository,
    campaigns_repository,
    parent_records_repository,
    rep_profiles_repository,
    users_repository,
)
from app.schemas.reps import (
    AcceptCampaignRequest,
    CampaignParticipationResponse,
    CampaignSummaryResponse,
    EarningsResponse,
    RepProfilePreviewResponse,
    RepProfileResponse,
    RepProfileUpdateRequest,
    StripeOnboardingResponse,
    SubmitCampaignRequest,
)
from app.services import stripe_service
from app.services.parent_service import apply_values_filter
from app.services.storage_service import SubmissionUploadError, get_storage_client

reps_router = APIRouter(prefix="/reps", tags=["reps"])
campaigns_router = APIRouter(prefix="/campaigns", tags=["campaigns"])

# Scope decision (Build Prompt 5 deliverable 6): rep-facing "recruiters
# interested" signal is NOT built at MVP. Deliberate cut pending a
# product decision on count-only vs. identity-revealing display and
# whether a recruiter contact-credit is charged just to appear
# interested. Nothing in this router computes or exposes that signal.

INVITE_APPROVAL_WINDOW_HOURS = 48


def _require_rep_profile_row(row) -> rep_profiles_repository.RepProfile:
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "rep_profile_not_found", "message": "Complete onboarding via PUT /reps/me first."},
        )
    return row


async def _get_own_profile(
    conn: asyncpg.Connection, user: AuthenticatedUser
) -> rep_profiles_repository.RepProfile:
    profile = await rep_profiles_repository.get_by_user_id(conn, user.id)
    return _require_rep_profile_row(profile)


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


def _score(profile: rep_profiles_repository.RepProfile) -> int:
    return compute_profile_completeness_score(
        bio=profile.bio,
        categories=profile.categories,
        school_type=profile.school_type,
        instagram_handle=profile.instagram_handle,
        tiktok_handle=profile.tiktok_handle,
        total_campaigns_completed=profile.total_campaigns_completed,
    )


def _to_profile_response(p: rep_profiles_repository.RepProfile) -> RepProfileResponse:
    return RepProfileResponse(
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
    )


def _to_preview_response(p: rep_profiles_repository.RepProfile) -> RepProfilePreviewResponse:
    """Shares the exact field set a brand/recruiter view will also use
    (Build Prompt 5 deliverable 2) -- both this function and any future
    brand/recruiter serializer should read from the same RepProfile
    dataclass so the two field lists cannot drift independently."""
    return RepProfilePreviewResponse(
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
    )


def _to_participation_response(cr: campaign_reps_repository.CampaignRep) -> CampaignParticipationResponse:
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
    )


# ══════════════════════════════════════════════════════════════════
# /reps/*
# ══════════════════════════════════════════════════════════════════


@reps_router.get("/me", response_model=RepProfileResponse)
async def get_me(
    user: AuthenticatedUser = Depends(require_role("rep")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> RepProfileResponse:
    profile = await _get_own_profile(conn, user)
    return _to_profile_response(profile)


@reps_router.put("/me", response_model=RepProfileResponse)
async def put_me(
    body: RepProfileUpdateRequest,
    user: AuthenticatedUser = Depends(require_role("rep")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> RepProfileResponse:
    """Creates rep_profiles on first call (onboarding) or updates it on
    subsequent calls. On first creation only, also creates the linked
    parent_records row -- but only for reps whose
    public.users.parent_verified_at IS NOT NULL (the under-16
    consent-flow path); see docs/parent_records_creation_timing.md.
    Both inserts happen in one transaction so parent_records' FK to
    rep_profiles is never left in a half-created state."""
    existing = await rep_profiles_repository.get_by_user_id(conn, user.id)

    async with conn.transaction():
        if existing is None:
            db_user = await users_repository.get_user_by_id(conn, user.id)
            if db_user is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"code": "user_not_found", "message": "No user record found for this account."},
                )

            profile = await rep_profiles_repository.create_rep_profile(
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
                    rep_id=profile.id,
                    parent_email=db_user.parent_email,
                    portal_expires_at=_eighteenth_birthday_utc(db_user.date_of_birth),
                    campaign_approval_required=True,
                    digest_enabled=True,
                )
        else:
            profile = await rep_profiles_repository.update_rep_profile(
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
        if new_score != profile.profile_completeness_score:
            await rep_profiles_repository.update_profile_completeness_score(conn, profile.id, new_score)
            profile = await rep_profiles_repository.get_by_id(conn, profile.id)

    return _to_profile_response(profile)


@reps_router.get("/me/profile-preview", response_model=RepProfilePreviewResponse)
async def profile_preview(
    user: AuthenticatedUser = Depends(require_role("rep")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> RepProfilePreviewResponse:
    profile = await _get_own_profile(conn, user)
    return _to_preview_response(profile)


@reps_router.get("/campaigns/available", response_model=list[CampaignSummaryResponse])
async def campaigns_available(
    user: AuthenticatedUser = Depends(require_role("rep")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[CampaignSummaryResponse]:
    profile = await _get_own_profile(conn, user)
    candidates = await campaigns_repository.list_available_for_rep(
        conn, rep_id=profile.id, categories=profile.categories, city=profile.city
    )

    # Values-filter exclusion is the enforcement point (Build Prompt 5
    # deliverable 3 / acceptance criterion) -- reused from
    # app.services.parent_service, not reimplemented. A campaign can
    # target multiple categories; it's excluded if ANY of its target
    # categories are blocked for this rep's parent, since the rep could
    # otherwise infer/participate in the blocked angle of the campaign.
    allowed: list[campaigns_repository.Campaign] = []
    for campaign in candidates:
        blocked = False
        for category in campaign.target_categories:
            if not await apply_values_filter(conn, rep_id=profile.id, campaign_category=category):
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
            payout_per_rep_cents=c.payout_per_rep_cents,
            start_date=c.start_date,
            end_date=c.end_date,
        )
        for c in allowed
    ]


@reps_router.get("/campaigns/active", response_model=list[CampaignParticipationResponse])
async def campaigns_active(
    user: AuthenticatedUser = Depends(require_role("rep")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[CampaignParticipationResponse]:
    profile = await _get_own_profile(conn, user)
    rows = await campaign_reps_repository.list_active_for_rep(conn, profile.id)
    return [_to_participation_response(r) for r in rows]


@reps_router.get("/campaigns/history", response_model=list[CampaignParticipationResponse])
async def campaigns_history(
    user: AuthenticatedUser = Depends(require_role("rep")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[CampaignParticipationResponse]:
    profile = await _get_own_profile(conn, user)
    rows = await campaign_reps_repository.list_history_for_rep(conn, profile.id)
    return [_to_participation_response(r) for r in rows]


@reps_router.get("/earnings", response_model=EarningsResponse)
async def earnings(
    user: AuthenticatedUser = Depends(require_role("rep")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> EarningsResponse:
    profile = await _get_own_profile(conn, user)
    breakdown = await campaign_reps_repository.earnings_breakdown(conn, profile.id)
    return EarningsResponse(
        pending_cents=breakdown["pending_cents"],
        confirmed_cents=breakdown["confirmed_cents"],
        paid_cents=breakdown["paid_cents"],
        lifetime_paid_cents=profile.total_earnings_cents,
    )


@reps_router.post("/stripe/onboarding", response_model=StripeOnboardingResponse)
async def stripe_onboarding(
    user: AuthenticatedUser = Depends(require_role("rep")),
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
    Representative/guardian requirement for reps under 18."""
    profile = await _get_own_profile(conn, user)

    account_id = profile.stripe_account_id
    if account_id is None:
        account_id = await stripe_service.create_connect_account(
            settings,
            email=user.email,
            metadata={"user_id": user.id, "rep_profile_id": profile.id},
        )
        await rep_profiles_repository.set_stripe_account_id(conn, profile.id, account_id)

    onboarding_url = f"{settings.next_public_app_url}/rep/onboarding/stripe"
    url = await stripe_service.create_connect_onboarding_link(
        settings,
        account_id=account_id,
        refresh_url=onboarding_url,
        return_url=onboarding_url,
    )
    return StripeOnboardingResponse(url=url)


# ══════════════════════════════════════════════════════════════════
# /campaigns/:id/* -- rep participation actions
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
    user: AuthenticatedUser = Depends(require_role("rep")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> CampaignParticipationResponse:
    profile = await _get_own_profile(conn, user)
    await _require_campaign(conn, campaign_id)

    existing = await campaign_reps_repository.get_for_rep_and_campaign(conn, profile.id, campaign_id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "already_applied", "message": "A campaign_reps row already exists for this rep/campaign pair."},
        )

    parent = await parent_records_repository.get_parent_by_rep_id(conn, profile.id)
    now = datetime.now(timezone.utc)
    if parent is not None and parent.campaign_approval_required:
        parent_approval_status = "pending"
        parent_approval_deadline = now + timedelta(hours=INVITE_APPROVAL_WINDOW_HOURS)
    else:
        parent_approval_status = "not_required"
        parent_approval_deadline = None

    created = await campaign_reps_repository.create_application(
        conn,
        rep_id=profile.id,
        campaign_id=campaign_id,
        parent_approval_status=parent_approval_status,
        parent_approval_deadline=parent_approval_deadline,
    )
    return _to_participation_response(created)


@campaigns_router.post("/{campaign_id}/accept", response_model=CampaignParticipationResponse)
async def accept_campaign(
    campaign_id: str,
    body: AcceptCampaignRequest = AcceptCampaignRequest(),
    user: AuthenticatedUser = Depends(require_role("rep")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> CampaignParticipationResponse:
    profile = await _get_own_profile(conn, user)
    cr = await campaign_reps_repository.get_for_rep_and_campaign(conn, profile.id, campaign_id)
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

    updated = await campaign_reps_repository.accept(
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
    return _to_participation_response(updated)


@campaigns_router.post("/{campaign_id}/decline", response_model=CampaignParticipationResponse)
async def decline_campaign(
    campaign_id: str,
    user: AuthenticatedUser = Depends(require_role("rep")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> CampaignParticipationResponse:
    profile = await _get_own_profile(conn, user)
    cr = await campaign_reps_repository.get_for_rep_and_campaign(conn, profile.id, campaign_id)
    if cr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "campaign_invitation_not_found", "message": "No invitation found for this campaign."},
        )

    updated = await campaign_reps_repository.decline(conn, profile.id, campaign_id)
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
    user: AuthenticatedUser = Depends(require_role("rep")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> CampaignParticipationResponse:
    profile = await _get_own_profile(conn, user)
    cr = await campaign_reps_repository.get_for_rep_and_campaign(conn, profile.id, campaign_id)
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

    updated = await campaign_reps_repository.submit(
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


@campaigns_router.post("/{campaign_id}/withdraw", response_model=CampaignParticipationResponse)
async def withdraw_campaign(
    campaign_id: str,
    user: AuthenticatedUser = Depends(require_role("rep")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> CampaignParticipationResponse:
    profile = await _get_own_profile(conn, user)
    cr = await campaign_reps_repository.get_for_rep_and_campaign(conn, profile.id, campaign_id)
    if cr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "campaign_invitation_not_found", "message": "No invitation found for this campaign."},
        )

    updated = await campaign_reps_repository.withdraw(conn, profile.id, campaign_id)
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
    user: AuthenticatedUser = Depends(require_role("rep")),
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_connection),
) -> dict:
    """Build Prompt 5 deliverable 11: Supabase Storage upload, scoped so
    only the rep and the relevant brand can read the file, and only
    accepted for campaigns the rep is actually invited to (a
    campaign_reps row must already exist -- any status is fine, since a
    rep may want to attach evidence before formally submitting)."""
    profile = await _get_own_profile(conn, user)
    cr = await campaign_reps_repository.get_for_rep_and_campaign(conn, profile.id, campaign_id)
    if cr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "campaign_invitation_not_found", "message": "You are not invited to this campaign."},
        )

    data = await file.read()
    storage = get_storage_client(settings)
    try:
        uploaded = await storage.upload(
            rep_id=profile.id,
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
