"""Parent Portal business logic (Prompt 4A / Section 9A).

Parents authenticate via a magic-link email flow (not Supabase Auth --
see app.core.parent_security for the session-token format) and have a
deliberately narrow surface: view their rep's summary + earnings,
approve/block pending campaign invitations, configure a values filter,
toggle a monthly digest, and suspend/unsuspend the account. They never
get co-pilot access to the rep's account, and several rep-facing
surfaces (recruiter message content, submission files, brand contact
details) are explicitly excluded from every parent-facing payload.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone

import psycopg

from app.core.config import Settings
from app.core.constants import PARENT_LOGIN_RATE_LIMIT_SECONDS, PARENT_MAGIC_LINK_TTL_MINUTES
from app.core.parent_security import issue_parent_session_token
from app.services import email_service

MAGIC_LINK_TTL = timedelta(minutes=PARENT_MAGIC_LINK_TTL_MINUTES)


# ── Errors ──────────────────────────────────────────────────────────


class TokenInvalidError(Exception):
    pass


class TokenExpiredError(Exception):
    pass


class TokenAlreadyUsedError(Exception):
    pass


class PortalClosedError(Exception):
    """Distinct from a generic token failure -- rep turned 18."""


class ParentRecordNotFoundError(Exception):
    pass


class CampaignNotPendingError(Exception):
    """No pending-approval campaign_reps row for this parent/campaign."""


class ApprovalToggleNotPermittedError(Exception):
    """campaign_approval_required is not parent-editable outside 16-17."""


class RateLimitedError(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Retry after {retry_after_seconds}s")


# Rate limiting: same lightweight per-process cooldown pattern as
# auth_service.resend_consent -- move to a shared store before running
# more than one API instance.
_last_request_at: dict[str, float] = {}


# ── Auth: request-link / verify ────────────────────────────────────


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def request_link(conn: psycopg.Connection, settings: Settings, *, parent_email: str) -> None:
    """Always behaves the same regardless of whether parent_email is
    linked to a parent_records row -- prevents enumerating minor reps'
    accounts by testing emails against this endpoint.
    """
    now_monotonic = time.monotonic()
    last = _last_request_at.get(parent_email)
    if last is not None and (now_monotonic - last) < PARENT_LOGIN_RATE_LIMIT_SECONDS:
        raise RateLimitedError(int(PARENT_LOGIN_RATE_LIMIT_SECONDS - (now_monotonic - last)))
    _last_request_at[parent_email] = now_monotonic

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT pr.id, pr.rep_id, rp.display_name
            FROM public.parent_records pr
            JOIN public.rep_profiles rp ON rp.id = pr.rep_id
            WHERE pr.parent_email = %s
            """,
            (parent_email,),
        )
        row = cur.fetchone()

        if row is None:
            # No enumeration signal: silently succeed from the caller's view.
            return

        raw_token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        cur.execute(
            """
            INSERT INTO public.parent_auth_tokens (parent_record_id, token_hash, expires_at)
            VALUES (%s, %s, %s)
            """,
            (row["id"], _hash_token(raw_token), now + MAGIC_LINK_TTL),
        )
    conn.commit()

    email_service.send_parent_magic_link_email(
        parent_email=parent_email,
        rep_display_name=row["display_name"],
        token=raw_token,
        settings=settings,
    )


def verify_token(conn: psycopg.Connection, settings: Settings, *, token: str) -> tuple[str, str]:
    """Returns (session_token, rep_id). Raises TokenInvalid/Expired/
    AlreadyUsed/PortalClosed.
    """
    token_hash = _hash_token(token)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT t.id AS token_id, t.expires_at, t.used_at,
                   pr.id AS parent_record_id, pr.rep_id, pr.portal_expires_at, pr.parent_email, rp.display_name
            FROM public.parent_auth_tokens t
            JOIN public.parent_records pr ON pr.id = t.parent_record_id
            JOIN public.rep_profiles rp ON rp.id = pr.rep_id
            WHERE t.token_hash = %s
            """,
            (token_hash,),
        )
        row = cur.fetchone()

        if row is None:
            raise TokenInvalidError("This login link is not valid")
        if row["used_at"] is not None:
            raise TokenAlreadyUsedError("This login link has already been used")
        if datetime.now(timezone.utc) > row["expires_at"]:
            raise TokenExpiredError("This login link has expired")

        # Portal expiry checked here too (not just on later session
        # verification) -- deliverable 8 requires this at every
        # verification step, and login is the first one.
        if datetime.now(timezone.utc) > row["portal_expires_at"]:
            email_service.send_portal_closed_email(
                parent_email=row["parent_email"], rep_display_name=row["display_name"], settings=settings
            )
            raise PortalClosedError()

        cur.execute(
            "UPDATE public.parent_auth_tokens SET used_at = now() WHERE id = %s",
            (row["token_id"],),
        )
    conn.commit()

    session_token = issue_parent_session_token(
        parent_record_id=str(row["parent_record_id"]), rep_id=str(row["rep_id"]), settings=settings
    )
    return session_token, str(row["rep_id"])


# ── Dashboard ───────────────────────────────────────────────────────


def get_dashboard(conn: psycopg.Connection, rep_id: str) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT display_name, school_name, graduation_year, categories,
                   profile_completeness_score, total_earnings_cents, total_campaigns_completed
            FROM public.rep_profiles WHERE id = %s
            """,
            (rep_id,),
        )
        row = cur.fetchone()
    if row is None:
        raise ParentRecordNotFoundError(rep_id)
    return row


# ── Campaign approval queue ─────────────────────────────────────────


def pending_campaigns(conn: psycopg.Connection, rep_id: str) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT cr.id AS campaign_reps_id, cr.campaign_id, cr.parent_approval_deadline,
                   c.product_name, c.key_messaging, c.deliverables_description,
                   c.prohibited_content, c.payout_per_rep_cents AS payout_cents,
                   c.start_date, c.end_date, c.target_categories,
                   b.company_name AS brand_name
            FROM public.campaign_reps cr
            JOIN public.campaigns c ON c.id = cr.campaign_id
            JOIN public.brand_profiles b ON b.id = c.brand_id
            WHERE cr.rep_id = %s AND cr.parent_approval_status = 'pending'
            ORDER BY cr.parent_approval_deadline ASC
            """,
            (rep_id,),
        )
        rows = cur.fetchall()
    for r in rows:
        r["requires_in_person"] = "in_person_travel_required" in (r.get("target_categories") or [])
    return rows


def _get_pending_campaign_rep(conn: psycopg.Connection, rep_id: str, campaign_id: str) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT * FROM public.campaign_reps
            WHERE rep_id = %s AND campaign_id = %s AND parent_approval_status = 'pending'
            """,
            (rep_id, campaign_id),
        )
        return cur.fetchone()


def approve_campaign(conn: psycopg.Connection, rep_id: str, campaign_id: str) -> dict:
    """Idempotent: re-approving an already-approved invite is a no-op
    success rather than an error.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM public.campaign_reps WHERE rep_id = %s AND campaign_id = %s",
            (rep_id, campaign_id),
        )
        cr = cur.fetchone()
    if cr is None:
        raise CampaignNotPendingError(campaign_id)
    if cr["parent_approval_status"] == "approved":
        return cr
    if cr["parent_approval_status"] != "pending":
        raise CampaignNotPendingError(campaign_id)

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE public.campaign_reps
            SET parent_approval_status = 'approved', parent_decided_at = now()
            WHERE id = %s RETURNING *
            """,
            (cr["id"],),
        )
        row = cur.fetchone()
    conn.commit()
    return row


def block_campaign(conn: psycopg.Connection, rep_id: str, campaign_id: str) -> dict:
    """Blocks the invitation and auto-declines it with a neutral,
    brand-facing message ("rep is unavailable") -- the parent's reason
    is never exposed to the brand. Nothing at the brand's layer
    distinguishes a parent block from an ordinary rep decline; both
    just land in status = 'declined'.
    """
    cr = _get_pending_campaign_rep(conn, rep_id, campaign_id)
    if cr is None:
        raise CampaignNotPendingError(campaign_id)

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE public.campaign_reps
            SET parent_approval_status = 'blocked', parent_decided_at = now(),
                status = 'declined'
            WHERE id = %s RETURNING *
            """,
            (cr["id"],),
        )
        row = cur.fetchone()
    conn.commit()
    return row


# ── Settings ────────────────────────────────────────────────────────


def get_parent_settings(conn: psycopg.Connection, parent_record_id: str) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT values_filters, campaign_approval_required, digest_enabled "
            "FROM public.parent_records WHERE id = %s",
            (parent_record_id,),
        )
        row = cur.fetchone()
    if row is None:
        raise ParentRecordNotFoundError(parent_record_id)
    return row


def update_values_filters(conn: psycopg.Connection, parent_record_id: str, values_filters: list[str]) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE public.parent_records SET values_filters = %s, updated_at = now()
            WHERE id = %s RETURNING values_filters, campaign_approval_required, digest_enabled
            """,
            (values_filters, parent_record_id),
        )
        row = cur.fetchone()
    conn.commit()
    return row


def _rep_age(conn: psycopg.Connection, rep_id: str) -> int:
    from app.services.auth_service import calculate_age

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT u.date_of_birth FROM public.users u
            JOIN public.rep_profiles rp ON rp.user_id = u.id
            WHERE rp.id = %s
            """,
            (rep_id,),
        )
        row = cur.fetchone()
    return calculate_age(row["date_of_birth"])


def update_approval_required(
    conn: psycopg.Connection, parent_record_id: str, rep_id: str, *, campaign_approval_required: bool
) -> dict:
    """Only legal for reps aged 16-17: under-16 always required (not
    parent-editable), 18+ means the portal itself has expired.
    """
    age = _rep_age(conn, rep_id)
    if not (16 <= age <= 17):
        raise ApprovalToggleNotPermittedError(
            "campaign_approval_required can only be changed for reps aged 16-17: "
            "under-16 reps always require approval, and the portal expires at 18"
        )

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE public.parent_records SET campaign_approval_required = %s, updated_at = now()
            WHERE id = %s RETURNING values_filters, campaign_approval_required, digest_enabled
            """,
            (campaign_approval_required, parent_record_id),
        )
        row = cur.fetchone()
    conn.commit()
    return row


def update_digest_enabled(conn: psycopg.Connection, parent_record_id: str, digest_enabled: bool) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE public.parent_records SET digest_enabled = %s, updated_at = now()
            WHERE id = %s RETURNING values_filters, campaign_approval_required, digest_enabled
            """,
            (digest_enabled, parent_record_id),
        )
        row = cur.fetchone()
    conn.commit()
    return row


# ── Monthly digest ──────────────────────────────────────────────────
#
# Strict content boundary (deliverable 5): the digest contains ONLY
# campaigns-completed-this-month, earnings this month + lifetime,
# profile-completeness change, and categories active in. It NEVER
# contains recruiter message content, submission text/files, or brand
# contact details -- those fields are simply never selected/serialized
# here, by construction (there is no column reference to them below).


def digest_preview(conn: psycopg.Connection, rep_id: str) -> dict:
    now = datetime.now(timezone.utc)
    month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT categories, profile_completeness_score, total_earnings_cents
            FROM public.rep_profiles WHERE id = %s
            """,
            (rep_id,),
        )
        profile = cur.fetchone()

        cur.execute(
            """
            SELECT COUNT(*) AS n, COALESCE(SUM(payout_cents), 0) AS earned
            FROM public.campaign_reps
            WHERE rep_id = %s AND status IN ('confirmed', 'paid') AND confirmed_at >= %s
            """,
            (rep_id, month_start),
        )
        month_row = cur.fetchone()

    return {
        "campaigns_completed_this_month": month_row["n"],
        "earnings_this_month_cents": month_row["earned"],
        "earnings_lifetime_cents": profile["total_earnings_cents"],
        "profile_completeness_score": profile["profile_completeness_score"],
        "categories_active_in": profile["categories"],
    }


def send_monthly_digests(conn: psycopg.Connection, settings: Settings) -> int:
    """Scheduled job (registered in app.jobs.runner): generates and sends
    one digest per parent_records row with digest_enabled = TRUE.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT pr.id AS parent_record_id, pr.parent_email, pr.rep_id, rp.display_name
            FROM public.parent_records pr
            JOIN public.rep_profiles rp ON rp.id = pr.rep_id
            WHERE pr.digest_enabled = TRUE
            """
        )
        parents = cur.fetchall()

    sent = 0
    for p in parents:
        content = digest_preview(conn, p["rep_id"])
        email_service.send_parent_digest_email(
            parent_email=p["parent_email"],
            rep_display_name=p["display_name"],
            digest=content,
            settings=settings,
        )
        sent += 1
    return sent


# ── Account controls ────────────────────────────────────────────────


def suspend_account(conn: psycopg.Connection, settings: Settings, *, parent_record_id: str, rep_id: str) -> None:
    now = datetime.now(timezone.utc)
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE public.parent_records SET suspended_by_parent_at = %s, updated_at = now() WHERE id = %s",
            (now, parent_record_id),
        )
        cur.execute(
            """
            UPDATE public.users SET account_status = 'suspended', updated_at = now()
            WHERE id = (SELECT user_id FROM public.rep_profiles WHERE id = %s)
            RETURNING email
            """,
            (rep_id,),
        )
        rep_row = cur.fetchone()
    conn.commit()

    if rep_row is not None:
        email_service.send_account_suspended_email(rep_email=rep_row["email"], settings=settings)
    # Admin alert: no admin-notification channel exists yet in this repo
    # (Admin Portal is Prompt 13/gh#262 territory, not this prompt) --
    # logged instead so the requirement is visibly met, not silently
    # dropped, until a real admin inbox exists.
    logging.getLogger("teenure.api").warning(
        "Admin alert: rep %s account suspended by parent (parent_record_id=%s)", rep_id, parent_record_id
    )


def unsuspend_account(conn: psycopg.Connection, parent_record_id: str, rep_id: str) -> None:
    """Reverses suspension only if it was parent-initiated -- an
    admin-initiated suspension is not reversible by the parent.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT suspended_by_parent_at FROM public.parent_records WHERE id = %s",
            (parent_record_id,),
        )
        row = cur.fetchone()
    if row is None or row["suspended_by_parent_at"] is None:
        raise PermissionError("This account was not suspended by a parent, so it cannot be unsuspended here")

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE public.parent_records SET suspended_by_parent_at = NULL, updated_at = now() WHERE id = %s",
            (parent_record_id,),
        )
        cur.execute(
            """
            UPDATE public.users SET account_status = 'active', updated_at = now()
            WHERE id = (SELECT user_id FROM public.rep_profiles WHERE id = %s)
            """,
            (rep_id,),
        )
    conn.commit()
