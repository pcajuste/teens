from __future__ import annotations

import asyncio
import os
import time

import asyncpg
import jwt
import pytest
from fastapi.testclient import TestClient

_TEST_ENV = {
    "ENVIRONMENT": "test",
    "NEXT_PUBLIC_SUPABASE_URL": "http://localhost:54321",
    "NEXT_PUBLIC_SUPABASE_ANON_KEY": "test-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
    "DATABASE_URL": "postgresql://teenure:teenure_dev_only@localhost:5434/teenure_test",
    "SUPABASE_JWT_SECRET": "test-supabase-jwt-secret",
    "STRIPE_SECRET_KEY": "sk_test_dummy",
    "STRIPE_PUBLISHABLE_KEY": "pk_test_dummy",
    "STRIPE_WEBHOOK_SECRET": "whsec_dummy",
    "RESEND_API_KEY": "re_dummy",
    "RESEND_PARENT_CONSENT_TEMPLATE_ID": "tmpl_consent",
    "RESEND_PARENT_MAGIC_LINK_TEMPLATE_ID": "tmpl_magic_link",
    "RESEND_PARENT_DIGEST_TEMPLATE_ID": "tmpl_digest",
    "NEXT_PUBLIC_APP_URL": "http://localhost:3300",
    "API_URL": "http://localhost:8300",
    "ADMIN_SECRET_KEY": "test-admin-secret",
    "ALLOWED_ORIGINS": "http://localhost:3300",
    "JOBS_RUNNER_SECRET": "test-jobs-runner-secret",
    "PARENT_SESSION_SECRET": "test-parent-session-secret",
}
for _key, _value in _TEST_ENV.items():
    os.environ.setdefault(_key, _value)

from app.core.config import get_settings  # noqa: E402
from app.core.security import PARENT_SESSION_ISSUER  # noqa: E402
from app.main import create_app  # noqa: E402
from app.routers import auth as auth_router  # noqa: E402
from app.services.resend_client import FakeResendClient  # noqa: E402


@pytest.fixture(scope="session")
def settings():
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture()
def fake_resend_client():
    return FakeResendClient()


@pytest.fixture()
def app(settings, fake_resend_client):
    application = create_app()
    application.dependency_overrides[auth_router._resend_client_dependency] = lambda: fake_resend_client
    return application


@pytest.fixture()
def client(app):
    with TestClient(app) as test_client:
        yield test_client


class SyncDB:
    """Test-side DB access via short-lived standalone connections --
    deliberately NOT the app's asyncpg pool, which lives on TestClient's
    background-thread event loop (starlette.testclient runs the ASGI
    app via an anyio portal in its own thread). Reusing that pool from
    a pytest-asyncio-driven fixture would hand asyncpg a connection
    bound to a different event loop. A fresh connection per call, each
    wrapped in its own asyncio.run(), sidesteps that entirely."""

    def __init__(self, dsn: str):
        self._dsn = dsn

    def _run(self, coro):
        return asyncio.run(coro)

    def fetchval(self, query: str, *args):
        async def _inner():
            conn = await asyncpg.connect(dsn=self._dsn)
            try:
                return await conn.fetchval(query, *args)
            finally:
                await conn.close()

        return self._run(_inner())

    def execute(self, query: str, *args):
        async def _inner():
            conn = await asyncpg.connect(dsn=self._dsn)
            try:
                return await conn.execute(query, *args)
            finally:
                await conn.close()

        return self._run(_inner())


@pytest.fixture()
def db(settings):
    return SyncDB(settings.database_url)


@pytest.fixture(autouse=True)
def _clean_database(db):
    yield
    db.execute("TRUNCATE public.parent_records, public.users, auth.users CASCADE")


def _supabase_jwt(settings, *, role: str, account_status: str = "active") -> str:
    payload = {
        "sub": "00000000-0000-0000-0000-000000000001",
        "email": f"{role}@example.com",
        "aud": "authenticated",
        "app_metadata": {"role": role, "account_status": account_status},
        "exp": int(time.time()) + 3600,
    }
    return jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")


@pytest.fixture()
def auth_headers_factory(settings):
    def _factory(role: str, account_status: str = "active") -> dict[str, str]:
        token = _supabase_jwt(settings, role=role, account_status=account_status)
        return {"Authorization": f"Bearer {token}"}

    return _factory


@pytest.fixture(params=["rep", "brand", "recruiter", "admin"])
def role(request):
    return request.param


@pytest.fixture()
def authenticated_headers(auth_headers_factory, role):
    """One fixture per role, parametrized — a test using this fixture
    runs once per role (rep/brand/recruiter/admin)."""
    return auth_headers_factory(role)


@pytest.fixture()
def parent_session_headers(settings):
    payload = {
        "parent_id": "parent-00000000-0000-0000-0000-000000000001",
        "rep_id": "rep-00000000-0000-0000-0000-000000000001",
        "iss": PARENT_SESSION_ISSUER,
        "exp": int(time.time()) + 3600,
    }
    token = jwt.encode(payload, settings.parent_session_secret, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}
