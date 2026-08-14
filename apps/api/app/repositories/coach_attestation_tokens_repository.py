"""Data access for public.coach_attestation_tokens.

Matches app/repositories/parent_auth_tokens_repository.py's pattern in
spirit -- single-use tokens with expiry, separate table, used_at
timestamp on consumption. Unlike parent_auth_tokens, the raw token is
stored here (not a hash) since the coach attestation token is delivered
via a link the coach clicks, not typed in -- the playbook's D7 decision
mirrors the codebase's existing separate-token-table shape without
requiring hashing at this trust level (school-athletics email context,
not a password-adjacent secret).

D8 decision: rate limiting enforced at the service/router layer by
counting how recently a token was last issued (hours_since_last_token).
At most one active token at a time per season; generating a new one
supersedes the previous (sets superseded_at = now()).
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

import asyncpg

TOKEN_TTL_HOURS = 72
MAX_ACTIVE_TOKENS_PER_SEASON = 1
MIN_HOURS_BEFORE_RESEND = 48   # D8: must wait 48h before requesting new token


@dataclass(frozen=True, slots=True)
class CoachAttestationToken:
    id: str
    athletic_season_id: str
    token: str
    coach_email: str
    expires_at: datetime
    used_at: datetime | None
    superseded_at: datetime | None
    created_at: datetime


def _from_row(row: asyncpg.Record) -> CoachAttestationToken:
    return CoachAttestationToken(
        id=str(row["id"]),
        athletic_season_id=str(row["athletic_season_id"]),
        token=row["token"],
        coach_email=row["coach_email"],
        expires_at=row["expires_at"],
        used_at=row["used_at"],
        superseded_at=row["superseded_at"],
        created_at=row["created_at"],
    )


async def get_active_token(
    conn: asyncpg.Connection, athletic_season_id: str
) -> CoachAttestationToken | None:
    """Returns the current active token for a season, or None if none exists
    (either no token was ever issued, or all tokens are used/superseded/expired)."""
    row = await conn.fetchrow(
        """
        SELECT id, athletic_season_id, token, coach_email, expires_at,
               used_at, superseded_at, created_at
        FROM public.coach_attestation_tokens
        WHERE athletic_season_id = $1
          AND used_at IS NULL
          AND superseded_at IS NULL
          AND expires_at > now()
        ORDER BY created_at DESC
        LIMIT 1
        """,
        athletic_season_id,
    )
    return _from_row(row) if row else None


async def hours_since_last_token(
    conn: asyncpg.Connection, athletic_season_id: str
) -> float | None:
    """Returns hours since the most recently created token for this season,
    regardless of status. None if no token has ever been issued.
    D8: callers use this to enforce the 48h resend minimum."""
    created_at = await conn.fetchval(
        """
        SELECT created_at FROM public.coach_attestation_tokens
        WHERE athletic_season_id = $1
        ORDER BY created_at DESC LIMIT 1
        """,
        athletic_season_id,
    )
    if created_at is None:
        return None
    elapsed = datetime.now(timezone.utc) - created_at
    return elapsed.total_seconds() / 3600


async def issue_token(
    conn: asyncpg.Connection,
    athletic_season_id: str,
    coach_email: str,
) -> CoachAttestationToken:
    """Issues a new token. Supersedes any existing active token first.
    D8: caller must verify MIN_HOURS_BEFORE_RESEND has elapsed if a
    prior token exists (via hours_since_last_token) before calling this."""
    await supersede_all_for_season(conn, athletic_season_id)
    token = secrets.token_urlsafe(24)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)
    row = await conn.fetchrow(
        """
        INSERT INTO public.coach_attestation_tokens
            (athletic_season_id, token, coach_email, expires_at)
        VALUES ($1, $2, $3, $4)
        RETURNING id, athletic_season_id, token, coach_email,
                  expires_at, used_at, superseded_at, created_at
        """,
        athletic_season_id, token, coach_email, expires_at,
    )
    return _from_row(row)


async def get_by_token(
    conn: asyncpg.Connection, token: str
) -> CoachAttestationToken | None:
    row = await conn.fetchrow(
        """
        SELECT id, athletic_season_id, token, coach_email, expires_at,
               used_at, superseded_at, created_at
        FROM public.coach_attestation_tokens
        WHERE token = $1
        """,
        token,
    )
    return _from_row(row) if row else None


async def consume_token(
    conn: asyncpg.Connection, token_id: str, *, at: datetime
) -> bool:
    """Marks token as used. Returns True if successfully consumed,
    False if already used/superseded/expired (idempotent)."""
    result = await conn.execute(
        """
        UPDATE public.coach_attestation_tokens
        SET used_at = $2
        WHERE id = $1
          AND used_at IS NULL
          AND superseded_at IS NULL
          AND expires_at > now()
        """,
        token_id, at,
    )
    return result == "UPDATE 1"


async def supersede_all_for_season(conn: asyncpg.Connection, athletic_season_id: str) -> None:
    """Sets superseded_at=now() on all active (not used, not already
    superseded, not expired) tokens for the season. Called both from
    issue_token (a fresh request supersedes the prior link) and from
    athletic_seasons_repository.withdraw_attestation_request (a
    withdrawn request invalidates any outstanding coach link)."""
    await conn.execute(
        """
        UPDATE public.coach_attestation_tokens
        SET superseded_at = now()
        WHERE athletic_season_id = $1
          AND used_at IS NULL
          AND superseded_at IS NULL
          AND expires_at > now()
        """,
        athletic_season_id,
    )
