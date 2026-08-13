"""Auth dependencies: Supabase JWT verification, role/account-status
enforcement, and the separate parent-session mechanism.

Two distinct token types flow through this module:

1. Supabase JWTs (HS256, signed with SUPABASE_JWT_SECRET) — issued to
   talents/brands/recruiters/admins on login. `role` and `account_status`
   are read from the token's `app_metadata` claim, which
   app/services/supabase_auth_client.py sets directly via Supabase's
   Auth Admin API at account creation and updates the same way
   whenever `public.users.account_status` changes (e.g. Prompt 4's
   parent-verify flipping pending -> active) — no DB-side sync trigger
   needed, since the Admin API manages `app_metadata` natively. This
   avoids a DB round-trip on every request; a status change takes
   effect on the user's next token refresh, matching Supabase's
   standard session-refresh cadence.
2. Parent session tokens (HS256, signed with PARENT_SESSION_SECRET —
   a distinct secret) — issued when a parent clicks their magic-link
   email (Prompt 4A). Parents have no `auth.users` row (Section 7), so
   they are never issued a Supabase-signed JWT; this is a
   purpose-built, short-lived session token carrying only
   `parent_id`/`talent_id`, verified by `get_parent_session` and never
   accepted by `get_current_user`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from typing import Literal

import asyncpg
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.db.pool import get_connection

Role = Literal["talent", "brand", "recruiter", "admin"]
AccountStatus = Literal["pending", "active", "suspended", "rejected"]

_supabase_bearer = HTTPBearer(auto_error=False)
_parent_bearer = HTTPBearer(auto_error=False)

PARENT_SESSION_ISSUER = "teenure-parent-portal"

# Supabase now issues project JWTs signed with an asymmetric per-project
# key (ES256/RS256, verified via GoTrue's JWKS endpoint) by default,
# rather than the legacy HS256-with-shared-secret model. Both are still
# valid in practice -- our own test fixtures (tests/conftest.py) sign
# HS256 tokens directly with SUPABASE_JWT_SECRET, and a token with no
# `kid` header is always the legacy HS256 case -- so we branch on
# whether the token's header carries a `kid` rather than assuming one
# algorithm project-wide.
@lru_cache
def _jwks_client(supabase_url: str) -> PyJWKClient:
    return PyJWKClient(f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json")


class AuthenticatedUser(BaseModel):
    id: str
    email: str
    role: Role
    account_status: AccountStatus


class ParentSession(BaseModel):
    parent_id: str
    talent_id: str


def _unauthorized(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": code, "message": message},
    )


def _forbidden(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": code, "message": message},
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_supabase_bearer),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    if credentials is None:
        raise _unauthorized("missing_credentials", "Authorization: Bearer token required.")

    try:
        header = jwt.get_unverified_header(credentials.credentials)
        if header.get("kid") is None:
            # Legacy HS256 token, shared-secret verification.
            payload = jwt.decode(
                credentials.credentials,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
        else:
            # Modern Supabase asymmetric-key token, verified against
            # GoTrue's published JWKS.
            signing_key = _jwks_client(settings.next_public_supabase_url).get_signing_key_from_jwt(
                credentials.credentials
            )
            payload = jwt.decode(
                credentials.credentials,
                signing_key.key,
                algorithms=["ES256", "RS256"],
                audience="authenticated",
            )
    except jwt.PyJWTError as exc:
        raise _unauthorized("invalid_token", "Supabase JWT is invalid or expired.") from exc

    app_metadata = payload.get("app_metadata") or {}
    role = app_metadata.get("role")
    account_status = app_metadata.get("account_status")
    if not role or not account_status or "sub" not in payload:
        raise _unauthorized("malformed_token", "Token is missing required user claims.")

    return AuthenticatedUser(
        id=payload["sub"],
        email=payload.get("email", ""),
        role=role,
        account_status=account_status,
    )


def require_active_account(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    if user.account_status != "active":
        raise _forbidden(
            "account_not_active",
            f"Account status is '{user.account_status}', not 'active'.",
        )
    return user


def require_role(*roles: Role):
    """Dependency factory: 403 with code 'role_mismatch' unless the
    caller's role is one of `roles`. Applies the account-status check
    first, so a suspended user gets 'account_not_active' rather than a
    role-mismatch message that would leak nothing useful."""

    async def _dependency(user: AuthenticatedUser = Depends(require_active_account)) -> AuthenticatedUser:
        if user.role not in roles:
            raise _forbidden(
                "role_mismatch",
                f"Requires role in {sorted(roles)}, caller has '{user.role}'.",
            )
        return user

    return _dependency


def require_role_any_status(*roles: Role):
    """Same role check as require_role, but does NOT require
    account_status == 'active'. Every brand/recruiter signup lands
    account_status='pending' until Prompt 13's admin-approval flow
    exists (and even once it does, a brand is *reviewed on* their
    profile -- they can't submit one for review if submitting it
    requires already being approved). Use this only for routes that
    must work pre-approval, e.g. GET/PUT /brands/me -- money-moving or
    campaign-launching routes must keep using require_role, which still
    requires 'active'. Discovered as a real gap (not a hypothetical)
    while building the brand-portal frontend: a freshly signed-up brand
    could not reach PUT /brands/me at all, meaning no brand account
    could ever progress past signup."""

    async def _dependency(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if user.role not in roles:
            raise _forbidden(
                "role_mismatch",
                f"Requires role in {sorted(roles)}, caller has '{user.role}'.",
            )
        if user.account_status in ("suspended", "rejected"):
            raise _forbidden(
                "account_not_active",
                f"Account status is '{user.account_status}', not usable.",
            )
        return user

    return _dependency


async def get_parent_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(_parent_bearer),
    settings: Settings = Depends(get_settings),
) -> ParentSession:
    if credentials is None:
        raise _unauthorized("missing_parent_session", "Parent session token required.")

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.parent_session_secret,
            algorithms=["HS256"],
            issuer=PARENT_SESSION_ISSUER,
        )
    except jwt.PyJWTError as exc:
        raise _unauthorized("invalid_parent_session", "Parent session token is invalid or expired.") from exc

    parent_id = payload.get("parent_id")
    talent_id = payload.get("talent_id")
    if not parent_id or not talent_id:
        raise _unauthorized("malformed_parent_session", "Token is missing required parent-session claims.")

    return ParentSession(parent_id=parent_id, talent_id=talent_id)


async def get_active_parent_session(
    session: ParentSession = Depends(get_parent_session),
    conn: asyncpg.Connection = Depends(get_connection),
) -> ParentSession:
    """Re-checks portal_expires_at on every /parent/* request, not just
    at magic-link verification (Prompt 4A deliverable 8) -- a session
    token issued the day before a talent's 18th birthday is still a valid
    JWT the day after, so expiry has to be enforced against current
    parent_records state on every call, not baked into the token."""
    from app.repositories.parent_records_repository import get_parent_by_id

    parent = await get_parent_by_id(conn, session.parent_id)
    if parent is None or datetime.now(timezone.utc) >= parent.portal_expires_at:
        raise _forbidden(
            "portal_closed",
            "The parent portal has closed because your child is now 18.",
        )
    return session
