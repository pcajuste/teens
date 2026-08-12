"""Creates the auth.users identity that public.users.id references.

public.users deliberately has no password column (Section 7) --
GoTrue (Supabase Auth) owns password storage/hashing entirely. Two
implementations:

- HttpSupabaseAuthClient: production. Calls Supabase's Auth Admin API
  (POST /auth/v1/admin/users) with the service-role key.
- LocalDevSupabaseAuthClient: local dev/test only. No GoTrue runs
  locally (see supabase/migrations/..._extensions_and_auth_shim.sql --
  the local auth.users table is a bare id/email shim for RLS testing).
  This implementation inserts directly into that shim table, in the
  same transaction as the public.users insert, so the FK is
  satisfiable without a real Supabase project. Selected only when
  Settings.environment is "development" or "test" -- see
  get_supabase_auth_client() below.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

import asyncpg
import httpx

from app.core.config import Settings


class EmailAlreadyRegisteredError(Exception):
    def __init__(self, email: str):
        self.email = email
        super().__init__(f"{email} is already registered")


@dataclass(frozen=True, slots=True)
class AuthUser:
    id: str
    email: str


class SupabaseAuthClient(Protocol):
    async def create_user(self, *, email: str, password: str, app_metadata: dict) -> AuthUser: ...

    async def update_app_metadata(self, user_id: str, app_metadata: dict) -> None: ...


class HttpSupabaseAuthClient:
    """`app_metadata` (role, account_status) is set directly via the
    Admin API's create/update-user calls -- Supabase exposes this
    natively, so app/core/security.py's JWT dependency can trust
    `app_metadata` without this repo needing to invent a
    public.users -> auth.users sync trigger. A status change (e.g.
    parent-verify flipping pending -> active) takes effect on the
    user's next token refresh, per security.py's docstring."""

    def __init__(self, settings: Settings):
        self._base_url = settings.next_public_supabase_url.rstrip("/")
        self._service_role_key = settings.supabase_service_role_key

    def _headers(self) -> dict:
        return {
            "apikey": self._service_role_key,
            "Authorization": f"Bearer {self._service_role_key}",
        }

    async def create_user(self, *, email: str, password: str, app_metadata: dict) -> AuthUser:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/auth/v1/admin/users",
                headers=self._headers(),
                json={
                    "email": email,
                    "password": password,
                    "email_confirm": True,
                    "app_metadata": app_metadata,
                },
            )
        if response.status_code in (400, 422):
            raise EmailAlreadyRegisteredError(email)
        response.raise_for_status()
        body = response.json()
        return AuthUser(id=body["id"], email=body["email"])

    async def update_app_metadata(self, user_id: str, app_metadata: dict) -> None:
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self._base_url}/auth/v1/admin/users/{user_id}",
                headers=self._headers(),
                json={"app_metadata": app_metadata},
            )
        response.raise_for_status()


class LocalDevSupabaseAuthClient:
    """Local dev/test only -- no real GoTrue runs locally, so there's no
    JWT to attach app_metadata to. Tests hand-craft JWTs with the
    desired app_metadata directly (see tests/conftest.py); this client
    only needs to satisfy public.users' FK to the local auth.users
    shim table."""

    def __init__(self, conn: asyncpg.Connection):
        self._conn = conn

    async def create_user(self, *, email: str, password: str, app_metadata: dict) -> AuthUser:
        existing = await self._conn.fetchrow("SELECT id FROM auth.users WHERE email = $1", email)
        if existing is not None:
            raise EmailAlreadyRegisteredError(email)
        user_id = str(uuid.uuid4())
        await self._conn.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", user_id, email)
        return AuthUser(id=user_id, email=email)

    async def update_app_metadata(self, user_id: str, app_metadata: dict) -> None:
        return None


def get_supabase_auth_client(settings: Settings, conn: asyncpg.Connection) -> SupabaseAuthClient:
    # "test" (pytest, see tests/conftest.py) runs against a bare
    # postgres:15-alpine container with no GoTrue -- the shim is
    # required there. "development" now runs against the local
    # Supabase CLI stack (`supabase start`), which has real GoTrue at
    # next_public_supabase_url, so it uses the same Admin API path as
    # production.
    if settings.environment == "test":
        return LocalDevSupabaseAuthClient(conn)
    return HttpSupabaseAuthClient(settings)
