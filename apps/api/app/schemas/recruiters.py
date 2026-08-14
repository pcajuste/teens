from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, field_validator

InstitutionType = Literal["college", "employer"]

# Below this fraction of the plan's full allotment, GET /recruiters/credits
# flags low_credit_warning (Build Prompt 11 deliverable 6: "20% remaining").
LOW_CREDIT_WARNING_THRESHOLD = 0.2


class RecruiterProfileUpdateRequest(BaseModel):
    institution_name: str
    institution_type: InstitutionType
    website: str | None = None


class RecruiterProfileResponse(BaseModel):
    id: str
    institution_name: str
    institution_type: InstitutionType
    website: str | None
    verified: bool


class CreditsResponse(BaseModel):
    contact_credits_remaining: int
    credits_reset_date: date | None
    low_credit_warning: bool


class RecruiterSearchCardResponse(BaseModel):
    """GET /recruiters/talents/search -- no PII, no credit cost. See
    talent_profiles_repository.RecruiterSearchCard's docstring."""

    talent_id: str
    city: str
    state: str
    graduation_year: int
    school_type: str | None
    categories: list[str]
    profile_completeness_score: int
    brand_average_rating: float | None
    brand_campaigns_completed: int
    challenges_converted_count: int = 0
    challenge_conversion_rate: float | None = None
    badge_count: int = 0
    badge_titles: list[str] = []


class RecruiterTalentDetailResponse(BaseModel):
    """GET /recruiters/talents/:id -- full identifying profile, costs 1
    credit (deducted server-side before this is ever returned).
    total_earnings_cents is the talent's own lifetime-paid figure
    (talent_profiles.total_earnings_cents) -- a recruiter who has spent
    a credit to view this profile sees the same earned-record number the
    talent sees on their own dashboard, not a separate recruiter-facing
    computation."""

    talent_id: str
    display_name: str
    school_name: str
    school_type: str | None
    city: str
    state: str
    graduation_year: int
    bio: str | None
    categories: list[str]
    instagram_handle: str | None
    tiktok_handle: str | None
    brand_campaigns_completed: int
    total_earnings_cents: int
    brand_average_rating: float | None
    profile_completeness_score: int


class ContactRequest(BaseModel):
    message_text: str

    @field_validator("message_text")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message_text must not be empty")
        return value


class ContactResponse(BaseModel):
    id: str
    talent_id: str
    message_text: str
    messaged_at: datetime


class SaveRequest(BaseModel):
    list_name: str | None = None


class SavedProfileResponse(BaseModel):
    talent_id: str
    list_name: str | None
    saved_at: datetime


class InboxMessageResponse(BaseModel):
    """GET /talents/inbox -- the talent-facing view of a recruiter_contacts
    row. Never the recruiter's identity beyond what the talent already has
    a legitimate reason to see once contacted (Build Prompt 11
    deliverable 4)."""

    id: str
    message_text: str
    read_at: datetime | None
    messaged_at: datetime


class CreditTopUpRequest(BaseModel):
    """POST /recruiters/credits/top-up -- `credits` is the number of
    contact credits being purchased; amount_cents is computed
    server-side from settings, never client-submitted (Section 9)."""

    credits: int

    @field_validator("credits")
    @classmethod
    def _positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("credits must be > 0")
        return value


class CreditTopUpResponse(BaseModel):
    stripe_payment_intent_client_secret: str


class SubscriptionCheckoutRequest(BaseModel):
    """POST /recruiters/subscribe -- see stripe_service.create_subscription_checkout_session's
    docstring for why this route exists despite Build Prompt 11 shipping
    without one."""

    plan: Literal["monthly", "annual"]


class SubscriptionCheckoutResponse(BaseModel):
    checkout_url: str


class RecruiterMessageResponse(BaseModel):
    """GET /recruiters/messages -- recruiter-facing list of sent
    messages with read-receipt status (Build Prompt 12 deliverable 4)."""

    id: str
    talent_id: str
    talent_display_name: str
    message_text: str
    read_at: datetime | None
    messaged_at: datetime
