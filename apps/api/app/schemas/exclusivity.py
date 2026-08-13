"""Request/response  schemas for Category Exclusivity (Build Prompt 8C)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ExclusivityCheckResponseConflict(BaseModel):
    exists: bool


class ExclusivityCheckResponse(BaseModel):
    available: bool
    conflict: ExclusivityCheckResponseConflict


class ExclusivityPricingResponse(BaseModel):
    days: int
    rate_per_day_cents: int
    total_cents: int
    starts_at: datetime
    ends_at: datetime


class ExclusivityPurchaseRequest(BaseModel):
    category: str
    city: str | None = None
    starts_at: datetime
    ends_at: datetime


class ExclusivityPurchaseResponse(BaseModel):
    agreement_id: str
    client_secret: str
    fee_cents: int
    starts_at: datetime
    ends_at: datetime


class ExclusivityAgreementResponse(BaseModel):
    id: str
    category: str
    city: str | None
    starts_at: datetime
    ends_at: datetime
    status: str
    payment_status: str
    fee_cents: int
    refund_cents: int | None


class AdminExclusivityAgreementResponse(ExclusivityAgreementResponse):
    brand_id: str
    stripe_payment_intent_id: str
    cancelled_at: datetime | None
    cancellation_reason: str | None
    created_at: datetime


class AdminExclusivityActiveResponse(AdminExclusivityAgreementResponse):
    days_remaining: int


class AdminExclusivityListResponse(BaseModel):
    agreements: list[AdminExclusivityAgreementResponse]
    total: int
    limit: int
    offset: int


class AdminExclusivityCancelRequest(BaseModel):
    cancellation_reason: str = Field(min_length=1)


class AdminExclusivityCancelResponse(BaseModel):
    id: str
    status: str
    cancelled_at: datetime
    refund_cents: int


class ExclusivityCategoryFrequency(BaseModel):
    category: str
    purchase_count: int


class AdminExclusivityAnalyticsResponse(BaseModel):
    total_revenue_cents: int
    active_count: int
    categories_by_purchase_frequency: list[ExclusivityCategoryFrequency]
    average_agreement_length_days: float
