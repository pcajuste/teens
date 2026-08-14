"""Build Prompt 5 deliverables 12 & 13: Living Achievement Link and Goal
Setting / Progress Tracking.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest

TALENT_USER_ID = "00000000-0000-0000-0000-000000000001"

_BASE_PROFILE_BODY = {
    "display_name": "Test Talent",
    "school_name": "Test High",
    "school_type": "public",
    "city": "Austin",
    "state": "TX",
    "graduation_year": 2027,
    "bio": "I make things.",
    "categories": ["gaming"],
    "instagram_handle": "test_talent",
    "tiktok_handle": None,
}


def _seed_talent_user(db, *, age: int = 20) -> None:
    dob = date(date.today().year - age, 6, 1)
    db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", TALENT_USER_ID, "talent@example.com")
    db.execute(
        "INSERT INTO public.users (id, email, role, account_status, date_of_birth) "
        "VALUES ($1, 'talent@example.com', 'talent', 'active', $2)",
        TALENT_USER_ID,
        dob,
    )


@pytest.fixture()
def talent_headers(auth_headers_factory):
    return auth_headers_factory("talent")


@pytest.fixture()
def onboarded_talent(client, db, talent_headers):
    _seed_talent_user(db)
    response = client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)
    assert response.status_code == 200
    return response.json()


# ---------------------------------------------------------------------
# Achievement Link (deliverable 12)
# ---------------------------------------------------------------------


def test_achievement_link_token_is_generated_once_and_stable(client, talent_headers, onboarded_talent):
    first = client.get("/talents/me/achievement-link", headers=talent_headers)
    assert first.status_code == 200
    body = first.json()
    assert body["token"]
    assert body["url"].endswith(f"/verified/{body['token']}")
    assert body["verified_profile_public"] is False
    assert body["earnings_visible_on_public_profile"] is False

    second = client.get("/talents/me/achievement-link", headers=talent_headers)
    assert second.json()["token"] == body["token"]


def test_verified_token_not_public_by_default(client, talent_headers, onboarded_talent):
    token = client.get("/talents/me/achievement-link", headers=talent_headers).json()["token"]
    res = client.get(f"/verified/{token}")
    assert res.status_code == 200
    assert res.json() == {
        "public": False,
        "display_name": None,
        "school_name": None,
        "graduation_year": None,
        "city": None,
        "categories": None,
        "badges": None,
        "brand_campaigns_completed": None,
        "brand_average_rating": None,
        "total_earnings_cents": None,
        "athletic_tracks_enabled": False,
        "attested_seasons": None,
        "last_updated": None,
    }


def test_unknown_token_returns_not_public_not_404(client):
    res = client.get("/verified/this-token-does-not-exist")
    assert res.status_code == 200
    assert res.json()["public"] is False


def test_verified_token_public_after_toggle_excludes_pii(client, talent_headers, onboarded_talent):
    client.get("/talents/me/achievement-link", headers=talent_headers)
    toggle = client.put(
        "/talents/me/achievement-link/visibility",
        json={"verified_profile_public": True, "earnings_visible_on_public_profile": False},
        headers=talent_headers,
    )
    assert toggle.status_code == 200
    token = toggle.json()["token"]

    res = client.get(f"/verified/{token}")
    assert res.status_code == 200
    body = res.json()
    assert body["public"] is True
    assert body["display_name"] == "Test Talent"
    assert body["school_name"] == "Test High"
    assert body["graduation_year"] == 2027
    assert body["city"] == "Austin"
    assert body["categories"] == ["gaming"]
    assert body["total_earnings_cents"] is None  # earnings toggle is off
    # structurally absent -- PublicVerifiedProfileResponse has no field for these at all
    assert "instagram_handle" not in body
    assert "tiktok_handle" not in body
    assert "bio" not in body


def test_verified_token_shows_earnings_only_when_opted_in(client, talent_headers, onboarded_talent):
    toggle = client.put(
        "/talents/me/achievement-link/visibility",
        json={"verified_profile_public": True, "earnings_visible_on_public_profile": True},
        headers=talent_headers,
    )
    token = toggle.json()["token"]
    res = client.get(f"/verified/{token}")
    assert res.json()["total_earnings_cents"] == 0  # no paid campaigns yet, but the field is present (not null)


def test_achievement_link_requires_talent_auth(client):
    res = client.get("/talents/me/achievement-link")
    assert res.status_code == 401


# ---------------------------------------------------------------------
# Goal Setting (deliverable 13)
# ---------------------------------------------------------------------


def test_create_goal_happy_path(client, talent_headers, onboarded_talent):
    res = client.post("/talents/goals", json={"goal_type": "campaigns_completed", "target_value": 5}, headers=talent_headers)
    assert res.status_code == 201
    body = res.json()
    assert body["goal_type"] == "campaigns_completed"
    assert body["target_value"] == 5
    assert body["current_value"] == 0
    assert body["progress_percentage"] == 0
    assert body["status"] == "active"


def test_create_goal_rejects_below_minimum_target(client, talent_headers, onboarded_talent):
    res = client.post("/talents/goals", json={"goal_type": "earnings_total", "target_value": 500}, headers=talent_headers)
    assert res.status_code == 422


def test_create_goal_rejects_over_maximum_for_profile_completeness(client, talent_headers, onboarded_talent):
    res = client.post("/talents/goals", json={"goal_type": "profile_completeness", "target_value": 150}, headers=talent_headers)
    assert res.status_code == 422


def test_fourth_active_goal_returns_409(client, talent_headers, onboarded_talent):
    for goal_type, target in [("campaigns_completed", 5), ("badges_earned", 1), ("categories_active", 2)]:
        res = client.post("/talents/goals", json={"goal_type": goal_type, "target_value": target}, headers=talent_headers)
        assert res.status_code == 201

    fourth = client.post("/talents/goals", json={"goal_type": "profile_completeness", "target_value": 80}, headers=talent_headers)
    assert fourth.status_code == 409
    assert fourth.json()["error"]["code"] == "max_active_goals_exceeded"


def test_abandon_goal_frees_a_slot(client, talent_headers, onboarded_talent):
    goal_id = client.post("/talents/goals", json={"goal_type": "badges_earned", "target_value": 1}, headers=talent_headers).json()["id"]
    abandon = client.delete(f"/talents/goals/{goal_id}", headers=talent_headers)
    assert abandon.status_code == 200
    assert abandon.json()["status"] == "abandoned"

    # slot freed -- three fresh goals now fit
    for goal_type, target in [("campaigns_completed", 5), ("badges_earned", 1), ("categories_active", 2)]:
        res = client.post("/talents/goals", json={"goal_type": goal_type, "target_value": target}, headers=talent_headers)
        assert res.status_code == 201


def test_abandoned_goal_excluded_from_list(client, talent_headers, onboarded_talent):
    goal_id = client.post("/talents/goals", json={"goal_type": "badges_earned", "target_value": 1}, headers=talent_headers).json()["id"]
    client.delete(f"/talents/goals/{goal_id}", headers=talent_headers)
    listed = client.get("/talents/goals", headers=talent_headers)
    assert listed.json() == []


def test_completed_goal_cannot_be_abandoned(client, db, talent_headers):
    # Onboard with a lower-scoring body (no bio) so a later PUT that adds
    # a bio is a genuine score change -- recompute only runs when the
    # score actually moves, matching update_profile_completeness_score's
    # existing no-op-on-unchanged-score guard.
    _seed_talent_user(db)
    low_score_body = {**_BASE_PROFILE_BODY, "bio": None}
    client.put("/talents/me", json=low_score_body, headers=talent_headers)

    goal_id = client.post(
        "/talents/goals", json={"goal_type": "profile_completeness", "target_value": 1}, headers=talent_headers
    ).json()["id"]

    put_res = client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)
    assert put_res.status_code == 200
    assert put_res.json()["profile_completeness_score"] > 0

    goals = client.get("/talents/goals", headers=talent_headers).json()
    goal = next(g for g in goals if g["id"] == goal_id)
    assert goal["status"] == "completed"
    assert goal["completed_at"] is not None

    abandon = client.delete(f"/talents/goals/{goal_id}", headers=talent_headers)
    assert abandon.status_code == 409
    assert abandon.json()["error"]["code"] == "goal_already_completed"


def test_profile_completeness_goal_completion_sends_email(client, db, talent_headers, fake_resend_client):
    _seed_talent_user(db)
    low_score_body = {**_BASE_PROFILE_BODY, "bio": None}
    client.put("/talents/me", json=low_score_body, headers=talent_headers)

    client.post("/talents/goals", json={"goal_type": "profile_completeness", "target_value": 1}, headers=talent_headers)
    client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)

    goal_emails = [e for e in fake_resend_client.sent if e.subject == "You hit your goal"]
    assert len(goal_emails) == 1
    assert goal_emails[0].to == "talent@example.com"


def test_goal_not_found_returns_404(client, talent_headers, onboarded_talent):
    res = client.delete(f"/talents/goals/{uuid.uuid4()}", headers=talent_headers)
    assert res.status_code == 404


def test_goal_suggestions_exclude_already_active_types_and_cap_at_three(client, talent_headers, onboarded_talent):
    suggestions = client.get("/talents/goals/suggestions", headers=talent_headers).json()
    assert len(suggestions) <= 3
    types = {s["goal_type"] for s in suggestions}
    assert "earnings_total" not in types  # not one of the four rule-based suggestion types

    client.post("/talents/goals", json={"goal_type": "campaigns_completed", "target_value": 5}, headers=talent_headers)
    after = client.get("/talents/goals/suggestions", headers=talent_headers).json()
    assert "campaigns_completed" not in {s["goal_type"] for s in after}


def test_goals_require_talent_auth(client):
    assert client.get("/talents/goals").status_code == 401
    assert client.post("/talents/goals", json={"goal_type": "badges_earned", "target_value": 1}).status_code == 401
