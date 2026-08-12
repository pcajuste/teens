"""Brand portal backend (Build Prompt 8): profile CRUD, campaign CRUD +
server-side fee-split + activation/retry-payment/pause/cancel, rep
discovery/invite, submission review/confirm/revision/rate.

Every route requires an active brand account (require_role("brand"),
which also requires account_status='active') -- consistent with how
Prompt 5's tests already seed brand users directly as 'active' via SQL
(there is no admin-approval flow yet; Prompt 13 builds it). A brand's
own rep_profiles-equivalent row (brand_profiles) is looked up from the
authenticated user's id on every request, never trusted from the URL,
so a brand can never read or write another brand's campaigns (mirrors
Build Prompt 5's rep-ownership acceptance criterion).
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.core.crypto import decrypt_ein, encrypt_ein
from app.core.security import AuthenticatedUser, require_role
from app.db.pool import get_connection
from app.repositories import brand_profiles_repository, campaign_reps_repository, campaigns_repository, rep_profiles_repository
from app.schemas.brands import (
    ActivateCampaignResponse,
    BrandProfileResponse,
    BrandProfileUpdateRequest,
    CampaignBriefRequest,
    CampaignRepResponse,
    CampaignResponse,
    CancelCampaignResponse,
    InviteResultResponse,
    InviteRepsRequest,
    RateRequest,
    ReceiptResponse,
    RepBrowseCardResponse,
    RevisionRequest,
    SubmissionResponse,
)
from app.services import stripe_service
from app.services.campaign_service import compute_campaign_fee_split
from app.services.parent_service import determine_parent_approval, send_campaign_approval_request
from app.services.resend_client import ResendClient, resend_client_dependency

brands_router = APIRouter(prefix="/brands", tags=["brands"])


def _require_brand_profile_row(row) -> brand_profiles_repository.BrandProfile:
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "brand_profile_not_found", "message": "Complete onboarding via PUT /brands/me first."},
        )
    return row


async def _get_own_brand_profile(
    conn: asyncpg.Connection, user: AuthenticatedUser
) -> brand_profiles_repository.BrandProfile:
    profile = await brand_profiles_repository.get_by_user_id(conn, user.id)
    return _require_brand_profile_row(profile)


async def _require_owned_campaign(conn: asyncpg.Connection, campaign_id: str, brand_id: str) -> campaigns_repository.Campaign:
    campaign = await campaigns_repository.get_by_id_and_brand(conn, campaign_id, brand_id)
    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "campaign_not_found", "message": "No campaign found for that id."},
        )
    return campaign


def _to_brand_response(p: brand_profiles_repository.BrandProfile) -> BrandProfileResponse:
    return BrandProfileResponse(
        id=p.id,
        company_name=p.company_name,
        website=p.website,
        has_ein_on_file=p.ein is not None,
        industry=p.industry,
        target_categories=p.target_categories,
        verified=p.verified,
    )


def _to_campaign_response(c: campaigns_repository.Campaign) -> CampaignResponse:
    return CampaignResponse(
        id=c.id,
        title=c.title,
        status=c.status,
        product_name=c.product_name,
        campaign_goal=c.campaign_goal,
        key_messaging=c.key_messaging,
        prohibited_content=c.prohibited_content,
        deliverables_description=c.deliverables_description,
        target_categories=c.target_categories,
        target_cities=c.target_cities,
        max_reps=c.max_reps,
        reps_accepted_count=c.reps_accepted_count,
        budget_cents=c.budget_cents,
        platform_fee_cents=c.platform_fee_cents,
        rep_pool_cents=c.rep_pool_cents,
        payout_per_rep_cents=c.payout_per_rep_cents,
        start_date=c.start_date,
        end_date=c.end_date,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


def _to_campaign_rep_response(cr: campaign_reps_repository.CampaignRep) -> CampaignRepResponse:
    return CampaignRepResponse(
        id=cr.id,
        rep_id=cr.rep_id,
        status=cr.status,
        ftc_disclosure_accepted=cr.ftc_disclosure_accepted,
        parent_approval_status=cr.parent_approval_status,
        submission_text=cr.submission_text,
        submission_file_urls=cr.submission_file_urls,
        revision_note=cr.revision_note,
        brand_rating=cr.brand_rating,
        brand_rating_note=cr.brand_rating_note,
        payout_cents=cr.payout_cents,
        payout_status=cr.payout_status,
        invited_at=cr.invited_at,
        accepted_at=cr.accepted_at,
        submitted_at=cr.submitted_at,
        confirmed_at=cr.confirmed_at,
        paid_at=cr.paid_at,
    )


# ══════════════════════════════════════════════════════════════════
# /brands/me
# ══════════════════════════════════════════════════════════════════


@brands_router.get("/me", response_model=BrandProfileResponse)
async def get_me(
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> BrandProfileResponse:
    profile = await _get_own_brand_profile(conn, user)
    return _to_brand_response(profile)


@brands_router.put("/me", response_model=BrandProfileResponse)
async def put_me(
    body: BrandProfileUpdateRequest,
    user: AuthenticatedUser = Depends(require_role("brand")),
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_connection),
) -> BrandProfileResponse:
    """Creates brand_profiles on first call (onboarding) or updates it
    on subsequent calls, mirroring reps.py's PUT /reps/me. `ein` is
    encrypted here (app/core/crypto.py) before it ever reaches the
    repository/DB layer -- Section 7: "ein TEXT, -- stored encrypted in
    production", implemented now per Build Prompt 8 deliverable 1
    rather than deferred."""
    existing = await brand_profiles_repository.get_by_user_id(conn, user.id)
    ein_encrypted = encrypt_ein(settings, body.ein) if body.ein else None

    if existing is None:
        profile = await brand_profiles_repository.create_brand_profile(
            conn,
            user_id=user.id,
            company_name=body.company_name,
            website=body.website,
            ein_encrypted=ein_encrypted,
            industry=body.industry,
            target_categories=body.target_categories,
        )
    else:
        # An update that omits `ein` keeps whatever was already on file
        # rather than clearing it -- a brand re-saving their profile
        # without re-typing their EIN every time shouldn't erase it.
        profile = await brand_profiles_repository.update_brand_profile(
            conn,
            existing.id,
            company_name=body.company_name,
            website=body.website,
            ein_encrypted=ein_encrypted if body.ein else existing.ein,
            industry=body.industry,
            target_categories=body.target_categories,
        )
    return _to_brand_response(profile)


# ══════════════════════════════════════════════════════════════════
# /brands/campaigns
# ══════════════════════════════════════════════════════════════════


@brands_router.get("/campaigns", response_model=list[CampaignResponse])
async def list_campaigns(
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[CampaignResponse]:
    brand = await _get_own_brand_profile(conn, user)
    campaigns = await campaigns_repository.list_for_brand(conn, brand.id)
    return [_to_campaign_response(c) for c in campaigns]


@brands_router.post("/campaigns", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    body: CampaignBriefRequest,
    user: AuthenticatedUser = Depends(require_role("brand")),
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_connection),
) -> CampaignResponse:
    brand = await _get_own_brand_profile(conn, user)

    if body.end_date <= body.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_dates", "message": "end_date must be after start_date."},
        )

    platform_fee_cents, rep_pool_cents, payout_per_rep_cents = compute_campaign_fee_split(
        budget_cents=body.budget_cents, max_reps=body.max_reps, platform_fee_percent=settings.stripe_platform_fee_percent
    )

    campaign = await campaigns_repository.create_campaign(
        conn,
        brand_id=brand.id,
        title=body.title,
        product_name=body.product_name,
        campaign_goal=body.campaign_goal,
        key_messaging=body.key_messaging,
        prohibited_content=body.prohibited_content,
        deliverables_description=body.deliverables_description,
        target_categories=body.target_categories,
        target_cities=body.target_cities,
        max_reps=body.max_reps,
        budget_cents=body.budget_cents,
        platform_fee_cents=platform_fee_cents,
        rep_pool_cents=rep_pool_cents,
        payout_per_rep_cents=payout_per_rep_cents,
        start_date=body.start_date,
        end_date=body.end_date,
    )
    return _to_campaign_response(campaign)


@brands_router.get("/campaigns/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: str,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> CampaignResponse:
    brand = await _get_own_brand_profile(conn, user)
    campaign = await _require_owned_campaign(conn, campaign_id, brand.id)
    return _to_campaign_response(campaign)


@brands_router.put("/campaigns/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: str,
    body: CampaignBriefRequest,
    user: AuthenticatedUser = Depends(require_role("brand")),
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_connection),
) -> CampaignResponse:
    brand = await _get_own_brand_profile(conn, user)
    await _require_owned_campaign(conn, campaign_id, brand.id)  # 404 if not owned, regardless of status

    if body.end_date <= body.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_dates", "message": "end_date must be after start_date."},
        )

    platform_fee_cents, rep_pool_cents, payout_per_rep_cents = compute_campaign_fee_split(
        budget_cents=body.budget_cents, max_reps=body.max_reps, platform_fee_percent=settings.stripe_platform_fee_percent
    )

    updated = await campaigns_repository.update_campaign(
        conn,
        campaign_id,
        brand.id,
        title=body.title,
        product_name=body.product_name,
        campaign_goal=body.campaign_goal,
        key_messaging=body.key_messaging,
        prohibited_content=body.prohibited_content,
        deliverables_description=body.deliverables_description,
        target_categories=body.target_categories,
        target_cities=body.target_cities,
        max_reps=body.max_reps,
        budget_cents=body.budget_cents,
        platform_fee_cents=platform_fee_cents,
        rep_pool_cents=rep_pool_cents,
        payout_per_rep_cents=payout_per_rep_cents,
        start_date=body.start_date,
        end_date=body.end_date,
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "campaign_not_draft", "message": "Cannot edit a campaign that has left 'draft'."},
        )
    return _to_campaign_response(updated)


@brands_router.post("/campaigns/{campaign_id}/activate", response_model=ActivateCampaignResponse)
async def activate_campaign(
    campaign_id: str,
    user: AuthenticatedUser = Depends(require_role("brand")),
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_connection),
) -> ActivateCampaignResponse:
    brand = await _get_own_brand_profile(conn, user)
    campaign = await _require_owned_campaign(conn, campaign_id, brand.id)

    if campaign.status == "payment_failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "use_retry_payment",
                "message": "This campaign's payment already failed once -- call POST /activate is not valid here, use POST /retry-payment instead.",
            },
        )
    if campaign.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "illegal_transition", "message": f"Cannot activate from status '{campaign.status}'."},
        )
    if campaign.start_date <= date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "start_date_not_future", "message": "start_date must be in the future to activate."},
        )
    if campaign.max_reps <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_max_reps", "message": "max_reps must be greater than 0."},
        )

    payment_intent_id, client_secret = await stripe_service.create_payment_intent(
        settings, amount_cents=campaign.budget_cents, metadata={"campaign_id": campaign.id, "brand_id": brand.id}
    )
    updated = await campaigns_repository.set_pending_payment(conn, campaign_id, stripe_payment_intent_id=payment_intent_id)
    if updated is None:
        # Lost a race with another request -- status moved on between
        # the check above and this UPDATE.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "illegal_transition", "message": "Campaign status changed before activation completed."},
        )
    return ActivateCampaignResponse(id=updated.id, status=updated.status, stripe_payment_intent_client_secret=client_secret)


@brands_router.post("/campaigns/{campaign_id}/retry-payment", response_model=ActivateCampaignResponse)
async def retry_payment(
    campaign_id: str,
    user: AuthenticatedUser = Depends(require_role("brand")),
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_connection),
) -> ActivateCampaignResponse:
    brand = await _get_own_brand_profile(conn, user)
    campaign = await _require_owned_campaign(conn, campaign_id, brand.id)

    if campaign.status != "payment_failed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "illegal_transition", "message": f"Cannot retry payment from status '{campaign.status}'."},
        )

    payment_intent_id, client_secret = await stripe_service.create_payment_intent(
        settings, amount_cents=campaign.budget_cents, metadata={"campaign_id": campaign.id, "brand_id": brand.id}
    )
    assert payment_intent_id != campaign.stripe_payment_intent_id  # always a new PaymentIntent, never the failed one reused
    updated = await campaigns_repository.retry_payment(conn, campaign_id, stripe_payment_intent_id=payment_intent_id)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "illegal_transition", "message": "Campaign status changed before retry completed."},
        )
    return ActivateCampaignResponse(id=updated.id, status=updated.status, stripe_payment_intent_client_secret=client_secret)


@brands_router.post("/campaigns/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(
    campaign_id: str,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> CampaignResponse:
    brand = await _get_own_brand_profile(conn, user)
    await _require_owned_campaign(conn, campaign_id, brand.id)
    updated = await campaigns_repository.set_paused(conn, campaign_id)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "illegal_transition", "message": "Only an 'active' campaign can be paused."},
        )
    return _to_campaign_response(updated)


@brands_router.post("/campaigns/{campaign_id}/cancel", response_model=CancelCampaignResponse)
async def cancel_campaign(
    campaign_id: str,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> CancelCampaignResponse:
    """See docs/campaign-cancellation-refund-policy.md -- the refund
    *amount* for an already-charged campaign is an explicitly unresolved
    business decision, not implemented here. This performs the status
    transition and reports whether a refund is owed
    (refund_pending=True for 'active'/'paused', which per the
    campaign_status enum's own semantics always means a Stripe charge
    already succeeded); it does not call stripe_service.refund_campaign,
    which remains the Prompt 10 NotImplementedError stub it was in
    Prompt 7."""
    brand = await _get_own_brand_profile(conn, user)
    campaign = await _require_owned_campaign(conn, campaign_id, brand.id)
    refund_pending = campaign.status in campaigns_repository.STATUSES_WITH_CAPTURED_PAYMENT

    updated = await campaigns_repository.set_cancelled(conn, campaign_id)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "illegal_transition", "message": f"Cannot cancel from status '{campaign.status}'."},
        )
    return CancelCampaignResponse(id=updated.id, status=updated.status, refund_pending=refund_pending)


@brands_router.get("/campaigns/{campaign_id}/receipt", response_model=ReceiptResponse)
async def get_receipt(
    campaign_id: str,
    user: AuthenticatedUser = Depends(require_role("brand")),
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_connection),
) -> ReceiptResponse:
    """Build Prompt 8 deliverable 10. No route path is given in Section
    8 for this -- it isn't in the documented Brand Routes list -- so
    this is placed under the campaign it bills, matching the shape of
    every other campaign-scoped route in this router. Returns
    receipt_url=None (not a 404) for a campaign with no successful
    charge yet, which is the honest, expected state before Prompt 10."""
    brand = await _get_own_brand_profile(conn, user)
    campaign = await _require_owned_campaign(conn, campaign_id, brand.id)
    if campaign.stripe_payment_intent_id is None:
        return ReceiptResponse(receipt_url=None)
    receipt_url = await stripe_service.get_payment_intent_receipt_url(
        settings, payment_intent_id=campaign.stripe_payment_intent_id
    )
    return ReceiptResponse(receipt_url=receipt_url)


# ══════════════════════════════════════════════════════════════════
# /brands/campaigns/:id/reps/*
# ══════════════════════════════════════════════════════════════════


@brands_router.get("/campaigns/{campaign_id}/reps", response_model=list[CampaignRepResponse])
async def list_campaign_reps(
    campaign_id: str,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[CampaignRepResponse]:
    brand = await _get_own_brand_profile(conn, user)
    await _require_owned_campaign(conn, campaign_id, brand.id)
    rows = await campaign_reps_repository.list_for_campaign(conn, campaign_id)
    return [_to_campaign_rep_response(r) for r in rows]


@brands_router.get("/campaigns/{campaign_id}/reps/browse", response_model=list[RepBrowseCardResponse])
async def browse_reps(
    campaign_id: str,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[RepBrowseCardResponse]:
    """No PII returned -- see rep_profiles_repository.RepBrowseCard's
    docstring for the exact field-set decision. Matches against this
    campaign's own target_categories/target_cities so a brand is
    browsing reps relevant to what they're actually running, not every
    opted-in rep on the platform."""
    brand = await _get_own_brand_profile(conn, user)
    campaign = await _require_owned_campaign(conn, campaign_id, brand.id)
    city = campaign.target_cities[0] if len(campaign.target_cities) == 1 else None
    cards = await rep_profiles_repository.browse_for_brand(conn, categories=campaign.target_categories, city=city)
    return [
        RepBrowseCardResponse(
            rep_id=c.rep_id,
            city=c.city,
            state=c.state,
            graduation_year=c.graduation_year,
            school_type=c.school_type,
            categories=c.categories,
            profile_completeness_score=c.profile_completeness_score,
            average_rating=c.average_rating,
            total_campaigns_completed=c.total_campaigns_completed,
        )
        for c in cards
    ]


@brands_router.post("/campaigns/{campaign_id}/reps/invite", response_model=list[InviteResultResponse])
async def invite_reps(
    campaign_id: str,
    body: InviteRepsRequest,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
    resend_client: ResendClient = Depends(resend_client_dependency),
) -> list[InviteResultResponse]:
    """Invites are processed one rep_id at a time so a bad id in a
    batch doesn't fail the whole request -- results report per-rep
    outcome instead. Capacity is enforced against a live COUNT of
    non-declined campaign_reps rows (campaign_reps_repository.count_non_declined_for_campaign),
    not the reps_accepted_count cache column, which nothing in this
    codebase currently keeps up to date (a pre-existing gap, flagged
    rather than silently worked around by also fixing that column
    here -- out of this prompt's stated deliverables)."""
    brand = await _get_own_brand_profile(conn, user)
    campaign = await _require_owned_campaign(conn, campaign_id, brand.id)

    results: list[InviteResultResponse] = []
    for rep_id in body.rep_ids:
        rep_profile = await rep_profiles_repository.get_by_id(conn, rep_id)
        if rep_profile is None:
            results.append(InviteResultResponse(rep_id=rep_id, campaign_rep_id=None, status="rep_not_found"))
            continue

        existing = await campaign_reps_repository.get_for_rep_and_campaign(conn, rep_id, campaign_id)
        if existing is not None:
            results.append(InviteResultResponse(rep_id=rep_id, campaign_rep_id=existing.id, status="already_invited"))
            continue

        current_count = await campaign_reps_repository.count_non_declined_for_campaign(conn, campaign_id)
        if current_count >= campaign.max_reps:
            results.append(InviteResultResponse(rep_id=rep_id, campaign_rep_id=None, status="campaign_full"))
            continue

        parent_approval_status, parent_approval_deadline = await determine_parent_approval(conn, rep_id)
        created = await campaign_reps_repository.create_invite(
            conn,
            campaign_id=campaign_id,
            rep_id=rep_id,
            parent_approval_status=parent_approval_status,
            parent_approval_deadline=parent_approval_deadline,
        )
        if parent_approval_status == "pending":
            await send_campaign_approval_request(conn, resend_client, rep_id=rep_id, campaign_id=campaign_id)
        results.append(InviteResultResponse(rep_id=rep_id, campaign_rep_id=created.id, status="invited"))

    return results


@brands_router.get("/campaigns/{campaign_id}/reps/{rep_id}/submission", response_model=SubmissionResponse)
async def get_submission(
    campaign_id: str,
    rep_id: str,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> SubmissionResponse:
    brand = await _get_own_brand_profile(conn, user)
    await _require_owned_campaign(conn, campaign_id, brand.id)
    cr = await campaign_reps_repository.get_by_rep_and_campaign_id(conn, rep_id, campaign_id)
    if cr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "campaign_rep_not_found", "message": "No campaign_reps row for that rep on this campaign."},
        )
    return SubmissionResponse(
        campaign_rep_id=cr.id,
        rep_id=cr.rep_id,
        status=cr.status,
        submission_text=cr.submission_text,
        submission_file_urls=cr.submission_file_urls,
        submitted_at=cr.submitted_at,
    )


@brands_router.post("/campaigns/{campaign_id}/reps/{rep_id}/confirm", response_model=CampaignRepResponse)
async def confirm_submission(
    campaign_id: str,
    rep_id: str,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> CampaignRepResponse:
    """Stubs the payout engine (Prompt 10 wires it -- Build Prompt 8
    deliverable 8): payout_cents is recorded now, server-computed from
    the campaign's own payout_per_rep_cents, but no Stripe transfer is
    initiated here (stripe_transfer_id / payout_status stay unset)."""
    brand = await _get_own_brand_profile(conn, user)
    campaign = await _require_owned_campaign(conn, campaign_id, brand.id)
    cr = await campaign_reps_repository.get_by_rep_and_campaign_id(conn, rep_id, campaign_id)
    if cr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "campaign_rep_not_found", "message": "No campaign_reps row for that rep on this campaign."},
        )

    payout_cents = campaign.payout_per_rep_cents or 0
    updated = await campaign_reps_repository.confirm(
        conn, cr.id, campaign_id, payout_cents=payout_cents, at=datetime.now(timezone.utc)
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "illegal_transition", "message": f"Cannot confirm from status '{cr.status}'."},
        )
    return _to_campaign_rep_response(updated)


@brands_router.post("/campaigns/{campaign_id}/reps/{rep_id}/revision", response_model=CampaignRepResponse)
async def request_revision(
    campaign_id: str,
    rep_id: str,
    body: RevisionRequest,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> CampaignRepResponse:
    brand = await _get_own_brand_profile(conn, user)
    await _require_owned_campaign(conn, campaign_id, brand.id)
    cr = await campaign_reps_repository.get_by_rep_and_campaign_id(conn, rep_id, campaign_id)
    if cr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "campaign_rep_not_found", "message": "No campaign_reps row for that rep on this campaign."},
        )
    updated = await campaign_reps_repository.request_revision(conn, cr.id, campaign_id, note=body.note)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "illegal_transition", "message": f"Cannot request revision from status '{cr.status}'."},
        )
    return _to_campaign_rep_response(updated)


@brands_router.post("/campaigns/{campaign_id}/reps/{rep_id}/rate", response_model=CampaignRepResponse)
async def rate_rep(
    campaign_id: str,
    rep_id: str,
    body: RateRequest,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> CampaignRepResponse:
    brand = await _get_own_brand_profile(conn, user)
    await _require_owned_campaign(conn, campaign_id, brand.id)
    cr = await campaign_reps_repository.get_by_rep_and_campaign_id(conn, rep_id, campaign_id)
    if cr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "campaign_rep_not_found", "message": "No campaign_reps row for that rep on this campaign."},
        )
    updated = await campaign_reps_repository.rate(
        conn, cr.id, campaign_id, brand_rating=body.brand_rating, brand_rating_note=body.brand_rating_note
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "illegal_transition",
                "message": "Rating requires status 'confirmed' or 'paid', and can only be set once.",
            },
        )
    return _to_campaign_rep_response(updated)
