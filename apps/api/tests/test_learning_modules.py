"""Build Prompt 8H: Learning Modules and Verified Badges.

Covers the acceptance criteria enumerated in Teenure_Build_Prompts.md's
8H section: correct_index never present in any client-facing response 
(recursive key search), disclosure enforcement, the four named FTC-gate
cases, retake cooldown, completion atomicity/idempotency, badge fields
in brand/recruiter no-PII serializers, and parent-portal module_activity
visibility (no quiz scores, no wrong answers).
"""
from __future__ import annotations

import time
import uuid
from datetime import date, datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import get_settings

_QUIZ_MODULE_BODY = {
    "title": "FTC Disclosure Essentials",
    "description": "Learn how to disclose sponsored content properly.",
    "category": None,
    "estimated_minutes": 5,
    "badge_title": "FTC Verified",
    "badge_description": "Demonstrated understanding of sponsored content disclosure rules.",
    "badge_color": "#6C3FC5",
    "badge_icon": None,
    "passing_score": 80,
    "content_blocks": [
        {"type": "text", "content": "Sponsored content must always be disclosed."},
        {
            "type": "quiz",
            "content": [
                {
                    "question": "When must you disclose a sponsorship?",
                    "options": ["Never", "Only if asked", "Always, clearly and conspicuously", "Only over $100"],
                    "correct_index": 2,
                },
                {
                    "question": "Where should the disclosure appear?",
                    "options": ["Buried in hashtags", "Early and easy to see", "In a linked document", "Nowhere"],
                    "correct_index": 1,
                },
            ],
        },
    ],
}

_NO_QUIZ_MODULE_BODY = {
    "title": "Client Communication Basics",
    "description": "How to communicate professionally with brands.",
    "category": "gaming",
    "estimated_minutes": 3,
    "badge_title": "Clear Communicator",
    "badge_description": "Demonstrated professional client communication.",
    "badge_color": "#2F855A",
    "badge_icon": None,
    "passing_score": None,
    "content_blocks": [{"type": "text", "content": "Always respond within 24 hours."}],
}


def _seed_rep(db, *, categories: list[str] | None = None) -> tuple[str, str]:
    """Returns (talent_profile_id, talent_user_id)."""
    talent_user_id = str(uuid.uuid4())
    talent_id = str(uuid.uuid4())
    talent_email = f"talent-{talent_user_id}@example.com"
    dob = date(date.today().year - 20, 6, 1)
    db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", talent_user_id, talent_email)
    db.execute(
        "INSERT INTO public.users (id, email, role, account_status, date_of_birth) VALUES ($1, $2, 'talent', 'active', $3)",
        talent_user_id,
        talent_email,
        dob,
    )
    db.execute(
        """
        INSERT INTO public.talent_profiles
            (id, user_id, display_name, school_name, city, state, graduation_year, categories)
        VALUES ($1, $2, 'Test Talent', 'Test High', 'Austin', 'TX', 2027, $3)
        """,
        talent_id,
        talent_user_id,
        categories or ["gaming"],
    )
    return talent_id, talent_user_id


@pytest.fixture()
def admin_headers(auth_headers_factory):
    return auth_headers_factory("admin")


@pytest.fixture()
def talent_headers_factory(auth_headers_factory, db):
    def _factory(talent_user_id: str) -> dict[str, str]:
        settings = get_settings()
        payload = {
            "sub": talent_user_id,
            "email": "talent@example.com",
            "aud": "authenticated",
            "app_metadata": {"role": "talent", "account_status": "active"},
            "exp": int(time.time()) + 3600,
        }
        token = jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")
        return {"Authorization": f"Bearer {token}"}

    return _factory


def _create_and_activate(client, admin_headers, body) -> dict:
    created = client.post("/admin/modules", json=body, headers=admin_headers)
    assert created.status_code == 201, created.text
    activated = client.post(f"/admin/modules/{created.json()['id']}/activate", headers=admin_headers)
    assert activated.status_code == 200, activated.text
    return activated.json()


def _recursive_key_search(obj, key: str) -> bool:
    if isinstance(obj, dict):
        if key in obj:
            return True
        return any(_recursive_key_search(v, key) for v in obj.values())
    if isinstance(obj, list):
        return any(_recursive_key_search(v, key) for v in obj)
    return False


# ---------------------------------------------------------------------
# Security: correct_index never present
# ---------------------------------------------------------------------


def test_talent_module_detail_never_contains_correct_index(client, db, admin_headers, talent_headers_factory):
    module = _create_and_activate(client, admin_headers, _QUIZ_MODULE_BODY)
    talent_id, talent_user_id = _seed_rep(db)
    talent_headers = talent_headers_factory(talent_user_id)

    response  = client.get(f"/talents/modules/{module['id']}", headers=talent_headers)
    assert response .status_code == 200
    assert not _recursive_key_search(response .json(), "correct_index")


def test_admin_module_detail_never_contains_correct_index(client, db, admin_headers):
    module = _create_and_activate(client, admin_headers, _QUIZ_MODULE_BODY)
    response  = client.get(f"/admin/modules/{module['id']}", headers=admin_headers)
    assert response .status_code == 200
    assert not _recursive_key_search(response .json(), "correct_index")


def test_admin_create_response_never_contains_correct_index(client, db, admin_headers):
    created = client.post("/admin/modules", json=_QUIZ_MODULE_BODY, headers=admin_headers)
    assert created.status_code == 201
    assert not _recursive_key_search(created.json(), "correct_index")


def test_admin_list_response_never_contains_correct_index(client, db, admin_headers):
    _create_and_activate(client, admin_headers, _QUIZ_MODULE_BODY)
    response  = client.get("/admin/modules", headers=admin_headers)
    assert response .status_code == 200
    assert not _recursive_key_search(response .json(), "correct_index")


def test_module_start_response_never_contains_correct_index(client, db, admin_headers, talent_headers_factory):
    module = _create_and_activate(client, admin_headers, _QUIZ_MODULE_BODY)
    talent_id, talent_user_id = _seed_rep(db)
    talent_headers = talent_headers_factory(talent_user_id)

    response  = client.post(
        f"/talents/modules/{module['id']}/start", json={"disclosure_acknowledged": True}, headers=talent_headers
    )
    assert response .status_code == 200
    assert not _recursive_key_search(response .json(), "correct_index")


def test_complete_ignores_client_submitted_correct_answers(client, db, admin_headers, talent_headers_factory):
    """The server fetches correct answers independently -- a client
    cannot pass anything answer-adjacent in the request body besides
    plain integer indices, and submitting the actual correct indices
    (guessed or leaked) is exactly what a legitimate pass looks like,
    not a bypass of anything: the server always recomputes from its own
    stored correct_index, never trusts the client's claim."""
    module = _create_and_activate(client, admin_headers, _QUIZ_MODULE_BODY)
    talent_id, talent_user_id = _seed_rep(db)
    talent_headers = talent_headers_factory(talent_user_id)
    client.post(f"/talents/modules/{module['id']}/start", json={"disclosure_acknowledged": True}, headers=talent_headers)

    # Submit wrong answers -- must fail regardless of what else is in the body.
    response  = client.post(
        f"/talents/modules/{module['id']}/complete",
        json={"answers": [0, 0], "correct_index": [2, 1]},  # extra field ignored
        headers=talent_headers,
    )
    assert response .status_code == 200
    body = response .json()
    assert body["passed"] is False
    assert body["quiz_score"] == 0


# ---------------------------------------------------------------------
# Disclosure enforcement
# ---------------------------------------------------------------------


def test_start_without_disclosure_field_returns_400(client, db, admin_headers, talent_headers_factory):
    module = _create_and_activate(client, admin_headers, _NO_QUIZ_MODULE_BODY)
    talent_id, talent_user_id = _seed_rep(db)
    talent_headers = talent_headers_factory(talent_user_id)
    response  = client.post(f"/talents/modules/{module['id']}/start", json={}, headers=talent_headers)
    assert response .status_code == 400
    assert response .json()["error"]["code"] == "disclosure_acknowledgment_required"


def test_start_with_disclosure_false_returns_400(client, db, admin_headers, talent_headers_factory):
    module = _create_and_activate(client, admin_headers, _NO_QUIZ_MODULE_BODY)
    talent_id, talent_user_id = _seed_rep(db)
    talent_headers = talent_headers_factory(talent_user_id)
    response  = client.post(
        f"/talents/modules/{module['id']}/start", json={"disclosure_acknowledged": False}, headers=talent_headers
    )
    assert response .status_code == 400
    assert response .json()["error"]["code"] == "disclosure_acknowledgment_required"


def test_start_with_disclosure_true_succeeds(client, db, admin_headers, talent_headers_factory):
    module = _create_and_activate(client, admin_headers, _NO_QUIZ_MODULE_BODY)
    talent_id, talent_user_id = _seed_rep(db)
    talent_headers = talent_headers_factory(talent_user_id)
    response  = client.post(
        f"/talents/modules/{module['id']}/start", json={"disclosure_acknowledged": True}, headers=talent_headers
    )
    assert response .status_code == 200
    assert response .json()["completion"]["status"] == "in_progress"


# ---------------------------------------------------------------------
# FTC gate: 4 named cases
# ---------------------------------------------------------------------


def _seed_campaign_invite(db, *, talent_id: str) -> str:
    brand_user_id = str(uuid.uuid4())
    brand_id = str(uuid.uuid4())
    campaign_id = str(uuid.uuid4())
    brand_email = f"brand-{brand_user_id}@example.com"
    db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", brand_user_id, brand_email)
    db.execute(
        "INSERT INTO public.users (id, email, role, account_status, date_of_birth) VALUES ($1, $2, 'brand', 'active', '1990-01-01')",
        brand_user_id,
        brand_email,
    )
    db.execute("INSERT INTO public.brand_profiles (id, user_id, company_name) VALUES ($1, $2, 'Acme Co')", brand_id, brand_user_id)
    db.execute(
        """
        INSERT INTO public.campaigns
            (id, brand_id, title, status, product_name, campaign_goal, key_messaging,
             deliverables_description, target_categories, budget_cents, platform_fee_cents,
             talent_pool_cents, payout_per_talent_cents, start_date, end_date)
        VALUES ($1, $2, 'Test Campaign', 'active', 'Widget', 'Awareness', 'Widgets are great',
                'One TikTok post', $3, 100000, 35000, 65000, 5000, CURRENT_DATE, CURRENT_DATE + 30)
        """,
        campaign_id,
        brand_id,
        ["gaming"],
    )
    db.execute(
        "INSERT INTO public.campaign_talents (campaign_id, talent_id) VALUES ($1, $2)",
        campaign_id,
        talent_id,
    )
    return campaign_id


@pytest.fixture()
def ftc_module(client, admin_headers):
    return _create_and_activate(client, admin_headers, _QUIZ_MODULE_BODY)


def test_ftc_gate_no_completion_returns_403(client, db, admin_headers, talent_headers_factory, ftc_module, settings, monkeypatch):
    monkeypatch.setattr(settings, "ftc_module_id", ftc_module["id"])
    talent_id, talent_user_id = _seed_rep(db)
    campaign_id = _seed_campaign_invite(db, talent_id=talent_id)
    talent_headers = talent_headers_factory(talent_user_id)

    response  = client.post(f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": True}, headers=talent_headers)
    assert response .status_code == 403
    assert response .json()["error"]["code"] == "ftc_module_required"
    assert response .json()["error"]["module_id"] == ftc_module["id"]


def test_ftc_gate_failed_completion_returns_403(client, db, admin_headers, talent_headers_factory, ftc_module, settings, monkeypatch):
    monkeypatch.setattr(settings, "ftc_module_id", ftc_module["id"])
    talent_id, talent_user_id = _seed_rep(db)
    campaign_id = _seed_campaign_invite(db, talent_id=talent_id)
    db.execute(
        "INSERT INTO public.talent_module_completions (talent_id, module_id, status) VALUES ($1, $2, 'failed')",
        talent_id,
        ftc_module["id"],
    )
    talent_headers = talent_headers_factory(talent_user_id)

    response  = client.post(f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": True}, headers=talent_headers)
    assert response .status_code == 403
    assert response .json()["error"]["code"] == "ftc_module_required"


def test_ftc_gate_passed_completion_proceeds(client, db, admin_headers, talent_headers_factory, ftc_module, settings, monkeypatch):
    monkeypatch.setattr(settings, "ftc_module_id", ftc_module["id"])
    talent_id, talent_user_id = _seed_rep(db)
    campaign_id = _seed_campaign_invite(db, talent_id=talent_id)
    db.execute(
        "INSERT INTO public.talent_module_completions (talent_id, module_id, status, passed_at) VALUES ($1, $2, 'passed', now())",
        talent_id,
        ftc_module["id"],
    )
    talent_headers = talent_headers_factory(talent_user_id)

    response  = client.post(f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": True}, headers=talent_headers)
    assert response .status_code == 200
    assert response .json()["status"] == "accepted"


def test_ftc_gate_skipped_when_module_id_not_configured(client, db, talent_headers_factory, settings, monkeypatch, caplog):
    monkeypatch.setattr(settings, "ftc_module_id", "")
    talent_id, talent_user_id = _seed_rep(db)
    campaign_id = _seed_campaign_invite(db, talent_id=talent_id)
    talent_headers = talent_headers_factory(talent_user_id)

    import logging

    with caplog.at_level(logging.WARNING):
        response  = client.post(f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": True}, headers=talent_headers)
    assert response .status_code == 200
    assert response .json()["status"] == "accepted"
    assert any("FTC_MODULE_ID not configured" in r.message for r in caplog.records)


# ---------------------------------------------------------------------
# Retake cooldown
# ---------------------------------------------------------------------


def test_retake_within_24h_returns_429(client, db, admin_headers, talent_headers_factory):
    module = _create_and_activate(client, admin_headers, _QUIZ_MODULE_BODY)
    talent_id, talent_user_id = _seed_rep(db)
    db.execute(
        "INSERT INTO public.talent_module_completions (talent_id, module_id, status, last_attempt_at, attempts) "
        "VALUES ($1, $2, 'failed', now() - interval '2 hours', 1)",
        talent_id,
        module["id"],
    )
    talent_headers = talent_headers_factory(talent_user_id)

    response  = client.post(f"/talents/modules/{module['id']}/start", json={"disclosure_acknowledged": True}, headers=talent_headers)
    assert response .status_code == 429
    body = response .json()
    assert body["error"]["code"] == "retake_cooldown"
    assert "available_at" in body["error"]


def test_retake_after_24h_succeeds(client, db, admin_headers, talent_headers_factory):
    module = _create_and_activate(client, admin_headers, _QUIZ_MODULE_BODY)
    talent_id, talent_user_id = _seed_rep(db)
    db.execute(
        "INSERT INTO public.talent_module_completions (talent_id, module_id, status, last_attempt_at, attempts) "
        "VALUES ($1, $2, 'failed', now() - interval '25 hours', 1)",
        talent_id,
        module["id"],
    )
    talent_headers = talent_headers_factory(talent_user_id)

    response  = client.post(f"/talents/modules/{module['id']}/start", json={"disclosure_acknowledged": True}, headers=talent_headers)
    assert response .status_code == 200
    assert response .json()["completion"]["attempts"] == 2


def test_retake_on_passed_module_returns_409(client, db, admin_headers, talent_headers_factory):
    module = _create_and_activate(client, admin_headers, _QUIZ_MODULE_BODY)
    talent_id, talent_user_id = _seed_rep(db)
    db.execute(
        "INSERT INTO public.talent_module_completions (talent_id, module_id, status, passed_at) VALUES ($1, $2, 'passed', now())",
        talent_id,
        module["id"],
    )
    talent_headers = talent_headers_factory(talent_user_id)

    response  = client.post(f"/talents/modules/{module['id']}/start", json={"disclosure_acknowledged": True}, headers=talent_headers)
    assert response .status_code == 409
    assert response .json()["error"]["code"] == "already_completed"


# ---------------------------------------------------------------------
# Completion atomicity / idempotency
# ---------------------------------------------------------------------


def test_passing_module_updates_completion_and_badge_atomically(client, db, admin_headers, talent_headers_factory):
    module = _create_and_activate(client, admin_headers, _QUIZ_MODULE_BODY)
    talent_id, talent_user_id = _seed_rep(db)
    talent_headers = talent_headers_factory(talent_user_id)
    client.post(f"/talents/modules/{module['id']}/start", json={"disclosure_acknowledged": True}, headers=talent_headers)

    response  = client.post(f"/talents/modules/{module['id']}/complete", json={"answers": [2, 1]}, headers=talent_headers)
    assert response .status_code == 200
    body = response .json()
    assert body["passed"] is True
    assert body["quiz_score"] == 100
    assert body["badge"]["badge_title"] == "FTC Verified"

    profile = client.get("/talents/me", headers=talent_headers).json()
    assert profile["badges_earned_count"] == 1
    assert profile["badges"][0]["badge_title"] == "FTC Verified"

    rows = db.fetch("SELECT status, badge_issued_at FROM public.talent_module_completions WHERE talent_id = $1 AND module_id = $2", talent_id, module["id"])
    assert rows[0]["status"] == "passed"
    assert rows[0]["badge_issued_at"] is not None


def test_failing_module_does_not_modify_badges(client, db, admin_headers, talent_headers_factory):
    module = _create_and_activate(client, admin_headers, _QUIZ_MODULE_BODY)
    talent_id, talent_user_id = _seed_rep(db)
    talent_headers = talent_headers_factory(talent_user_id)
    client.post(f"/talents/modules/{module['id']}/start", json={"disclosure_acknowledged": True}, headers=talent_headers)

    response  = client.post(f"/talents/modules/{module['id']}/complete", json={"answers": [0, 0]}, headers=talent_headers)
    assert response .status_code == 200
    body = response .json()
    assert body["passed"] is False
    assert len(body["correct_answers"]) == 2
    assert body["correct_answers"][0]["correct_index"] == 2

    profile = client.get("/talents/me", headers=talent_headers).json()
    assert profile["badges_earned_count"] == 0
    assert profile["badges"] == []


def test_completion_rollback_on_badge_issuance_failure(client, db, admin_headers, talent_headers_factory, monkeypatch):
    """Mocks a DB failure mid-transaction on the badge-append step and
    asserts the completion status is rolled back too -- a talent is never
    left 'passed' with no badge (spec: "if the badges jsonb append
    fails, the completion status must not be set to 'passed'")."""
    from app.repositories import talent_profiles_repository

    module = _create_and_activate(client, admin_headers, _QUIZ_MODULE_BODY)
    talent_id, talent_user_id = _seed_rep(db)
    talent_headers = talent_headers_factory(talent_user_id)
    client.post(f"/talents/modules/{module['id']}/start", json={"disclosure_acknowledged": True}, headers=talent_headers)

    async def _boom(*args, **kwargs):
        raise RuntimeError("simulated DB failure mid-transaction")

    monkeypatch.setattr(talent_profiles_repository, "append_badge_and_recompute_score", _boom)

    with pytest.raises(RuntimeError, match="simulated DB failure"):
        client.post(f"/talents/modules/{module['id']}/complete", json={"answers": [2, 1]}, headers=talent_headers)

    rows = db.fetch(
        "SELECT status FROM public.talent_module_completions WHERE talent_id = $1 AND module_id = $2", talent_id, module["id"]
    )
    assert rows[0]["status"] == "in_progress"  # rolled back, NOT 'passed'

    profile = client.get("/talents/me", headers=talent_headers).json()
    assert profile["badges_earned_count"] == 0


def test_complete_called_twice_does_not_double_issue_badge(client, db, admin_headers, talent_headers_factory):
    module = _create_and_activate(client, admin_headers, _QUIZ_MODULE_BODY)
    talent_id, talent_user_id = _seed_rep(db)
    talent_headers = talent_headers_factory(talent_user_id)
    client.post(f"/talents/modules/{module['id']}/start", json={"disclosure_acknowledged": True}, headers=talent_headers)

    first = client.post(f"/talents/modules/{module['id']}/complete", json={"answers": [2, 1]}, headers=talent_headers)
    assert first.status_code == 200
    assert first.json()["passed"] is True

    # Second call: no in_progress row left (it's now 'passed'), so this
    # must be rejected, not silently re-issue a second badge.
    second = client.post(f"/talents/modules/{module['id']}/complete", json={"answers": [2, 1]}, headers=talent_headers)
    assert second.status_code == 409

    profile = client.get("/talents/me", headers=talent_headers).json()
    assert profile["badges_earned_count"] == 1


# ---------------------------------------------------------------------
# Badge fields in serializers
# ---------------------------------------------------------------------


def _pass_module(client, db, talent_id, talent_headers, module) -> None:
    client.post(f"/talents/modules/{module['id']}/start", json={"disclosure_acknowledged": True}, headers=talent_headers)
    talents = client.post(f"/talents/modules/{module['id']}/complete", json={"answers": [2, 1]}, headers=talent_headers)
    assert talents.status_code == 200, talents.text


def test_recruiter_search_includes_badge_fields_without_credit_spend(client, db, admin_headers, talent_headers_factory):
    module = _create_and_activate(client, admin_headers, _QUIZ_MODULE_BODY)
    talent_id, talent_user_id = _seed_rep(db)
    db.execute("UPDATE public.talent_profiles SET recruiter_visible = TRUE WHERE id = $1", talent_id)
    talent_headers = talent_headers_factory(talent_user_id)
    _pass_module(client, db, talent_id, talent_headers, module)

    recruiter_user_id = str(uuid.uuid4())
    db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", recruiter_user_id, "recruiter@example.com")
    db.execute(
        "INSERT INTO public.users (id, email, role, account_status, date_of_birth) VALUES ($1, 'recruiter@example.com', 'recruiter', 'active', '1990-01-01')",
        recruiter_user_id,
    )
    db.execute(
        "INSERT INTO public.recruiter_profiles (id, user_id, institution_name, institution_type, verified, contact_credits_remaining) "
        "VALUES ($1, $2, 'Acme University', 'college', TRUE, 25)",
        str(uuid.uuid4()),
        recruiter_user_id,
    )
    settings = get_settings()
    payload = {
        "sub": recruiter_user_id,
        "email": "recruiter@example.com",
        "aud": "authenticated",
        "app_metadata": {"role": "recruiter", "account_status": "active"},
        "exp": int(time.time()) + 3600,
    }
    recruiter_headers = {"Authorization": f"Bearer {jwt.encode(payload, settings.supabase_jwt_secret, algorithm='HS256')}"}

    before_credits = client.get("/recruiters/credits", headers=recruiter_headers).json()["contact_credits_remaining"]
    response  = client.get("/recruiters/talents/search", headers=recruiter_headers)
    assert response .status_code == 200
    cards = response .json()
    assert len(cards) == 1
    assert cards[0]["badge_count"] == 1
    assert cards[0]["badge_titles"] == ["FTC Verified"]

    after_credits = client.get("/recruiters/credits", headers=recruiter_headers).json()["contact_credits_remaining"]
    assert after_credits == before_credits  # search costs nothing


def test_brand_browse_includes_badge_titles(client, db, admin_headers, talent_headers_factory, auth_headers_factory):
    module = _create_and_activate(client, admin_headers, _QUIZ_MODULE_BODY)
    talent_id, talent_user_id = _seed_rep(db, categories=["gaming"])
    db.execute("UPDATE public.talent_profiles SET recruiter_visible = TRUE WHERE id = $1", talent_id)
    talent_headers = talent_headers_factory(talent_user_id)
    _pass_module(client, db, talent_id, talent_headers, module)

    brand_user_id = "00000000-0000-0000-0000-000000000001"
    db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", brand_user_id, "brand@example.com")
    db.execute(
        "INSERT INTO public.users (id, email, role, account_status, date_of_birth) VALUES ($1, 'brand@example.com', 'brand', 'active', '1990-01-01')",
        brand_user_id,
    )
    brand_headers = auth_headers_factory("brand")
    brand_body = {
        "company_name": "Acme Co",
        "website": "https://acme.example.com",
        "ein": "12-3456789",
        "industry": "apparel",
        "target_categories": ["gaming"],
    }
    assert client.put("/brands/me", json=brand_body, headers=brand_headers).status_code == 200

    campaign_body = {
        "title": "Spring Launch",
        "product_name": "Acme Widget",
        "campaign_goal": "Awareness",
        "key_messaging": "Widgets are great",
        "prohibited_content": None,
        "deliverables_description": "One TikTok post",
        "target_categories": ["gaming"],
        "target_cities": [],
        "max_talents": 1,
        "budget_cents": 100_000,
        "start_date": (date.today() + timedelta(days=10)).isoformat(),
        "end_date": (date.today() + timedelta(days=40)).isoformat(),
    }
    created = client.post("/brands/campaigns", json=campaign_body, headers=brand_headers).json()

    response  = client.get(f"/brands/campaigns/{created['id']}/talents/browse", headers=brand_headers)
    assert response .status_code == 200
    cards = response .json()
    assert len(cards) == 1
    assert cards[0]["badge_titles"] == ["FTC Verified"]
    assert cards[0]["badge_count"] == 1


# ---------------------------------------------------------------------
# Module content protection: archived modules
# ---------------------------------------------------------------------


def test_archived_module_cannot_be_started(client, db, admin_headers, talent_headers_factory):
    module = _create_and_activate(client, admin_headers, _NO_QUIZ_MODULE_BODY)
    archived = client.post(f"/admin/modules/{module['id']}/archive", headers=admin_headers)
    assert archived.status_code == 200

    talent_id, talent_user_id = _seed_rep(db)
    talent_headers = talent_headers_factory(talent_user_id)
    response  = client.post(f"/talents/modules/{module['id']}/start", json={"disclosure_acknowledged": True}, headers=talent_headers)
    assert response .status_code == 400
    assert response .json()["error"]["code"] == "module_not_active"


def test_in_progress_completion_on_archived_module_returns_clear_message(client, db, admin_headers, talent_headers_factory):
    module = _create_and_activate(client, admin_headers, _NO_QUIZ_MODULE_BODY)
    talent_id, talent_user_id = _seed_rep(db)
    talent_headers = talent_headers_factory(talent_user_id)
    client.post(f"/talents/modules/{module['id']}/start", json={"disclosure_acknowledged": True}, headers=talent_headers)

    archived = client.post(f"/admin/modules/{module['id']}/archive", headers=admin_headers)
    assert archived.status_code == 200

    response  = client.post(f"/talents/modules/{module['id']}/complete", json={"answers": []}, headers=talent_headers)
    assert response .status_code == 410
    assert response .json()["error"]["code"] == "module_archived"


# ---------------------------------------------------------------------
# Admin module management
# ---------------------------------------------------------------------


def test_active_module_cannot_be_edited(client, db, admin_headers):
    module = _create_and_activate(client, admin_headers, _NO_QUIZ_MODULE_BODY)
    response  = client.put(f"/admin/modules/{module['id']}", json=_NO_QUIZ_MODULE_BODY, headers=admin_headers)
    assert response .status_code == 409
    assert response .json()["error"]["code"] == "module_not_editable"


def test_admin_list_includes_pass_rate_and_average_attempts(client, db, admin_headers, talent_headers_factory):
    module = _create_and_activate(client, admin_headers, _QUIZ_MODULE_BODY)
    talent_id, talent_user_id = _seed_rep(db)
    talent_headers = talent_headers_factory(talent_user_id)
    _pass_module(client, db, talent_id, talent_headers, module)

    response  = client.get("/admin/modules", headers=admin_headers)
    assert response .status_code == 200
    entry = next(m for m in response .json() if m["id"] == module["id"])
    assert entry["completion_count"] == 1
    assert entry["pass_rate"] == 1.0
    assert entry["average_attempts"] == 1.0


# ---------------------------------------------------------------------
# Admin analytics
# ---------------------------------------------------------------------


def test_admin_module_analytics_shape(client, db, admin_headers, talent_headers_factory, settings, monkeypatch):
    module = _create_and_activate(client, admin_headers, _QUIZ_MODULE_BODY)
    monkeypatch.setattr(settings, "ftc_module_id", module["id"])
    talent_id, talent_user_id = _seed_rep(db)
    talent_headers = talent_headers_factory(talent_user_id)
    _pass_module(client, db, talent_id, talent_headers, module)

    response  = client.get("/admin/analytics/modules", headers=admin_headers)
    assert response .status_code == 200
    body = response .json()
    assert body["total_modules"] == 1
    assert body["completions_passed"] == 1
    assert body["ftc_module_readiness"] is not None
    assert len(body["badge_distribution"]) == 1


# ---------------------------------------------------------------------
# Parent portal: module_activity, no quiz scores/wrong answers
# ---------------------------------------------------------------------


def test_parent_dashboard_module_activity_hides_quiz_details(client, db, admin_headers, talent_headers_factory, parent_headers_factory, seed_talent_with_parent, settings, monkeypatch):
    seeded = seed_talent_with_parent()
    monkeypatch.setattr(settings, "ftc_module_id", "")

    module = _create_and_activate(client, admin_headers, _QUIZ_MODULE_BODY)
    talent_headers = talent_headers_factory(seeded.talent_user_id)
    client.post(f"/talents/modules/{module['id']}/start", json={"disclosure_acknowledged": True}, headers=talent_headers)
    complete_resp = client.post(f"/talents/modules/{module['id']}/complete", json={"answers": [0, 0]}, headers=talent_headers)
    assert complete_resp.status_code == 200
    assert complete_resp.json()["passed"] is False

    parent_headers = parent_headers_factory(parent_id=seeded.parent_id, talent_id=seeded.talent_id)
    response  = client.get("/parent/dashboard", headers=parent_headers)
    assert response .status_code == 200
    body = response .json()
    assert body["module_activity"]["total_started"] == 1
    assert body["module_activity"]["total_failed"] == 1
    assert body["module_activity"]["total_passed"] == 0
    assert body["module_activity"]["badges_earned"] == []
    assert "quiz_score" not in str(body["module_activity"])
    assert "correct_answers" not in str(body["module_activity"])
    assert "talent_answer_index" not in str(body["module_activity"])


def test_parent_dashboard_shows_badges_earned_and_ftc_status(client, db, admin_headers, talent_headers_factory, parent_headers_factory, seed_talent_with_parent, settings, monkeypatch):
    seeded = seed_talent_with_parent()
    module = _create_and_activate(client, admin_headers, _QUIZ_MODULE_BODY)
    monkeypatch.setattr(settings, "ftc_module_id", module["id"])

    talent_headers = talent_headers_factory(seeded.talent_user_id)
    client.post(f"/talents/modules/{module['id']}/start", json={"disclosure_acknowledged": True}, headers=talent_headers)
    complete_resp = client.post(f"/talents/modules/{module['id']}/complete", json={"answers": [2, 1]}, headers=talent_headers)
    assert complete_resp.status_code == 200
    assert complete_resp.json()["passed"] is True

    parent_headers = parent_headers_factory(parent_id=seeded.parent_id, talent_id=seeded.talent_id)
    response  = client.get("/parent/dashboard", headers=parent_headers)
    assert response .status_code == 200
    body = response .json()["module_activity"]
    assert body["total_passed"] == 1
    assert body["ftc_module_passed"] is True
    assert body["badges_earned"] == [{"badge_title": "FTC Verified", "earned_at": body["badges_earned"][0]["earned_at"]}]
