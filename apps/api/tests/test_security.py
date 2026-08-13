from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import register_exception_handlers
from app.core.security import get_current_user, get_parent_session, require_role


def _protected_app() -> FastAPI:
    """A throwaway app exercising the security dependencies directly —
    Prompt 3 ships no protected business routes yet, those land with
    each portal's routers in later prompts."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/whoami")
    def whoami(user=Depends(get_current_user)):
        return {"id": user.id, "role": user.role}

    @app.get("/brand-only")
    def brand_only(user=Depends(require_role("brand"))):
        return {"ok": True}

    @app.get("/parent-portal/ping")
    def parent_ping(session=Depends(get_parent_session)):
        return {"parent_id": session.parent_id, "talent_id": session.talent_id}

    return app


@pytest.fixture()
def protected_client():
    return TestClient(_protected_app())


def test_missing_authorization_header_returns_401(protected_client):
    response  = protected_client.get("/whoami")
    assert response .status_code == 401
    assert response .json()["error"]["code"] == "missing_credentials"


def test_wrong_role_jwt_returns_403(protected_client, auth_headers_factory):
    headers = auth_headers_factory("talent")
    response  = protected_client.get("/brand-only", headers=headers)
    assert response .status_code == 403
    assert response .json()["error"]["code"] == "role_mismatch"


def test_matching_role_jwt_succeeds(protected_client, auth_headers_factory):
    headers = auth_headers_factory("brand")
    response  = protected_client.get("/brand-only", headers=headers)
    assert response .status_code == 200


def test_suspended_account_returns_403_distinct_from_role_mismatch(protected_client, auth_headers_factory):
    headers = auth_headers_factory("brand", account_status="suspended")
    response  = protected_client.get("/brand-only", headers=headers)
    assert response .status_code == 403
    assert response .json()["error"]["code"] == "account_not_active"


def test_authenticated_headers_fixture_works_for_every_role(protected_client, authenticated_headers, role):
    response  = protected_client.get("/whoami", headers=authenticated_headers)
    assert response .status_code == 200
    assert response .json()["role"] == role


def test_parent_session_fixture_authenticates_parent_portal_route(protected_client, parent_session_headers):
    response  = protected_client.get("/parent-portal/ping", headers=parent_session_headers)
    assert response .status_code == 200
    body = response .json()
    assert body["parent_id"] == "parent-00000000-0000-0000-0000-000000000001"
    assert body["talent_id"] == "talent-00000000-0000-0000-0000-000000000001"


def test_supabase_jwt_rejected_by_parent_session_dependency(protected_client, auth_headers_factory):
    headers = auth_headers_factory("talent")
    response  = protected_client.get("/parent-portal/ping", headers=headers)
    assert response .status_code == 401
    assert response .json()["error"]["code"] == "invalid_parent_session"


def test_missing_required_env_var_fails_fast(settings, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
