"""Parent session token verification (Prompt 4A).

Parents are not `auth.users` -- they authenticate via a magic-link
email flow (`app.services.parent_service`) and are issued a **stateless,
signed session token**, not a Supabase JWT:

  - Format: JWT, HS256, signed with `PARENT_SESSION_SECRET` (a new env
    var, distinct from `SUPABASE_JWT_SECRET` since this token is never
    issued by Supabase).
  - Claims: `{parent_record_id, rep_id, exp}`.
  - Expiry: 24 hours from issuance (`PARENT_SESSION_TTL_HOURS`) -- long
    enough for a "check in on my kid" use case without the same
    always-on-session expectations a rep/brand has.
  - Nothing further is stored server-side for the session itself; only
    the one-time login link (`parent_auth_tokens`) needs a DB row, so it
    can be marked used / rate-limited.

Every `/parent/*` route depends on `require_parent_session`, which also
enforces **portal expiry at 18** (deliverable 8) -- checked live against
`parent_records.portal_expires_at` on every call, not just baked into
the token at issuance, so a still-valid-looking 24h session token can't
outlive the rep's 18th birthday mid-session.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.core.constants import PARENT_SESSION_TTL_HOURS

parent_bearer_scheme = HTTPBearer(auto_error=False)


class ParentAuthError(HTTPException):
    """401: missing/invalid/expired parent session token."""

    def __init__(self, message: str = "Not authenticated") -> None:
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=message)


class PortalClosedError(HTTPException):
    """A distinct, non-generic response when the rep has turned 18."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This parent portal has closed because your child is now an adult.",
        )


@dataclass
class ParentSession:
    parent_record_id: str
    rep_id: str


def issue_parent_session_token(*, parent_record_id: str, rep_id: str, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "parent_record_id": parent_record_id,
        "rep_id": rep_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=PARENT_SESSION_TTL_HOURS)).timestamp()),
    }
    return jwt.encode(payload, settings.parent_session_secret, algorithm="HS256")


def decode_parent_session_token(token: str, settings: Settings) -> dict:
    try:
        return jwt.decode(token, settings.parent_session_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise ParentAuthError("Invalid or expired session") from exc


def load_parent_record(parent_record_id: str, settings: Settings) -> dict | None:
    """Single seam (real DB call) so route tests can monkeypatch it --
    same pattern as app.core.security.load_user_row.
    """
    from app.core.db import get_connection

    with get_connection(settings) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM public.parent_records WHERE id = %s",
            (parent_record_id,),
        )
        row = cur.fetchone()
    return dict(row) if row is not None else None


def require_parent_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(parent_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> ParentSession:
    if credentials is None or not credentials.credentials:
        raise ParentAuthError("Missing Authorization header")

    payload = decode_parent_session_token(credentials.credentials, settings)
    parent_record_id = payload.get("parent_record_id")
    rep_id = payload.get("rep_id")
    if not parent_record_id or not rep_id:
        raise ParentAuthError("Session token missing required claims")

    record = load_parent_record(parent_record_id, settings)
    if record is None:
        raise ParentAuthError("Parent record no longer exists")

    # Portal expiry at 18 (deliverable 8): enforced live, every call --
    # not just at token issuance or record creation.
    if datetime.now(timezone.utc) > record["portal_expires_at"]:
        raise PortalClosedError()

    return ParentSession(parent_record_id=str(record["id"]), rep_id=str(record["rep_id"]))
