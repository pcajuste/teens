"""Admin Portal backend (Build Prompt 13): approval queues, campaign
oversight, stuck-payment management, analytics, outlier-rating
detection, parent-suspension reversal, and the safety report queue.

Internal-only. Every route requires require_role("admin") -- the same
dependency-factory pattern every other portal router uses (auth.py's
signup flow issues admin accounts out-of-band, same as any other role;
there is nothing admin-specific about app/core/security.py, by design
-- see that module's Role literal, which already includes "admin").
require_role (not require_role_any_status) throughout: an admin
account itself is provisioned pre-activated, there is no "pending
admin" onboarding gap the way there is for brands/recruiters.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.config import Settings, get_settings
from app.core.security import AuthenticatedUser, require_role
from app.db.pool import get_connection
from app.repositories import admin_repository, campaign_reps_repository, campaigns_repository, rep_profiles_repository, users_repository
from app.schemas.admin import (
    AccountType,
    ApprovalActionResponse,
    AdminCampaignResponse,
    CampaignsByStatusCategoryResponse,
    ConsentStatusEntry,
    FlagCampaignRequest,
    OutlierBrandResponse,
    ParentSuspendedRepResponse,
    QueueEntryResponse,
    RejectRequest,
    ReleasePayoutResponse,
    RepsByCityCategoryResponse,
    ResolveCampaignRequest,
    ResolveSafetyReportRequest,
    ReverseSuspensionResponse,
    RevenuePeriodResponse,
    SafetyReportResponse,
    StuckPaymentResponse,
)
from app.services import payout_service
from app.services.email_service import send_account_approved_email, send_account_rejected_email
from app.services.resend_client import ResendClient
from app.services.resend_client import resend_client_dependency as _resend_client_dependency
from app.services.supabase_auth_client import get_supabase_auth_client

admin_router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_role("admin"))])


def _queue_to_response(entries: list[admin_repository.QueueEntry]) -> list[QueueEntryResponse]:
    return [
        QueueEntryResponse(
            user_id=e.user_id,
            email=e.email,
            role=e.role,
            account_status=e.account_status,
            pending_reason=e.pending_reason,
            display_name=e.display_name,
            created_at=e.created_at,
        )
        for e in entries
    ]


# ══════════════════════════════════════════════════════════════════
# Deliverable 1: approval queues
# ══════════════════════════════════════════════════════════════════


@admin_router.get("/queue/reps", response_model=list[QueueEntryResponse])
async def queue_reps(conn: asyncpg.Connection = Depends(get_connection)) -> list[QueueEntryResponse]:
    return _queue_to_response(await admin_repository.queue_reps(conn))


@admin_router.get("/queue/brands", response_model=list[QueueEntryResponse])
async def queue_brands(conn: asyncpg.Connection = Depends(get_connection)) -> list[QueueEntryResponse]:
    return _queue_to_response(await admin_repository.queue_brands(conn))


@admin_router.get("/queue/recruiters", response_model=list[QueueEntryResponse])
async def queue_recruiters(conn: asyncpg.Connection = Depends(get_connection)) -> list[QueueEntryResponse]:
    return _queue_to_response(await admin_repository.queue_recruiters(conn))


def _require_reviewable_type(account_type: AccountType) -> None:
    """Reps never sit in an admin-approval pending state (Section 5
    Phase 1 / Section 8: a rep goes 'active' either immediately at
    signup, at 16+, or the moment a parent completes double opt-in --
    never via admin review). POST /admin/approve|reject/rep is
    therefore intentionally unsupported rather than a silent no-op --
    a 400 makes the "reps don't go through this path" decision visible
    to any caller, instead of quietly accepting a request that can
    never do anything (queue_reps never returns a row that
    approve_account's WHERE account_status='pending' AND the rep
    branch could act on in a way that means anything -- see
    admin_repository.queue_reps's own docstring for the full
    reasoning)."""
    if account_type == "rep":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "reps_not_admin_reviewed",
                "message": "Rep accounts activate via parental consent, not admin approval -- there is nothing to approve or reject here.",
            },
        )


@admin_router.post("/approve/{account_type}/{user_id}", response_model=ApprovalActionResponse)
async def approve_account(
    account_type: AccountType,
    user_id: str,
    admin: AuthenticatedUser = Depends(require_role("admin")),
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_connection),
    resend_client: ResendClient = Depends(_resend_client_dependency),
) -> ApprovalActionResponse:
    """Approving a pending brand/recruiter flips account_status to
    'active' -- which is also the exact gate require_role checks, so
    this unblocks campaign creation (brand) / search+contact
    (recruiter) with no separate flag to flip anywhere else."""
    _require_reviewable_type(account_type)

    row = await admin_repository.approve_account(conn, user_id=user_id, admin_id=admin.id)
    if row is None or row["role"] != account_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found_or_not_pending", "message": f"No pending {account_type} account with that id."},
        )

    auth_client = get_supabase_auth_client(settings, conn)
    await auth_client.update_app_metadata(user_id, {"role": account_type, "account_status": "active"})
    await send_account_approved_email(row["email"], account_type=account_type, client=resend_client)

    return ApprovalActionResponse(user_id=str(row["id"]), account_status=row["account_status"])


@admin_router.post("/reject/{account_type}/{user_id}", response_model=ApprovalActionResponse)
async def reject_account(
    account_type: AccountType,
    user_id: str,
    body: RejectRequest,
    admin: AuthenticatedUser = Depends(require_role("admin")),
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_connection),
    resend_client: ResendClient = Depends(_resend_client_dependency),
) -> ApprovalActionResponse:
    """Reason is required (RejectRequest.reason has min_length=1) and is
    always emailed to the applicant (deliverable 1 / acceptance
    criterion)."""
    _require_reviewable_type(account_type)

    row = await admin_repository.reject_account(conn, user_id=user_id, admin_id=admin.id, reason=body.reason)
    if row is None or row["role"] != account_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found_or_not_pending", "message": f"No pending {account_type} account with that id."},
        )

    auth_client = get_supabase_auth_client(settings, conn)
    await auth_client.update_app_metadata(user_id, {"role": account_type, "account_status": "rejected"})
    await send_account_rejected_email(row["email"], account_type=account_type, reason=body.reason, client=resend_client)

    return ApprovalActionResponse(user_id=str(row["id"]), account_status=row["account_status"])


# ══════════════════════════════════════════════════════════════════
# Deliverable 2: campaign oversight
# ══════════════════════════════════════════════════════════════════


@admin_router.get("/campaigns", response_model=list[AdminCampaignResponse])
async def list_campaigns(
    campaign_status: str | None = Query(default=None, alias="status"),
    flagged_only: bool = Query(default=False),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[AdminCampaignResponse]:
    rows = await admin_repository.list_campaigns(conn, status_filter=campaign_status, flagged_only=flagged_only)
    return [AdminCampaignResponse(**asdict(r)) for r in rows]


@admin_router.post("/campaigns/{campaign_id}/flag", response_model=AdminCampaignResponse)
async def flag_campaign(
    campaign_id: str,
    body: FlagCampaignRequest,
    admin: AuthenticatedUser = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> AdminCampaignResponse:
    row = await admin_repository.flag_campaign(conn, campaign_id, admin_id=admin.id, reason=body.reason)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "campaign_not_found", "message": "No campaign with that id."})
    return AdminCampaignResponse(**asdict(row))


@admin_router.post("/campaigns/{campaign_id}/resolve", response_model=AdminCampaignResponse)
async def resolve_campaign(
    campaign_id: str,
    body: ResolveCampaignRequest,
    admin: AuthenticatedUser = Depends(require_role("admin")),
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_connection),
) -> AdminCampaignResponse:
    """Enumerated action set only (ResolveCampaignRequest.action is a
    Literal, not free text -- deliverable 2 / acceptance criterion).
    force_confirm/force_cancel_refund both still have to go through the
    same state-mutating repositories the brand-facing flow uses (never
    a raw UPDATE campaigns SET status here) so every other invariant
    those flows enforce -- FTC disclosure, payout math -- still holds;
    an admin override changes *who* triggers the transition, never
    what's required for it to be legal. force_confirm therefore only
    ever candidate-applies to campaign_reps rows already sitting in
    'submitted' (the same precondition campaign_reps_repository.confirm
    enforces for the brand path); rows in any other state are left
    untouched rather than silently skipped without a trace."""
    existing = await admin_repository.get_admin_campaign(conn, campaign_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "campaign_not_found", "message": "No campaign with that id."})

    if body.action == "force_cancel_refund":
        await campaigns_repository.set_cancelled(conn, campaign_id)
    else:  # force_confirm
        campaign = await campaigns_repository.get_by_id(conn, campaign_id)
        payout_cents = (campaign.payout_per_rep_cents if campaign else None) or 0
        for cr in await campaign_reps_repository.list_for_campaign(conn, campaign_id):
            if cr.status != "submitted" or not cr.ftc_disclosure_accepted:
                # Mirrors app/routers/brands.py's own confirm_submission
                # precondition, and CLAUDE.md's compliance posture ("no
                # submission endpoint or admin override can create a
                # 'submitted' campaign_reps row without
                # ftc_disclosure_accepted") -- an admin force-confirm
                # cannot manufacture a legal confirmation for a row that
                # never legally reached 'submitted' in the first place,
                # so rows outside that state are left untouched rather
                # than silently skipped without a trace.
                continue
            confirmed = await campaign_reps_repository.confirm(
                conn, cr.id, campaign_id, payout_cents=payout_cents, at=datetime.now(timezone.utc)
            )
            if confirmed is not None:
                await payout_service.release_payout(conn, settings, confirmed.id)

    updated = await admin_repository.mark_campaign_resolved(conn, campaign_id, admin_id=admin.id, action=body.action)
    return AdminCampaignResponse(**asdict(updated))


# ══════════════════════════════════════════════════════════════════
# Deliverable 3: payment management (stuck payments)
# ══════════════════════════════════════════════════════════════════


@admin_router.get("/payments/stuck", response_model=list[StuckPaymentResponse])
async def stuck_payments(conn: asyncpg.Connection = Depends(get_connection)) -> list[StuckPaymentResponse]:
    rows = await admin_repository.list_stuck_payments(conn)
    return [StuckPaymentResponse(**asdict(r)) for r in rows]


@admin_router.post("/payments/{transfer_id}/release", response_model=ReleasePayoutResponse)
async def release_payment(
    transfer_id: str,
    admin: AuthenticatedUser = Depends(require_role("admin")),
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_connection),
) -> ReleasePayoutResponse:
    row = await admin_repository.get_by_stripe_transfer_id(conn, transfer_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "transfer_not_found", "message": "No campaign_reps row with that Stripe transfer id."},
        )

    result = await payout_service.admin_release_payout(conn, settings, str(row["id"]), admin_id=admin.id)
    if result.outcome == "not_confirmed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "not_confirmed", "message": "This row isn't in a confirmed, payable state."})
    if result.outcome == "already_processed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "not_stuck", "message": "This transfer isn't currently processing or failed."})
    if result.outcome == "rep_not_onboarded":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "rep_not_onboarded", "message": "The rep has no completed Stripe Connect account."})

    return ReleasePayoutResponse(
        campaign_rep_id=result.campaign_rep.id,
        payout_status=result.campaign_rep.payout_status,
        admin_released=True,
    )


# ══════════════════════════════════════════════════════════════════
# Deliverable 4: analytics
# ══════════════════════════════════════════════════════════════════


@admin_router.get("/analytics/revenue", response_model=list[RevenuePeriodResponse])
async def analytics_revenue(conn: asyncpg.Connection = Depends(get_connection)) -> list[RevenuePeriodResponse]:
    rows = await admin_repository.revenue_by_stream_and_period(conn)
    return [RevenuePeriodResponse(**r) for r in rows]


@admin_router.get("/analytics/reps", response_model=RepsByCityCategoryResponse)
async def analytics_reps(conn: asyncpg.Connection = Depends(get_connection)) -> RepsByCityCategoryResponse:
    result = await admin_repository.reps_by_city_and_category(conn)
    return RepsByCityCategoryResponse(**result)


@admin_router.get("/analytics/campaigns", response_model=CampaignsByStatusCategoryResponse)
async def analytics_campaigns(conn: asyncpg.Connection = Depends(get_connection)) -> CampaignsByStatusCategoryResponse:
    result = await admin_repository.campaigns_by_status_and_category(conn)
    return CampaignsByStatusCategoryResponse(**result)


@admin_router.get("/analytics/consent-status", response_model=list[ConsentStatusEntry])
async def analytics_consent_status(conn: asyncpg.Connection = Depends(get_connection)) -> list[ConsentStatusEntry]:
    """Addition beyond Section 8 (deliverable 4), flagged as such:
    parental-consent funnel visibility."""
    rows = await admin_repository.consent_status_breakdown(conn)
    return [ConsentStatusEntry(**r) for r in rows]


# ══════════════════════════════════════════════════════════════════
# Deliverable 5: outlier-rating detection
# ══════════════════════════════════════════════════════════════════


@admin_router.get("/analytics/outlier-brands", response_model=list[OutlierBrandResponse])
async def outlier_brands(conn: asyncpg.Connection = Depends(get_connection)) -> list[OutlierBrandResponse]:
    rows = await admin_repository.flagged_outlier_brands(conn)
    return [OutlierBrandResponse(**asdict(r)) for r in rows]


# ══════════════════════════════════════════════════════════════════
# Deliverable 6: parent suspension queue
# ══════════════════════════════════════════════════════════════════


@admin_router.get("/parent-suspensions", response_model=list[ParentSuspendedRepResponse])
async def parent_suspensions(conn: asyncpg.Connection = Depends(get_connection)) -> list[ParentSuspendedRepResponse]:
    rows = await admin_repository.list_parent_suspended_reps(conn)
    return [ParentSuspendedRepResponse(**asdict(r)) for r in rows]


@admin_router.post("/parent-suspensions/{rep_id}/reverse", response_model=ReverseSuspensionResponse)
async def reverse_parent_suspension(
    rep_id: str,
    admin: AuthenticatedUser = Depends(require_role("admin")),
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_connection),
) -> ReverseSuspensionResponse:
    """Only reverses a *parent*-initiated suspension (parent_records.
    suspended_by_parent_at IS NOT NULL) -- separate from admin-initiated
    suspension per deliverable 6, mirroring app/routers/parent.py's
    unsuspend_account 403 in the opposite direction: a parent can never
    reverse an admin suspension, and this route can only ever reverse a
    parent one (admin_repository.reverse_parent_suspension's WHERE
    clause is the enforcement, not a convention)."""
    row = await admin_repository.reverse_parent_suspension(conn, rep_id, admin_id=admin.id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found_or_not_parent_suspended", "message": "No parent-suspended rep with that id."},
        )

    rep = await rep_profiles_repository.get_by_id(conn, rep_id)
    if rep is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "rep_not_found", "message": "Rep profile not found."})

    updated_user = await users_repository.set_account_status(conn, rep.user_id, "active")
    auth_client = get_supabase_auth_client(settings, conn)
    await auth_client.update_app_metadata(rep.user_id, {"role": "rep", "account_status": "active"})

    return ReverseSuspensionResponse(rep_id=rep_id, account_status=updated_user.account_status)


# ══════════════════════════════════════════════════════════════════
# Deliverable 7: safety report queue (highest-priority lane)
# ══════════════════════════════════════════════════════════════════


@admin_router.get("/safety-reports", response_model=list[SafetyReportResponse])
async def safety_reports(
    open_only: bool = Query(default=True),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[SafetyReportResponse]:
    rows = await admin_repository.list_safety_reports(conn, open_only=open_only)
    return [SafetyReportResponse(**asdict(r)) for r in rows]


@admin_router.post("/safety-reports/{report_id}/resolve", response_model=SafetyReportResponse)
async def resolve_safety_report(
    report_id: str,
    body: ResolveSafetyReportRequest,
    admin: AuthenticatedUser = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> SafetyReportResponse:
    updated = await admin_repository.resolve_safety_report(
        conn, report_id, admin_id=admin.id, status=body.status, resolution_note=body.resolution_note
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "not_found_or_not_open", "message": "No open safety report with that id."})
    return SafetyReportResponse(**asdict(updated))
