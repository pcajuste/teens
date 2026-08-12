"""Signup / age-gate / parental-consent state machine (Prompt 4).

Implements Section 8's Auth Routes behavior table and Section 9's
parental-consent requirement literally:

  - age < 13                       -> blocked, no row created
  - age < 16                       -> parent_email required; 'pending',
                                       single-use consent_token emailed,
                                       72-hour expiry
  - age >= 16 and role == 'rep'    -> 'active' immediately
  - role in ('brand', 'recruiter') -> always 'pending' (admin approval),
                                       regardless of age -- this branch
                                       is checked before the parental-
                                       consent branch, per Section 8's
                                       literal ordering ("Brands and
                                       recruiters: always pending...").
                                       A brand/recruiter signup under 16
                                       is not realistically expected
                                       (these are business accounts),
                                       but if it happens they get the
                                       admin-approval pending reason,
                                       not the parent-consent one --
                                       there is no parent to consent for
                                       a business account.

Functions take an open psycopg connection and commit on success; the
caller (router) owns the connection lifecycle.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import psycopg

from app.core.config import Settings
from app.services import email_service, supabase_admin

CONSENT_TOKEN_TTL = timedelta(hours=72)

# Resend-consent is rate-limited because it emails a third party (the
# parent), who never asked to be on this platform's mailing list --
# unlimited resend would let anyone harass an arbitrary inbox by
# hammering /auth/resend-consent with a guessed/known rep email. A
# simple per-email cooldown is enough to stop that without needing a
# distributed rate limiter for a single-process MVP; move this to a
# shared store (Redis/DB) before running more than one API instance.
RESEND_COOLDOWN_SECONDS = 10 * 60
_last_resend_at: dict[str, float] = {}


class SignupError(Exception):
    """Base class for signup rejections that should map to a 4xx response."""


class AgeNotPermittedError(SignupError):
    """Age < 13 -- hard block, no account created."""


class ParentEmailRequiredError(SignupError):
    """Age < 16 (rep) and no parent_email supplied."""


class EmailAlreadyRegisteredError(SignupError):
    pass


class TokenError(Exception):
    """Base class for parent-verify/resend-consent token failures."""


class TokenInvalidError(TokenError):
    """Token doesn't match any user -- never issued, or superseded by a resend."""


class TokenExpiredError(TokenError):
    pass


class TokenAlreadyUsedError(TokenError):
    pass


class UserNotFoundError(Exception):
    pass


class ResendRateLimitedError(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Retry after {retry_after_seconds}s")


@dataclass
class SignupResult:
    user_id: str
    email: str
    role: str
    account_status: str


def calculate_age(date_of_birth: date, *, as_of: date | None = None) -> int:
    as_of = as_of or date.today()
    years = as_of.year - date_of_birth.year
    had_birthday = (as_of.month, as_of.day) >= (date_of_birth.month, date_of_birth.day)
    return years if had_birthday else years - 1


def _generate_consent_token() -> str:
    return secrets.token_urlsafe(32)


def signup(
    conn: psycopg.Connection,
    settings: Settings,
    *,
    email: str,
    password: str,
    role: str,
    date_of_birth: date,
    parent_email: str | None,
) -> SignupResult:
    age = calculate_age(date_of_birth)
    if age < 13:
        # Universal hard age gate (Section 9): under 13 is blocked for
        # every role, not just reps.
        raise AgeNotPermittedError("Users under 13 may not create an account")

    consent_token: str | None = None
    consent_created_at: datetime | None = None
    consent_expires_at: datetime | None = None

    if role in ("brand", "recruiter"):
        account_status = "pending"
    elif age < settings.parental_consent_required_under:
        if not parent_email:
            raise ParentEmailRequiredError(
                f"parent_email is required for reps under {settings.parental_consent_required_under}"
            )
        account_status = "pending"
        consent_token = _generate_consent_token()
        consent_created_at = datetime.now(timezone.utc)
        consent_expires_at = consent_created_at + CONSENT_TOKEN_TTL
    else:
        account_status = "active"

    auth_user_id = supabase_admin.create_auth_user(email=email, password=password, settings=settings)

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.users
                    (id, email, role, account_status, date_of_birth, parent_email,
                     consent_token, consent_token_created_at, consent_token_expires_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    auth_user_id,
                    email,
                    role,
                    account_status,
                    date_of_birth,
                    parent_email,
                    consent_token,
                    consent_created_at,
                    consent_expires_at,
                ),
            )
        conn.commit()
    except psycopg.errors.UniqueViolation as exc:
        conn.rollback()
        raise EmailAlreadyRegisteredError("An account with this email already exists") from exc

    if consent_token is not None:
        email_service.send_parental_consent_email(
            parent_email=parent_email,
            rep_display_name=email,
            consent_token=consent_token,
            settings=settings,
        )

    return SignupResult(user_id=auth_user_id, email=email, role=role, account_status=account_status)


def verify_parent_token(conn: psycopg.Connection, token: str) -> str:
    """Returns the user_id activated. Raises TokenInvalid/Expired/AlreadyUsed."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, consent_token_expires_at, consent_token_used_at
            FROM public.users
            WHERE consent_token = %s
            """,
            (token,),
        )
        row = cur.fetchone()

        if row is None:
            raise TokenInvalidError("This consent link is not valid")
        if row["consent_token_used_at"] is not None:
            raise TokenAlreadyUsedError("This consent link has already been used")
        expires_at = row["consent_token_expires_at"]
        if expires_at is not None and datetime.now(timezone.utc) > expires_at:
            raise TokenExpiredError("This consent link has expired")

        now = datetime.now(timezone.utc)
        cur.execute(
            """
            UPDATE public.users
            SET parent_verified_at = %s, account_status = 'active', consent_token_used_at = %s
            WHERE id = %s
            """,
            (now, now, row["id"]),
        )
    conn.commit()
    return str(row["id"])


def resend_consent(conn: psycopg.Connection, settings: Settings, *, email: str) -> None:
    last_sent = _last_resend_at.get(email)
    now_monotonic = time.monotonic()
    if last_sent is not None and (now_monotonic - last_sent) < RESEND_COOLDOWN_SECONDS:
        raise ResendRateLimitedError(int(RESEND_COOLDOWN_SECONDS - (now_monotonic - last_sent)))

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, parent_email, account_status, consent_token_used_at
            FROM public.users
            WHERE email = %s
            """,
            (email,),
        )
        row = cur.fetchone()

        if row is None or not row["parent_email"] or row["account_status"] != "pending":
            # Do not reveal whether the email exists or is eligible --
            # same as a successful resend from the caller's perspective.
            _last_resend_at[email] = now_monotonic
            return

        new_token = _generate_consent_token()
        created_at = datetime.now(timezone.utc)
        expires_at = created_at + CONSENT_TOKEN_TTL
        cur.execute(
            """
            UPDATE public.users
            SET consent_token = %s, consent_token_created_at = %s,
                consent_token_expires_at = %s, consent_token_used_at = NULL
            WHERE id = %s
            """,
            (new_token, created_at, expires_at, row["id"]),
        )
    conn.commit()
    _last_resend_at[email] = now_monotonic

    email_service.send_parental_consent_email(
        parent_email=row["parent_email"],
        rep_display_name=email,
        consent_token=new_token,
        settings=settings,
    )


def get_user_by_id(conn: psycopg.Connection, user_id: str) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, email, role, account_status, consent_token, parent_verified_at
            FROM public.users
            WHERE id = %s
            """,
            (user_id,),
        )
        row = cur.fetchone()
    if row is None:
        raise UserNotFoundError(user_id)
    return row


def pending_reason(user_row: dict) -> str | None:
    if user_row["account_status"] != "pending":
        return None
    if user_row["consent_token"] is not None and user_row["parent_verified_at"] is None:
        return "awaiting_parent_consent"
    return "awaiting_admin_approval"
