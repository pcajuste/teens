from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.core.constants import VALUES_FILTER_CATEGORIES


class RequestLinkRequest(BaseModel):
    parent_email: EmailStr


class ParentSessionResponse(BaseModel):
    session_token: str
    rep_id: str


class RepSummary(BaseModel):
    """Exactly the fields a recruiter would see in no-PII card mode, plus
    earnings (deliverable 2) -- parents have a legitimate interest in
    income their child is earning.
    """

    display_name: str
    school_name: str
    graduation_year: int
    categories: list[str]
    profile_completeness_score: int
    total_earnings_cents: int
    total_campaigns_completed: int


class PendingCampaignBrief(BaseModel):
    campaign_reps_id: str
    campaign_id: str
    brand_name: str
    product_name: str
    key_messaging: str
    deliverables_description: str
    prohibited_content: str | None
    payout_cents: int | None
    start_date: str
    end_date: str
    requires_in_person: bool
    parent_approval_deadline: str | None


class ParentSettings(BaseModel):
    values_filters: list[str]
    campaign_approval_required: bool
    digest_enabled: bool


class ValuesFiltersUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    values_filters: list[str]

    @field_validator("values_filters")
    @classmethod
    def validate_categories(cls, v: list[str]) -> list[str]:
        invalid = sorted(set(v) - set(VALUES_FILTER_CATEGORIES))
        if invalid:
            raise ValueError(f"Invalid filter categories {invalid}; allowed: {VALUES_FILTER_CATEGORIES}")
        return v


class ApprovalRequiredUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    campaign_approval_required: bool


class DigestSettingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    digest_enabled: bool


class DigestPreview(BaseModel):
    campaigns_completed_this_month: int
    earnings_this_month_cents: int
    earnings_lifetime_cents: int
    profile_completeness_score: int
    categories_active_in: list[str]
