from __future__ import annotations

from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.core.db import get_connection
from app.core.security import CurrentUser, require_role_and_active
from app.schemas.rep import AcceptRequest, SubmitRequest
from app.services import rep_service, storage_service

router = APIRouter(prefix="/campaigns", tags=["campaigns"])

require_active_rep = require_role_and_active("rep")


class UploadUrlRequest(BaseModel):
    file_name: str
    content_type: str
    file_size_bytes: int


def _rep_profile(conn, user_id: str) -> dict:
    return rep_service.get_rep_profile_by_user_id(conn, user_id)


@router.post("/{campaign_id}/apply", status_code=status.HTTP_201_CREATED)
def apply(campaign_id: str, user: CurrentUser = Depends(require_active_rep), settings: Settings = Depends(get_settings)) -> dict:
    with get_connection(settings) as conn:
        rep = _rep_profile(conn, user.id)
        try:
            row = rep_service.apply_to_campaign(conn, rep, campaign_id)
        except rep_service.CampaignNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found") from exc
        except rep_service.CampaignNotEligibleError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except rep_service.AlreadyAppliedError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return {"campaign_reps_id": str(row["id"]), "status": row["status"]}


@router.post("/{campaign_id}/accept")
def accept(
    campaign_id: str,
    body: AcceptRequest,
    user: CurrentUser = Depends(require_active_rep),
    settings: Settings = Depends(get_settings),
) -> dict:
    with get_connection(settings) as conn:
        rep = _rep_profile(conn, user.id)
        try:
            row = rep_service.accept_invite(conn, rep["id"], campaign_id, body.ftc_disclosure_accepted)
        except rep_service.InviteNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No invite found for this campaign") from exc
        except rep_service.IllegalTransitionError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        except rep_service.AwaitingParentApprovalError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        except rep_service.FtcDisclosureRequiredError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"campaign_reps_id": str(row["id"]), "status": row["status"]}


@router.post("/{campaign_id}/decline")
def decline(campaign_id: str, user: CurrentUser = Depends(require_active_rep), settings: Settings = Depends(get_settings)) -> dict:
    with get_connection(settings) as conn:
        rep = _rep_profile(conn, user.id)
        try:
            row = rep_service.decline_invite(conn, rep["id"], campaign_id)
        except rep_service.InviteNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No invite found for this campaign") from exc
        except rep_service.IllegalTransitionError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return {"campaign_reps_id": str(row["id"]), "status": row["status"]}


@router.post("/{campaign_id}/withdraw")
def withdraw(campaign_id: str, user: CurrentUser = Depends(require_active_rep), settings: Settings = Depends(get_settings)) -> dict:
    """Prompt 5 deliverable 9 / Prompt 4A retrofit deliverable 9:
    one-tap withdrawal at any point where it's still meaningful, no
    penalty, no explanation required.
    """
    with get_connection(settings) as conn:
        rep = _rep_profile(conn, user.id)
        try:
            row = rep_service.withdraw_campaign(conn, rep["id"], campaign_id)
        except rep_service.InviteNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No invite found for this campaign") from exc
        except rep_service.IllegalTransitionError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return {"campaign_reps_id": str(row["id"]), "status": row["status"]}


@router.post("/{campaign_id}/submit")
def submit(
    campaign_id: str,
    body: SubmitRequest,
    user: CurrentUser = Depends(require_active_rep),
    settings: Settings = Depends(get_settings),
) -> dict:
    with get_connection(settings) as conn:
        rep = _rep_profile(conn, user.id)
        try:
            row = rep_service.submit_campaign(
                conn,
                rep["id"],
                campaign_id,
                submission_text=body.submission_text,
                submission_file_urls=body.submission_file_urls,
            )
        except rep_service.InviteNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No invite found for this campaign") from exc
        except rep_service.IllegalTransitionError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        except rep_service.FtcDisclosureRequiredError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"campaign_reps_id": str(row["id"]), "status": row["status"]}


@router.post("/{campaign_id}/upload-url")
def upload_url(
    campaign_id: str,
    body: UploadUrlRequest,
    user: CurrentUser = Depends(require_active_rep),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Addition beyond Section 8's literal route list -- see
    app.services.storage_service's module docstring for why this is
    needed before /submit can be called with real file URLs.
    """
    with get_connection(settings) as conn:
        rep = _rep_profile(conn, user.id)
        cr = rep_service._get_campaign_rep(conn, campaign_id, rep["id"])
        if cr is None or cr["status"] not in ("accepted", "revision_requested"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You may only upload files for a campaign you're actively accepted on",
            )
    try:
        return storage_service.create_signed_upload_url(
            campaign_id=campaign_id,
            rep_id=rep["id"],
            file_name=body.file_name,
            content_type=body.content_type,
            file_size_bytes=body.file_size_bytes,
            settings=settings,
        )
    except storage_service.UploadValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except storage_service.StorageError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
