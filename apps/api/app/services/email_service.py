"""Transactional email shell, sent via Resend.

Prompt 4 implements send_parental_consent_email against
app/services/resend_client.py's injectable client (real HTTP in
production, an in-memory fake in dev/test -- see that module). The
rest remain unimplemented shells for later prompts.
"""
from __future__ import annotations

from app.services.resend_client import ResendClient


async def send_signup_verification_email(to: str, verification_link: str) -> None:
    """Prompt 4A+: post-signup email verification (not required by
    Prompt 4's signup flow, which activates 16+ reps immediately and
    gates under-16 reps on parental consent instead)."""
    raise NotImplementedError


async def send_parental_consent_email(parent_email: str, consent_link: str, client: ResendClient) -> None:
    """Double opt-in consent email to a parent. Plain language, no
    legalese: explains that their teen signed up for Teenure, what the
    platform does, and that the link expires in 72 hours."""
    html = f"""
    <p>Your teen has started signing up for Teenure, a platform where
    teens complete brand campaigns for pay and build a verified record
    of their work for college and job applications.</p>
    <p>Because they're under 16, we need your permission before their
    account can go live. You'll also get access to a parent portal
    where you can review and approve campaigns, filter out content
    categories you don't want them exposed to, and get a monthly
    summary of their activity.</p>
    <p><a href="{consent_link}">Review and give consent</a></p>
    <p>This link expires in 72 hours. If you didn't expect this email,
    you can safely ignore it -- no account will be activated without
    your consent.</p>
    """
    await client.send_email(
        to=parent_email,
        subject="Action needed: parental consent for Teenure",
        html=html,
    )
