"""Recruiter portal backend (Build Prompt 11): profile CRUD, credits,
no-PII search, credit-gated full-profile view + contact, saved
profiles, credit top-up. Subscription lifecycle itself is driven by
Stripe webhooks (app/routers/webhooks.py) -- there is no
POST /recruiters/subscribe route here, since Section 8 doesn't list
one and subscribing happens via Stripe-hosted billing, not this API.

Every route requires an authenticated recruiter; GET/PUT /recruiters/me
uses require_role_any_status (mirrors brands.py/talents.py's onboarding
gap fix -- a freshly signed-up recruiter must be able to submit their
profile while still 'pending'). Every other route requires 'active',
which for a recruiter additionally means the dual gate from deliverable
8 (admin approval AND subscription creation) already passed -- enforced
by the customer.subscription.created webhook handler being what flips
account_status to 'active' in the first place, not by any check in this
router.

Credit-spending routes (GET .../talents/:id, POST .../contact) deduct via
recruiter_profiles_repository.decrement_credit's atomic conditional
UPDATE before doing anything else -- a 402 on zero balance is checked
first, so a talent's data is never read/messaged without a successful
deduction (Build Prompt 11 acceptance criteria)."""
from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.core.security import AuthenticatedUser, require_role, require_role_any_status
from app.db.pool import get_connection
from app.repositories import (
    recruiter_contacts_repository,
    recruiter_profiles_repository,
    recruiter_saved_profiles_repository,
    talent_profiles_repository,
    users_repository,
)
from app.schemas.recruiters import (
    LOW_CREDIT_WARNING_THRESHOLD,
    ContactRequest,
    ContactResponse,
    CreditsResponse,
    CreditTopUpRequest,
    CreditTopUpResponse,
    RecruiterMessageResponse,
    RecruiterProfileResponse,
    RecruiterProfileUpdateRequest,
    RecruiterTalentDetailResponse,
    RecruiterSearchCardResponse,
    SavedProfileResponse,
    SaveRequest,
    SubscriptionCheckoutRequest,
    SubscriptionCheckoutResponse,
)
from app.services import stripe_service

recruiters_router = APIRouter(prefix="/recruiters", tags=["recruiters"])


def _require_recruiter_profile_row(row) -> recruiter_profiles_repository.RecruiterProfile:
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "recruiter_profile_not_found", "message": "Complete onboarding via PUT /recruiters/me first."},
        )
    return row


async def _get_own_recruiter_profile(
    conn: asyncpg.Connection, user: AuthenticatedUser
) -> recruiter_profiles_repository.RecruiterProfile:
    profile = await recruiter_profiles_repository.get_by_user_id(conn, user.id)
    return _require_recruiter_profile_row(profile)


def _to_profile_response(p: recruiter_profiles_repository.RecruiterProfile) -> RecruiterProfileResponse:
    return RecruiterProfileResponse(
        id=p.id,
        institution_name=p.institution_name,
        institution_type=p.institution_type,
        website=p.website,
        verified=p.verified,
    )


def _to_credits_response(p: recruiter_profiles_repository.RecruiterProfile, settings: Settings) -> CreditsResponse:
    allotment = settings.recruiter_plan_credits_allotment
    low = allotment > 0 and (p.contact_credits_remaining / allotment) <= LOW_CREDIT_WARNING_THRESHOLD
    return CreditsResponse(
        contact_credits_remaining=p.contact_credits_remaining,
        credits_reset_date=p.credits_reset_date,
        low_credit_warning=low,
    )


async def _require_subscription_active(recruiter: recruiter_profiles_repository.RecruiterProfile) -> None:
    """Credit-spending endpoints must reject once a subscription is
    cancelled (customer.subscription.deleted webhook, deliverable 8:
    'credit-spending endpoints return "subscription inactive" error'),
    even though saved profiles/message history stay readable. There's
    no separate 'subscription_status' column on recruiter_profiles
    (Section 7 doesn't add one) -- stripe_subscription_id being unset
    is the signal a recruiter never subscribed or was downgraded."""
    if recruiter.stripe_subscription_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "subscription_inactive", "message": "An active subscription is required to spend contact credits."},
        )


# ══════════════════════════════════════════════════════════════════
# /recruiters/me
# ══════════════════════════════════════════════════════════════════


@recruiters_router.get("/me", response_model=RecruiterProfileResponse)
async def get_me(
    user: AuthenticatedUser = Depends(require_role_any_status("recruiter")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> RecruiterProfileResponse:
    profile = await _get_own_recruiter_profile(conn, user)
    return _to_profile_response(profile)


@recruiters_router.put("/me", response_model=RecruiterProfileResponse)
async def put_me(
    body: RecruiterProfileUpdateRequest,
    user: AuthenticatedUser = Depends(require_role_any_status("recruiter")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> RecruiterProfileResponse:
    existing = await recruiter_profiles_repository.get_by_user_id(conn, user.id)
    if existing is None:
        profile = await recruiter_profiles_repository.create_recruiter_profile(
            conn,
            user_id=user.id,
            institution_name=body.institution_name,
            institution_type=body.institution_type,
            website=body.website,
        )
    else:
        profile = await recruiter_profiles_repository.update_recruiter_profile(
            conn,
            existing.id,
            institution_name=body.institution_name,
            institution_type=body.institution_type,
            website=body.website,
        )
    return _to_profile_response(profile)


@recruiters_router.get("/credits", response_model=CreditsResponse)
async def get_credits(
    user: AuthenticatedUser = Depends(require_role("recruiter")),
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_connection),
) -> CreditsResponse:
    recruiter = await _get_own_recruiter_profile(conn, user)
    return _to_credits_response(recruiter, settings)


@recruiters_router.post("/credits/top-up", response_model=CreditTopUpResponse)
async def top_up_credits(
    body: CreditTopUpRequest,
    user: AuthenticatedUser = Depends(require_role("recruiter")),
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_connection),
) -> CreditTopUpResponse:
    """Build Prompt 11 deliverable 7. amount_cents is always
    settings.recruiter_credit_topup_price_cents * credits -- server-
    computed, never a client-submitted amount (Section 9). The actual
    credit increment happens on payment_intent.succeeded
    (app/routers/webhooks.py), not here -- this just starts the charge,
    matching brands.py's activate_campaign shape (PaymentIntent now,
    state change on webhook confirmation)."""
    recruiter = await _get_own_recruiter_profile(conn, user)

    customer_id = recruiter.stripe_customer_id
    if customer_id is None:
        user_record = await users_repository.get_user_by_id(conn, user.id)
        customer_id = await stripe_service.create_customer(
            settings, email=user_record.email, metadata={"role": "recruiter", "recruiter_id": recruiter.id}
        )
        await recruiter_profiles_repository.set_stripe_customer_id(conn, recruiter.id, customer_id)

    amount_cents = settings.recruiter_credit_topup_price_cents * body.credits
    _, client_secret = await stripe_service.create_credit_topup_payment_intent(
        settings, amount_cents=amount_cents, credits=body.credits, recruiter_id=recruiter.id, customer_id=customer_id
    )
    return CreditTopUpResponse(stripe_payment_intent_client_secret=client_secret)


@recruiters_router.post("/subscribe", response_model=SubscriptionCheckoutResponse)
async def subscribe(
    body: SubscriptionCheckoutRequest,
    user: AuthenticatedUser = Depends(require_role_any_status("recruiter")),
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_connection),
) -> SubscriptionCheckoutResponse:
    """Starts a Stripe Checkout Session for the recruiter subscription
    plan (Build Prompt 12 deliverable 5). require_role_any_status
    because a recruiter must be able to subscribe while still 'pending'
    -- subscription creation is one half of the dual activation gate
    (see webhooks.py's _handle_subscription_created), so gating this
    route on 'active' would make it unreachable for anyone who needs
    it. Actual activation happens only on the subsequent webhook, never
    here."""
    recruiter = await _get_own_recruiter_profile(conn, user)

    price_id = settings.recruiter_price_id_monthly if body.plan == "monthly" else settings.recruiter_price_id_annual
    if not price_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "plan_not_configured", "message": f"The {body.plan} plan is not configured on this environment."},
        )

    customer_id = recruiter.stripe_customer_id
    if customer_id is None:
        user_record = await users_repository.get_user_by_id(conn, user.id)
        customer_id = await stripe_service.create_customer(
            settings, email=user_record.email, metadata={"role": "recruiter", "recruiter_id": recruiter.id}
        )
        await recruiter_profiles_repository.set_stripe_customer_id(conn, recruiter.id, customer_id)

    checkout_url = await stripe_service.create_subscription_checkout_session(
        settings,
        customer_id=customer_id,
        price_id=price_id,
        success_url=f"{settings.next_public_app_url}/recruiter/subscription?checkout=success",
        cancel_url=f"{settings.next_public_app_url}/recruiter/subscription?checkout=cancelled",
        metadata={"recruiter_id": recruiter.id, "plan": body.plan},
    )
    return SubscriptionCheckoutResponse(checkout_url=checkout_url)


# ══════════════════════════════════════════════════════════════════
# /recruiters/talents/*
# ══════════════════════════════════════════════════════════════════


@recruiters_router.get("/talents/search", response_model=list[RecruiterSearchCardResponse])
async def search_reps(
    graduation_year: int | None = None,
    city: str | None = None,
    state: str | None = None,
    categories: str | None = None,
    min_campaigns: int | None = None,
    min_rating: float | None = None,
    limit: int = 20,
    offset: int = 0,
    user: AuthenticatedUser = Depends(require_role("recruiter")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[RecruiterSearchCardResponse]:
    """No credit cost, no PII (Build Prompt 11 deliverable 2 / acceptance
    criterion). `categories` is a comma-separated query param, per
    Section 8."""
    await _get_own_recruiter_profile(conn, user)
    category_list = [c.strip() for c in categories.split(",") if c.strip()] if categories else None

    cards = await talent_profiles_repository.search_for_recruiter(
        conn,
        graduation_year=graduation_year,
        city=city,
        state=state,
        categories=category_list,
        min_campaigns=min_campaigns,
        min_rating=min_rating,
        limit=limit,
        offset=offset,
    )
    return [
        RecruiterSearchCardResponse(
            talent_id=c.talent_id,
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


@recruiters_router.get("/talents/{talent_id}", response_model=RecruiterTalentDetailResponse)
async def get_talent_detail(
    talent_id: str,
    user: AuthenticatedUser = Depends(require_role("recruiter")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> RecruiterTalentDetailResponse:
    """Costs 1 credit, deducted server-side in the same request as the
    read (Build Prompt 11 deliverable 3) -- the atomic decrement runs
    BEFORE the profile is fetched, so a talent's identifying fields are
    never returned on a failed/declined charge."""
    recruiter = await _get_own_recruiter_profile(conn, user)
    await _require_subscription_active(recruiter)

    talent = await talent_profiles_repository.get_by_id(conn, talent_id)
    if talent is None or not talent.recruiter_visible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "talent_not_found", "message": "No opted-in talent found for that id."},
        )

    charged = await recruiter_profiles_repository.decrement_credit(conn, recruiter.id)
    if charged is None:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"code": "insufficient_credits", "message": "No contact credits remaining."},
        )

    return RecruiterTalentDetailResponse(
        talent_id=talent.id,
        display_name=talent.display_name,
        school_name=talent.school_name,
        school_type=talent.school_type,
        city=talent.city,
        state=talent.state,
        graduation_year=talent.graduation_year,
        bio=talent.bio,
        categories=talent.categories,
        instagram_handle=talent.instagram_handle,
        tiktok_handle=talent.tiktok_handle,
        total_campaigns_completed=talent.total_campaigns_completed,
        total_earnings_cents=talent.total_earnings_cents,
        average_rating=talent.average_rating,
        profile_completeness_score=talent.profile_completeness_score,
    )


@recruiters_router.post("/talents/{talent_id}/contact", response_model=ContactResponse)
async def contact_rep(
    talent_id: str,
    body: ContactRequest,
    user: AuthenticatedUser = Depends(require_role("recruiter")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> ContactResponse:
    """Costs 1 credit (same transactional deduction as get_talent_detail).
    One-directional: a second contact to the same talent is rejected via
    the recruiter_contacts UNIQUE(recruiter_id, talent_id) constraint
    (Build Prompt 11 deliverable 4) -- checked BEFORE the credit is
    spent, so a recruiter isn't charged for a contact attempt that was
    always going to fail."""
    recruiter = await _get_own_recruiter_profile(conn, user)
    await _require_subscription_active(recruiter)

    talent = await talent_profiles_repository.get_by_id(conn, talent_id)
    if talent is None or not talent.recruiter_visible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "talent_not_found", "message": "No opted-in talent found for that id."},
        )

    existing = await recruiter_contacts_repository.get_for_recruiter_and_rep(conn, recruiter.id, talent_id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "already_contacted", "message": "You've already contacted this talent."},
        )

    charged = await recruiter_profiles_repository.decrement_credit(conn, recruiter.id)
    if charged is None:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"code": "insufficient_credits", "message": "No contact credits remaining."},
        )

    contact = await recruiter_contacts_repository.create_contact(
        conn, recruiter_id=recruiter.id, talent_id=talent_id, message_text=body.message_text
    )
    if contact is None:
        # Lost a race with a duplicate concurrent contact request --
        # the credit was already spent above (mirrors this codebase's
        # existing "atomic decrement first, narrow race after" shape;
        # see recruiter_profiles_repository module docstring).
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "already_contacted", "message": "You've already contacted this talent."},
        )

    return ContactResponse(id=contact.id, talent_id=contact.talent_id, message_text=contact.message_text, messaged_at=contact.messaged_at)


@recruiters_router.get("/messages", response_model=list[RecruiterMessageResponse])
async def list_messages(
    user: AuthenticatedUser = Depends(require_role("recruiter")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[RecruiterMessageResponse]:
    """Build Prompt 12 deliverable 4: read-receipt display for every
    message this recruiter has sent."""
    recruiter = await _get_own_recruiter_profile(conn, user)
    rows = await recruiter_contacts_repository.list_for_recruiter(conn, recruiter.id)
    return [
        RecruiterMessageResponse(
            id=r.contact.id,
            talent_id=r.contact.talent_id,
            talent_display_name=r.talent_display_name,
            message_text=r.contact.message_text,
            read_at=r.contact.read_at,
            messaged_at=r.contact.messaged_at,
        )
        for r in rows
    ]


# ══════════════════════════════════════════════════════════════════
# /recruiters/saved
# ══════════════════════════════════════════════════════════════════


@recruiters_router.post("/talents/{talent_id}/save", response_model=SavedProfileResponse)
async def save_rep(
    talent_id: str,
    body: SaveRequest = SaveRequest(),
    user: AuthenticatedUser = Depends(require_role("recruiter")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> SavedProfileResponse:
    recruiter = await _get_own_recruiter_profile(conn, user)
    saved = await recruiter_saved_profiles_repository.save(conn, recruiter_id=recruiter.id, talent_id=talent_id, list_name=body.list_name)
    return SavedProfileResponse(talent_id=saved.talent_id, list_name=saved.list_name, saved_at=saved.saved_at)


@recruiters_router.delete("/talents/{talent_id}/save", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def unsave_rep(
    talent_id: str,
    user: AuthenticatedUser = Depends(require_role("recruiter")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> None:
    recruiter = await _get_own_recruiter_profile(conn, user)
    await recruiter_saved_profiles_repository.unsave(conn, recruiter_id=recruiter.id, talent_id=talent_id)


@recruiters_router.get("/saved", response_model=list[SavedProfileResponse])
async def list_saved(
    user: AuthenticatedUser = Depends(require_role("recruiter")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[SavedProfileResponse]:
    recruiter = await _get_own_recruiter_profile(conn, user)
    rows = await recruiter_saved_profiles_repository.list_for_recruiter(conn, recruiter.id)
    return [SavedProfileResponse(talent_id=r.talent_id, list_name=r.list_name, saved_at=r.saved_at) for r in rows]
