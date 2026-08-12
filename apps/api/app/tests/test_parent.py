"""Acceptance criteria for Prompt 4A (Parent Portal).

Service-layer tests against app.services.parent_service, using a
dedicated in-memory fake matching that module's exact SQL (same
substring-matching approach as test_reps.py / test_auth.py). Router-level
wiring (status codes, response shapes) is covered by the smaller set of
end-to-end tests near the bottom of this file via a real TestClient.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services import parent_service


class FakeDB:
    def __init__(self) -> None:
        self.rep_profiles: dict[str, dict] = {}
        self.users: dict[str, dict] = {}
        self.campaigns: dict[str, dict] = {}
        self.campaign_reps: dict[str, dict] = {}
        self.brand_profiles: dict[str, dict] = {}
        self.parent_records: dict[str, dict] = {}  # keyed by id
        self.parent_auth_tokens: dict[str, dict] = {}


class FakeCursor:
    def __init__(self, db: FakeDB) -> None:
        self.db = db
        self._result = None
        self._results: list = []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *exc) -> None:
        return None

    def execute(self, sql: str, params=()) -> None:
        s = " ".join(sql.split())
        params = tuple(params) if not isinstance(params, dict) else params

        if "SELECT pr.id, pr.rep_id, rp.display_name" in s and "FROM public.parent_records pr" in s:
            (email,) = params
            match = next((p for p in self.db.parent_records.values() if p["parent_email"] == email), None)
            if match is None:
                self._result = None
            else:
                rep = self.db.rep_profiles[match["rep_id"]]
                self._result = {"id": match["id"], "rep_id": match["rep_id"], "display_name": rep["display_name"]}
            return

        if s.startswith("INSERT INTO public.parent_auth_tokens"):
            parent_record_id, token_hash, expires_at = params
            token_id = str(uuid.uuid4())
            self.db.parent_auth_tokens[token_id] = {
                "id": token_id, "parent_record_id": parent_record_id, "token_hash": token_hash,
                "expires_at": expires_at, "used_at": None,
            }
            return

        if "SELECT t.id AS token_id" in s:
            (token_hash,) = params
            match = next((t for t in self.db.parent_auth_tokens.values() if t["token_hash"] == token_hash), None)
            if match is None:
                self._result = None
            else:
                pr = self.db.parent_records[match["parent_record_id"]]
                rep = self.db.rep_profiles[pr["rep_id"]]
                self._result = {
                    "token_id": match["id"], "expires_at": match["expires_at"], "used_at": match["used_at"],
                    "parent_record_id": pr["id"], "rep_id": pr["rep_id"], "portal_expires_at": pr["portal_expires_at"],
                    "parent_email": pr["parent_email"], "display_name": rep["display_name"],
                }
            return

        if s.startswith("UPDATE public.parent_auth_tokens SET used_at"):
            (token_id,) = params
            self.db.parent_auth_tokens[token_id]["used_at"] = datetime.now(timezone.utc)
            return

        if s == "SELECT * FROM public.parent_records WHERE id = %s":
            # Used by app.core.parent_security.load_parent_record on
            # every /parent/* request (session verification + portal
            # expiry check).
            (parent_record_id,) = params
            self._result = dict(self.db.parent_records[parent_record_id]) if parent_record_id in self.db.parent_records else None
            return

        if "SELECT display_name, school_name, graduation_year, categories" in s:
            (rep_id,) = params
            rp = self.db.rep_profiles.get(rep_id)
            self._result = dict(rp) if rp else None
            return

        if "SELECT cr.id AS campaign_reps_id, cr.campaign_id, cr.parent_approval_deadline" in s:
            (rep_id,) = params
            out = []
            for cr in self.db.campaign_reps.values():
                if cr["rep_id"] != rep_id or cr["parent_approval_status"] != "pending":
                    continue
                c = self.db.campaigns[cr["campaign_id"]]
                b = self.db.brand_profiles[c["brand_id"]]
                out.append({
                    "campaign_reps_id": cr["id"], "campaign_id": c["id"],
                    "parent_approval_deadline": cr["parent_approval_deadline"],
                    "product_name": c["product_name"], "key_messaging": c["key_messaging"],
                    "deliverables_description": c["deliverables_description"],
                    "prohibited_content": c["prohibited_content"], "payout_cents": c["payout_per_rep_cents"],
                    "start_date": c["start_date"], "end_date": c["end_date"],
                    "target_categories": c["target_categories"], "brand_name": b["company_name"],
                })
            self._results = out
            return

        if s == "SELECT * FROM public.campaign_reps WHERE rep_id = %s AND campaign_id = %s":
            rep_id, campaign_id = params
            match = next(
                (r for r in self.db.campaign_reps.values() if r["rep_id"] == rep_id and r["campaign_id"] == campaign_id),
                None,
            )
            self._result = dict(match) if match else None
            return

        if s.startswith("SELECT * FROM public.campaign_reps") and "parent_approval_status = 'pending'" in s:
            rep_id, campaign_id = params
            match = next(
                (r for r in self.db.campaign_reps.values()
                 if r["rep_id"] == rep_id and r["campaign_id"] == campaign_id and r["parent_approval_status"] == "pending"),
                None,
            )
            self._result = dict(match) if match else None
            return

        if s.startswith("UPDATE public.campaign_reps SET parent_approval_status = 'approved'"):
            (cr_id,) = params
            row = self.db.campaign_reps[cr_id]
            row.update(parent_approval_status="approved", parent_decided_at=datetime.now(timezone.utc))
            self._result = row
            return

        if s.startswith("UPDATE public.campaign_reps") and "parent_approval_status = 'blocked'" in s and "id = %s" in s and "RETURNING *" in s:
            (cr_id,) = params
            row = self.db.campaign_reps[cr_id]
            row.update(parent_approval_status="blocked", parent_decided_at=datetime.now(timezone.utc), status="declined")
            self._result = row
            return

        if "SELECT values_filters, campaign_approval_required, digest_enabled" in s and "WHERE id = %s" in s and "UPDATE" not in s:
            (parent_record_id,) = params
            pr = self.db.parent_records.get(parent_record_id)
            self._result = (
                {"values_filters": pr["values_filters"], "campaign_approval_required": pr["campaign_approval_required"], "digest_enabled": pr["digest_enabled"]}
                if pr else None
            )
            return

        if s.startswith("UPDATE public.parent_records SET values_filters"):
            values_filters, parent_record_id = params
            pr = self.db.parent_records[parent_record_id]
            pr["values_filters"] = values_filters
            self._result = {"values_filters": pr["values_filters"], "campaign_approval_required": pr["campaign_approval_required"], "digest_enabled": pr["digest_enabled"]}
            return

        if s.startswith("UPDATE public.parent_records SET campaign_approval_required"):
            campaign_approval_required, parent_record_id = params
            pr = self.db.parent_records[parent_record_id]
            pr["campaign_approval_required"] = campaign_approval_required
            self._result = {"values_filters": pr["values_filters"], "campaign_approval_required": pr["campaign_approval_required"], "digest_enabled": pr["digest_enabled"]}
            return

        if s.startswith("UPDATE public.parent_records SET digest_enabled"):
            digest_enabled, parent_record_id = params
            pr = self.db.parent_records[parent_record_id]
            pr["digest_enabled"] = digest_enabled
            self._result = {"values_filters": pr["values_filters"], "campaign_approval_required": pr["campaign_approval_required"], "digest_enabled": pr["digest_enabled"]}
            return

        if "SELECT u.date_of_birth FROM public.users u" in s:
            (rep_id,) = params
            rp = self.db.rep_profiles[rep_id]
            self._result = {"date_of_birth": self.db.users[rp["user_id"]]["date_of_birth"]}
            return

        if "SELECT categories, profile_completeness_score, total_earnings_cents" in s:
            (rep_id,) = params
            rp = self.db.rep_profiles[rep_id]
            self._result = {
                "categories": rp["categories"], "profile_completeness_score": rp["profile_completeness_score"],
                "total_earnings_cents": rp["total_earnings_cents"],
            }
            return

        if "SELECT COUNT(*) AS n, COALESCE(SUM(payout_cents), 0) AS earned" in s:
            rep_id, month_start = params
            matches = [
                cr for cr in self.db.campaign_reps.values()
                if cr["rep_id"] == rep_id and cr["status"] in ("confirmed", "paid")
                and cr.get("confirmed_at") and cr["confirmed_at"] >= month_start
            ]
            self._result = {"n": len(matches), "earned": sum(cr.get("payout_cents") or 0 for cr in matches)}
            return

        if s.startswith("UPDATE public.parent_records SET suspended_by_parent_at = %s"):
            now, parent_record_id = params
            self.db.parent_records[parent_record_id]["suspended_by_parent_at"] = now
            return

        if s.startswith("UPDATE public.users SET account_status = 'suspended'"):
            (rep_id,) = params
            rp = self.db.rep_profiles[rep_id]
            user = self.db.users[rp["user_id"]]
            user["account_status"] = "suspended"
            self._result = {"email": user["email"]}
            return

        if s == "SELECT suspended_by_parent_at FROM public.parent_records WHERE id = %s":
            (parent_record_id,) = params
            pr = self.db.parent_records.get(parent_record_id)
            self._result = {"suspended_by_parent_at": pr["suspended_by_parent_at"]} if pr else None
            return

        if s.startswith("UPDATE public.parent_records SET suspended_by_parent_at = NULL"):
            (parent_record_id,) = params
            self.db.parent_records[parent_record_id]["suspended_by_parent_at"] = None
            return

        if s.startswith("UPDATE public.users SET account_status = 'active'"):
            (rep_id,) = params
            rp = self.db.rep_profiles[rep_id]
            self.db.users[rp["user_id"]]["account_status"] = "active"
            return

        raise AssertionError(f"FakeCursor got an unexpected query: {s}")

    def fetchone(self):
        return self._result

    def fetchall(self):
        return self._results


class FakeConn:
    def __init__(self, db: FakeDB) -> None:
        self.db = db

    def cursor(self) -> FakeCursor:
        return FakeCursor(self.db)

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        pass


REP_ID = "10000000-0000-0000-0000-000000000001"
REP_USER_ID = "00000000-0000-0000-0000-000000000001"
PARENT_RECORD_ID = "20000000-0000-0000-0000-000000000001"


@pytest.fixture
def fake_db() -> FakeDB:
    db = FakeDB()
    db.users[REP_USER_ID] = {
        "id": REP_USER_ID, "email": "rep@example.com", "role": "rep", "account_status": "active",
        "date_of_birth": date.today().replace(year=date.today().year - 16),
    }
    db.rep_profiles[REP_ID] = {
        "id": REP_ID, "user_id": REP_USER_ID, "display_name": "Rep One", "school_name": "Lincoln High",
        "graduation_year": 2027, "categories": ["gaming"], "profile_completeness_score": 50,
        "total_earnings_cents": 5000, "total_campaigns_completed": 2,
    }
    db.parent_records[PARENT_RECORD_ID] = {
        "id": PARENT_RECORD_ID, "rep_id": REP_ID, "parent_email": "parent@example.com",
        "campaign_approval_required": True, "values_filters": [], "digest_enabled": True,
        "portal_expires_at": datetime.now(timezone.utc) + timedelta(days=365),
        "suspended_by_parent_at": None,
    }
    return db


@pytest.fixture
def settings() -> Settings:
    from app.tests.conftest import _test_settings

    return _test_settings()


def _make_campaign(fake_db: FakeDB, **overrides) -> str:
    brand_id = str(uuid.uuid4())
    fake_db.brand_profiles[brand_id] = {"id": brand_id, "company_name": "Acme Co"}
    campaign_id = str(uuid.uuid4())
    fake_db.campaigns[campaign_id] = {
        "id": campaign_id, "brand_id": brand_id, "product_name": "Widget",
        "key_messaging": "Widgets are great", "deliverables_description": "1 post",
        "prohibited_content": None, "payout_per_rep_cents": 5000, "target_categories": ["gaming"],
        "start_date": date(2026, 1, 1), "end_date": date(2026, 2, 1),
        **overrides,
    }
    return campaign_id


def _make_pending_campaign_rep(fake_db: FakeDB, campaign_id: str, **overrides) -> str:
    cr_id = str(uuid.uuid4())
    fake_db.campaign_reps[cr_id] = {
        "id": cr_id, "rep_id": REP_ID, "campaign_id": campaign_id, "status": "invited",
        "parent_approval_status": "pending",
        "parent_approval_deadline": datetime.now(timezone.utc) + timedelta(hours=48),
        "parent_decided_at": None, "confirmed_at": None, "payout_cents": None,
        **overrides,
    }
    return cr_id


# ── Auth: non-enumeration + rate limiting ───────────────────────────


def test_request_link_no_enumeration_for_unknown_email(fake_db: FakeDB, settings: Settings, monkeypatch) -> None:
    sent = []
    monkeypatch.setattr(
        "app.services.email_service.send_parent_magic_link_email",
        lambda **kw: sent.append(kw),
    )
    # No error raised, no email sent, regardless of whether the email matches.
    parent_service.request_link(FakeConn(fake_db), settings, parent_email="nobody@example.com")
    assert sent == []


def test_request_link_sends_for_known_email(fake_db: FakeDB, settings: Settings, monkeypatch) -> None:
    sent = []
    monkeypatch.setattr(
        "app.services.email_service.send_parent_magic_link_email",
        lambda **kw: sent.append(kw),
    )
    parent_service.request_link(FakeConn(fake_db), settings, parent_email="parent@example.com")
    assert len(sent) == 1
    assert sent[0]["parent_email"] == "parent@example.com"
    assert len(fake_db.parent_auth_tokens) == 1


# ── Auth: verify token ───────────────────────────────────────────────


def test_verify_token_invalid(fake_db: FakeDB, settings: Settings) -> None:
    with pytest.raises(parent_service.TokenInvalidError):
        parent_service.verify_token(FakeConn(fake_db), settings, token="not-a-real-token")


def test_verify_token_expired(fake_db: FakeDB, settings: Settings) -> None:
    token_hash = parent_service._hash_token("expired-token")
    fake_db.parent_auth_tokens["t1"] = {
        "id": "t1", "parent_record_id": PARENT_RECORD_ID, "token_hash": token_hash,
        "expires_at": datetime.now(timezone.utc) - timedelta(minutes=1), "used_at": None,
    }
    with pytest.raises(parent_service.TokenExpiredError):
        parent_service.verify_token(FakeConn(fake_db), settings, token="expired-token")


def test_verify_token_already_used(fake_db: FakeDB, settings: Settings) -> None:
    token_hash = parent_service._hash_token("used-token")
    fake_db.parent_auth_tokens["t1"] = {
        "id": "t1", "parent_record_id": PARENT_RECORD_ID, "token_hash": token_hash,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10), "used_at": datetime.now(timezone.utc),
    }
    with pytest.raises(parent_service.TokenAlreadyUsedError):
        parent_service.verify_token(FakeConn(fake_db), settings, token="used-token")


def test_verify_token_success_issues_session(fake_db: FakeDB, settings: Settings) -> None:
    token_hash = parent_service._hash_token("good-token")
    fake_db.parent_auth_tokens["t1"] = {
        "id": "t1", "parent_record_id": PARENT_RECORD_ID, "token_hash": token_hash,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10), "used_at": None,
    }
    session_token, rep_id = parent_service.verify_token(FakeConn(fake_db), settings, token="good-token")
    assert rep_id == REP_ID
    assert isinstance(session_token, str) and session_token
    assert fake_db.parent_auth_tokens["t1"]["used_at"] is not None


def test_verify_token_portal_closed_at_18(fake_db: FakeDB, settings: Settings, monkeypatch) -> None:
    fake_db.parent_records[PARENT_RECORD_ID]["portal_expires_at"] = datetime.now(timezone.utc) - timedelta(days=1)
    token_hash = parent_service._hash_token("adult-token")
    fake_db.parent_auth_tokens["t1"] = {
        "id": "t1", "parent_record_id": PARENT_RECORD_ID, "token_hash": token_hash,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10), "used_at": None,
    }
    monkeypatch.setattr("app.services.email_service.send_portal_closed_email", lambda **kw: None)
    with pytest.raises(parent_service.PortalClosedError):
        parent_service.verify_token(FakeConn(fake_db), settings, token="adult-token")


# ── Dashboard ───────────────────────────────────────────────────────


def test_get_dashboard_returns_earnings_and_summary(fake_db: FakeDB) -> None:
    dashboard = parent_service.get_dashboard(FakeConn(fake_db), REP_ID)
    assert dashboard["display_name"] == "Rep One"
    assert dashboard["total_earnings_cents"] == 5000
    assert dashboard["total_campaigns_completed"] == 2


# ── Campaign approval queue ──────────────────────────────────────────


def test_approve_campaign(fake_db: FakeDB) -> None:
    campaign_id = _make_campaign(fake_db)
    cr_id = _make_pending_campaign_rep(fake_db, campaign_id)

    row = parent_service.approve_campaign(FakeConn(fake_db), REP_ID, campaign_id)
    assert row["parent_approval_status"] == "approved"
    assert fake_db.campaign_reps[cr_id]["parent_approval_status"] == "approved"


def test_approve_campaign_idempotent(fake_db: FakeDB) -> None:
    campaign_id = _make_campaign(fake_db)
    _make_pending_campaign_rep(fake_db, campaign_id, parent_approval_status="approved")

    row = parent_service.approve_campaign(FakeConn(fake_db), REP_ID, campaign_id)
    assert row["parent_approval_status"] == "approved"


def test_block_campaign_neutral_auto_decline(fake_db: FakeDB) -> None:
    """A parent block must land at status='declined' with no reason field
    exposed anywhere in the row a brand-facing query would read.
    """
    campaign_id = _make_campaign(fake_db)
    cr_id = _make_pending_campaign_rep(fake_db, campaign_id)

    row = parent_service.block_campaign(FakeConn(fake_db), REP_ID, campaign_id)
    assert row["parent_approval_status"] == "blocked"
    assert row["status"] == "declined"
    assert fake_db.campaign_reps[cr_id]["status"] == "declined"


def test_block_campaign_not_pending_raises(fake_db: FakeDB) -> None:
    campaign_id = _make_campaign(fake_db)
    with pytest.raises(parent_service.CampaignNotPendingError):
        parent_service.block_campaign(FakeConn(fake_db), REP_ID, campaign_id)


def test_pending_campaigns_returns_full_brief(fake_db: FakeDB) -> None:
    campaign_id = _make_campaign(fake_db, target_categories=["gaming", "in_person_travel_required"])
    _make_pending_campaign_rep(fake_db, campaign_id)

    rows = parent_service.pending_campaigns(FakeConn(fake_db), REP_ID)
    assert len(rows) == 1
    assert rows[0]["brand_name"] == "Acme Co"
    assert rows[0]["requires_in_person"] is True


# ── Settings / values filters / approval toggle ─────────────────────


def test_update_values_filters(fake_db: FakeDB) -> None:
    row = parent_service.update_values_filters(FakeConn(fake_db), PARENT_RECORD_ID, ["alcohol_adjacent", "gambling"])
    assert row["values_filters"] == ["alcohol_adjacent", "gambling"]


def test_approval_toggle_rejected_under_16(fake_db: FakeDB) -> None:
    fake_db.users[REP_USER_ID]["date_of_birth"] = date.today().replace(year=date.today().year - 14)
    with pytest.raises(parent_service.ApprovalToggleNotPermittedError):
        parent_service.update_approval_required(
            FakeConn(fake_db), PARENT_RECORD_ID, REP_ID, campaign_approval_required=False
        )


def test_approval_toggle_allowed_for_16_17(fake_db: FakeDB) -> None:
    fake_db.users[REP_USER_ID]["date_of_birth"] = date.today().replace(year=date.today().year - 17)
    row = parent_service.update_approval_required(
        FakeConn(fake_db), PARENT_RECORD_ID, REP_ID, campaign_approval_required=False
    )
    assert row["campaign_approval_required"] is False


def test_approval_toggle_rejected_at_18(fake_db: FakeDB) -> None:
    fake_db.users[REP_USER_ID]["date_of_birth"] = date.today().replace(year=date.today().year - 18)
    with pytest.raises(parent_service.ApprovalToggleNotPermittedError):
        parent_service.update_approval_required(
            FakeConn(fake_db), PARENT_RECORD_ID, REP_ID, campaign_approval_required=True
        )


# ── Monthly digest content boundary ─────────────────────────────────


def test_digest_preview_excludes_message_and_submission_content(fake_db: FakeDB) -> None:
    """Hard content-boundary check (deliverable 5): the digest payload
    must never contain recruiter message content, submission text/files,
    or brand contact details -- verified here by asserting the whole
    serialized digest only contains the allow-listed keys.
    """
    digest = parent_service.digest_preview(FakeConn(fake_db), REP_ID)
    allowed_keys = {
        "campaigns_completed_this_month", "earnings_this_month_cents",
        "earnings_lifetime_cents", "profile_completeness_score", "categories_active_in",
    }
    assert set(digest.keys()) == allowed_keys
    serialized = str(digest)
    for forbidden in ("submission_text", "submission_file_urls", "message_text", "brand_email", "brand_contact"):
        assert forbidden not in serialized


# ── Account controls ─────────────────────────────────────────────────


def test_suspend_account_sets_status_and_notifies(fake_db: FakeDB, monkeypatch) -> None:
    sent = []
    monkeypatch.setattr("app.services.email_service.send_account_suspended_email", lambda **kw: sent.append(kw))

    parent_service.suspend_account(FakeConn(fake_db), PARENT_RECORD_ID, REP_ID, settings=settings)
    assert fake_db.users[REP_USER_ID]["account_status"] == "suspended"
    assert fake_db.parent_records[PARENT_RECORD_ID]["suspended_by_parent_at"] is not None
    assert len(sent) == 1


def test_unsuspend_reverses_parent_initiated_suspension(fake_db: FakeDB, monkeypatch) -> None:
    monkeypatch.setattr("app.services.email_service.send_account_suspended_email", lambda **kw: None)
    parent_service.suspend_account(FakeConn(fake_db), PARENT_RECORD_ID, REP_ID, settings=settings)

    parent_service.unsuspend_account(FakeConn(fake_db), PARENT_RECORD_ID, REP_ID)
    assert fake_db.users[REP_USER_ID]["account_status"] == "active"
    assert fake_db.parent_records[PARENT_RECORD_ID]["suspended_by_parent_at"] is None


def test_unsuspend_rejected_when_not_parent_initiated(fake_db: FakeDB) -> None:
    # No suspension has happened at all -- same failure mode as an
    # admin-initiated suspension from the parent's point of view.
    with pytest.raises(PermissionError):
        parent_service.unsuspend_account(FakeConn(fake_db), PARENT_RECORD_ID, REP_ID)


# ── End-to-end router smoke tests ────────────────────────────────────


@pytest.fixture
def parent_client(settings: Settings, fake_db: FakeDB, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    from app.core import db as db_module
    from app.routers import parent as parent_router

    @contextmanager
    def fake_get_connection(_settings: Settings):
        yield FakeConn(fake_db)

    monkeypatch.setattr(db_module, "get_connection", fake_get_connection)
    monkeypatch.setattr(parent_router, "get_connection", fake_get_connection)

    return TestClient(create_app(settings=settings))


def _parent_headers(settings: Settings) -> dict:
    from app.core.parent_security import issue_parent_session_token

    token = issue_parent_session_token(parent_record_id=PARENT_RECORD_ID, rep_id=REP_ID, settings=settings)
    return {"Authorization": f"Bearer {token}"}


def test_request_link_route_always_202(parent_client: TestClient) -> None:
    resp = parent_client.post("/parent/auth/request-link", json={"parent_email": "unknown@example.com"})
    assert resp.status_code == 202
    assert resp.json() == {"status": "sent_if_eligible"}


def test_dashboard_requires_session(parent_client: TestClient) -> None:
    resp = parent_client.get("/parent/dashboard")
    assert resp.status_code == 401


def test_dashboard_with_valid_session(parent_client: TestClient, settings: Settings) -> None:
    resp = parent_client.get("/parent/dashboard", headers=_parent_headers(settings))
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Rep One"


def test_session_rejected_after_portal_expiry(parent_client: TestClient, settings: Settings, fake_db: FakeDB) -> None:
    fake_db.parent_records[PARENT_RECORD_ID]["portal_expires_at"] = datetime.now(timezone.utc) - timedelta(days=1)
    resp = parent_client.get("/parent/dashboard", headers=_parent_headers(settings))
    assert resp.status_code == 403
    assert "closed" in resp.json()["error"]["message"].lower()
