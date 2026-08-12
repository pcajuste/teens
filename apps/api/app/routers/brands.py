"""Brand portal backend (Build Prompt 8): profile CRUD, campaign CRUD +
server-side fee-split + activation/retry-payment/pause/cancel, rep
discovery/invite, submission review/confirm/revision/rate.

Every route requires account_status='active' (require_role("brand")) --
consistent with how Prompt 5's tests already seed brand users directly
as 'active' via SQL (there is no admin-approval flow yet; Prompt 13
builds it) -- EXCEPT GET/PUT /brands/me, which uses
require_role_any_status: a brand must be able to submit their profile
for review while still 'pending', since submitting it is what an admin
would review. Discovered as a real gap while building the frontend for
this prompt -- a freshly signed-up brand (always 'pending' at signup)
could not reach PUT /brands/me at all under the original require_role
everywhere, meaning no brand account could ever progress past signup.
A brand's own rep_profiles-equivalent row (brand_profiles) is looked up
from the authenticated user's id on every request, never trusted from
the URL, so a brand can never read or write another brand's campaigns
(mirrors Build Prompt 5's rep-ownership acceptance criterion).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.core.crypto import decrypt_ein, encrypt_ein
from app.core.security import AuthenticatedUser, require_role, require_role_any_status
from app.db.pool import get_connection
from app.repositories import (
    admin_repository,
    brand_profiles_repository,
    campaign_milestones_repository,
    campaign_reps_repository,
    campaigns_repository,
    rep_profiles_repository,
    users_repository,
)
from app.services import exclusivity_service
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
    MilestoneDisputeRequest,
    MilestoneProgressResponse,
    RateRequest,
    ReceiptResponse,
    RepBrowseCardResponse,
    RevisionRequest,
    SubmissionResponse,
)
from app.services import payout_service, stripe_service
from app.services.campaign_service import MilestoneValidationError, compute_campaign_fee_split, get_or_create_stripe_customer_id, validate_milestones
from app.services.email_service import send_milestone_disputed_email
from app.services.parent_service import determine_parent_approval, send_campaign_approval_request
from app.services.resend_client import ResendClient, resend_client_dependency

MILESTONE_DISPUTE_WINDOW_HOURS = 24

brands_router = APIRouter(prefix="/brands", tags=["brands"])

EXCLUSIVITY_CONFLICT_DETAIL = {
    "code": "exclusivity_conflict",
    "message": (
        "Another brand holds exclusivity in this category and market during "
        "your requested campaign period. Consider a different category, city, "
        "or time window."
    ),
}


def _date_to_datetime(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


async def _check_campaign_exclusivity_conflict(
    conn: asyncpg.Connection,
    *,
    target_categories: list[str],
    target_cities: list[str],
    start_date: date,
    end_date: date | None,
    exclude_brand_id: str,
) -> None:
    """Build Prompt 8C deliverable 5: runs
    exclusivity_service.check_exclusivity_conflict for every
    (category, city) pair a campaign targets -- the campaigns schema
    stores target_categories/target_cities as arrays (Section 7), while
    an exclusivity agreement is scoped to exactly one category and at
    most one city, so a campaign that targets several categories/cities
    conflicts if ANY one of those combinations is exclusively held.
    Cities default to [None] (checked against platform-wide-or-null-city
    agreements only) when the campaign doesn't target any specific
    city. Raises the exact 409 the spec text asks for on first
    conflict found."""
    starts_at = _date_to_datetime(start_date)
    ends_at = _date_to_datetime(end_date) if end_date is not None else starts_at + timedelta(days=30)
    cities: list[str | None] = list(target_cities) if target_cities else [None]
    for category in target_categories:
        for city in cities:
            conflict_brand_id = await exclusivity_service.check_exclusivity_conflict(
                conn,
                category=category,
                city=city,
                starts_at=starts_at,
                ends_at=ends_at,
                exclude_brand_id=exclude_brand_id,
            )
            if conflict_brand_id is not None:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=EXCLUSIVITY_CONFLICT_DETAIL)


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
        payment_type=c.payment_type,
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
        milestones_completed_count=cr.milestones_completed_count,
        total_milestone_payout_cents=cr.total_milestone_payout_cents,
    )


# ══════════════════════════════════════════════════════════════════
# /brands/me
# ══════════════════════════════════════════════════════════════════


@brands_router.get("/me", response_model=BrandProfileResponse)
async def get_me(
    user: AuthenticatedUser = Depends(require_role_any_status("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> BrandProfileResponse:
    profile = await _get_own_brand_profile(conn, user)
    return _to_brand_response(profile)


@brands_router.put("/me", response_model=BrandProfileResponse)
async def put_me(
    body: BrandProfileUpdateRequest,
    user: AuthenticatedUser = Depends(require_role_any_status("brand")),
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_connection),
) -> BrandProfileResponse:
    """Creates brand_profiles on first call (onboarding) or updates it
    on subsequent calls, mirroring reps.py's PUT /reps/me. Uses
    require_role_any_status, not require_role: a brand must be able to
    submit their profile for review while still account_status='pending'
    -- that submission is what admin review (Prompt 13) actually
    reviews. Every other route in this file still requires 'active'.
    `ein` is
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

    # Build Prompt 8B deliverable 1: milestones array required (and
    # validated) when payment_type='milestone'; must be absent/empty
    # for 'flat'. Validation happens before any DB write so a bad
    # milestone list never even opens the transaction below.
    if body.payment_type == "milestone":
        if not body.milestones:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "milestones_required", "message": "milestones is required when payment_type='milestone'."},
            )
        try:
            validate_milestones([m.model_dump() for m in body.milestones])
        except MilestoneValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "invalid_milestones", "message": str(exc)}
            ) from exc
    elif body.milestones:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "milestones_not_allowed", "message": "milestones must be absent/empty for payment_type='flat'."},
        )

    platform_fee_cents, rep_pool_cents, payout_per_rep_cents = compute_campaign_fee_split(
        budget_cents=body.budget_cents, max_reps=body.max_reps, platform_fee_percent=settings.stripe_platform_fee_percent
    )

    # Build Prompt 8C deliverable 5: the exclusivity conflict check must
    # run in the same transaction as the campaign INSERT, and if the
    # check passes but the INSERT fails due to a concurrent exclusivity
    # purchase, the whole check+INSERT is retried once before giving up
    # (Section 8C: "If the conflict check passes but the INSERT fails
    # due to a concurrent exclusivity purchase: the INSERT must be
    # retried once before returning an error"). Also atomic with
    # campaign_milestones creation (Build Prompt 8B deliverable 1).
    last_exc: Exception | None = None
    campaign = None
    for attempt in range(2):
        try:
            async with conn.transaction():
                await _check_campaign_exclusivity_conflict(
                    conn,
                    target_categories=body.target_categories,
                    target_cities=body.target_cities,
                    start_date=body.start_date,
                    end_date=body.end_date,
                    exclude_brand_id=brand.id,
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
                    payment_type=body.payment_type,
                )
                if body.payment_type == "milestone":
                    await campaign_milestones_repository.create_milestones(
                        conn, campaign.id, [m.model_dump() for m in body.milestones]
                    )
            break
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001 -- genuinely any DB error triggers the documented single retry
            last_exc = exc
            campaign = None
            continue
    if campaign is None:
        raise last_exc
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
    existing = await _require_owned_campaign(conn, campaign_id, brand.id)  # 404 if not owned, regardless of status

    if body.end_date <= body.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_dates", "message": "end_date must be after start_date."},
        )

    # Build Prompt 8B: "payment_type is immutable after campaign
    # activation." update_campaign itself is already only legal from
    # status='draft' (a campaign that's left draft has, by definition,
    # been activated at least once) -- this check surfaces the specific
    # error the spec asks for rather than the generic "campaign_not_draft"
    # 409 a would-be payment_type change would otherwise get lumped
    # into. A no-op resend of the same payment_type is always fine.
    if body.payment_type != existing.payment_type and existing.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "payment_type_immutable",
                "message": "Payment type cannot be changed after campaign activation.",
            },
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

    # Build Prompt 8C deliverable 5: the conflict check also fires at
    # activation, not just creation -- a campaign might be created in
    # draft before any exclusivity agreement exists, then a competitor
    # buys exclusivity before this brand activates it.
    async with conn.transaction():
        await _check_campaign_exclusivity_conflict(
            conn,
            target_categories=campaign.target_categories,
            target_cities=campaign.target_cities,
            start_date=campaign.start_date,
            end_date=campaign.end_date,
            exclude_brand_id=brand.id,
        )

    customer_id = await get_or_create_stripe_customer_id(conn, settings, brand)
    payment_intent_id, client_secret = await stripe_service.create_payment_intent(
        settings,
        amount_cents=campaign.budget_cents,
        metadata={"campaign_id": campaign.id, "brand_id": brand.id},
        customer_id=customer_id,
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

    customer_id = await get_or_create_stripe_customer_id(conn, settings, brand)
    payment_intent_id, client_secret = await stripe_service.create_payment_intent(
        settings,
        amount_cents=campaign.budget_cents,
        metadata={"campaign_id": campaign.id, "brand_id": brand.id},
        customer_id=customer_id,
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
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_connection),
) -> CancelCampaignResponse:
    """See docs/campaign-cancellation-refund-policy.md, updated by Build
    Prompt 10 to resolve what was left an open question in Prompt 8:
    the *un-paid remainder* of budget_cents is refunded -- budget_cents
    minus whatever's already been transferred or is in flight to reps
    (payout_status IN ('processing','paid')), which also refunds the
    portion of the platform fee attributable to that unpaid remainder
    (nothing was delivered for it, so nothing should be kept for it).
    Money already transferred to a rep is never clawed back. This is
    Prompt 10's own proposed fallback ("partial refund for un-paid
    remainder when some reps already paid"), not a guess -- see the doc
    for the full writeup and what's still open (e.g. whether a brand
    should be able to dispute a specific rep's already-paid transfer,
    which is out of scope here)."""
    brand = await _get_own_brand_profile(conn, user)
    campaign = await _require_owned_campaign(conn, campaign_id, brand.id)
    has_captured_payment = campaign.status in campaigns_repository.STATUSES_WITH_CAPTURED_PAYMENT

    updated = await campaigns_repository.set_cancelled(conn, campaign_id)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "illegal_transition", "message": f"Cannot cancel from status '{campaign.status}'."},
        )

    refund_amount_cents = 0
    if has_captured_payment and updated.stripe_payment_intent_id is not None:
        committed_cents = await campaign_reps_repository.sum_committed_payouts_for_campaign(conn, campaign_id)
        refund_amount_cents = max(0, updated.budget_cents - committed_cents)
        if refund_amount_cents > 0:
            await stripe_service.refund_campaign(
                settings,
                payment_intent_id=updated.stripe_payment_intent_id,
                amount_cents=refund_amount_cents,
                campaign_id=updated.id,
            )
    return CancelCampaignResponse(
        id=updated.id, status=updated.status, refund_pending=refund_amount_cents > 0, refund_amount_cents=refund_amount_cents
    )


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
            challenges_converted_count=c.challenges_converted_count,
            challenge_conversion_rate=c.challenge_conversion_rate,
            badge_count=c.badge_count,
            badge_titles=c.badge_titles or [],
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
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_connection),
) -> CampaignRepResponse:
    """payout_cents is recorded server-computed from the campaign's own
    payout_per_rep_cents (never client-submitted), then
    payout_service.release_payout initiates the Stripe transfer in the
    same request (Build Prompt 10 deliverable 4). release_payout's own
    'rep_not_onboarded' outcome doesn't fail this call -- the rep is
    still confirmed and owed the payout, it just can't be transferred
    yet, so it stays payout_status='pending' until the rep finishes
    Connect onboarding (nothing currently retries this automatically --
    flagged, not a Prompt 10 deliverable)."""
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

    result = await payout_service.release_payout(conn, settings, updated.id)
    return _to_campaign_rep_response(result.campaign_rep or updated)


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


# ══════════════════════════════════════════════════════════════════
# /brands/campaigns/:id/reps/:rep_id/milestones/* (Build Prompt 8B)
# ══════════════════════════════════════════════════════════════════


def _to_milestone_progress_response(
    crm: campaign_milestones_repository.CampaignRepMilestone, m: campaign_milestones_repository.CampaignMilestone
) -> MilestoneProgressResponse:
    return MilestoneProgressResponse(
        id=crm.id,
        campaign_milestone_id=m.id,
        milestone_number=m.milestone_number,
        title=m.title,
        verification_method=m.verification_method,
        payout_percentage=m.payout_percentage,
        status=crm.status,
        rep_submission_text=crm.rep_submission_text,
        rep_submission_file_urls=crm.rep_submission_file_urls,
        payout_cents=crm.payout_cents,
        payout_status=crm.payout_status,
        dispute_flag=crm.dispute_flag,
        threshold_count=m.threshold_count,
        current_count=crm.current_count,
        submitted_at=crm.submitted_at,
        confirmed_at=crm.confirmed_at,
        paid_at=crm.paid_at,
    )


async def _require_campaign_rep_milestone(
    conn: asyncpg.Connection, campaign_id: str, rep_id: str, milestone_id: str
) -> tuple[campaign_reps_repository.CampaignRep, campaign_milestones_repository.CampaignRepMilestone]:
    cr = await campaign_reps_repository.get_by_rep_and_campaign_id(conn, rep_id, campaign_id)
    if cr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "campaign_rep_not_found", "message": "No campaign_reps row for that rep on this campaign."},
        )
    milestone = await campaign_milestones_repository.get_by_id_and_campaign(conn, milestone_id, campaign_id)
    if milestone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "milestone_not_found", "message": "No milestone found for that id on this campaign."},
        )
    crm = await campaign_milestones_repository.get_by_campaign_rep_and_milestone(conn, cr.id, milestone.id)
    if crm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "campaign_rep_milestone_not_found", "message": "This rep has no row for that milestone."},
        )
    return cr, crm


@brands_router.get("/campaigns/{campaign_id}/reps/{rep_id}/milestones", response_model=list[MilestoneProgressResponse])
async def list_rep_milestones(
    campaign_id: str,
    rep_id: str,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[MilestoneProgressResponse]:
    """Brand's per-rep milestone progress view (frontend note under
    Build Prompt 8B: "which milestones are pending, submitted, or
    confirmed per rep")."""
    brand = await _get_own_brand_profile(conn, user)
    await _require_owned_campaign(conn, campaign_id, brand.id)
    cr = await campaign_reps_repository.get_by_rep_and_campaign_id(conn, rep_id, campaign_id)
    if cr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "campaign_rep_not_found", "message": "No campaign_reps row for that rep on this campaign."},
        )
    milestones = {m.id: m for m in await campaign_milestones_repository.list_for_campaign(conn, campaign_id)}
    rows = await campaign_milestones_repository.list_for_campaign_rep(conn, cr.id)
    return [
        _to_milestone_progress_response(crm, milestones[crm.campaign_milestone_id])
        for crm in rows
        if crm.campaign_milestone_id in milestones
    ]


@brands_router.post(
    "/campaigns/{campaign_id}/reps/{rep_id}/milestones/{milestone_id}/confirm", response_model=MilestoneProgressResponse
)
async def confirm_milestone(
    campaign_id: str,
    rep_id: str,
    milestone_id: str,
    user: AuthenticatedUser = Depends(require_role("brand")),
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_connection),
) -> MilestoneProgressResponse:
    """POST .../milestones/:milestone_id/confirm (Build Prompt 8B
    deliverable 5). Brand-only, legal only from 'submitted'.
    payout_cents is computed server-side (percentage of
    payout_per_rep_cents, rounded down, with the rounding remainder
    added on the final milestone by milestone_number --
    campaign_milestones_repository.compute_payout_cents) then
    payout_service.release_milestone_payout initiates the Transfer in
    the same request, mirroring how confirm_submission above pairs
    campaign_reps_repository.confirm with payout_service.release_payout
    for flat campaigns. After the final milestone, campaign_reps.status
    advances to 'confirmed' so the flat rating/status pipeline keeps
    working unmodified (deliverable 5's own instruction)."""
    brand = await _get_own_brand_profile(conn, user)
    campaign = await _require_owned_campaign(conn, campaign_id, brand.id)
    if campaign.payment_type != "milestone":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "not_a_milestone_campaign", "message": "This campaign is not a milestone campaign."},
        )
    cr, crm = await _require_campaign_rep_milestone(conn, campaign_id, rep_id, milestone_id)
    if crm.status != "submitted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "illegal_transition", "message": f"Cannot confirm from status '{crm.status}'."},
        )

    payout_cents = await campaign_milestones_repository.compute_payout_cents(conn, crm.id)
    updated = await campaign_milestones_repository.confirm(
        conn, crm.id, payout_cents=payout_cents or 0, at=datetime.now(timezone.utc)
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "illegal_transition", "message": f"Cannot confirm from status '{crm.status}'."},
        )

    await payout_service.release_milestone_payout(conn, settings, updated.id)
    agg = await campaign_milestones_repository.bump_campaign_rep_milestone_totals(conn, cr.id)
    if agg is not None and agg["completed_count"] == agg["total_milestones"]:
        # Final milestone confirmed -- campaign_reps.status advances to
        # 'confirmed' the same way the flat-campaign confirm route does,
        # so the rating flow and every other status-gated route (rate,
        # withdraw's terminal-state guard, etc.) keep working unmodified
        # regardless of payment type. Milestone campaigns never pass
        # through the flat /submit endpoint, so this transitions from
        # 'accepted', not 'submitted' -- see
        # mark_confirmed_via_final_milestone's own docstring.
        await campaign_reps_repository.mark_confirmed_via_final_milestone(conn, cr.id, at=datetime.now(timezone.utc))

    milestone = await campaign_milestones_repository.get_by_id_and_campaign(conn, milestone_id, campaign_id)
    final_crm = await campaign_milestones_repository.get_by_id(conn, updated.id)
    return _to_milestone_progress_response(final_crm or updated, milestone)


@brands_router.post(
    "/campaigns/{campaign_id}/reps/{rep_id}/milestones/{milestone_id}/dispute", response_model=MilestoneProgressResponse
)
async def dispute_milestone(
    campaign_id: str,
    rep_id: str,
    milestone_id: str,
    body: MilestoneDisputeRequest,
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
    resend_client: ResendClient = Depends(resend_client_dependency),
) -> MilestoneProgressResponse:
    """POST .../milestones/:milestone_id/dispute (Build Prompt 8B
    deliverable 7). Brand-only, legal only within
    MILESTONE_DISPUTE_WINDOW_HOURS of the rep's submission (the same
    24h window the auto-release job uses) -- past that window the
    milestone has already auto-released (or been brand-confirmed) and
    there is nothing left to dispute. Sets dispute_flag, which both
    pauses the auto-release job (list_eligible_for_auto_release filters
    on dispute_flag=false) and creates the admin-queue entry; resolution
    is admin-only (no self-serve brand/rep resolution at MVP, per the
    spec's own instruction)."""
    brand = await _get_own_brand_profile(conn, user)
    campaign = await _require_owned_campaign(conn, campaign_id, brand.id)
    cr, crm = await _require_campaign_rep_milestone(conn, campaign_id, rep_id, milestone_id)
    if crm.status != "submitted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "illegal_transition", "message": f"Cannot dispute from status '{crm.status}'."},
        )
    if crm.submitted_at is None or datetime.now(timezone.utc) - crm.submitted_at > timedelta(hours=MILESTONE_DISPUTE_WINDOW_HOURS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "dispute_window_closed",
                "message": f"Disputes are only legal within {MILESTONE_DISPUTE_WINDOW_HOURS} hours of submission.",
            },
        )

    updated = await campaign_milestones_repository.set_dispute_flag(conn, crm.id)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "illegal_transition", "message": f"Cannot dispute from status '{crm.status}'."},
        )
    await admin_repository.create_milestone_dispute(conn, campaign_rep_milestone_id=crm.id, raised_by=user.id, reason=body.reason)

    milestone = await campaign_milestones_repository.get_by_id_and_campaign(conn, milestone_id, campaign_id)
    rep = await rep_profiles_repository.get_by_id(conn, rep_id)
    if rep is not None:
        rep_user = await users_repository.get_user_by_id(conn, rep.user_id)
        if rep_user is not None:
            await send_milestone_disputed_email(
                rep_user.email, campaign_title=campaign.title, milestone_title=milestone.title, client=resend_client
            )
    return _to_milestone_progress_response(updated, milestone)
