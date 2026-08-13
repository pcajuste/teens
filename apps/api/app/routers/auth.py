"""Auth routes: signup, parental-consent verification, consent resend,
and the current-user endpoint. This is the highest-legal-risk surface
in the platform (COPPA-style age gate + parental consent) -- every
branch below is covered by tests/test_auth.py, one test per acceptance
criterion in Build Prompt 4.

parent_records is deliberately NOT created here -- see
docs/parent_records_creation_timing.md for why (FK to talent_profiles,
which doesn't exist until Prompt 5).
"""
from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta, timezone

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.age import compute_age
from app.core.config import Settings, get_settings
from app.core.security import AuthenticatedUser, get_current_user
from app.db.pool import get_connection
from app.repositories.users_repository import (
    create_user,
    get_user_by_consent_token,
    get_user_by_email,
    mark_consent_email_sent,
    mark_parent_verified_and_activate,
    set_consent_token,
)
from app.schemas.auth import (
    MeResponse,
    ParentVerifyResponse,
    ResendConsentRequest,
    ResendConsentResponse,
    SignupRequest,
    SignupResponse,
)
from app.services.email_service import send_parental_consent_email
from app.services.resend_client import ResendClient
from app.services.resend_client import resend_client_dependency as _resend_client_dependency
from app.services.supabase_auth_client import EmailAlreadyRegisteredError, get_supabase_auth_client

router = APIRouter(prefix="/auth", tags=["auth"])

CONSENT_TOKEN_TTL = timedelta(hours=72)

# A parent's inbox is a third party, not the signer of this request --
# rate-limit resend on a per-account cooldown so /auth/resend-consent
# can't be used to spam a parent. 5 minutes is generous enough for a
# genuine "I fat-fingered the email" retry while making an abuse loop
# impractical. Tracked in Postgres (consent_email_last_sent_at), not
# in-process memory, so it's correct if apps/api ever runs >1 instance.
RESEND_COOLDOWN = timedelta(minutes=5)


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    body: SignupRequest,
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_connection),
    resend_client: ResendClient = Depends(_resend_client_dependency),
) -> SignupResponse:
    today = date.today()  # server-side only -- never trust a client-computed age
    age = compute_age(body.date_of_birth, today=today)

    if age < settings.min_talent_age:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "age_not_permitted", "message": f"You must be at least {settings.min_talent_age} to sign up for Teenure."},
        )

    requires_parental_consent = body.role == "talent" and age < settings.parental_consent_required_under
    if requires_parental_consent and not body.parent_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "parent_email_required", "message": "parent_email is required for talents under 16."},
        )

    if body.role != "talent":
        # Brands and recruiters always land pending admin approval,
        # regardless of age (Section 8).
        account_status = "pending"
    elif requires_parental_consent:
        account_status = "pending"
    else:
        # 16-17 and 18+ talents both activate immediately; the difference
        # (parent_record with campaign-approval gating for 16-17) is a
        # Prompt 5 concern once talent_profiles exists -- see the design
        # note referenced in this module's docstring.
        account_status = "active"

    consent_token: str | None = None
    consent_token_issued_at: datetime | None = None
    if requires_parental_consent:
        consent_token = secrets.token_urlsafe(32)
        consent_token_issued_at = datetime.now(timezone.utc)

    auth_client = get_supabase_auth_client(settings, conn)
    app_metadata = {"role": body.role, "account_status": account_status}

    async with conn.transaction():
        try:
            auth_user = await auth_client.create_user(
                email=body.email, password=body.password, app_metadata=app_metadata
            )
        except EmailAlreadyRegisteredError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "email_already_registered", "message": str(exc)},
            ) from exc

        try:
            user = await create_user(
                conn,
                user_id=auth_user.id,
                email=body.email,
                role=body.role,
                account_status=account_status,
                date_of_birth=body.date_of_birth,
                parent_email=body.parent_email,
                consent_token=consent_token,
                consent_token_issued_at=consent_token_issued_at,
            )
        except asyncpg.UniqueViolationError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "email_already_registered", "message": f"{body.email} is already registered"},
            ) from exc

    if requires_parental_consent:
        assert consent_token is not None
        consent_link = f"{settings.next_public_app_url}/parent/consent/{consent_token}"
        await send_parental_consent_email(body.parent_email, consent_link, resend_client)
        await mark_consent_email_sent(conn, user.id, sent_at=datetime.now(timezone.utc))

    return SignupResponse(id=user.id, email=user.email, role=user.role, account_status=user.account_status)


@router.post("/parent-verify/{token}", response_model=ParentVerifyResponse)
async def parent_verify(
    token: str,
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_connection),
) -> ParentVerifyResponse:
    user = await get_user_by_consent_token(conn, token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "invalid_token", "message": "No signup found for this consent link."},
        )

    if user.parent_verified_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "token_already_used", "message": "This consent link has already been used."},
        )

    issued_at = user.consent_token_issued_at
    if issued_at is None or datetime.now(timezone.utc) - issued_at > CONSENT_TOKEN_TTL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "token_expired", "message": "This consent link has expired. Ask your teen to request a new one."},
        )

    verified_at = datetime.now(timezone.utc)
    updated = await mark_parent_verified_and_activate(conn, user.id, verified_at=verified_at)

    auth_client = get_supabase_auth_client(settings, conn)
    await auth_client.update_app_metadata(user.id, {"role": updated.role, "account_status": "active"})

    return ParentVerifyResponse(account_status=updated.account_status, parent_verified_at=updated.parent_verified_at)


@router.post("/resend-consent", response_model=ResendConsentResponse)
async def resend_consent(
    body: ResendConsentRequest,
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_connection),
    resend_client: ResendClient = Depends(_resend_client_dependency),
) -> ResendConsentResponse:
    user = await get_user_by_email(conn, body.email)

    # Same-response -regardless-of-existence principle Section 9A applies
    # to parent-portal auth ("no enumeration via parent login") -- this
    # also emails a third party, so it gets the same treatment.
    if user is None or user.consent_token is None or user.parent_verified_at is not None:
        return ResendConsentResponse(status="sent")

    now = datetime.now(timezone.utc)
    if user.consent_email_last_sent_at is not None and now - user.consent_email_last_sent_at < RESEND_COOLDOWN:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "resend_rate_limited", "message": "Please wait a few minutes before requesting another consent email."},
        )

    # Rotate the token on resend so a previously-sent (possibly leaked
    # or stale) link stops working once a fresh one is issued.
    new_token = secrets.token_urlsafe(32)
    await set_consent_token(conn, user.id, consent_token=new_token, issued_at=now)

    assert user.parent_email is not None
    consent_link = f"{settings.next_public_app_url}/parent/consent/{new_token}"
    await send_parental_consent_email(user.parent_email, consent_link, resend_client)
    await mark_consent_email_sent(conn, user.id, sent_at=now)

    return ResendConsentResponse(status="sent")


@router.get("/me", response_model=MeResponse)
async def me(user: AuthenticatedUser = Depends(get_current_user)) -> MeResponse:
    pending_reason = None
    if user.account_status == "pending":
        pending_reason = "awaiting_parental_consent" if user.role == "talent" else "pending_admin_approval"

    return MeResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        account_status=user.account_status,
        pending_reason=pending_reason,
    )
