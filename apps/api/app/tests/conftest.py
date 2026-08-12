"""Shared pytest fixtures (Prompt 3 scaffold).

Provides a test client wired to fully-stubbed Settings (no real
Supabase/Stripe/Resend credentials needed) and a factory for minting a
fake-but-valid Supabase JWT + backing public.users row for each role,
so later prompts can write route tests like:

    def test_brand_route_rejects_rep(client, auth_headers):
        resp = client.get("/brands/me", headers=auth_headers("rep"))
        assert resp.status_code == 403
"""

from __future__ import annotations

import os

TEST_JWT_SECRET = "test-secret-not-for-production-use"

# app.main instantiates Settings() at import time (fail-fast on a real
# missing var, per this prompt's acceptance criteria) -- set every
# required var before any test module imports app.main, so collection
# itself doesn't explode. test_config_fails_fast_on_missing_required_var
# proves the fail-fast behavior separately, in-process.
os.environ.setdefault("NEXT_PUBLIC_SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("NEXT_PUBLIC_SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
os.environ.setdefault("DATABASE_URL", "postgresql://teenure:teenure_dev_only@127.0.0.1:5434/teenure")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_dummy")
os.environ.setdefault("STRIPE_PUBLISHABLE_KEY", "pk_test_dummy")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_dummy")
os.environ.setdefault("STRIPE_PLATFORM_FEE_PERCENT", "35")
os.environ.setdefault("RESEND_API_KEY", "test-resend-key")
os.environ.setdefault("RESEND_FROM_EMAIL", "noreply@teenure.com")
os.environ.setdefault("RESEND_PARENT_CONSENT_TEMPLATE_ID", "tmpl_dummy")
os.environ.setdefault("NEXT_PUBLIC_APP_URL", "http://localhost:3100")
os.environ.setdefault("API_URL", "http://localhost:8001")
os.environ.setdefault("ADMIN_SECRET_KEY", "test-admin-secret")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3100")
os.environ.setdefault("JOBS_RUNNER_SECRET", "test-jobs-runner-secret")
os.environ.setdefault("MIN_REP_AGE", "14")
os.environ.setdefault("PARENTAL_CONSENT_REQUIRED_UNDER", "16")
os.environ.setdefault("PARENT_SESSION_SECRET", "test-parent-session-secret")

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core import security
from app.core.config import Settings
from app.main import create_app

FAKE_USERS: dict[str, dict] = {
    "rep": {
        "id": "00000000-0000-0000-0000-000000000001",
        "email": "dev-rep-1@example.test",
        "role": "rep",
        "account_status": "active",
    },
    "brand": {
        "id": "00000000-0000-0000-0000-000000000003",
        "email": "dev-brand-1@example.test",
        "role": "brand",
        "account_status": "active",
    },
    "recruiter": {
        "id": "00000000-0000-0000-0000-000000000004",
        "email": "dev-recruiter-1@example.test",
        "role": "recruiter",
        "account_status": "active",
    },
    "admin": {
        "id": "00000000-0000-0000-0000-000000000005",
        "email": "dev-admin-1@example.test",
        "role": "admin",
        "account_status": "active",
    },
    "pending_rep": {
        "id": "00000000-0000-0000-0000-000000000002",
        "email": "dev-rep-2@example.test",
        "role": "rep",
        "account_status": "pending",
    },
}


def _test_settings() -> Settings:
    return Settings(
        next_public_supabase_url="http://localhost:54321",
        next_public_supabase_anon_key="test-anon-key",
        supabase_service_role_key="test-service-role-key",
        supabase_jwt_secret=TEST_JWT_SECRET,
        database_url="postgresql://teenure:teenure_dev_only@127.0.0.1:5434/teenure",
        stripe_secret_key="sk_test_dummy",
        stripe_publishable_key="pk_test_dummy",
        stripe_webhook_secret="whsec_dummy",
        stripe_platform_fee_percent=35,
        resend_api_key="test-resend-key",
        resend_from_email="noreply@teenure.com",
        resend_parent_consent_template_id="tmpl_dummy",
        next_public_app_url="http://localhost:3100",
        api_url="http://localhost:8001",
        admin_secret_key="test-admin-secret",
        allowed_origins="http://localhost:3100",
        jobs_runner_secret="test-jobs-runner-secret",
        min_rep_age=14,
        parental_consent_required_under=16,
        parent_session_secret="test-parent-session-secret",
    )


@pytest.fixture
def settings() -> Settings:
    return _test_settings()


@pytest.fixture
def client(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    def fake_load_user_row(user_id: str, _settings: Settings) -> dict | None:
        for user in FAKE_USERS.values():
            if user["id"] == user_id:
                return user
        return None

    monkeypatch.setattr(security, "load_user_row", fake_load_user_row)

    app = create_app(settings=settings)
    return TestClient(app)


@pytest.fixture
def make_token() -> callable:
    def _make_token(user_key: str) -> str:
        user = FAKE_USERS[user_key]
        return jwt.encode(
            {"sub": user["id"], "email": user["email"], "aud": "authenticated"},
            TEST_JWT_SECRET,
            algorithm="HS256",
        )

    return _make_token


@pytest.fixture
def auth_headers(make_token: callable) -> callable:
    def _auth_headers(user_key: str) -> dict:
        return {"Authorization": f"Bearer {make_token(user_key)}"}

    return _auth_headers
