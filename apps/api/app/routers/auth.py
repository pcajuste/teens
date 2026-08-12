"""Auth routes -- signup, parental consent, current-user (Prompt 4).

Section 8's Auth Routes, implemented literally. This is the single
highest-legal-risk surface in the spec (Section 9), so every branch of
the age-gate/consent state machine has a dedicated exception type in
app.services.auth_service and a dedicated pytest case in
app/tests/test_auth.py -- no branch is inferred/left implicit here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.core.db import get_connection
from app.core.security import CurrentUser, get_current_user
from app.schemas.auth import MeResponse, ResendConsentRequest, SignupRequest, SignupResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, settings: Settings = Depends(get_settings)) -> SignupResponse:
    try:
        with get_connection(settings) as conn:
            result = auth_service.signup(
                conn,
                settings,
                email=body.email,
                password=body.password,
                role=body.role,
                date_of_birth=body.date_of_birth,
                parent_email=body.parent_email,
            )
    except auth_service.AgeNotPermittedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except auth_service.ParentEmailRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except auth_service.EmailAlreadyRegisteredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return SignupResponse(
        user_id=result.user_id, email=result.email, role=result.role, account_status=result.account_status
    )


@router.post("/parent-verify/{token}")
def parent_verify(token: str, settings: Settings = Depends(get_settings)) -> dict:
    try:
        with get_connection(settings) as conn:
            user_id = auth_service.verify_parent_token(conn, token)
    except auth_service.TokenInvalidError as exc:
        # Distinct status per state (not just distinct messages) so the
        # frontend can branch without string-matching: 400 invalid,
        # 409 already used, 410 expired.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except auth_service.TokenAlreadyUsedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except auth_service.TokenExpiredError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc)) from exc

    return {"user_id": user_id, "account_status": "active"}


@router.post("/resend-consent", status_code=status.HTTP_202_ACCEPTED)
def resend_consent(body: ResendConsentRequest, settings: Settings = Depends(get_settings)) -> dict:
    try:
        with get_connection(settings) as conn:
            auth_service.resend_consent(conn, settings, email=body.email)
    except auth_service.ResendRateLimitedError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Please wait before requesting another consent email (retry in {exc.retry_after_seconds}s)",
        ) from exc

    return {"status": "sent_if_eligible"}


@router.get("/me", response_model=MeResponse)
def me(user: CurrentUser = Depends(get_current_user), settings: Settings = Depends(get_settings)) -> MeResponse:
    with get_connection(settings) as conn:
        row = auth_service.get_user_by_id(conn, user.id)

    return MeResponse(
        id=str(row["id"]),
        email=row["email"],
        role=row["role"],
        account_status=row["account_status"],
        pending_reason=auth_service.pending_reason(row),
    )
