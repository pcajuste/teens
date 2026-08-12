"""Transactional email shell, sent via Resend.

Template ids are read from Settings (RESEND_*_TEMPLATE_ID). Generic
send is the primitive; the parent-portal-specific sends live in
parent_service.py since they carry Section 9A's content restrictions.
"""
from __future__ import annotations


async def send_email(to: str, template_id: str, template_data: dict) -> None:
    """Send a templated transactional email via Resend. All other send_*
    helpers across the codebase should call through this."""
    raise NotImplementedError


async def send_signup_verification_email(to: str, verification_link: str) -> None:
    """Prompt 4: post-signup email verification."""
    raise NotImplementedError


async def send_parental_consent_email(parent_email: str, consent_link: str) -> None:
    """Prompt 4: double opt-in consent email to a parent, 72-hour expiry
    token embedded in `consent_link`."""
    raise NotImplementedError
