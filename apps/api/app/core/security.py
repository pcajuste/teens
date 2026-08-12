"""Supabase JWT verification and role/account-status enforcement (Prompt 3).

Per Section 8: every route requires `Authorization: Bearer <supabase_jwt>`
unless explicitly marked [PUBLIC] in the spec (public routes simply don't
depend on `get_current_user`). A rep hitting a brand-only endpoint must
get 403, not 401 — 401 is reserved for "no/invalid credentials at all."
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings

bearer_scheme = HTTPBearer(auto_error=False)


class AuthError(HTTPException):
    """401: missing, malformed, or invalid/expired credentials."""

    def __init__(self, message: str = "Not authenticated") -> None:
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=message)


class ForbiddenError(HTTPException):
    """403: valid credentials, but not allowed to do this."""

    def __init__(self, message: str) -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=message)


@dataclass
class CurrentUser:
    """The authenticated principal, loaded from public.users.

    id/email come from the verified JWT; role/account_status come from
    the public.users row itself (never from JWT claims) since those are
    the fields Section 9's compliance rules actually gate on and must
    reflect the current database state, not a token issued minutes ago.
    """

    id: str
    email: str
    role: str
    account_status: str


def decode_supabase_jwt(token: str, settings: Settings) -> dict:
    try:
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid or expired token") from exc


def load_user_row(user_id: str, settings: Settings) -> dict | None:
    """Load {id, email, role, account_status} from public.users.

    Kept as a single seam (real DB call) so route tests can monkeypatch
    it in-process without needing a live database -- see
    app/tests/conftest.py's `client` fixture.
    """
    from app.core.db import get_connection

    with get_connection(settings) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, email, role, account_status FROM public.users WHERE id = %s",
            (user_id,),
        )
        row = cur.fetchone()
    return dict(row) if row is not None else None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    if credentials is None or not credentials.credentials:
        raise AuthError("Missing Authorization header")

    payload = decode_supabase_jwt(credentials.credentials, settings)
    user_id = payload.get("sub")
    if not user_id:
        raise AuthError("Token missing subject claim")

    row = load_user_row(user_id, settings)
    if row is None:
        raise AuthError("User not found")

    return CurrentUser(
        id=row["id"],
        email=row["email"],
        role=row["role"],
        account_status=row["account_status"],
    )


def require_role(*allowed_roles: str) -> Callable[[CurrentUser], CurrentUser]:
    """Dependency factory: 403 if the current user's role isn't allowed.

    Usage: `user: CurrentUser = Depends(require_role("brand"))`.
    """

    def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in allowed_roles:
            raise ForbiddenError(
                f"Role '{user.role}' is not permitted to access this resource"
            )
        return user

    return dependency


def require_active_account(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """403 (distinct from role mismatch) if the account isn't 'active'.

    Covers 'pending' (parental consent or admin approval still
    outstanding), 'suspended', and 'rejected' — none of those states
    should be able to reach routes gated behind this dependency.
    """
    if user.account_status != "active":
        raise ForbiddenError(
            f"Account status '{user.account_status}' does not permit this action"
        )
    return user


def require_role_and_active(*allowed_roles: str) -> Callable[[CurrentUser], CurrentUser]:
    """Convenience combinator for the common "right role AND active" case."""

    def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in allowed_roles:
            raise ForbiddenError(
                f"Role '{user.role}' is not permitted to access this resource"
            )
        if user.account_status != "active":
            raise ForbiddenError(
                f"Account status '{user.account_status}' does not permit this action"
            )
        return user

    return dependency
