from __future__ import annotations

import os
import time

import jwt
import pytest
from fastapi.testclient import TestClient

_TEST_ENV = {
    "ENVIRONMENT": "test",
    "NEXT_PUBLIC_SUPABASE_URL": "http://localhost:54321",
    "NEXT_PUBLIC_SUPABASE_ANON_KEY": "test-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
    "DATABASE_URL": "postgresql://teenure:teenure@localhost:5434/teenure_test",
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


@pytest.fixture(scope="session")
def settings():
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture()
def app(settings):
    return create_app()


@pytest.fixture()
def client(app):
    return TestClient(app)


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
