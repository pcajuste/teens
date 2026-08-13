"""Parent portal: dashboard, campaign approval queue, values-filter and
digest settings, and account controls. Every route requires a valid,
not-yet-expired parent session (app.core.security.get_active_parent_session).
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.age import compute_age
from app.core.config import Settings, get_settings
from app.core.security import ParentSession, get_active_parent_session
from app.db.pool import get_connection
from app.repositories import campaign_talents_repository, challenges_repository, learning_modules_repository, parent_records_repository
from app.repositories.users_repository import set_account_status
from app.schemas.parent import (
    AccountControlResponse,
    ApprovalRequiredRequest,
    CampaignDecisionResponse,
    ChallengeActivityResponse,
    DashboardResponse,
    DigestPreviewResponse,
    DigestSettingRequest,
    ModuleActivityResponse,
    PendingCampaignResponse,
    SettingsResponse,
    ValuesFiltersRequest,
)
from app.services.email_service import send_account_suspended_email
from app.services.parent_service import (
    apply_values_filter,  # noqa: F401  -- re-exported for Prompt 5's campaign matching
    record_campaign_approval,
    record_campaign_block,
)
from app.services.resend_client import ResendClient
from app.services.resend_client import resend_client_dependency as _resend_client_dependency
from app.services.supabase_auth_client import get_supabase_auth_client

router = APIRouter(prefix="/parent", tags=["parent"])

MIN_AGE_FOR_PARENT_TOGGLE = 16


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    session: ParentSession = Depends(get_active_parent_session),
    conn: asyncpg.Connection = Depends(get_connection),
) -> DashboardResponse:
    talent = await parent_records_repository.get_talent_context(conn, session.talent_id)
    if talent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "talent_not_found", "message": "Linked talent profile not found."})
    activity = await challenges_repository.parent_dashboard_activity(conn, session.talent_id)
    settings = get_settings()
    module_activity = await learning_modules_repository.parent_dashboard_activity(
        conn, session.talent_id, ftc_module_id=settings.ftc_module_id or None
    )
    return DashboardResponse(
        display_name=talent.display_name,
        school_name=talent.school_name,
        graduation_year=talent.graduation_year,
        categories=talent.categories,
        profile_completeness_score=talent.profile_completeness_score,
        total_earnings_cents=talent.total_earnings_cents,
        total_campaigns_completed=talent.total_campaigns_completed,
        challenge_activity=ChallengeActivityResponse(**activity),
        module_activity=ModuleActivityResponse(**module_activity),
    )


@router.get("/campaigns/pending", response_model=list[PendingCampaignResponse])
async def pending_campaigns(
    session: ParentSession = Depends(get_active_parent_session),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[PendingCampaignResponse]:
    briefs = await campaign_talents_repository.list_pending_for_rep(conn, session.talent_id)
    return [
        PendingCampaignResponse(
            campaign_id=b.campaign_id,
            brand_name=b.brand_name,
            title=b.title,
            product_name=b.product_name,
            campaign_goal=b.campaign_goal,
            key_messaging=b.key_messaging,
            prohibited_content=b.prohibited_content,
            deliverables_description=b.deliverables_description,
            payout_per_talent_cents=b.payout_per_talent_cents,
            start_date=b.start_date,
            end_date=b.end_date,
            requires_in_person_activation=b.requires_in_person_activation,
            parent_approval_deadline=b.parent_approval_deadline,
        )
        for b in briefs
    ]


@router.post("/campaigns/{campaign_id}/approve", response_model=CampaignDecisionResponse)
async def approve_campaign(
    campaign_id: str,
    session: ParentSession = Depends(get_active_parent_session),
    conn: asyncpg.Connection = Depends(get_connection),
) -> CampaignDecisionResponse:
    ok = await record_campaign_approval(conn, talent_id=session.talent_id, campaign_id=campaign_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "campaign_invitation_not_found", "message": "No pending invitation found for this campaign."},
        )
    return CampaignDecisionResponse(campaign_id=campaign_id, parent_approval_status="approved")


@router.post("/campaigns/{campaign_id}/block", response_model=CampaignDecisionResponse)
async def block_campaign(
    campaign_id: str,
    session: ParentSession = Depends(get_active_parent_session),
    conn: asyncpg.Connection = Depends(get_connection),
    resend_client: ResendClient = Depends(_resend_client_dependency),
) -> CampaignDecisionResponse:
    ok = await record_campaign_block(conn, resend_client, talent_id=session.talent_id, campaign_id=campaign_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "campaign_invitation_not_found", "message": "No invitation found for this campaign."},
        )
    return CampaignDecisionResponse(campaign_id=campaign_id, parent_approval_status="blocked")


@router.get("/settings", response_model=SettingsResponse)
async def get_settings_endpoint(
    session: ParentSession = Depends(get_active_parent_session),
    conn: asyncpg.Connection = Depends(get_connection),
) -> SettingsResponse:
    parent = await parent_records_repository.get_parent_by_id(conn, session.parent_id)
    if parent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "parent_record_not_found", "message": "Parent record not found."})
    return SettingsResponse(
        values_filters=parent.values_filters,
        campaign_approval_required=parent.campaign_approval_required,
        digest_enabled=parent.digest_enabled,
    )


@router.put("/settings/values-filters", response_model=SettingsResponse)
async def update_values_filters(
    body: ValuesFiltersRequest,
    session: ParentSession = Depends(get_active_parent_session),
    conn: asyncpg.Connection = Depends(get_connection),
) -> SettingsResponse:
    parent = await parent_records_repository.update_values_filters(conn, session.parent_id, body.values_filters)
    return SettingsResponse(
        values_filters=parent.values_filters,
        campaign_approval_required=parent.campaign_approval_required,
        digest_enabled=parent.digest_enabled,
    )


@router.put("/settings/approval-required", response_model=SettingsResponse)
async def update_approval_required(
    body: ApprovalRequiredRequest,
    session: ParentSession = Depends(get_active_parent_session),
    conn: asyncpg.Connection = Depends(get_connection),
) -> SettingsResponse:
    talent = await parent_records_repository.get_talent_context(conn, session.talent_id)
    if talent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "talent_not_found", "message": "Linked talent profile not found."})

    age = compute_age(talent.date_of_birth, today=date.today())
    # 18+ can't reach this route at all -- get_active_parent_session
    # already rejects the session once portal_expires_at has passed.
    if age < MIN_AGE_FOR_PARENT_TOGGLE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "approval_required_locked_under_16",
                "message": "Campaign approval is always required for talents under 16 and can't be turned off.",
            },
        )

    parent = await parent_records_repository.update_campaign_approval_required(conn, session.parent_id, body.enabled)
    return SettingsResponse(
        values_filters=parent.values_filters,
        campaign_approval_required=parent.campaign_approval_required,
        digest_enabled=parent.digest_enabled,
    )


@router.put("/settings/digest", response_model=SettingsResponse)
async def update_digest_setting(
    body: DigestSettingRequest,
    session: ParentSession = Depends(get_active_parent_session),
    conn: asyncpg.Connection = Depends(get_connection),
) -> SettingsResponse:
    parent = await parent_records_repository.update_digest_enabled(conn, session.parent_id, body.enabled)
    return SettingsResponse(
        values_filters=parent.values_filters,
        campaign_approval_required=parent.campaign_approval_required,
        digest_enabled=parent.digest_enabled,
    )


@router.get("/digest/preview", response_model=DigestPreviewResponse)
async def digest_preview(
    session: ParentSession = Depends(get_active_parent_session),
    conn: asyncpg.Connection = Depends(get_connection),
) -> DigestPreviewResponse:
    parent = await parent_records_repository.get_parent_by_id(conn, session.parent_id)
    talent = await parent_records_repository.get_talent_context(conn, session.talent_id)
    if parent is None or talent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "not_found", "message": "Parent or talent record not found."})

    since = parent.digest_last_sent_at or datetime(1970, 1, 1, tzinfo=timezone.utc)
    stats = await campaign_talents_repository.monthly_digest_stats(conn, session.talent_id, since=since)
    previous_score = parent.last_digest_profile_completeness_score
    change = None if previous_score is None else talent.profile_completeness_score - previous_score

    return DigestPreviewResponse(
        campaigns_completed_this_month=stats["campaigns_completed_this_month"],
        earnings_this_month_cents=stats["earnings_this_month_cents"],
        lifetime_earnings_cents=talent.total_earnings_cents,
        profile_completeness_score=talent.profile_completeness_score,
        profile_completeness_change=change,
        active_categories=stats["active_categories"],
    )


@router.post("/account/suspend", response_model=AccountControlResponse)
async def suspend_account(
    session: ParentSession = Depends(get_active_parent_session),
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_connection),
    resend_client: ResendClient = Depends(_resend_client_dependency),
) -> AccountControlResponse:
    talent = await parent_records_repository.get_talent_context(conn, session.talent_id)
    if talent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "talent_not_found", "message": "Linked talent profile not found."})

    now = datetime.now(timezone.utc)
    updated = await set_account_status(conn, talent.talent_user_id, "suspended")
    await parent_records_repository.set_suspended_by_parent(conn, session.parent_id, at=now)

    auth_client = get_supabase_auth_client(settings, conn)
    await auth_client.update_app_metadata(talent.talent_user_id, {"role": "talent", "account_status": "suspended"})

    await send_account_suspended_email(talent.talent_email, resend_client)
    # Admin alerting is a Prompt 13 (Admin Portal) concern -- the admin
    # queue can query account_status='suspended' AND
    # parent_records.suspended_by_parent_at IS NOT NULL until then.

    return AccountControlResponse(account_status=updated.account_status)


@router.post("/account/unsuspend", response_model=AccountControlResponse)
async def unsuspend_account(
    session: ParentSession = Depends(get_active_parent_session),
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_connection),
) -> AccountControlResponse:
    parent = await parent_records_repository.get_parent_by_id(conn, session.parent_id)
    talent = await parent_records_repository.get_talent_context(conn, session.talent_id)
    if parent is None or talent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "not_found", "message": "Parent or talent record not found."})

    if talent.talent_account_status != "suspended":
        return AccountControlResponse(account_status=talent.talent_account_status)

    if parent.suspended_by_parent_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "admin_suspension_not_reversible_by_parent",
                "message": "This account was suspended by an admin and can only be reinstated by an admin.",
            },
        )

    updated = await set_account_status(conn, talent.talent_user_id, "active")
    await parent_records_repository.set_suspended_by_parent(conn, session.parent_id, at=None)

    auth_client = get_supabase_auth_client(settings, conn)
    await auth_client.update_app_metadata(talent.talent_user_id, {"role": "talent", "account_status": "active"})

    return AccountControlResponse(account_status=updated.account_status)
