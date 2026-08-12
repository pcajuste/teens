"""Acceptance criteria for Prompt 4A (Parent Portal).

Exercises app.services.parent_service directly against a lightweight
in-memory fake connection -- same approach as test_reps.py's FakeDB,
scoped to the tables/queries parent_service.py actually touches.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from app.core.config import Settings
from app.core.parent_security import PortalClosedError as SessionPortalClosedError
from app.core.parent_security import decode_parent_session_token, issue_parent_session_token
from app.services import parent_service


class FakeDB:
    def __init__(self) -> None:
        self.users: dict[str, dict] = {}
        self.rep_profiles: dict[str, dict] = {}
        self.campaigns: dict[str, dict] = {}
        self.brand_profiles: dict[str, dict] = {}
        self.campaign_reps: dict[str, dict] = {}
        self.parent_records: dict[str, dict] = {}
        self.parent_auth_tokens: dict[str, dict] = {}


class FakeCursor:
    def __init__(self, db: FakeDB) -> None:
        self.db = db
        self._result = None
        self._results: list = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None

    def execute(self, sql: str, params=()) -> None:
        s = " ".join(sql.split())

        if "JOIN public.rep_profiles rp ON rp.id = pr.rep_id" in s and "WHERE pr.parent_email" in s:
            (email,) = params
            for pr in self.db.parent_records.values():
                if pr["parent_email"] == email:
                    rep = self.db.rep_profiles[pr["rep_id"]]
                    self._result = {"id": pr["id"], "rep_id": pr["rep_id"], "display_name": rep["display_name"]}
                    return
            self._result = None
            return

        if s.startswith("INSERT INTO public.parent_auth_tokens"):
            parent_record_id, token_hash, expires_at = params
            token_id = str(uuid.uuid4())
            self.db.parent_auth_tokens[token_id] = {
                "id": token_id, "parent_record_id": parent_record_id, "token_hash": token_hash,
                "expires_at": expires_at, "used_at": None,
            }
            return

        if "FROM public.parent_auth_tokens t" in s and "JOIN public.parent_records pr" in s and "JOIN public.rep_profiles rp" in s:
            (token_hash,) = params
            for t in self.db.parent_auth_tokens.values():
                if t["token_hash"] == token_hash:
                    pr = self.db.parent_records[t["parent_record_id"]]
                    rep = self.db.rep_profiles[pr["rep_id"]]
                    self._result = {
                        "token_id": t["id"], "expires_at": t["expires_at"], "used_at": t["used_at"],
                        "parent_record_id": pr["id"], "rep_id": pr["rep_id"],
                        "portal_expires_at": pr["portal_expires_at"], "parent_email": pr["parent_email"],
                        "display_name": rep["display_name"],
                    }
                    return
            self._result = None
            return

        if s == "UPDATE public.parent_auth_tokens SET used_at = now() WHERE id = %s":
            (token_id,) = params
            self.db.parent_auth_tokens[token_id]["used_at"] = datetime.now(timezone.utc)
            return

        if s == "SELECT * FROM public.parent_records WHERE id = %s":
            (parent_record_id,) = params
            self._result = self.db.parent_records.get(parent_record_id)
            return

        if s.startswith("SELECT display_name, school_name, graduation_year"):
            (rep_id,) = params
            rep = self.db.rep_profiles.get(rep_id)
            self._result = rep
            return

        if "FROM public.campaign_reps cr" in s and "JOIN public.brand_profiles b" in s:
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
            self._result = next(
                (r for r in self.db.campaign_reps.values() if r["rep_id"] == rep_id and r["campaign_id"] == campaign_id),
                None,
            )
            return

        if s.startswith("SELECT * FROM public.campaign_reps WHERE rep_id = %s AND campaign_id = %s AND parent_approval_status = 'pending'"):
            rep_id, campaign_id = params
            self._result = next(
                (r for r in self.db.campaign_reps.values()
                 if r["rep_id"] == rep_id and r["campaign_id"] == campaign_id and r["parent_approval_status"] == "pending"),
                None,
            )
            return

        if s.startswith("UPDATE public.campaign_reps") and "parent_approval_status = 'approved'" in s:
            (cr_id,) = params
            row = self.db.campaign_reps[cr_id]
            row.update(parent_approval_status="approved", parent_decided_at=datetime.now(timezone.utc))
            self._result = row
            return

        if s.startswith("UPDATE public.campaign_reps") and "parent_approval_status = 'blocked'" in s:
            (cr_id,) = params
            row = self.db.campaign_reps[cr_id]
            row.update(parent_approval_status="blocked", parent_decided_at=datetime.now(timezone.utc), status="declined")
            self._result = row
            return

        if s == "SELECT values_filters, campaign_approval_required, digest_enabled FROM public.parent_records WHERE id = %s":
            (parent_record_id,) = params
            pr = self.db.parent_records.get(parent_record_id)
            self._result = {k: pr[k] for k in ("values_filters", "campaign_approval_required", "digest_enabled")} if pr else None
            return

        if s.startswith("UPDATE public.parent_records SET values_filters"):
            values_filters, parent_record_id = params
            self.db.parent_records[parent_record_id]["values_filters"] = values_filters
            pr = self.db.parent_records[parent_record_id]
            self._result = {k: pr[k] for k in ("values_filters", "campaign_approval_required", "digest_enabled")}
            return

        if s.startswith("SELECT u.date_of_birth"):
            (rep_id,) = params
            rep = self.db.rep_profiles[rep_id]
            user = self.db.users[rep["user_id"]]
            self._result = {"date_of_birth": user["date_of_birth"]}
            return

        if s.startswith("UPDATE public.parent_records SET campaign_approval_required"):
            campaign_approval_required, parent_record_id = params
            self.db.parent_records[parent_record_id]["campaign_approval_required"] = campaign_approval_required
            pr = self.db.parent_records[parent_record_id]
            self._result = {k: pr[k] for k in ("values_filters", "campaign_approval_required", "digest_enabled")}
            return

        if s.startswith("UPDATE public.parent_records SET digest_enabled"):
            digest_enabled, parent_record_id = params
            self.db.parent_records[parent_record_id]["digest_enabled"] = digest_enabled
            pr = self.db.parent_records[parent_record_id]
            self._result = {k: pr[k] for k in ("values_filters", "campaign_approval_required", "digest_enabled")}
            return

        if s.startswith("SELECT categories, profile_completeness_score, total_earnings_cents"):
            (rep_id,) = params
            rep = self.db.rep_profiles[rep_id]
            self._result = {k: rep[k] for k in ("categories", "profile_completeness_score", "total_earnings_cents")}
            return

        if "COUNT(*) AS n" in s:
            rep_id, month_start = params
            n = sum(
                1 for cr in self.db.campaign_reps.values()
                if cr["rep_id"] == rep_id and cr["status"] in ("confirmed", "paid")
                and cr.get("confirmed_at") and cr["confirmed_at"] >= month_start
            )
            earned = sum(
                cr["payout_cents"] or 0 for cr in self.db.campaign_reps.values()
                if cr["rep_id"] == rep_id and cr["status"] in ("confirmed", "paid")
                and cr.get("confirmed_at") and cr["confirmed_at"] >= month_start
            )
            self._result = {"n": n, "earned": earned}
            return

        if s.startswith("UPDATE public.parent_records SET suspended_by_parent_at = %s"):
            suspended_at, parent_record_id = params
            self.db.parent_records[parent_record_id]["suspended_by_parent_at"] = suspended_at
            return

        if s.startswith("UPDATE public.users SET account_status = 'suspended'"):
            (rep_id,) = params
            rep = self.db.rep_profiles[rep_id]
            self.db.users[rep["user_id"]]["account_status"] = "suspended"
            self._result = {"email": self.db.users[rep["user_id"]]["email"]}
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
            rep = self.db.rep_profiles[rep_id]
            self.db.users[rep["user_id"]]["account_status"] = "active"
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


REP_ID = "10000000-0000-0000-0000-000000000001"
USER_ID = "00000000-0000-0000-0000-000000000001"
PARENT_RECORD_ID = "20000000-0000-0000-0000-000000000001"


def _settings() -> Settings:
    return Settings(
        next_public_supabase_url="http://localhost:54321", next_public_supabase_anon_key="x",
        supabase_service_role_key="x", supabase_jwt_secret="x", database_url="postgresql://x",
        stripe_secret_key="sk_test_x", stripe_publishable_key="pk_test_x", stripe_webhook_secret="whsec_x",
        stripe_platform_fee_percent=35, resend_api_key="x", resend_from_email="noreply@teenure.com",
        resend_parent_consent_template_id="t", next_public_app_url="http://localhost:3100",
        api_url="http://localhost:8001", admin_secret_key="x", allowed_origins="http://localhost:3100",
        jobs_runner_secret="x", min_rep_age=14, parental_consent_required_under=16,
        parent_session_secret="test-parent-secret",
    )


@pytest.fixture
def fake_db() -> FakeDB:
    db = FakeDB()
    db.users[USER_ID] = {
        "id": USER_ID, "email": "rep@example.com", "account_status": "active",
        "date_of_birth": date.today().replace(year=date.today().year - 16),
    }
    db.rep_profiles[REP_ID] = {
        "id": REP_ID, "user_id": USER_ID, "display_name": "Rep One", "school_name": "Lincoln High",
        "graduation_year": 2027, "categories": ["gaming"], "profile_completeness_score": 50,
        "total_earnings_cents": 5000, "total_campaigns_completed": 1,
    }
    db.parent_records[PARENT_RECORD_ID] = {
        "id": PARENT_RECORD_ID, "rep_id": REP_ID, "parent_email": "parent@example.com",
        "campaign_approval_required": True, "values_filters": [], "digest_enabled": True,
        "portal_expires_at": datetime.now(timezone.utc) + timedelta(days=365),
        "suspended_by_parent_at": None,
    }
    return db


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    parent_service._last_request_at.clear()
    yield


def test_request_link_non_enumerating_for_unknown_email(fake_db: FakeDB) -> None:
    settings = _settings()
    calls = []

    def fake_send(**kwargs):
        calls.append(kwargs)

    import app.services.email_service as es

    orig = es.send_parent_magic_link_email
    es.send_parent_magic_link_email = fake_send
    try:
        parent_service.request_link(FakeConn(fake_db), settings, parent_email="nobody@example.com")
    finally:
        es.send_parent_magic_link_email = orig
    assert calls == []  # no email sent, but also no exception/signal that it doesn't exist


def test_request_link_sends_email_for_known_parent(fake_db: FakeDB) -> None:
    settings = _settings()
    calls = []
    import app.services.email_service as es

    orig = es.send_parent_magic_link_email
    es.send_parent_magic_link_email = lambda **kw: calls.append(kw)
    try:
        parent_service.request_link(FakeConn(fake_db), settings, parent_email="parent@example.com")
    finally:
        es.send_parent_magic_link_email = orig
    assert len(calls) == 1
    assert len(fake_db.parent_auth_tokens) == 1


def test_request_link_rate_limited_on_second_call(fake_db: FakeDB) -> None:
    settings = _settings()
    import app.services.email_service as es

    orig = es.send_parent_magic_link_email
    es.send_parent_magic_link_email = lambda **kw: None
    try:
        parent_service.request_link(FakeConn(fake_db), settings, parent_email="parent@example.com")
        with pytest.raises(parent_service.RateLimitedError):
            parent_service.request_link(FakeConn(fake_db), settings, parent_email="parent@example.com")
    finally:
        es.send_parent_magic_link_email = orig


def _issue_and_verify(fake_db: FakeDB, settings: Settings) -> tuple[str, str]:
    import app.services.email_service as es

    orig = es.send_parent_magic_link_email
    captured = {}
    es.send_parent_magic_link_email = lambda **kw: captured.update(kw)
    try:
        parent_service.request_link(FakeConn(fake_db), settings, parent_email="parent@example.com")
    finally:
        es.send_parent_magic_link_email = orig
    token = captured["token"]
    return parent_service.verify_token(FakeConn(fake_db), settings, token=token)


def test_verify_token_issues_working_session(fake_db: FakeDB) -> None:
    settings = _settings()
    session_token, rep_id = _issue_and_verify(fake_db, settings)
    assert rep_id == REP_ID
    payload = decode_parent_session_token(session_token, settings)
    assert payload["rep_id"] == REP_ID
    assert payload["parent_record_id"] == PARENT_RECORD_ID


def test_verify_token_rejects_reuse(fake_db: FakeDB) -> None:
    settings = _settings()
    import app.services.email_service as es

    orig = es.send_parent_magic_link_email
    captured = {}
    es.send_parent_magic_link_email = lambda **kw: captured.update(kw)
    try:
        parent_service.request_link(FakeConn(fake_db), settings, parent_email="parent@example.com")
    finally:
        es.send_parent_magic_link_email = orig
    token = captured["token"]
    parent_service.verify_token(FakeConn(fake_db), settings, token=token)
    with pytest.raises(parent_service.TokenAlreadyUsedError):
        parent_service.verify_token(FakeConn(fake_db), settings, token=token)


def test_verify_token_invalid_for_unknown_token(fake_db: FakeDB) -> None:
    with pytest.raises(parent_service.TokenInvalidError):
        parent_service.verify_token(FakeConn(fake_db), _settings(), token="garbage")


def test_verify_token_portal_closed_when_rep_18(fake_db: FakeDB) -> None:
    fake_db.parent_records[PARENT_RECORD_ID]["portal_expires_at"] = datetime.now(timezone.utc) - timedelta(days=1)
    settings = _settings()
    import app.services.email_service as es

    orig_link, orig_closed = es.send_parent_magic_link_email, es.send_portal_closed_email
    es.send_parent_magic_link_email = lambda **kw: None
    es.send_portal_closed_email = lambda **kw: None
    try:
        parent_service.request_link(FakeConn(fake_db), settings, parent_email="parent@example.com")
        token_id = next(iter(fake_db.parent_auth_tokens))
        # can't recover raw token here (only hash stored) -- simulate via
        # direct verify_token call using the known hash bypass instead:
        # re-derive by calling request_link's captured token via a spy.
    finally:
        pass
    # Simpler: directly exercise the portal-expiry branch through a fresh
    # captured token.
    captured = {}
    es.send_parent_magic_link_email = lambda **kw: captured.update(kw)
    parent_service._last_request_at.clear()
    parent_service.request_link(FakeConn(fake_db), settings, parent_email="parent@example.com")
    es.send_parent_magic_link_email = orig_link
    es.send_portal_closed_email = orig_closed
    with pytest.raises(parent_service.PortalClosedError):
        parent_service.verify_token(FakeConn(fake_db), settings, token=captured["token"])


def _session(fake_db: FakeDB) -> parent_service:
    return PARENT_RECORD_ID, REP_ID


def test_get_dashboard_returns_allow_listed_fields(fake_db: FakeDB) -> None:
    row = parent_service.get_dashboard(FakeConn(fake_db), REP_ID)
    assert row["display_name"] == "Rep One"
    assert row["total_earnings_cents"] == 5000
    assert "submission_text" not in row


def _make_campaign(fake_db: FakeDB, *, pending: bool = True) -> tuple[str, str]:
    campaign_id = str(uuid.uuid4())
    brand_id = str(uuid.uuid4())
    fake_db.brand_profiles[brand_id] = {"id": brand_id, "company_name": "Acme Co"}
    fake_db.campaigns[campaign_id] = {
        "id": campaign_id, "brand_id": brand_id, "product_name": "Widget", "key_messaging": "Widgets rule",
        "deliverables_description": "1 post", "prohibited_content": None, "payout_per_rep_cents": 5000,
        "start_date": date(2026, 1, 1), "end_date": date(2026, 2, 1), "target_categories": ["gaming"],
    }
    cr_id = str(uuid.uuid4())
    fake_db.campaign_reps[cr_id] = {
        "id": cr_id, "campaign_id": campaign_id, "rep_id": REP_ID,
        "parent_approval_status": "pending" if pending else "approved",
        "parent_approval_deadline": datetime.now(timezone.utc) + timedelta(hours=48),
        "status": "invited", "payout_cents": 5000, "confirmed_at": None,
    }
    return campaign_id, cr_id


def test_pending_campaigns_returns_full_brief(fake_db: FakeDB) -> None:
    campaign_id, _ = _make_campaign(fake_db)
    rows = parent_service.pending_campaigns(FakeConn(fake_db), REP_ID)
    assert len(rows) == 1
    assert rows[0]["brand_name"] == "Acme Co"
    assert rows[0]["campaign_id"] == campaign_id


def test_approve_campaign_is_idempotent(fake_db: FakeDB) -> None:
    campaign_id, cr_id = _make_campaign(fake_db)
    row1 = parent_service.approve_campaign(FakeConn(fake_db), REP_ID, campaign_id)
    assert row1["parent_approval_status"] == "approved"
    row2 = parent_service.approve_campaign(FakeConn(fake_db), REP_ID, campaign_id)
    assert row2["parent_approval_status"] == "approved"


def test_block_campaign_auto_declines_neutrally(fake_db: FakeDB) -> None:
    campaign_id, cr_id = _make_campaign(fake_db)
    row = parent_service.block_campaign(FakeConn(fake_db), REP_ID, campaign_id)
    assert row["parent_approval_status"] == "blocked"
    assert row["status"] == "declined"


def test_block_campaign_not_found_for_non_pending(fake_db: FakeDB) -> None:
    campaign_id, _ = _make_campaign(fake_db, pending=False)
    with pytest.raises(parent_service.CampaignNotPendingError):
        parent_service.block_campaign(FakeConn(fake_db), REP_ID, campaign_id)


def test_update_values_filters(fake_db: FakeDB) -> None:
    row = parent_service.update_values_filters(FakeConn(fake_db), PARENT_RECORD_ID, ["alcohol_adjacent"])
    assert row["values_filters"] == ["alcohol_adjacent"]


def test_update_approval_required_allowed_for_16_17(fake_db: FakeDB) -> None:
    row = parent_service.update_approval_required(
        FakeConn(fake_db), PARENT_RECORD_ID, REP_ID, campaign_approval_required=False
    )
    assert row["campaign_approval_required"] is False


def test_update_approval_required_rejected_outside_16_17(fake_db: FakeDB) -> None:
    fake_db.users[USER_ID]["date_of_birth"] = date.today().replace(year=date.today().year - 20)
    with pytest.raises(parent_service.ApprovalToggleNotPermittedError):
        parent_service.update_approval_required(
            FakeConn(fake_db), PARENT_RECORD_ID, REP_ID, campaign_approval_required=False
        )


def test_digest_preview_excludes_message_and_submission_content(fake_db: FakeDB) -> None:
    preview = parent_service.digest_preview(FakeConn(fake_db), REP_ID)
    serialized_keys = set(preview.keys())
    assert serialized_keys == {
        "campaigns_completed_this_month", "earnings_this_month_cents", "earnings_lifetime_cents",
        "profile_completeness_score", "categories_active_in",
    }
    for forbidden in ("submission_text", "submission_file_urls", "message_text", "brand_contact"):
        assert forbidden not in preview


def test_suspend_and_unsuspend_by_parent(fake_db: FakeDB) -> None:
    settings = _settings()
    import app.services.email_service as es

    orig = es.send_account_suspended_email
    es.send_account_suspended_email = lambda **kw: None
    try:
        parent_service.suspend_account(FakeConn(fake_db), settings, parent_record_id=PARENT_RECORD_ID, rep_id=REP_ID)
    finally:
        es.send_account_suspended_email = orig
    assert fake_db.users[USER_ID]["account_status"] == "suspended"
    assert fake_db.parent_records[PARENT_RECORD_ID]["suspended_by_parent_at"] is not None

    parent_service.unsuspend_account(FakeConn(fake_db), PARENT_RECORD_ID, REP_ID)
    assert fake_db.users[USER_ID]["account_status"] == "active"
    assert fake_db.parent_records[PARENT_RECORD_ID]["suspended_by_parent_at"] is None


def test_unsuspend_rejected_when_not_parent_initiated(fake_db: FakeDB) -> None:
    # Admin-initiated: status is suspended but suspended_by_parent_at is None.
    fake_db.users[USER_ID]["account_status"] = "suspended"
    with pytest.raises(PermissionError):
        parent_service.unsuspend_account(FakeConn(fake_db), PARENT_RECORD_ID, REP_ID)


def test_session_token_round_trip(fake_db: FakeDB) -> None:
    settings = _settings()
    token = issue_parent_session_token(parent_record_id=PARENT_RECORD_ID, rep_id=REP_ID, settings=settings)
    payload = decode_parent_session_token(token, settings)
    assert payload["parent_record_id"] == PARENT_RECORD_ID
    assert payload["rep_id"] == REP_ID
