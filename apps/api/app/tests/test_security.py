"""Acceptance criteria for Prompt 3."""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.errors import register_exception_handlers
from app.core.security import CurrentUser, require_active_account, require_role


def _app_with_test_routes(settings: Settings) -> FastAPI:
    from app.main import create_app

    app = create_app(settings=settings)

    @app.get("/_test/brand-only")
    def brand_only(user: CurrentUser = Depends(require_role("brand"))) -> dict:
        return {"ok": True}

    @app.get("/_test/active-only")
    def active_only(user: CurrentUser = Depends(require_active_account)) -> dict:
        return {"ok": True}

    return app


@pytest.fixture
def test_client(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    from app.core import security
    from app.tests.conftest import FAKE_USERS

    def fake_load_user_row(user_id: str, _settings: Settings) -> dict | None:
        for user in FAKE_USERS.values():
            if user["id"] == user_id:
                return user
        return None

    monkeypatch.setattr(security, "load_user_row", fake_load_user_row)
    return TestClient(_app_with_test_routes(settings))


def test_no_auth_header_returns_401(test_client: TestClient) -> None:
    resp = test_client.get("/_test/brand-only")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


def test_wrong_role_returns_403(test_client: TestClient, auth_headers) -> None:
    resp = test_client.get("/_test/brand-only", headers=auth_headers("rep"))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


def test_correct_role_returns_200(test_client: TestClient, auth_headers) -> None:
    resp = test_client.get("/_test/brand-only", headers=auth_headers("brand"))
    assert resp.status_code == 200


def test_pending_account_rejected_by_active_dependency(test_client: TestClient, auth_headers) -> None:
    resp = test_client.get("/_test/active-only", headers=auth_headers("pending_rep"))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


def test_active_account_allowed(test_client: TestClient, auth_headers) -> None:
    resp = test_client.get("/_test/active-only", headers=auth_headers("rep"))
    assert resp.status_code == 200


def test_config_fails_fast_on_missing_required_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    monkeypatch.setenv("NEXT_PUBLIC_SUPABASE_URL", "http://localhost:54321")
    with pytest.raises(Exception):
        Settings(_env_file=None)


def test_health_endpoint(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
