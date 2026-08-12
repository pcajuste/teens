"""Acceptance criteria for Prompt 4 (signup / age-gate / parental consent).

Uses an in-memory fake for app.core.db.get_connection so the whole
state machine is exercised without a live Postgres -- mirrors Prompt
3's approach of monkeypatching a single DB seam (there,
security.load_user_row; here, get_connection itself, since Prompt 4
introduces real writes). supabase_admin.create_auth_user and
email_service.send_parental_consent_email are monkeypatched too, so no
network call ever happens in this suite.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


class FakeCursor:
    def __init__(self, store: dict[str, dict]) -> None:
        self.store = store
        self._result: dict | None = None

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *exc) -> None:
        return None

    def execute(self, sql: str, params: tuple = ()) -> None:
        sql_norm = " ".join(sql.split())

        if sql_norm.startswith("INSERT INTO public.users"):
            (
                user_id, email, role, account_status, dob, parent_email,
                consent_token, consent_created_at, consent_expires_at,
            ) = params
            for row in self.store.values():
                if row["email"] == email:
                    raise psycopg.errors.UniqueViolation("duplicate email")
            self.store[user_id] = {
                "id": user_id,
                "email": email,
                "role": role,
                "account_status": account_status,
                "date_of_birth": dob,
                "parent_email": parent_email,
                "consent_token": consent_token,
                "consent_token_created_at": consent_created_at,
                "consent_token_expires_at": consent_expires_at,
                "consent_token_used_at": None,
                "parent_verified_at": None,
            }
            self._result = None
            return

        if "WHERE consent_token = %s" in sql_norm and sql_norm.startswith("SELECT"):
            (token,) = params
            self._result = next((r for r in self.store.values() if r["consent_token"] == token), None)
            return

        if sql_norm.startswith("UPDATE public.users SET parent_verified_at"):
            now, used_at, user_id = params
            self.store[user_id]["parent_verified_at"] = now
            self.store[user_id]["account_status"] = "active"
            self.store[user_id]["consent_token_used_at"] = used_at
            self._result = None
            return

        if sql_norm.startswith("SELECT id, parent_email, account_status"):
            (email,) = params
            self._result = next((r for r in self.store.values() if r["email"] == email), None)
            return

        if sql_norm.startswith("UPDATE public.users SET consent_token = %s"):
            new_token, created_at, expires_at, user_id = params
            self.store[user_id]["consent_token"] = new_token
            self.store[user_id]["consent_token_created_at"] = created_at
            self.store[user_id]["consent_token_expires_at"] = expires_at
            self.store[user_id]["consent_token_used_at"] = None
            self._result = None
            return

        if sql_norm.startswith("SELECT id, email, role, account_status, consent_token, parent_verified_at"):
            (user_id,) = params
            self._result = self.store.get(user_id)
            return

        if sql_norm.startswith("SELECT id, email, role, account_status FROM public.users"):
            (user_id,) = params
            self._result = self.store.get(user_id)
            return

        raise AssertionError(f"FakeCursor got an unexpected query: {sql_norm}")

    def fetchone(self) -> dict | None:
        return self._result


class FakeConn:
    def __init__(self, store: dict[str, dict]) -> None:
        self.store = store

    def cursor(self) -> FakeCursor:
        return FakeCursor(self.store)

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        pass


@pytest.fixture
def fake_store() -> dict[str, dict]:
    return {}


@pytest.fixture
def sent_emails() -> list[dict]:
    return []


@pytest.fixture
def auth_client(settings: Settings, fake_store: dict, sent_emails: list, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    from app.core import db as db_module
    from app.routers import auth as auth_router_module
    from app.services import email_service, supabase_admin

    @contextmanager
    def fake_get_connection(_settings: Settings):
        yield FakeConn(fake_store)

    monkeypatch.setattr(db_module, "get_connection", fake_get_connection)
    monkeypatch.setattr(auth_router_module, "get_connection", fake_get_connection)

    def fake_create_auth_user(*, email: str, password: str, settings: Settings) -> str:
        return str(uuid.uuid4())

    monkeypatch.setattr(supabase_admin, "create_auth_user", fake_create_auth_user)

    def fake_send_consent_email(*, parent_email: str, rep_display_name: str, consent_token: str, settings: Settings) -> None:
        sent_emails.append({"parent_email": parent_email, "consent_token": consent_token})

    monkeypatch.setattr(email_service, "send_parental_consent_email", fake_send_consent_email)

    app = create_app(settings=settings)
    return TestClient(app)


def _dob_for_age(age: int) -> str:
    today = date.today()
    return date(today.year - age, today.month, today.day).isoformat()


def test_signup_age_12_rejected_no_row_created(auth_client: TestClient, fake_store: dict) -> None:
    resp = auth_client.post(
        "/auth/signup",
        json={
            "email": "kid@example.com",
            "password": "hunter2hunter2",
            "role": "rep",
            "date_of_birth": _dob_for_age(12),
        },
    )
    assert resp.status_code == 400
    assert fake_store == {}


def test_signup_age_15_rep_requires_parent_email(auth_client: TestClient) -> None:
    resp = auth_client.post(
        "/auth/signup",
        json={
            "email": "teen15@example.com",
            "password": "hunter2hunter2",
            "role": "rep",
            "date_of_birth": _dob_for_age(15),
        },
    )
    assert resp.status_code == 400


def test_signup_age_15_rep_pending_and_sends_email(auth_client: TestClient, fake_store: dict, sent_emails: list) -> None:
    resp = auth_client.post(
        "/auth/signup",
        json={
            "email": "teen15b@example.com",
            "password": "hunter2hunter2",
            "role": "rep",
            "date_of_birth": _dob_for_age(15),
            "parent_email": "parent@example.com",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["account_status"] == "pending"

    row = fake_store[body["user_id"]]
    assert row["consent_token"] is not None
    assert len(sent_emails) == 1
    assert sent_emails[0]["parent_email"] == "parent@example.com"


def test_signup_age_16_rep_active_immediately(auth_client: TestClient) -> None:
    resp = auth_client.post(
        "/auth/signup",
        json={
            "email": "teen16@example.com",
            "password": "hunter2hunter2",
            "role": "rep",
            "date_of_birth": _dob_for_age(16),
        },
    )
    assert resp.status_code == 201
    assert resp.json()["account_status"] == "active"


@pytest.mark.parametrize("role", ["brand", "recruiter"])
def test_signup_brand_recruiter_always_pending(auth_client: TestClient, role: str) -> None:
    resp = auth_client.post(
        "/auth/signup",
        json={
            "email": f"{role}@example.com",
            "password": "hunter2hunter2",
            "role": role,
            "date_of_birth": _dob_for_age(30),
        },
    )
    assert resp.status_code == 201
    assert resp.json()["account_status"] == "pending"


def test_consent_token_activates_account(auth_client: TestClient, fake_store: dict) -> None:
    signup_resp = auth_client.post(
        "/auth/signup",
        json={
            "email": "teen15c@example.com",
            "password": "hunter2hunter2",
            "role": "rep",
            "date_of_birth": _dob_for_age(15),
            "parent_email": "parent2@example.com",
        },
    )
    token = fake_store[signup_resp.json()["user_id"]]["consent_token"]

    resp = auth_client.post(f"/auth/parent-verify/{token}")
    assert resp.status_code == 200
    assert resp.json()["account_status"] == "active"


def test_consent_token_used_twice_returns_conflict(auth_client: TestClient, fake_store: dict) -> None:
    signup_resp = auth_client.post(
        "/auth/signup",
        json={
            "email": "teen15d@example.com",
            "password": "hunter2hunter2",
            "role": "rep",
            "date_of_birth": _dob_for_age(15),
            "parent_email": "parent3@example.com",
        },
    )
    token = fake_store[signup_resp.json()["user_id"]]["consent_token"]

    first = auth_client.post(f"/auth/parent-verify/{token}")
    assert first.status_code == 200

    second = auth_client.post(f"/auth/parent-verify/{token}")
    assert second.status_code == 409
    

def test_consent_token_expired_returns_410(auth_client: TestClient, fake_store: dict) -> None:
    signup_resp = auth_client.post(
        "/auth/signup",
        json={
            "email": "teen15e@example.com",
            "password": "hunter2hunter2",
            "role": "rep",
            "date_of_birth": _dob_for_age(15),
            "parent_email": "parent4@example.com",
        },
    )
    user_id = signup_resp.json()["user_id"]
    token = fake_store[user_id]["consent_token"]
    fake_store[user_id]["consent_token_expires_at"] = datetime.now(timezone.utc) - timedelta(hours=1)

    resp = auth_client.post(f"/auth/parent-verify/{token}")
    assert resp.status_code == 410
    

def test_consent_token_invalid_returns_400(auth_client: TestClient) -> None:
    resp = auth_client.post("/auth/parent-verify/not-a-real-token")
    assert resp.status_code == 400
    

def test_resend_consent_regenerates_token_and_sends_email(auth_client: TestClient, fake_store: dict, sent_emails: list) -> None:
    signup_resp = auth_client.post(
        "/auth/signup",
        json={
            "email": "teen15f@example.com",
            "password": "hunter2hunter2",
            "role": "rep",
            "date_of_birth": _dob_for_age(15),
            "parent_email": "parent5@example.com",
        },
    )
    user_id = signup_resp.json()["user_id"]
    original_token = fake_store[user_id]["consent_token"]

    resp = auth_client.post("/auth/resend-consent", json={"email": "teen15f@example.com"})
    assert resp.status_code == 202
    assert fake_store[user_id]["consent_token"] != original_token
    assert len(sent_emails) == 2


def test_resend_consent_rate_limited(auth_client: TestClient) -> None:
    auth_client.post(
        "/auth/signup",
        json={
            "email": "teen15g@example.com",
            "password": "hunter2hunter2",
            "role": "rep",
            "date_of_birth": _dob_for_age(15),
            "parent_email": "parent6@example.com",
        },
    )
    first = auth_client.post("/auth/resend-consent", json={"email": "teen15g@example.com"})
    assert first.status_code == 202
    second = auth_client.post("/auth/resend-consent", json={"email": "teen15g@example.com"})
    assert second.status_code == 429


def test_me_reports_awaiting_parent_consent(auth_client: TestClient, fake_store: dict) -> None:
    import jwt
    from app.tests.conftest import TEST_JWT_SECRET

    signup_resp = auth_client.post(
        "/auth/signup",
        json={
            "email": "teen15h@example.com",
            "password": "hunter2hunter2",
            "role": "rep",
            "date_of_birth": _dob_for_age(15),
            "parent_email": "parent7@example.com",
        },
    )
    user_id = signup_resp.json()["user_id"]
    token = jwt.encode({"sub": user_id, "email": "teen15h@example.com", "aud": "authenticated"}, TEST_JWT_SECRET, algorithm="HS256")

    resp = auth_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["account_status"] == "pending"
    assert body["pending_reason"] == "awaiting_parent_consent"
