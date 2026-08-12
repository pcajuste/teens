"""Parent magic-link authentication.

Two distinct tokens (see app/core/security.py's module docstring):
1. The magic-link token itself -- a random value, hashed with SHA-256
   before storage in parent_auth_tokens, 15-minute expiry (schema
   comment: "login link, not session").
2. The parent session token issued after a successful verify -- an
   HS256 JWT signed with PARENT_SESSION_SECRET, 24-hour expiry (a
   "check in on my kid" session is reasonably long-lived; it's
   re-validated against portal_expires_at on every request regardless,
   via app.core.security.get_active_parent_session).
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import asyncpg
import jwt
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.core.security import PARENT_SESSION_ISSUER
from app.db.pool import get_connection
from app.repositories import parent_auth_tokens_repository, parent_records_repository
from app.schemas.parent import (
    RequestLinkRequest,
    RequestLinkResponse,
    VerifyResponse,
)
from app.services.email_service import send_magic_link_email
from app.services.resend_client import ResendClient
from app.services.resend_client import resend_client_dependency as _resend_client_dependency

router = APIRouter(prefix="/parent/auth", tags=["parent-auth"])

MAGIC_LINK_TTL = timedelta(minutes=15)
SESSION_TTL = timedelta(hours=24)

# Same reasoning as /auth/resend-consent's cooldown (Prompt 4): this
# emails a parent, tracked in Postgres so it holds under >1 API
# instance.
REQUEST_LINK_COOLDOWN = timedelta(minutes=5)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@router.post("/request-link", response_model=RequestLinkResponse)
async def request_link(
    body: RequestLinkRequest,
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_connection),
    resend_client: ResendClient = Depends(_resend_client_dependency),
) -> RequestLinkResponse:
    # Same-response-regardless-of-existence: never confirm whether this
    # email is linked to a parent_record (Section 9A: "no enumeration
    # via parent login").
    parent = await parent_records_repository.get_most_recent_parent_by_email(conn, body.parent_email)
    if parent is None:
        return RequestLinkResponse(status="sent")

    now = datetime.now(timezone.utc)
    if (
        parent.magic_link_last_requested_at is not None
        and now - parent.magic_link_last_requested_at < REQUEST_LINK_COOLDOWN
    ):
        # Still don't reveal existence -- rate-limit silently rather
        # than returning 429 (a 429 here would itself confirm the
        # email is linked to a parent_record).
        return RequestLinkResponse(status="sent")

    token = secrets.token_urlsafe(32)
    await parent_auth_tokens_repository.create_token(
        conn,
        parent_record_id=parent.parent_id,
        token_hash=_hash_token(token),
        expires_at=now + MAGIC_LINK_TTL,
    )
    await parent_records_repository.update_magic_link_last_requested_at(conn, parent.parent_id, at=now)

    magic_link = f"{settings.next_public_app_url}/parent/verify/{token}"
    await send_magic_link_email(parent.parent_email, magic_link, resend_client)

    return RequestLinkResponse(status="sent")


@router.get("/verify/{token}", response_model=VerifyResponse)
async def verify(
    token: str,
    settings: Settings = Depends(get_settings),
    conn: asyncpg.Connection = Depends(get_connection),
) -> VerifyResponse:
    token_hash = _hash_token(token)
    record = await parent_auth_tokens_repository.get_by_token_hash(conn, token_hash)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_magic_link", "message": "This sign-in link is invalid."},
        )
    if record.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "magic_link_already_used", "message": "This sign-in link has already been used."},
        )
    now = datetime.now(timezone.utc)
    if record.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "magic_link_expired", "message": "This sign-in link has expired."},
        )

    parent = await parent_records_repository.get_parent_by_id(conn, record.parent_record_id)
    if parent is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_magic_link", "message": "This sign-in link is invalid."},
        )

    # Portal expiry, enforced here too (not only on subsequent
    # requests) -- a parent shouldn't even get a session once the
    # rep has turned 18.
    if now >= parent.portal_expires_at:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "portal_closed",
                "message": "The parent portal has closed because your child is now 18.",
            },
        )

    await parent_auth_tokens_repository.mark_used(conn, record.id, used_at=now)

    session_payload = {
        "parent_id": parent.parent_id,
        "rep_id": parent.rep_id,
        "iss": PARENT_SESSION_ISSUER,
        "iat": int(now.timestamp()),
        "exp": int((now + SESSION_TTL).timestamp()),
    }
    session_token = jwt.encode(session_payload, settings.parent_session_secret, algorithm="HS256")

    return VerifyResponse(session_token=session_token, expires_at=now + SESSION_TTL)
