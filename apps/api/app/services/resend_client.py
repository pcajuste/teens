"""Thin Resend API client, injectable so email_service can be tested
without hitting a real Resend account.

Mirrors the environment-selected pattern in supabase_auth_client.py:
local dev/test never has a usable RESEND_API_KEY (the checked-in
.env.local value is a placeholder), so real sends there would just
fail loudly on every signup below the parental-consent age threshold.
FakeResendClient records sends in-memory instead.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import httpx
from fastapi import Depends

from app.core.config import Settings, get_settings


class ResendClient(Protocol):
    async def send_email(self, *, to: str, subject: str, html: str) -> None: ...


class HttpResendClient:
    def __init__(self, settings: Settings):
        self._api_key = settings.resend_api_key
        self._from_email = settings.resend_from_email

    async def send_email(self, *, to: str, subject: str, html: str) -> None:
        async with httpx.AsyncClient() as client:
            response  = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"from": self._from_email, "to": [to], "subject": subject, "html": html},
            )
        response .raise_for_status()


@dataclass
class SentEmail:
    to: str
    subject: str
    html: str


@dataclass
class FakeResendClient:
    sent: list[SentEmail] = field(default_factory=list)

    async def send_email(self, *, to: str, subject: str, html: str) -> None:
        self.sent.append(SentEmail(to=to, subject=subject, html=html))


def get_resend_client(settings: Settings) -> ResendClient:
    if settings.environment in ("development", "test"):
        return FakeResendClient()
    return HttpResendClient(settings)


def resend_client_dependency(settings: Settings = Depends(get_settings)) -> ResendClient:
    """Single shared FastAPI dependency so every router that sends email
    can be overridden in tests via one dependency-overrides key, instead
    of each router needing its own identical wrapper function."""
    return get_resend_client(settings)
