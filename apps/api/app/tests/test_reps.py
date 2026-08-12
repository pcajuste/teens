"""Acceptance criteria for Prompt 5 (Rep Portal backend).

Same approach as test_auth.py: an in-memory fake standing in for
app.core.db.get_connection, with one handler per distinct SQL
statement rep_service.py actually issues (there are few enough that
matching by substring is more reliable here than a real mini-SQL
parser would be worth building).
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.tests.conftest import TEST_JWT_SECRET


class FakeDB:
    def __init__(self) -> None:
        self.users: dict[str, dict] = {}
        self.rep_profiles: dict[str, dict] = {}
        self.campaigns: dict[str, dict] = {}
        self.campaign_reps: dict[str, dict] = {}
        self.parent_records: dict[str, dict] = {}  # keyed by rep_id


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

        if s == "SELECT id, email, role, account_status FROM public.users WHERE id = %s":
            (user_id,) = params
            self._result = self.db.users.get(user_id)
            return

        if s == "SELECT * FROM public.rep_profiles WHERE user_id = %s":
            (user_id,) = params
            self._result = next((r for r in self.db.rep_profiles.values() if r["user_id"] == user_id), None)
            return

        if s.startswith("UPDATE public.rep_profiles SET"):
            middle = s[len("UPDATE public.rep_profiles SET "):s.index(" WHERE id = %s")]
            cols = [pair.split(" = ")[0] for pair in middle.split(", ") if pair.endswith("= %s")]
            profile_id = params[-1]
            row = self.db.rep_profiles[profile_id]
            for col, val in zip(cols, params[:-1]):
                row[col] = val
            self._result = row
            return

        if s == "SELECT values_filters FROM public.parent_records WHERE rep_id = %s":
            (rep_id,) = params
            pr = self.db.parent_records.get(rep_id)
            self._result = {"values_filters": pr["values_filters"]} if pr else None
            return

        if s == "SELECT campaign_approval_required FROM public.parent_records WHERE rep_id = %s":
            (rep_id,) = params
            pr = self.db.parent_records.get(rep_id)
            self._result = {"campaign_approval_required": pr["campaign_approval_required"]} if pr else None
            return

        if "target_categories &&" in s:
            categories, city, rep_id, blocked = params["categories"], params["city"], params["rep_id"], params["blocked"]
            existing_campaign_ids = {cr["campaign_id"] for cr in self.db.campaign_reps.values() if cr["rep_id"] == rep_id}
            out = []
            for c in self.db.campaigns.values():
                if c["status"] != "active":
                    continue
                if not (set(c["target_categories"]) & set(categories)):
                    continue
                if c["target_cities"] and city not in c["target_cities"]:
                    continue
                if set(c["target_categories"]) & set(blocked):
                    continue
                if c["id"] in existing_campaign_ids:
                    continue
                out.append(c)
            self._results = out
            return

        if "JOIN public.campaigns c ON c.id = cr.campaign_id" in s:
            rep_id, statuses = params
            out = []
            for cr in self.db.campaign_reps.values():
                if cr["rep_id"] != rep_id or cr["status"] not in statuses:
                    continue
                c = self.db.campaigns[cr["campaign_id"]]
                out.append({
                    "campaign_reps_id": cr["id"], "status": cr["status"], "payout_cents": cr["payout_cents"],
                    "invite_expires_at": cr["invite_expires_at"],
                    "parent_approval_status": cr.get("parent_approval_status", "not_required"),
                    "campaign_id": c["id"], "title": c["title"],
                    "product_name": c["product_name"], "deliverables_description": c["deliverables_description"],
                    "start_date": c["start_date"], "end_date": c["end_date"],
                })
            self._results = out
            return

        if "GROUP BY payout_status" in s:
            (rep_id,) = params
            totals: dict[str, int] = {}
            for cr in self.db.campaign_reps.values():
                if cr["rep_id"] != rep_id or cr["payout_cents"] is None:
                    continue
                totals[cr["payout_status"]] = totals.get(cr["payout_status"], 0) + cr["payout_cents"]
            self._results = [{"payout_status": k, "total": v} for k, v in totals.items()]
            return

        if s == "SELECT * FROM public.campaigns WHERE id = %s":
            (campaign_id,) = params
            self._result = self.db.campaigns.get(campaign_id)
            return

        if s == "SELECT * FROM public.campaign_reps WHERE campaign_id = %s AND rep_id = %s":
            # dict(...) copy, not the live object -- matches real psycopg
            # dict_row semantics (a fresh dict per fetch), so a snapshot
            # taken before a subsequent UPDATE...RETURNING on the same row
            # doesn't get silently mutated out from under the caller (e.g.
            # withdraw_campaign's pre-update status check).
            campaign_id, rep_id = params
            match = next(
                (r for r in self.db.campaign_reps.values() if r["campaign_id"] == campaign_id and r["rep_id"] == rep_id),
                None,
            )
            self._result = dict(match) if match is not None else None
            return

        if s.startswith("INSERT INTO public.campaign_reps"):
            campaign_id, rep_id, invited_at, expires_at, parent_approval_status, parent_approval_deadline = params
            new_id = str(uuid.uuid4())
            row = {
                "id": new_id, "campaign_id": campaign_id, "rep_id": rep_id, "status": "invited",
                "invited_at": invited_at, "invite_expires_at": expires_at, "accepted_at": None,
                "submitted_at": None, "ftc_disclosure_accepted": False, "ftc_accepted_at": None,
                "submission_text": None, "submission_file_urls": [], "payout_cents": None,
                "payout_status": "pending",
                "parent_approval_status": parent_approval_status,
                "parent_approval_deadline": parent_approval_deadline, "parent_decided_at": None,
            }
            self.db.campaign_reps[new_id] = row
            self._result = row
            return

        if s.startswith("UPDATE public.campaign_reps SET status = 'accepted'"):
            accepted_at, ftc_accepted_at, cr_id = params
            row = self.db.campaign_reps[cr_id]
            row.update(status="accepted", accepted_at=accepted_at, ftc_disclosure_accepted=True, ftc_accepted_at=ftc_accepted_at)
            self._result = row
            return

        if s == "UPDATE public.campaigns SET reps_accepted_count = reps_accepted_count + 1 WHERE id = %s":
            (campaign_id,) = params
            self.db.campaigns[campaign_id]["reps_accepted_count"] += 1
            return

        if s == "UPDATE public.campaigns SET reps_accepted_count = GREATEST(0, reps_accepted_count - 1) WHERE id = %s":
            (campaign_id,) = params
            self.db.campaigns[campaign_id]["reps_accepted_count"] = max(0, self.db.campaigns[campaign_id]["reps_accepted_count"] - 1)
            return

        if s == "UPDATE public.campaign_reps SET status = 'declined', parent_approval_status = 'blocked', parent_decided_at = now() WHERE parent_approval_status = 'pending' AND status = 'invited' AND parent_approval_deadline < now() RETURNING id":
            now = datetime.now(timezone.utc)
            expired = [
                r for r in self.db.campaign_reps.values()
                if r.get("parent_approval_status") == "pending" and r["status"] == "invited"
                and r.get("parent_approval_deadline") and r["parent_approval_deadline"] < now
            ]
            for r in expired:
                r["status"] = "declined"
                r["parent_approval_status"] = "blocked"
            self._results = [{"id": r["id"]} for r in expired]
            return

        if s == "UPDATE public.campaign_reps SET status = 'declined' WHERE status = 'invited' AND invite_expires_at < now() RETURNING id":
            now = datetime.now(timezone.utc)
            expired = [r for r in self.db.campaign_reps.values() if r["status"] == "invited" and r["invite_expires_at"] and r["invite_expires_at"] < now]
            for r in expired:
                r["status"] = "declined"
            self._results = [{"id": r["id"]} for r in expired]
            return

        if s == "UPDATE public.campaign_reps SET status = 'declined' WHERE id = %s RETURNING *":
            (cr_id,) = params
            row = self.db.campaign_reps[cr_id]
            row["status"] = "declined"
            self._result = row
            return

        if s.startswith("UPDATE public.campaign_reps SET status = 'submitted'"):
            submission_text, submission_file_urls, cr_id = params
            row = self.db.campaign_reps[cr_id]
            row.update(status="submitted", submission_text=submission_text, submission_file_urls=submission_file_urls)
            self._result = row
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


REP_USER_ID = "00000000-0000-0000-0000-000000000001"
REP_PROFILE_ID = "10000000-0000-0000-0000-000000000001"
OTHER_REP_USER_ID = "00000000-0000-0000-0000-000000000099"
OTHER_REP_PROFILE_ID = "10000000-0000-0000-0000-000000000099"


@pytest.fixture
def fake_db() -> FakeDB:
    db = FakeDB()
    db.users[REP_USER_ID] = {"id": REP_USER_ID, "email": "rep@example.com", "role": "rep", "account_status": "active"}
    db.users[OTHER_REP_USER_ID] = {"id": OTHER_REP_USER_ID, "email": "other@example.com", "role": "rep", "account_status": "active"}
    db.rep_profiles[REP_PROFILE_ID] = {
        "id": REP_PROFILE_ID, "user_id": REP_USER_ID, "display_name": "Rep One",
        "school_name": "Lincoln High", "school_type": None, "city": "Hartford", "state": "CT",
        "graduation_year": 2027, "bio": None, "categories": ["gaming"], "instagram_handle": None,
        "tiktok_handle": None, "recruiter_visible": False, "total_campaigns_completed": 0,
        "total_earnings_cents": 0, "average_rating": None, "profile_completeness_score": 0,
    }
    db.rep_profiles[OTHER_REP_PROFILE_ID] = {
        **db.rep_profiles[REP_PROFILE_ID], "id": OTHER_REP_PROFILE_ID, "user_id": OTHER_REP_USER_ID,
    }
    return db


@pytest.fixture
def rep_client(settings: Settings, fake_db: FakeDB, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    from app.core import db as db_module
    from app.routers import campaigns as campaigns_router
    from app.routers import reps as reps_router

    @contextmanager
    def fake_get_connection(_settings: Settings):
        yield FakeConn(fake_db)

    monkeypatch.setattr(db_module, "get_connection", fake_get_connection)
    monkeypatch.setattr(reps_router, "get_connection", fake_get_connection)
    monkeypatch.setattr(campaigns_router, "get_connection", fake_get_connection)

    return TestClient(create_app(settings=settings))


def _rep_headers(user_id: str = REP_USER_ID, email: str = "rep@example.com") -> dict:
    token = jwt.encode({"sub": user_id, "email": email, "aud": "authenticated"}, TEST_JWT_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def _make_campaign(fake_db: FakeDB, *, target_categories, target_cities=(), status="active") -> str:
    campaign_id = str(uuid.uuid4())
    fake_db.campaigns[campaign_id] = {
        "id": campaign_id, "title": "Test Campaign", "status": status, "product_name": "Widget",
        "campaign_goal": "Sell widgets", "key_messaging": "Widgets are great", "prohibited_content": None,
        "deliverables_description": "1 post", "target_categories": list(target_categories),
        "target_cities": list(target_cities), "max_reps": 5, "reps_accepted_count": 0,
        "budget_cents": 100000, "platform_fee_cents": 35000, "rep_pool_cents": 65000,
        "payout_per_rep_cents": 13000, "start_date": date(2026, 1, 1), "end_date": date(2026, 2, 1),
    }
    return campaign_id


def test_update_profile_rejects_computed_fields(rep_client: TestClient) -> None:
    resp = rep_client.put("/reps/me", json={"total_earnings_cents": 999999}, headers=_rep_headers())
    assert resp.status_code == 422


def test_update_profile_rejects_invalid_category(rep_client: TestClient) -> None:
    resp = rep_client.put("/reps/me", json={"categories": ["crypto"]}, headers=_rep_headers())
    assert resp.status_code == 422


def test_update_profile_rejects_bad_graduation_year(rep_client: TestClient) -> None:
    resp = rep_client.put("/reps/me", json={"graduation_year": 1999}, headers=_rep_headers())
    assert resp.status_code == 422


def test_update_profile_recomputes_completeness(rep_client: TestClient, fake_db: FakeDB) -> None:
    resp = rep_client.put("/reps/me", json={"bio": "I make gaming content"}, headers=_rep_headers())
    assert resp.status_code == 200
    assert resp.json()["profile_completeness_score"] > 0


def test_available_excludes_non_matching_category(rep_client: TestClient, fake_db: FakeDB) -> None:
    _make_campaign(fake_db, target_categories=["fashion"], target_cities=[])
    resp = rep_client.get("/reps/campaigns/available", headers=_rep_headers())
    assert resp.status_code == 200
    assert resp.json() == []


def test_available_includes_matching_category(rep_client: TestClient, fake_db: FakeDB) -> None:
    _make_campaign(fake_db, target_categories=["gaming"], target_cities=[])
    resp = rep_client.get("/reps/campaigns/available", headers=_rep_headers())
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_apply_rejected_for_non_matching_category(rep_client: TestClient, fake_db: FakeDB) -> None:
    campaign_id = _make_campaign(fake_db, target_categories=["fashion"], target_cities=[])
    resp = rep_client.post(f"/campaigns/{campaign_id}/apply", headers=_rep_headers())
    assert resp.status_code == 400


def test_apply_accept_submit_happy_path(rep_client: TestClient, fake_db: FakeDB) -> None:
    campaign_id = _make_campaign(fake_db, target_categories=["gaming"], target_cities=[])

    apply_resp = rep_client.post(f"/campaigns/{campaign_id}/apply", headers=_rep_headers())
    assert apply_resp.status_code == 201
    assert apply_resp.json()["status"] == "invited"

    accept_resp = rep_client.post(
        f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": True}, headers=_rep_headers()
    )
    assert accept_resp.status_code == 200
    assert accept_resp.json()["status"] == "accepted"
    assert fake_db.campaigns[campaign_id]["reps_accepted_count"] == 1

    submit_resp = rep_client.post(
        f"/campaigns/{campaign_id}/submit",
        json={"submission_text": "Done!", "submission_file_urls": ["https://example.com/a.png"]},
        headers=_rep_headers(),
    )
    assert submit_resp.status_code == 200
    assert submit_resp.json()["status"] == "submitted"


def test_accept_without_ftc_disclosure_rejected(rep_client: TestClient, fake_db: FakeDB) -> None:
    campaign_id = _make_campaign(fake_db, target_categories=["gaming"], target_cities=[])
    rep_client.post(f"/campaigns/{campaign_id}/apply", headers=_rep_headers())

    resp = rep_client.post(f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": False}, headers=_rep_headers())
    assert resp.status_code == 400


def test_submit_without_ftc_disclosure_rejected(rep_client: TestClient, fake_db: FakeDB) -> None:
    campaign_id = _make_campaign(fake_db, target_categories=["gaming"], target_cities=[])
    cr_id = str(uuid.uuid4())
    fake_db.campaign_reps[cr_id] = {
        "id": cr_id, "campaign_id": campaign_id, "rep_id": REP_PROFILE_ID, "status": "accepted",
        "invited_at": datetime.now(timezone.utc), "invite_expires_at": None, "accepted_at": datetime.now(timezone.utc),
        "submitted_at": None, "ftc_disclosure_accepted": False, "ftc_accepted_at": None,
        "submission_text": None, "submission_file_urls": [], "payout_cents": None, "payout_status": "pending",
    }
    resp = rep_client.post(
        f"/campaigns/{campaign_id}/submit", json={"submission_text": "x", "submission_file_urls": []}, headers=_rep_headers()
    )
    assert resp.status_code == 400


def test_double_accept_returns_409(rep_client: TestClient, fake_db: FakeDB) -> None:
    campaign_id = _make_campaign(fake_db, target_categories=["gaming"], target_cities=[])
    rep_client.post(f"/campaigns/{campaign_id}/apply", headers=_rep_headers())
    rep_client.post(f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": True}, headers=_rep_headers())

    resp = rep_client.post(f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": True}, headers=_rep_headers())
    assert resp.status_code == 409


def test_decline_already_declined_returns_409(rep_client: TestClient, fake_db: FakeDB) -> None:
    campaign_id = _make_campaign(fake_db, target_categories=["gaming"], target_cities=[])
    rep_client.post(f"/campaigns/{campaign_id}/apply", headers=_rep_headers())
    rep_client.post(f"/campaigns/{campaign_id}/decline", headers=_rep_headers())

    resp = rep_client.post(f"/campaigns/{campaign_id}/decline", headers=_rep_headers())
    assert resp.status_code == 409


def test_accept_expired_invite_returns_409(rep_client: TestClient, fake_db: FakeDB) -> None:
    campaign_id = _make_campaign(fake_db, target_categories=["gaming"], target_cities=[])
    apply_resp = rep_client.post(f"/campaigns/{campaign_id}/apply", headers=_rep_headers())
    cr_id = apply_resp.json()["campaign_reps_id"]
    fake_db.campaign_reps[cr_id]["invite_expires_at"] = datetime.now(timezone.utc) - timedelta(hours=1)

    resp = rep_client.post(f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": True}, headers=_rep_headers())
    assert resp.status_code == 409


def test_rep_cannot_access_another_reps_invite(rep_client: TestClient, fake_db: FakeDB) -> None:
    campaign_id = _make_campaign(fake_db, target_categories=["gaming"], target_cities=[])
    rep_client.post(f"/campaigns/{campaign_id}/apply", headers=_rep_headers())

    resp = rep_client.post(
        f"/campaigns/{campaign_id}/accept",
        json={"ftc_disclosure_accepted": True},
        headers=_rep_headers(OTHER_REP_USER_ID, "other@example.com"),
    )
    assert resp.status_code == 404


def test_expire_stale_invites_job_frees_slot(fake_db: FakeDB) -> None:
    from app.services import rep_service

    campaign_id = _make_campaign(fake_db, target_categories=["gaming"], target_cities=[])
    cr_id = str(uuid.uuid4())
    fake_db.campaign_reps[cr_id] = {
        "id": cr_id, "campaign_id": campaign_id, "rep_id": REP_PROFILE_ID, "status": "invited",
        "invited_at": datetime.now(timezone.utc) - timedelta(hours=50),
        "invite_expires_at": datetime.now(timezone.utc) - timedelta(hours=2),
        "accepted_at": None, "submitted_at": None, "ftc_disclosure_accepted": False, "ftc_accepted_at": None,
        "submission_text": None, "submission_file_urls": [], "payout_cents": None, "payout_status": "pending",
    }

    expired_count = rep_service.expire_stale_invites(FakeConn(fake_db))
    assert expired_count == 1
    assert fake_db.campaign_reps[cr_id]["status"] == "declined"

    available = rep_service.campaigns_available(FakeConn(fake_db), fake_db.rep_profiles[OTHER_REP_PROFILE_ID])
    assert any(c["id"] == campaign_id for c in available)


def test_accept_blocked_while_pending_parent_approval(rep_client: TestClient, fake_db: FakeDB) -> None:
    """Prompt 4A retrofit deliverable 9: accept must return a distinct
    'awaiting parent approval' 403, not a generic 409/403.
    """
    fake_db.parent_records[REP_PROFILE_ID] = {
        "rep_id": REP_PROFILE_ID, "values_filters": [], "campaign_approval_required": True,
    }
    campaign_id = _make_campaign(fake_db, target_categories=["gaming"], target_cities=[])
    apply_resp = rep_client.post(f"/campaigns/{campaign_id}/apply", headers=_rep_headers())
    assert apply_resp.status_code == 201
    cr_id = apply_resp.json()["campaign_reps_id"]
    assert fake_db.campaign_reps[cr_id]["parent_approval_status"] == "pending"

    resp = rep_client.post(f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": True}, headers=_rep_headers())
    assert resp.status_code == 403
    assert "awaiting parent approval" in resp.json()["error"]["message"].lower()


def test_accept_succeeds_once_parent_approved(rep_client: TestClient, fake_db: FakeDB) -> None:
    fake_db.parent_records[REP_PROFILE_ID] = {
        "rep_id": REP_PROFILE_ID, "values_filters": [], "campaign_approval_required": True,
    }
    campaign_id = _make_campaign(fake_db, target_categories=["gaming"], target_cities=[])
    apply_resp = rep_client.post(f"/campaigns/{campaign_id}/apply", headers=_rep_headers())
    cr_id = apply_resp.json()["campaign_reps_id"]
    fake_db.campaign_reps[cr_id]["parent_approval_status"] = "approved"

    resp = rep_client.post(f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": True}, headers=_rep_headers())
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"


def test_available_excludes_parent_blocked_category(rep_client: TestClient, fake_db: FakeDB) -> None:
    """Prompt 4A retrofit deliverable 9: values-filter exclusion on
    GET /reps/campaigns/available -- a blocked-category campaign is
    absent entirely, not just un-acceptable.
    """
    fake_db.parent_records[REP_PROFILE_ID] = {
        "rep_id": REP_PROFILE_ID, "values_filters": ["gaming"], "campaign_approval_required": False,
    }
    _make_campaign(fake_db, target_categories=["gaming"], target_cities=[])
    resp = rep_client.get("/reps/campaigns/available", headers=_rep_headers())
    assert resp.status_code == 200
    assert resp.json() == []


def test_available_unaffected_when_no_parent_record(rep_client: TestClient, fake_db: FakeDB) -> None:
    _make_campaign(fake_db, target_categories=["gaming"], target_cities=[])
    resp = rep_client.get("/reps/campaigns/available", headers=_rep_headers())
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_withdraw_from_accepted_frees_slot(rep_client: TestClient, fake_db: FakeDB) -> None:
    campaign_id = _make_campaign(fake_db, target_categories=["gaming"], target_cities=[])
    rep_client.post(f"/campaigns/{campaign_id}/apply", headers=_rep_headers())
    rep_client.post(f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": True}, headers=_rep_headers())
    assert fake_db.campaigns[campaign_id]["reps_accepted_count"] == 1

    resp = rep_client.post(f"/campaigns/{campaign_id}/withdraw", headers=_rep_headers())
    assert resp.status_code == 200
    assert resp.json()["status"] == "declined"
    assert fake_db.campaigns[campaign_id]["reps_accepted_count"] == 0


def test_withdraw_from_invited_status(rep_client: TestClient, fake_db: FakeDB) -> None:
    campaign_id = _make_campaign(fake_db, target_categories=["gaming"], target_cities=[])
    rep_client.post(f"/campaigns/{campaign_id}/apply", headers=_rep_headers())

    resp = rep_client.post(f"/campaigns/{campaign_id}/withdraw", headers=_rep_headers())
    assert resp.status_code == 200
    assert resp.json()["status"] == "declined"


def test_withdraw_after_confirmed_rejected(rep_client: TestClient, fake_db: FakeDB) -> None:
    campaign_id = _make_campaign(fake_db, target_categories=["gaming"], target_cities=[])
    cr_id = str(uuid.uuid4())
    fake_db.campaign_reps[cr_id] = {
        "id": cr_id, "campaign_id": campaign_id, "rep_id": REP_PROFILE_ID, "status": "confirmed",
        "invited_at": datetime.now(timezone.utc), "invite_expires_at": None, "accepted_at": None,
        "submitted_at": None, "ftc_disclosure_accepted": True, "ftc_accepted_at": None,
        "submission_text": None, "submission_file_urls": [], "payout_cents": None, "payout_status": "pending",
        "parent_approval_status": "not_required",
    }
    resp = rep_client.post(f"/campaigns/{campaign_id}/withdraw", headers=_rep_headers())
    assert resp.status_code == 409


def test_expire_lapsed_parent_approvals_job(fake_db: FakeDB) -> None:
    from app.services import rep_service

    campaign_id = _make_campaign(fake_db, target_categories=["gaming"], target_cities=[])
    cr_id = str(uuid.uuid4())
    fake_db.campaign_reps[cr_id] = {
        "id": cr_id, "campaign_id": campaign_id, "rep_id": REP_PROFILE_ID, "status": "invited",
        "invited_at": datetime.now(timezone.utc) - timedelta(hours=50), "invite_expires_at": None,
        "accepted_at": None, "submitted_at": None, "ftc_disclosure_accepted": False, "ftc_accepted_at": None,
        "submission_text": None, "submission_file_urls": [], "payout_cents": None, "payout_status": "pending",
        "parent_approval_status": "pending",
        "parent_approval_deadline": datetime.now(timezone.utc) - timedelta(hours=2),
    }

    expired_count = rep_service.expire_lapsed_parent_approvals(FakeConn(fake_db))
    assert expired_count == 1
    assert fake_db.campaign_reps[cr_id]["status"] == "declined"
    assert fake_db.campaign_reps[cr_id]["parent_approval_status"] == "blocked"


def test_earnings_breakdown_buckets_by_payout_status(rep_client: TestClient, fake_db: FakeDB) -> None:
    campaign_id = _make_campaign(fake_db, target_categories=["gaming"], target_cities=[])
    for i, payout_status in enumerate(["pending", "processing", "paid"]):
        cr_id = str(uuid.uuid4())
        fake_db.campaign_reps[cr_id] = {
            "id": cr_id, "campaign_id": campaign_id, "rep_id": REP_PROFILE_ID, "status": "confirmed",
            "invited_at": datetime.now(timezone.utc), "invite_expires_at": None, "accepted_at": None,
            "submitted_at": None, "ftc_disclosure_accepted": True, "ftc_accepted_at": None,
            "submission_text": None, "submission_file_urls": [], "payout_cents": (i + 1) * 1000,
            "payout_status": payout_status,
        }

    resp = rep_client.get("/reps/earnings", headers=_rep_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"pending_cents": 1000, "confirmed_cents": 2000, "paid_cents": 3000, "lifetime_total_cents": 6000}


# ── Prompt 4A retrofit (deliverable 9): parent approval gate, values-filter
# exclusion, and withdraw ───────────────────────────────────────────────


def test_apply_sets_pending_parent_approval_when_required(rep_client: TestClient, fake_db: FakeDB) -> None:
    fake_db.parent_records[REP_PROFILE_ID] = {"campaign_approval_required": True, "values_filters": []}
    campaign_id = _make_campaign(fake_db, target_categories=["gaming"], target_cities=[])

    resp = rep_client.post(f"/campaigns/{campaign_id}/apply", headers=_rep_headers())
    assert resp.status_code == 201
    cr_id = resp.json()["campaign_reps_id"]
    assert fake_db.campaign_reps[cr_id]["parent_approval_status"] == "pending"


def test_accept_blocked_pending_parent_approval_returns_403(rep_client: TestClient, fake_db: FakeDB) -> None:
    fake_db.parent_records[REP_PROFILE_ID] = {"campaign_approval_required": True, "values_filters": []}
    campaign_id = _make_campaign(fake_db, target_categories=["gaming"], target_cities=[])
    rep_client.post(f"/campaigns/{campaign_id}/apply", headers=_rep_headers())

    resp = rep_client.post(
        f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": True}, headers=_rep_headers()
    )
    assert resp.status_code == 403
    assert "awaiting parent approval" in resp.json()["error"]["message"].lower()


def test_accept_succeeds_once_parent_approves(rep_client: TestClient, fake_db: FakeDB) -> None:
    fake_db.parent_records[REP_PROFILE_ID] = {"campaign_approval_required": True, "values_filters": []}
    campaign_id = _make_campaign(fake_db, target_categories=["gaming"], target_cities=[])
    apply_resp = rep_client.post(f"/campaigns/{campaign_id}/apply", headers=_rep_headers())
    cr_id = apply_resp.json()["campaign_reps_id"]
    fake_db.campaign_reps[cr_id]["parent_approval_status"] = "approved"

    resp = rep_client.post(
        f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": True}, headers=_rep_headers()
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"


def test_available_excludes_parent_blocked_category(rep_client: TestClient, fake_db: FakeDB) -> None:
    fake_db.parent_records[REP_PROFILE_ID] = {"campaign_approval_required": False, "values_filters": ["gaming"]}
    _make_campaign(fake_db, target_categories=["gaming"], target_cities=[])

    resp = rep_client.get("/reps/campaigns/available", headers=_rep_headers())
    assert resp.status_code == 200
    assert resp.json() == []


def test_available_includes_non_blocked_category_with_parent_record(rep_client: TestClient, fake_db: FakeDB) -> None:
    fake_db.parent_records[REP_PROFILE_ID] = {"campaign_approval_required": False, "values_filters": ["fashion"]}
    _make_campaign(fake_db, target_categories=["gaming"], target_cities=[])

    resp = rep_client.get("/reps/campaigns/available", headers=_rep_headers())
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_withdraw_from_accepted_campaign(rep_client: TestClient, fake_db: FakeDB) -> None:
    campaign_id = _make_campaign(fake_db, target_categories=["gaming"], target_cities=[])
    rep_client.post(f"/campaigns/{campaign_id}/apply", headers=_rep_headers())
    rep_client.post(f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": True}, headers=_rep_headers())
    assert fake_db.campaigns[campaign_id]["reps_accepted_count"] == 1

    resp = rep_client.post(f"/campaigns/{campaign_id}/withdraw", headers=_rep_headers())
    assert resp.status_code == 200
    assert resp.json()["status"] == "declined"
    assert fake_db.campaigns[campaign_id]["reps_accepted_count"] == 0


def test_withdraw_from_invited_campaign(rep_client: TestClient, fake_db: FakeDB) -> None:
    campaign_id = _make_campaign(fake_db, target_categories=["gaming"], target_cities=[])
    rep_client.post(f"/campaigns/{campaign_id}/apply", headers=_rep_headers())

    resp = rep_client.post(f"/campaigns/{campaign_id}/withdraw", headers=_rep_headers())
    assert resp.status_code == 200
    assert resp.json()["status"] == "declined"


def test_withdraw_no_penalty_no_explanation_required(rep_client: TestClient, fake_db: FakeDB) -> None:
    """Deliverable 9 (Prompt 5): withdraw takes no body/reason at all."""
    campaign_id = _make_campaign(fake_db, target_categories=["gaming"], target_cities=[])
    rep_client.post(f"/campaigns/{campaign_id}/apply", headers=_rep_headers())

    resp = rep_client.post(f"/campaigns/{campaign_id}/withdraw", headers=_rep_headers())
    assert resp.status_code == 200


def test_withdraw_on_nonexistent_invite_returns_404(rep_client: TestClient, fake_db: FakeDB) -> None:
    campaign_id = _make_campaign(fake_db, target_categories=["gaming"], target_cities=[])
    resp = rep_client.post(f"/campaigns/{campaign_id}/withdraw", headers=_rep_headers())
    assert resp.status_code == 404


def test_withdraw_after_already_declined_returns_409(rep_client: TestClient, fake_db: FakeDB) -> None:
    campaign_id = _make_campaign(fake_db, target_categories=["gaming"], target_cities=[])
    rep_client.post(f"/campaigns/{campaign_id}/apply", headers=_rep_headers())
    rep_client.post(f"/campaigns/{campaign_id}/decline", headers=_rep_headers())

    resp = rep_client.post(f"/campaigns/{campaign_id}/withdraw", headers=_rep_headers())
    assert resp.status_code == 409


def test_expire_lapsed_parent_approvals_job(fake_db: FakeDB) -> None:
    from app.services import rep_service

    campaign_id = _make_campaign(fake_db, target_categories=["gaming"], target_cities=[])
    cr_id = str(uuid.uuid4())
    fake_db.campaign_reps[cr_id] = {
        "id": cr_id, "campaign_id": campaign_id, "rep_id": REP_PROFILE_ID, "status": "invited",
        "invited_at": datetime.now(timezone.utc) - timedelta(hours=50),
        "invite_expires_at": datetime.now(timezone.utc) + timedelta(hours=10),  # rep's own window still open
        "parent_approval_status": "pending",
        "parent_approval_deadline": datetime.now(timezone.utc) - timedelta(hours=2),  # but parent's window lapsed
        "accepted_at": None, "submitted_at": None, "ftc_disclosure_accepted": False, "ftc_accepted_at": None,
        "submission_text": None, "submission_file_urls": [], "payout_cents": None, "payout_status": "pending",
    }

    expired_count = rep_service.expire_lapsed_parent_approvals(FakeConn(fake_db))
    assert expired_count == 1
    assert fake_db.campaign_reps[cr_id]["status"] == "declined"
    assert fake_db.campaign_reps[cr_id]["parent_approval_status"] == "blocked"
