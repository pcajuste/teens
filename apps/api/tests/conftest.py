from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

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
    "EIN_ENCRYPTION_KEY": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
}
for _key, _value in _TEST_ENV.items():
    os.environ.setdefault(_key, _value)

from app.core.config import get_settings  # noqa: E402
from app.core.security import PARENT_SESSION_ISSUER  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.resend_client import FakeResendClient  # noqa: E402
from app.services.resend_client import resend_client_dependency  # noqa: E402


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
    application.dependency_overrides[resend_client_dependency] = lambda: fake_resend_client
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

    def fetch(self, query: str, *args):
        async def _inner():
            conn = await asyncpg.connect(dsn=self._dsn)
            try:
                return [dict(row) for row in await conn.fetch(query, *args)]
            finally:
                await conn.close()

        return self._run(_inner())


@pytest.fixture()
def db(settings):
    return SyncDB(settings.database_url)


@pytest.fixture(autouse=True)
def _clean_database(db):
    yield
    db.execute(
        "TRUNCATE public.stripe_events, public.safety_reports, public.intelligence_events_anonymized, "
        "public.parent_auth_tokens, public.parent_records, "
        "public.milestone_disputes, public.campaign_rep_milestones, public.campaign_milestones, "
        "public.challenge_submissions, public.challenges, "
        "public.campaign_reps, public.category_exclusivity_agreements, "
        "public.campaigns, public.recruiter_saved_profiles, public.recruiter_contacts, public.recruiter_profiles, "
        "public.rep_profiles, public.brand_profiles, public.users, auth.users CASCADE"
    )


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


@pytest.fixture()
def parent_headers_factory(settings):
    def _factory(*, parent_id: str, rep_id: str) -> dict[str, str]:
        payload = {
            "parent_id": parent_id,
            "rep_id": rep_id,
            "iss": PARENT_SESSION_ISSUER,
            "exp": int(time.time()) + 3600,
        }
        token = jwt.encode(payload, settings.parent_session_secret, algorithm="HS256")
        return {"Authorization": f"Bearer {token}"}

    return _factory


@dataclass
class SeededRep:
    rep_user_id: str
    rep_email: str
    rep_id: str
    parent_id: str
    parent_email: str


@pytest.fixture()
def seed_rep_with_parent(db):
    """Direct-SQL seed for a rep + linked parent_records row. Prompt 4A
    ships before Prompt 5 (rep onboarding) and Prompt 8 (brand
    campaigns) exist, so there's no app flow that produces this state
    yet -- tests build it directly, the same way Prompt 4's tests
    backdate a consent token."""

    def _seed(
        *,
        age: int = 15,
        campaign_approval_required: bool = True,
        portal_expires_in_days: int = 3650,
        parent_email: str | None = None,
        values_filters: list[str] | None = None,
        digest_enabled: bool = True,
        categories: list[str] | None = None,
        profile_completeness_score: int = 50,
        total_earnings_cents: int = 12345,
        total_campaigns_completed: int = 2,
        suspended_by_parent_at: datetime | None = None,
        rep_account_status: str = "active",
    ) -> SeededRep:
        rep_user_id = str(uuid.uuid4())
        rep_id = str(uuid.uuid4())
        parent_id = str(uuid.uuid4())
        rep_email = f"rep-{rep_user_id}@example.com"
        resolved_parent_email = parent_email or f"parent-{parent_id}@example.com"
        dob = date(date.today().year - age, 6, 1)

        db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", rep_user_id, rep_email)
        db.execute(
            "INSERT INTO public.users (id, email, role, account_status, date_of_birth) "
            "VALUES ($1, $2, 'rep', $3, $4)",
            rep_user_id,
            rep_email,
            rep_account_status,
            dob,
        )
        db.execute(
            """
            INSERT INTO public.rep_profiles
                (id, user_id, display_name, school_name, city, state, graduation_year,
                 categories, profile_completeness_score, total_earnings_cents, total_campaigns_completed)
            VALUES ($1, $2, 'Test Rep', 'Test High', 'Austin', 'TX', 2027, $3, $4, $5, $6)
            """,
            rep_id,
            rep_user_id,
            categories or ["gaming"],
            profile_completeness_score,
            total_earnings_cents,
            total_campaigns_completed,
        )
        portal_expires_at = datetime.now(timezone.utc) + timedelta(days=portal_expires_in_days)
        db.execute(
            """
            INSERT INTO public.parent_records
                (parent_id, rep_id, parent_email, campaign_approval_required, values_filters,
                 digest_enabled, portal_expires_at, suspended_by_parent_at)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8)
            """,
            parent_id,
            rep_id,
            resolved_parent_email,
            campaign_approval_required,
            json.dumps(values_filters or []),
            digest_enabled,
            portal_expires_at,
            suspended_by_parent_at,
        )
        return SeededRep(
            rep_user_id=rep_user_id,
            rep_email=rep_email,
            rep_id=rep_id,
            parent_id=parent_id,
            parent_email=resolved_parent_email,
        )

    return _seed


@pytest.fixture()
def seed_pending_campaign(db):
    """Seeds a brand + campaign + a campaign_reps invitation awaiting
    parent approval for the given rep."""

    def _seed(
        *,
        rep_id: str,
        target_categories: list[str] | None = None,
        parent_approval_status: str = "pending",
        payout_per_rep_cents: int = 5000,
    ) -> str:
        brand_user_id = str(uuid.uuid4())
        brand_id = str(uuid.uuid4())
        campaign_id = str(uuid.uuid4())
        brand_email = f"brand-{brand_user_id}@example.com"

        db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", brand_user_id, brand_email)
        db.execute(
            "INSERT INTO public.users (id, email, role, account_status, date_of_birth) "
            "VALUES ($1, $2, 'brand', 'active', '1990-01-01')",
            brand_user_id,
            brand_email,
        )
        db.execute(
            "INSERT INTO public.brand_profiles (id, user_id, company_name) VALUES ($1, $2, 'Acme Co')",
            brand_id,
            brand_user_id,
        )
        db.execute(
            """
            INSERT INTO public.campaigns
                (id, brand_id, title, status, product_name, campaign_goal, key_messaging,
                 deliverables_description, target_categories, budget_cents, platform_fee_cents,
                 rep_pool_cents, payout_per_rep_cents, start_date, end_date)
            VALUES ($1, $2, 'Test Campaign', 'active', 'Widget', 'Awareness', 'Widgets are great',
                    'One TikTok post', $3, 100000, 35000, 65000, $4, CURRENT_DATE, CURRENT_DATE + 30)
            """,
            campaign_id,
            brand_id,
            target_categories or ["gaming"],
            payout_per_rep_cents,
        )
        db.execute(
            """
            INSERT INTO public.campaign_reps
                (campaign_id, rep_id, parent_approval_status, parent_approval_deadline)
            VALUES ($1, $2, $3, now() + interval '48 hours')
            """,
            campaign_id,
            rep_id,
            parent_approval_status,
        )
        return campaign_id

    return _seed


@dataclass
class SeededIntelligenceSource:
    campaign_rep_id: str
    campaign_id: str
    rep_id: str
    rep_user_id: str


@pytest.fixture()
def seed_confirmed_campaign_rep(db):
    """Build Prompt 14: seeds a full-PII rep + brand + campaign +
    campaign_reps row already in 'confirmed' or 'paid' status, for
    testing the intelligence write path (write_intelligence_events job)
    directly. Every PII field the build prompt calls out (display_name,
    school_name, instagram_handle, tiktok_handle, city, school_type) is
    populated non-default so a test can assert none of it survives into
    intelligence_events_anonymized."""

    def _seed(
        *,
        status: str = "confirmed",
        target_categories: list[str] | None = None,
        payout_per_rep_cents: int = 12000,
        school_type: str | None = "public",
        city: str = "Austin",
        state: str = "TX",
        display_name: str = "Jordan PII-Test Rep",
        school_name: str = "Identifying High School",
        instagram_handle: str = "jordan_ig_handle",
        tiktok_handle: str = "jordan_tt_handle",
    ) -> SeededIntelligenceSource:
        rep_user_id = str(uuid.uuid4())
        rep_id = str(uuid.uuid4())
        brand_user_id = str(uuid.uuid4())
        brand_id = str(uuid.uuid4())
        campaign_id = str(uuid.uuid4())
        campaign_rep_id = str(uuid.uuid4())
        rep_email = f"rep-{rep_user_id}@example.com"
        brand_email = f"brand-{brand_user_id}@example.com"

        db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", rep_user_id, rep_email)
        db.execute(
            "INSERT INTO public.users (id, email, role, account_status, date_of_birth) "
            "VALUES ($1, $2, 'rep', 'active', '2008-01-01')",
            rep_user_id,
            rep_email,
        )
        db.execute(
            """
            INSERT INTO public.rep_profiles
                (id, user_id, display_name, school_name, school_type, city, state, graduation_year,
                 categories, instagram_handle, tiktok_handle)
            VALUES ($1, $2, $3, $4, $5, $6, $7, 2027, $8, $9, $10)
            """,
            rep_id,
            rep_user_id,
            display_name,
            school_name,
            school_type,
            city,
            state,
            target_categories or ["gaming"],
            instagram_handle,
            tiktok_handle,
        )
        db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", brand_user_id, brand_email)
        db.execute(
            "INSERT INTO public.users (id, email, role, account_status, date_of_birth) "
            "VALUES ($1, $2, 'brand', 'active', '1990-01-01')",
            brand_user_id,
            brand_email,
        )
        db.execute(
            "INSERT INTO public.brand_profiles (id, user_id, company_name) VALUES ($1, $2, 'Acme Co')",
            brand_id,
            brand_user_id,
        )
        db.execute(
            """
            INSERT INTO public.campaigns
                (id, brand_id, title, status, product_name, campaign_goal, key_messaging,
                 deliverables_description, target_categories, budget_cents, platform_fee_cents,
                 rep_pool_cents, payout_per_rep_cents, start_date, end_date)
            VALUES ($1, $2, 'Test Campaign', 'active', 'Widget', 'Awareness', 'Widgets are great',
                    'One TikTok post', $3, 100000, 35000, 65000, $4, CURRENT_DATE, CURRENT_DATE + 30)
            """,
            campaign_id,
            brand_id,
            target_categories or ["gaming"],
            payout_per_rep_cents,
        )
        confirmed_at = datetime.now(timezone.utc)
        paid_at = confirmed_at if status == "paid" else None
        db.execute(
            """
            INSERT INTO public.campaign_reps
                (id, campaign_id, rep_id, status, payout_cents, confirmed_at, paid_at, ftc_disclosure_accepted)
            VALUES ($1, $2, $3, $4, $5, $6, $7, TRUE)
            """,
            campaign_rep_id,
            campaign_id,
            rep_id,
            status,
            payout_per_rep_cents,
            confirmed_at,
            paid_at,
        )
        return SeededIntelligenceSource(
            campaign_rep_id=campaign_rep_id, campaign_id=campaign_id, rep_id=rep_id, rep_user_id=rep_user_id
        )

    return _seed
