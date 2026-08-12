from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

AccountType = Literal["rep", "brand", "recruiter"]
ResolutionAction = Literal["force_confirm", "force_cancel_refund"]
SafetyReportResolution = Literal["resolved", "dismissed"]


class QueueEntryResponse(BaseModel):
    user_id: str
    email: str
    role: str
    account_status: str
    pending_reason: str
    display_name: str
    created_at: datetime


class RejectRequest(BaseModel):
    reason: str = Field(min_length=1)


class ApprovalActionResponse(BaseModel):
    user_id: str
    account_status: str


class AdminCampaignResponse(BaseModel):
    id: str
    title: str
    status: str
    brand_name: str
    budget_cents: int
    target_categories: list[str]
    flagged_at: datetime | None
    flagged_reason: str | None
    resolved_at: datetime | None
    resolution_action: str | None
    created_at: datetime


class FlagCampaignRequest(BaseModel):
    reason: str = Field(min_length=1)


class ResolveCampaignRequest(BaseModel):
    action: ResolutionAction


class StuckPaymentResponse(BaseModel):
    campaign_rep_id: str
    campaign_id: str
    rep_id: str
    payout_cents: int | None
    payout_status: str
    stripe_transfer_id: str | None
    payout_processing_started_at: datetime | None
    hours_stuck: float


class ReleasePayoutResponse(BaseModel):
    campaign_rep_id: str
    payout_status: str
    admin_released: bool


class RevenuePeriodResponse(BaseModel):
    period: str
    brand_campaign_fees_cents: int
    intelligence_subscription_cents: int
    recruiter_active_subscriptions: int


class RepsByCityCategoryResponse(BaseModel):
    by_city: list[dict]
    by_category: list[dict]


class CampaignsByStatusCategoryResponse(BaseModel):
    by_status: list[dict]
    by_category: list[dict]


class ConsentStatusEntry(BaseModel):
    consent_state: str
    count: int


class OutlierBrandResponse(BaseModel):
    brand_id: str
    company_name: str
    rating_count: int
    average_rating: float
    reason: str


class ParentSuspendedRepResponse(BaseModel):
    rep_id: str
    rep_user_id: str
    display_name: str
    parent_id: str
    suspended_by_parent_at: datetime


class ReverseSuspensionResponse(BaseModel):
    rep_id: str
    account_status: str


class SafetyReportResponse(BaseModel):
    id: str
    reporter_rep_id: str
    reporter_display_name: str
    campaign_id: str | None
    reason: str
    description: str | None
    status: str
    created_at: datetime
    resolved_at: datetime | None
    resolution_note: str | None


class ResolveSafetyReportRequest(BaseModel):
    status: SafetyReportResolution
    resolution_note: str | None = None


class SafetyReportCreateRequest(BaseModel):
    reason: str = Field(min_length=1)
    campaign_id: str | None = None
    description: str | None = None


# ══════════════════════════════════════════════════════════════════
# Build Prompt 8B: milestone dispute queue -- distinct admin-queue
# category from campaign-level disputes (AdminCampaignResponse's
# flagged_*/resolved_* fields) and stuck-payment disputes
# (StuckPaymentResponse), per the prompt's own explicit instruction.
# ══════════════════════════════════════════════════════════════════

MilestoneDisputeStatus = Literal["open", "resolved_confirmed", "resolved_declined"]
MilestoneDisputeResolution = Literal["confirm", "decline"]


class MilestoneDisputeResponse(BaseModel):
    id: str
    campaign_rep_milestone_id: str
    campaign_id: str
    campaign_title: str
    milestone_title: str
    rep_id: str
    rep_display_name: str
    raised_by: str
    reason: str | None
    status: MilestoneDisputeStatus
    created_at: datetime
    resolved_at: datetime | None
    resolved_by: str | None
    resolution_note: str | None


class ResolveMilestoneDisputeRequest(BaseModel):
    resolution: MilestoneDisputeResolution
    resolution_note: str | None = None
