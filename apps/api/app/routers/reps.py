from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.core.db import get_connection
from app.core.security import CurrentUser, require_role_and_active
from app.schemas.rep import (
    CampaignSummary,
    EarningsBreakdown,
    ProfilePreview,
    RepProfile,
    RepProfileUpdate,
)
from app.services import rep_service

router = APIRouter(prefix="/reps", tags=["reps"])

require_active_rep = require_role_and_active("rep")


def _serialize_campaign(row: dict) -> CampaignSummary:
    return CampaignSummary(
        campaign_reps_id=str(row["campaign_reps_id"]),
        campaign_id=str(row["campaign_id"]),
        title=row["title"],
        status=row["status"],
        product_name=row["product_name"],
        deliverables_description=row["deliverables_description"],
        payout_cents=row["payout_cents"],
        invite_expires_at=row["invite_expires_at"].isoformat() if row["invite_expires_at"] else None,
        start_date=row["start_date"].isoformat(),
        end_date=row["end_date"].isoformat(),
        parent_approval_status=row.get("parent_approval_status", "not_required"),
    )


@router.get("/me", response_model=RepProfile)
def get_me(user: CurrentUser = Depends(require_active_rep), settings: Settings = Depends(get_settings)) -> dict:
    with get_connection(settings) as conn:
        profile = rep_service.get_rep_profile_by_user_id(conn, user.id)
    return profile


@router.put("/me", response_model=RepProfile)
def update_me(
    body: RepProfileUpdate,
    user: CurrentUser = Depends(require_active_rep),
    settings: Settings = Depends(get_settings),
) -> dict:
    with get_connection(settings) as conn:
        return rep_service.update_rep_profile(conn, user.id, body.model_dump(exclude_unset=True))


@router.get("/me/profile-preview", response_model=ProfilePreview)
def get_profile_preview(
    user: CurrentUser = Depends(require_active_rep), settings: Settings = Depends(get_settings)
) -> dict:
    with get_connection(settings) as conn:
        profile = rep_service.get_rep_profile_by_user_id(conn, user.id)
    return rep_service.profile_preview(profile)


@router.get("/campaigns/available", response_model=list[CampaignSummary])
def get_campaigns_available(
    user: CurrentUser = Depends(require_active_rep), settings: Settings = Depends(get_settings)
) -> list:
    with get_connection(settings) as conn:
        profile = rep_service.get_rep_profile_by_user_id(conn, user.id)
        campaigns = rep_service.campaigns_available(conn, profile)
    return [
        CampaignSummary(
            campaign_reps_id="",
            campaign_id=str(c["id"]),
            title=c["title"],
            status=c["status"],
            product_name=c["product_name"],
            deliverables_description=c["deliverables_description"],
            payout_cents=c["payout_per_rep_cents"],
            start_date=c["start_date"].isoformat(),
            end_date=c["end_date"].isoformat(),
        )
        for c in campaigns
    ]


@router.get("/campaigns/active", response_model=list[CampaignSummary])
def get_campaigns_active(
    user: CurrentUser = Depends(require_active_rep), settings: Settings = Depends(get_settings)
) -> list:
    with get_connection(settings) as conn:
        profile = rep_service.get_rep_profile_by_user_id(conn, user.id)
        rows = rep_service.campaigns_active(conn, profile["id"])
    return [_serialize_campaign(r) for r in rows]


@router.get("/campaigns/history", response_model=list[CampaignSummary])
def get_campaigns_history(
    user: CurrentUser = Depends(require_active_rep), settings: Settings = Depends(get_settings)
) -> list:
    with get_connection(settings) as conn:
        profile = rep_service.get_rep_profile_by_user_id(conn, user.id)
        rows = rep_service.campaigns_history(conn, profile["id"])
    return [_serialize_campaign(r) for r in rows]


@router.get("/earnings", response_model=EarningsBreakdown)
def get_earnings(
    user: CurrentUser = Depends(require_active_rep), settings: Settings = Depends(get_settings)
) -> dict:
    with get_connection(settings) as conn:
        profile = rep_service.get_rep_profile_by_user_id(conn, user.id)
        return rep_service.earnings_breakdown(conn, profile["id"])
