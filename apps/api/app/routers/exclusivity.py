"""Category Exclusivity purchase flow (Build Prompt 8C).

GET /brands/exclusivity/check and GET /brands/exclusivity/pricing are
deliberately unauthenticated (Section 8C: "No authentication required
to check availability -- a brand should be able to check before
committing.") -- neither leaks anything beyond a bool/price preview, so
there's nothing sensitive to gate. POST /brands/exclusivity/purchase and
GET /brands/exclusivity require an active brand, same as every other
route in app/routers/brands.py.
"""
from __future__ import annotations

from datetime import datetime, timezone

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.config import Settings, get_settings
from app.core.categories import BASE_CATEGORIES
from app.core.security import AuthenticatedUser, require_role
from app.db.pool import get_connection
from app.repositories import brand_profiles_repository, exclusivity_repository
from app.schemas.exclusivity import (
    ExclusivityAgreementResponse,
    ExclusivityCheckResponse,
    ExclusivityCheckResponseConflict,
    ExclusivityPricingResponse,
    ExclusivityPurchaseRequest,
    ExclusivityPurchaseResponse,
)
from app.services import exclusivity_service, stripe_service

router = APIRouter(prefix="/brands/exclusivity", tags=["exclusivity"])

CONFLICT_MESSAGE = (
    "This category is exclusively held by another brand during part or "
    "all of your requested window. Check availability for adjacent dates."
)


def _require_valid_category(category: str) -> None:
    if category not in BASE_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_category", "message": f"'{category}' is not a valid category."},
        )


def _require_valid_window(settings: Settings, *, starts_at: datetime, ends_at: datetime, require_future_start: bool) -> None:
    if starts_at.tzinfo is None or ends_at.tzinfo is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_dates", "message": "starts_at/ends_at must be timezone-aware."},
        )
    if ends_at <= starts_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_dates", "message": "ends_at must be after starts_at."},
        )
    if require_future_start and starts_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_dates", "message": "starts_at must be in the future."},
        )
    days = (ends_at - starts_at).total_seconds() / 86400.0
    if days > settings.exclusivity_max_days:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "window_too_long",
                "message": f"Exclusivity window cannot exceed {settings.exclusivity_max_days} days.",
            },
        )


def _pricing(settings: Settings, *, starts_at: datetime, ends_at: datetime) -> tuple[int, int, int]:
    days = max(1, -(-int((ends_at - starts_at).total_seconds()) // 86400))  # ceil division, at least 1 day
    rate = settings.exclusivity_base_rate_cents_per_day
    return days, rate, days * rate


@router.get("/check", response_model=ExclusivityCheckResponse)
async def check_availability(
    category: str = Query(...),
    city: str | None = Query(default=None),
    starts_at: datetime = Query(...),
    ends_at: datetime = Query(...),
    conn: asyncpg.Connection = Depends(get_connection),
) -> ExclusivityCheckResponse:
    conflict_brand_id = await exclusivity_service.check_exclusivity_conflict(
        conn, category=category, city=city, starts_at=starts_at, ends_at=ends_at
    )
    exists = conflict_brand_id is not None
    return ExclusivityCheckResponse(available=not exists, conflict=ExclusivityCheckResponseConflict(exists=exists))


@router.get("/pricing", response_model=ExclusivityPricingResponse)
async def pricing(
    category: str = Query(...),
    city: str | None = Query(default=None),
    starts_at: datetime = Query(...),
    ends_at: datetime = Query(...),
    settings: Settings = Depends(get_settings),
) -> ExclusivityPricingResponse:
    if ends_at <= starts_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_dates", "message": "ends_at must be after starts_at."},
        )
    days, rate, total = _pricing(settings, starts_at=starts_at, ends_at=ends_at)
    return ExclusivityPricingResponse(days=days, rate_per_day_cents=rate, total_cents=total, starts_at=starts_at, ends_at=ends_at)


@router.post("/purchase", response_model=ExclusivityPurchaseResponse, status_code=status.HTTP_201_CREATED)
async def purchase(
    body: ExclusivityPurchaseRequest,
    user: AuthenticatedUser = Depends(require_role("brand")),
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_connection),
) -> ExclusivityPurchaseResponse:
    brand = await brand_profiles_repository.get_by_user_id(conn, user.id)
    if brand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "brand_profile_not_found", "message": "Complete onboarding via PUT /brands/me first."},
        )

    _require_valid_category(body.category)
    _require_valid_window(settings, starts_at=body.starts_at, ends_at=body.ends_at, require_future_start=True)

    _, _, fee_cents = _pricing(settings, starts_at=body.starts_at, ends_at=body.ends_at)

    async with conn.transaction():
        conflict_brand_id = await exclusivity_service.check_exclusivity_conflict(
            conn,
            category=body.category,
            city=body.city,
            starts_at=body.starts_at,
            ends_at=body.ends_at,
            exclude_brand_id=brand.id,
        )
        if conflict_brand_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": CONFLICT_MESSAGE},
            )

        payment_intent_id, client_secret = await stripe_service.create_payment_intent(
            settings,
            amount_cents=fee_cents,
            metadata={
                "type": "category_exclusivity",
                "brand_id": brand.id,
                "category": body.category,
                "city": body.city or "all",
                "starts_at": body.starts_at.isoformat(),
                "ends_at": body.ends_at.isoformat(),
            },
        )

        try:
            agreement = await exclusivity_repository.create_agreement(
                conn,
                brand_id=brand.id,
                category=body.category,
                city=body.city,
                starts_at=body.starts_at,
                ends_at=body.ends_at,
                fee_cents=fee_cents,
                stripe_payment_intent_id=payment_intent_id,
            )
        except Exception:
            # Steps e (PaymentIntent) and f (agreement row) must be
            # atomic (Section 8C deliverable 3): if the row insert fails
            # -- e.g. a UNIQUE violation, a DB error -- the PaymentIntent
            # must not be left dangling.
            await stripe_service.cancel_payment_intent(settings, payment_intent_id=payment_intent_id)
            raise

    return ExclusivityPurchaseResponse(
        agreement_id=agreement.id,
        client_secret=client_secret,
        fee_cents=agreement.fee_cents,
        starts_at=agreement.starts_at,
        ends_at=agreement.ends_at,
    )


@router.get("", response_model=list[ExclusivityAgreementResponse])
async def list_own_agreements(
    user: AuthenticatedUser = Depends(require_role("brand")),
    conn: asyncpg.Connection = Depends(get_connection),
) -> list[ExclusivityAgreementResponse]:
    brand = await brand_profiles_repository.get_by_user_id(conn, user.id)
    if brand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "brand_profile_not_found", "message": "Complete onboarding via PUT /brands/me first."},
        )
    agreements = await exclusivity_repository.list_for_brand(conn, brand.id)
    return [
        ExclusivityAgreementResponse(
            id=a.id,
            category=a.category,
            city=a.city,
            starts_at=a.starts_at,
            ends_at=a.ends_at,
            status=a.status,
            payment_status=a.payment_status,
            fee_cents=a.fee_cents,
            refund_cents=a.refund_cents,
        )
        for a in agreements
    ]
