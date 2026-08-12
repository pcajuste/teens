"""Transactional email via Resend (Prompt 4).

send_transactional is the one seam that actually talks to Resend's API;
every other helper (send_parental_consent_email, etc.) builds
template_data and calls through it, so tests only need to monkeypatch
one function to capture "sent" email instead of making a real call.
"""

from __future__ import annotations

import httpx

from app.core.config import Settings


def send_parental_consent_email(
    *, parent_email: str, rep_display_name: str, consent_token: str, settings: Settings
) -> None:
    """Send the parent a plain-language consent request with a signed link.

    Uses RESEND_PARENT_CONSENT_TEMPLATE_ID. Link target is
    `{NEXT_PUBLIC_APP_URL}/parent-consent/{consent_token}`, handled by
    POST /auth/parent-verify/:token. Copy must be age-appropriate/
    non-legalese per Section 9 -- the template itself lives in Resend;
    template_data below is what fills it in.
    """
    consent_link = f"{settings.next_public_app_url}/parent-consent/{consent_token}"
    send_transactional(
        to_email=parent_email,
        template_id=settings.resend_parent_consent_template_id,
        template_data={
            "rep_display_name": rep_display_name,
            "consent_link": consent_link,
            "explainer": (
                f"{rep_display_name} signed up for Teenure, a site where teens track "
                "brand partnerships and paid opportunities for their school/social media "
                "activities. Because they're under 16, we need a parent or guardian to "
                "confirm before their account can be used. Click the link below to "
                "confirm -- it expires in 72 hours."
            ),
        },
        settings=settings,
    )


def send_account_suspended_email(*, rep_email: str, settings: Settings) -> None:
    """Prompt 4A deliverable 6: notify the rep their account was suspended
    by their parent. Does not explain the parent's underlying reasoning
    beyond "your parent/guardian suspended your account", matching the
    same neutral-disclosure principle as the campaign-block flow.
    """
    send_transactional(
        to_email=rep_email,
        template_id=settings.resend_parent_consent_template_id,
        template_data={
            "explainer": (
                "Your parent or guardian has suspended your Teenure account. "
                "You won't be able to accept new campaigns until it's reactivated. "
                "Contact your parent/guardian if you have questions."
            ),
        },
        settings=settings,
    )


def send_parent_magic_link_email(
    *, parent_email: str, rep_display_name: str, token: str, settings: Settings
) -> None:
    """Parent Portal magic-link login (Section 9A / Prompt 4A).

    Link target is `{NEXT_PUBLIC_APP_URL}/parent/verify/{token}`, handled
    by GET /parent/auth/verify/:token. Uses
    RESEND_PARENT_MAGIC_LINK_TEMPLATE_ID. Only ever called once
    request-link has already confirmed a matching parent_records row
    exists -- the router/service layer above this is what enforces the
    non-enumerating response, not this function.
    """
    login_link = f"{settings.next_public_app_url}/parent/verify/{token}"
    send_transactional(
        to_email=parent_email,
        template_id=settings.resend_parent_magic_link_template_id,
        template_data={
            "rep_display_name": rep_display_name,
            "login_link": login_link,
            "explainer": (
                f"Click the link below to check in on {rep_display_name}'s Teenure account. "
                "This link expires in 15 minutes and can only be used once."
            ),
        },
        settings=settings,
    )


def send_parent_digest_email(
    *, parent_email: str, rep_display_name: str, digest: dict, settings: Settings
) -> None:
    """Monthly digest (deliverable 5). `digest` must only ever contain the
    strict-content-boundary fields from
    app.services.parent_service.build_monthly_digest -- never recruiter
    message content, submission text/files, or brand contact details.
    """
    send_transactional(
        to_email=parent_email,
        template_id=settings.resend_parent_digest_template_id,
        template_data={"rep_display_name": rep_display_name, **digest},
        settings=settings,
    )


def send_portal_closed_email(*, parent_email: str, rep_display_name: str, settings: Settings) -> None:
    """Sent once portal_expires_at has passed (deliverable 8) -- either at
    a rejected login attempt or (in future) proactively at the birthday
    itself.
    """
    send_transactional(
        to_email=parent_email,
        template_id=settings.resend_parent_digest_template_id,
        template_data={
            "rep_display_name": rep_display_name,
            "explainer": (
                f"The Teenure parent portal for {rep_display_name} has closed because they are "
                "now 18. Their account is now fully theirs to manage."
            ),
        },
        settings=settings,
    )


def send_transactional(*, to_email: str, template_id: str, template_data: dict, settings: Settings) -> None:
    """Generic Resend transactional send for all other email flows."""
    resp = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {settings.resend_api_key}"},
        json={
            "from": settings.resend_from_email,
            "to": [to_email],
            "template_id": template_id,
            "template_data": template_data,
        },
        timeout=10.0,
    )
    resp.raise_for_status()
