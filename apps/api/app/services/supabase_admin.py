"""Supabase Auth Admin API calls (Prompt 4).

public.users.id is a foreign key into auth.users(id) (Section 7), and
Supabase owns auth.users -- we never write to it directly. Creating the
auth identity (email/password, confirmed) has to go through Supabase's
Admin API using the service role key, which returns the UUID we then
use as public.users.id.

Kept as a single seam (like security.load_user_row in Prompt 3) so
tests can monkeypatch it instead of needing a live Supabase project.
"""

from __future__ import annotations

import httpx

from app.core.config import Settings


class SupabaseAdminError(RuntimeError):
    """Raised when the Supabase Admin API rejects a request (e.g. duplicate email)."""


def create_auth_user(*, email: str, password: str, settings: Settings) -> str:
    """Create a confirmed auth.users row via Supabase's Admin API, return its id."""
    resp = httpx.post(
        f"{settings.next_public_supabase_url}/auth/v1/admin/users",
        headers={
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
        },
        json={"email": email, "password": password, "email_confirm": True},
        timeout=10.0,
    )
    if resp.status_code >= 400:
        raise SupabaseAdminError(f"Supabase admin user creation failed: {resp.status_code} {resp.text}")
    return resp.json()["id"]
