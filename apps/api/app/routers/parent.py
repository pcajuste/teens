"""Parent Portal routes (Prompt 4A / Section 9A).

All routes except request-link/verify require a valid parent session
token via `require_parent_session` (app.core.parent_security) -- the
Prompt 3-style dependency, parented specifically for the non-Supabase
parent auth flow.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.core.db import get_connection
from app.core.parent_security import ParentSession, PortalClosedError, require_parent_session
from app.schemas.parent import (
    ApprovalRequiredUpdate,
    DigestPreview,
    DigestSettingUpdate,
    ParentSessionResponse,
    ParentSettings,
    PendingCampaignBrief,
    RepSummary,
    RequestLinkRequest,
    ValuesFiltersUpdate,
)
from app.services import parent_service

router = APIRouter(prefix="/parent", tags=["parent"])


@router.post("/auth/request-link", status_code=status.HTTP_202_ACCEPTED)
def request_link(body: RequestLinkRequest, settings: Settings = Depends(get_settings)) -> dict:
    try:
        with get_connection(settings) as conn:
            parent_service.request_link(conn, settings, parent_email=body.parent_email)
    except parent_service.RateLimitedError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Please wait before requesting another login link (retry in {exc.retry_after_seconds}s)",
        ) from exc
    # Always the same response, whether or not the email is linked to a
    # parent_records row -- prevents enumeration.
    return {"status": "sent_if_eligible"}


@router.get("/auth/verify/{token}", response_model=ParentSessionResponse)
def verify(token: str, settings: Settings = Depends(get_settings)) -> ParentSessionResponse:
    try:
        with get_connection(settings) as conn:
            session_token, rep_id = parent_service.verify_token(conn, settings, token=token)
    except parent_service.TokenInvalidError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except parent_service.TokenAlreadyUsedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except parent_service.TokenExpiredError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc)) from exc
    except parent_service.PortalClosedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This parent portal has closed because your child is now an adult.",
        ) from exc

    return ParentSessionResponse(session_token=session_token, rep_id=rep_id)


@router.get("/dashboard", response_model=RepSummary)
def dashboard(
    session: ParentSession = Depends(require_parent_session), settings: Settings = Depends(get_settings)
) -> dict:
    with get_connection(settings) as conn:
        return parent_service.get_dashboard(conn, session.rep_id)


@router.get("/campaigns/pending", response_model=list[PendingCampaignBrief])
def campaigns_pending(
    session: ParentSession = Depends(require_parent_session), settings: Settings = Depends(get_settings)
) -> list:
    with get_connection(settings) as conn:
        rows = parent_service.pending_campaigns(conn, session.rep_id)
    return [
        PendingCampaignBrief(
            campaign_reps_id=str(r["campaign_reps_id"]),
            campaign_id=str(r["campaign_id"]),
            brand_name=r["brand_name"],
            product_name=r["product_name"],
            key_messaging=r["key_messaging"],
            deliverables_description=r["deliverables_description"],
            prohibited_content=r["prohibited_content"],
            payout_cents=r["payout_cents"],
            start_date=r["start_date"].isoformat(),
            end_date=r["end_date"].isoformat(),
            requires_in_person=r["requires_in_person"],
            parent_approval_deadline=r["parent_approval_deadline"].isoformat()
            if r["parent_approval_deadline"]
            else None,
        )
        for r in rows
    ]


@router.post("/campaigns/{campaign_id}/approve")
def approve_campaign(
    campaign_id: str,
    session: ParentSession = Depends(require_parent_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    with get_connection(settings) as conn:
        try:
            row = parent_service.approve_campaign(conn, session.rep_id, campaign_id)
        except parent_service.CampaignNotPendingError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending invitation found") from exc
    return {"campaign_reps_id": str(row["id"]), "parent_approval_status": row["parent_approval_status"]}


@router.post("/campaigns/{campaign_id}/block")
def block_campaign(
    campaign_id: str,
    session: ParentSession = Depends(require_parent_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    with get_connection(settings) as conn:
        try:
            row = parent_service.block_campaign(conn, session.rep_id, campaign_id)
        except parent_service.CampaignNotPendingError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending invitation found") from exc
    return {"campaign_reps_id": str(row["id"]), "parent_approval_status": row["parent_approval_status"]}


@router.get("/settings", response_model=ParentSettings)
def get_settings_route(
    session: ParentSession = Depends(require_parent_session), settings: Settings = Depends(get_settings)
) -> dict:
    with get_connection(settings) as conn:
        return parent_service.get_parent_settings(conn, session.parent_record_id)


@router.put("/settings/values-filters", response_model=ParentSettings)
def put_values_filters(
    body: ValuesFiltersUpdate,
    session: ParentSession = Depends(require_parent_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    with get_connection(settings) as conn:
        return parent_service.update_values_filters(conn, session.parent_record_id, body.values_filters)


@router.put("/settings/approval-required", response_model=ParentSettings)
def put_approval_required(
    body: ApprovalRequiredUpdate,
    session: ParentSession = Depends(require_parent_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    with get_connection(settings) as conn:
        try:
            return parent_service.update_approval_required(
                conn, session.parent_record_id, session.rep_id,
                campaign_approval_required=body.campaign_approval_required,
            )
        except parent_service.ApprovalToggleNotPermittedError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.put("/settings/digest", response_model=ParentSettings)
def put_digest(
    body: DigestSettingUpdate,
    session: ParentSession = Depends(require_parent_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    with get_connection(settings) as conn:
        return parent_service.update_digest_enabled(conn, session.parent_record_id, body.digest_enabled)


@router.get("/digest/preview", response_model=DigestPreview)
def digest_preview(
    session: ParentSession = Depends(require_parent_session), settings: Settings = Depends(get_settings)
) -> dict:
    with get_connection(settings) as conn:
        return parent_service.digest_preview(conn, session.rep_id)


@router.post("/account/suspend")
def suspend(
    session: ParentSession = Depends(require_parent_session), settings: Settings = Depends(get_settings)
) -> dict:
    with get_connection(settings) as conn:
        parent_service.suspend_account(
            conn, settings, parent_record_id=session.parent_record_id, rep_id=session.rep_id
        )
    return {"status": "suspended"}


@router.post("/account/unsuspend")
def unsuspend(
    session: ParentSession = Depends(require_parent_session), settings: Settings = Depends(get_settings)
) -> dict:
    with get_connection(settings) as conn:
        try:
            parent_service.unsuspend_account(conn, session.parent_record_id, session.rep_id)
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return {"status": "active"}
