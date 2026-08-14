"""ATHLETICS-1 tests: track enable/sport-profile stub endpoints, athletic
season CRUD + state machine, sport-stats validation, coach attestation
token issuance/rate-limiting, and profile-score functions (D1-D10
decisions, teenure_athletics_playbook.md)."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

TALENT_USER_ID = "00000000-0000-0000-0000-000000000001"

_BASE_PROFILE_BODY = {
    "display_name": "Athlete Test",
    "school_name": "Test High",
    "school_type": "public",
    "city": "Austin",
    "state": "TX",
    "graduation_year": 2027,
    "bio": "I play sports.",
    "categories": ["gaming"],
    "instagram_handle": None,
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
def onboarded_talent_id(client, db, talent_headers) -> str:
    """Seeds a users row and onboards via PUT /talents/me (creates
    talent_profiles), returning the talent_profiles.id."""
    _seed_talent_user(db)
    resp = client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)
    assert resp.status_code == 200
    return resp.json()["id"]


@pytest.fixture()
def athletics_talent_id(client, db, onboarded_talent_id, talent_headers) -> str:
    """onboarded_talent_id, plus athletics track enabled."""
    resp = client.post("/talents/athletics/enable", headers=talent_headers)
    assert resp.status_code == 200
    assert "athletics" in resp.json()["enabled_tracks"]
    return onboarded_talent_id


def _football_stats() -> dict:
    return {"passing_yards": 2400, "passing_touchdowns": 22}


def _create_season_body(**overrides) -> dict:
    body = {
        "sport": "football",
        "season_year": 2025,
        "season_type": "high_school",
        "team_name": "Wildcats",
        "level": "varsity",
        "sport_stats": _football_stats(),
        "coach_name": "Coach Smith",
        "coach_email": "coach@example.com",
    }
    body.update(overrides)
    return body


# ---------------------------------------------------------------------
# Track gate + enable
# ---------------------------------------------------------------------


def test_enable_athletic_track(client, db, onboarded_talent_id, talent_headers):
    resp = client.post("/talents/athletics/enable", headers=talent_headers)
    assert resp.status_code == 200
    assert resp.json()["enabled_tracks"] == ["brand", "athletics"]

    # Idempotent -- calling again doesn't duplicate the entry.
    resp2 = client.post("/talents/athletics/enable", headers=talent_headers)
    assert resp2.status_code == 200
    assert resp2.json()["enabled_tracks"] == ["brand", "athletics"]


def test_seasons_blocked_before_enable(client, db, onboarded_talent_id, talent_headers):
    resp = client.post("/talents/athletics/seasons", json=_create_season_body(), headers=talent_headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "athletics_not_enabled"


def test_sports_list_blocked_before_enable(client, db, onboarded_talent_id, talent_headers):
    resp = client.get("/talents/athletics/sports", headers=talent_headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "athletics_not_enabled"


# ---------------------------------------------------------------------
# Sport profiles
# ---------------------------------------------------------------------


def test_upsert_sport_profile_valid(client, db, athletics_talent_id, talent_headers):
    body = {"sport": "football", "positions": ["QB"], "gpa": 3.5, "hudl_url": "https://hudl.com/x"}
    resp = client.put("/talents/athletics/sports/football", json=body, headers=talent_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["sport"] == "football"
    assert data["positions"] == ["QB"]
    assert data["gpa"] == 3.5


def test_upsert_sport_profile_unsupported_sport(client, db, athletics_talent_id, talent_headers):
    body = {"sport": "fencing", "positions": []}
    resp = client.put("/talents/athletics/sports/fencing", json=body, headers=talent_headers)
    assert resp.status_code == 422


def test_upsert_sport_profile_updates_athletic_completeness(client, db, athletics_talent_id, talent_headers):
    body = {"sport": "football", "positions": ["QB"], "gpa": 3.5, "hudl_url": "https://hudl.com/x"}
    resp = client.put("/talents/athletics/sports/football", json=body, headers=talent_headers)
    assert resp.status_code == 200

    score = db.fetchval(
        "SELECT athletic_completeness_score FROM public.talent_profiles WHERE id = $1", athletics_talent_id
    )
    # has_sport_profile (30) + has_gpa (20) + has_film_url (15) = 65
    assert score == 65


# ---------------------------------------------------------------------
# Season CRUD + state machine
# ---------------------------------------------------------------------


def test_create_season_creates_in_draft(client, db, athletics_talent_id, talent_headers):
    resp = client.post("/talents/athletics/seasons", json=_create_season_body(), headers=talent_headers)
    assert resp.status_code == 201
    season_id = resp.json()["id"]
    assert resp.json()["status"] == "draft"

    get_resp = client.get(f"/talents/athletics/seasons/{season_id}", headers=talent_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "draft"


def test_list_seasons_ordered(client, db, athletics_talent_id, talent_headers):
    client.post("/talents/athletics/seasons", json=_create_season_body(season_year=2024), headers=talent_headers)
    client.post("/talents/athletics/seasons", json=_create_season_body(season_year=2025), headers=talent_headers)
    resp = client.get("/talents/athletics/seasons", headers=talent_headers)
    assert resp.status_code == 200
    years = [s["season_year"] for s in resp.json()]
    assert years == [2025, 2024]


def test_put_on_pending_attestation_returns_409(client, db, athletics_talent_id, talent_headers):
    create_resp = client.post("/talents/athletics/seasons", json=_create_season_body(), headers=talent_headers)
    season_id = create_resp.json()["id"]

    req_resp = client.post(f"/talents/athletics/seasons/{season_id}/request-attestation", headers=talent_headers)
    assert req_resp.status_code == 200

    put_resp = client.put(f"/talents/athletics/seasons/{season_id}", json=_create_season_body(), headers=talent_headers)
    assert put_resp.status_code == 409
    assert put_resp.json()["error"]["code"] == "season_not_editable"


def test_delete_draft_returns_204(client, db, athletics_talent_id, talent_headers):
    create_resp = client.post("/talents/athletics/seasons", json=_create_season_body(), headers=talent_headers)
    season_id = create_resp.json()["id"]
    del_resp = client.delete(f"/talents/athletics/seasons/{season_id}", headers=talent_headers)
    assert del_resp.status_code == 204

    get_resp = client.get(f"/talents/athletics/seasons/{season_id}", headers=talent_headers)
    assert get_resp.status_code == 404


def test_delete_pending_attestation_returns_409(client, db, athletics_talent_id, talent_headers):
    create_resp = client.post("/talents/athletics/seasons", json=_create_season_body(), headers=talent_headers)
    season_id = create_resp.json()["id"]
    client.post(f"/talents/athletics/seasons/{season_id}/request-attestation", headers=talent_headers)

    del_resp = client.delete(f"/talents/athletics/seasons/{season_id}", headers=talent_headers)
    assert del_resp.status_code == 409
    assert del_resp.json()["error"]["code"] == "season_not_editable"


def test_request_attestation_without_coach_email_returns_422(client, db, athletics_talent_id, talent_headers):
    body = _create_season_body(coach_email=None)
    create_resp = client.post("/talents/athletics/seasons", json=body, headers=talent_headers)
    season_id = create_resp.json()["id"]

    resp = client.post(f"/talents/athletics/seasons/{season_id}/request-attestation", headers=talent_headers)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "coach_email_required"


def test_request_attestation_without_coach_name_returns_422(client, db, athletics_talent_id, talent_headers):
    body = _create_season_body(coach_name=None)
    create_resp = client.post("/talents/athletics/seasons", json=body, headers=talent_headers)
    season_id = create_resp.json()["id"]

    resp = client.post(f"/talents/athletics/seasons/{season_id}/request-attestation", headers=talent_headers)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "coach_name_required"


def test_request_attestation_twice_within_48h_rate_limited(client, db, athletics_talent_id, talent_headers):
    create_resp = client.post("/talents/athletics/seasons", json=_create_season_body(), headers=talent_headers)
    season_id = create_resp.json()["id"]

    first = client.post(f"/talents/athletics/seasons/{season_id}/request-attestation", headers=talent_headers)
    assert first.status_code == 200

    # Withdraw so status is back to 'draft' (a legal state to re-request
    # from), but the token issued above is still within the 48h window --
    # the rate limit is keyed on token recency, not season status.
    withdraw = client.post(f"/talents/athletics/seasons/{season_id}/withdraw-attestation", headers=talent_headers)
    assert withdraw.status_code == 200

    second = client.post(f"/talents/athletics/seasons/{season_id}/request-attestation", headers=talent_headers)
    assert second.status_code == 429
    body = second.json()["error"]
    assert body["code"] == "rate_limited"
    assert body["hours_until_resend_allowed"] > 0


def test_withdraw_attestation_returns_to_draft_and_supersedes_token(client, db, athletics_talent_id, talent_headers):
    create_resp = client.post("/talents/athletics/seasons", json=_create_season_body(), headers=talent_headers)
    season_id = create_resp.json()["id"]
    client.post(f"/talents/athletics/seasons/{season_id}/request-attestation", headers=talent_headers)

    resp = client.post(f"/talents/athletics/seasons/{season_id}/withdraw-attestation", headers=talent_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "draft"

    rows = db.fetch(
        "SELECT used_at, superseded_at FROM public.coach_attestation_tokens WHERE athletic_season_id = $1",
        season_id,
    )
    assert len(rows) == 1
    assert rows[0]["superseded_at"] is not None


def test_withdraw_attestation_illegal_from_draft_returns_409(client, db, athletics_talent_id, talent_headers):
    create_resp = client.post("/talents/athletics/seasons", json=_create_season_body(), headers=talent_headers)
    season_id = create_resp.json()["id"]

    resp = client.post(f"/talents/athletics/seasons/{season_id}/withdraw-attestation", headers=talent_headers)
    assert resp.status_code == 409


# ---------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------


def test_create_season_out_of_range_stat_returns_422(client, db, athletics_talent_id, talent_headers):
    body = _create_season_body(sport_stats={"passing_yards": 99999})
    resp = client.post("/talents/athletics/seasons", json=body, headers=talent_headers)
    assert resp.status_code == 422


def test_create_season_malformed_achievement_returns_422(client, db, athletics_talent_id, talent_headers):
    body = _create_season_body(sport_stats={"achievements": [{"title": "MVP"}]})
    resp = client.post("/talents/athletics/seasons", json=body, headers=talent_headers)
    assert resp.status_code == 422


def test_create_season_valid_achievement_succeeds(client, db, athletics_talent_id, talent_headers):
    body = _create_season_body(
        sport_stats={
            "passing_yards": 2400,
            "achievements": [{"title": "All-Conference", "type": "honor", "season_year": 2025}],
        }
    )
    resp = client.post("/talents/athletics/seasons", json=body, headers=talent_headers)
    assert resp.status_code == 201


def test_create_season_unsupported_sport_returns_422(client, db, athletics_talent_id, talent_headers):
    body = _create_season_body(sport="fencing")
    resp = client.post("/talents/athletics/seasons", json=body, headers=talent_headers)
    assert resp.status_code == 422


# ---------------------------------------------------------------------
# Ownership
# ---------------------------------------------------------------------


def test_get_other_talents_season_returns_404(client, db, athletics_talent_id, talent_headers):
    other_talent_id = str(uuid.uuid4())
    other_user_id = str(uuid.uuid4())
    db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", other_user_id, "other@example.com")
    db.execute(
        "INSERT INTO public.users (id, email, role, account_status, date_of_birth) "
        "VALUES ($1, 'other@example.com', 'talent', 'active', '2008-01-01')",
        other_user_id,
    )
    db.execute(
        """
        INSERT INTO public.talent_profiles
            (id, user_id, display_name, school_name, city, state, graduation_year, enabled_tracks)
        VALUES ($1, $2, 'Other Talent', 'Other High', 'Dallas', 'TX', 2027, ARRAY['brand','athletics'])
        """,
        other_talent_id,
        other_user_id,
    )
    season_id = str(uuid.uuid4())
    db.execute(
        """
        INSERT INTO public.athletic_seasons
            (id, talent_id, sport, season_year, season_type, team_name, level, sport_stats)
        VALUES ($1, $2, 'football', 2025, 'high_school', 'Cowboys', 'varsity', '{}'::jsonb)
        """,
        season_id,
        other_talent_id,
    )

    resp = client.get(f"/talents/athletics/seasons/{season_id}", headers=talent_headers)
    assert resp.status_code == 404

    put_resp = client.put(f"/talents/athletics/seasons/{season_id}", json=_create_season_body(), headers=talent_headers)
    assert put_resp.status_code == 404

    del_resp = client.delete(f"/talents/athletics/seasons/{season_id}", headers=talent_headers)
    assert del_resp.status_code == 404


def test_get_missing_season_returns_404(client, db, athletics_talent_id, talent_headers):
    resp = client.get(f"/talents/athletics/seasons/{uuid.uuid4()}", headers=talent_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------
# Coach attestation token issuance (repository-level)
# ---------------------------------------------------------------------


def test_coach_attestation_token_issue_supersedes_prior(client, db, athletics_talent_id, talent_headers):
    create_resp = client.post("/talents/athletics/seasons", json=_create_season_body(), headers=talent_headers)
    season_id = create_resp.json()["id"]

    client.post(f"/talents/athletics/seasons/{season_id}/request-attestation", headers=talent_headers)
    rows = db.fetch(
        "SELECT token, superseded_at, used_at FROM public.coach_attestation_tokens "
        "WHERE athletic_season_id = $1 ORDER BY created_at",
        season_id,
    )
    assert len(rows) == 1
    assert rows[0]["superseded_at"] is None
    assert rows[0]["used_at"] is None


def test_coach_attestation_token_expiry_ttl(client, db, athletics_talent_id, talent_headers):
    create_resp = client.post("/talents/athletics/seasons", json=_create_season_body(), headers=talent_headers)
    season_id = create_resp.json()["id"]
    client.post(f"/talents/athletics/seasons/{season_id}/request-attestation", headers=talent_headers)

    row = db.fetch(
        "SELECT expires_at, created_at FROM public.coach_attestation_tokens WHERE athletic_season_id = $1",
        season_id,
    )[0]
    delta = row["expires_at"] - row["created_at"]
    assert timedelta(hours=71) < delta < timedelta(hours=73)


# ---------------------------------------------------------------------
# NIL state rules (seeded data, ATHLETICS-1 verifies the seed exists --
# the acknowledgment endpoint itself is ATHLETICS-3's scope)
# ---------------------------------------------------------------------


def test_nil_state_rules_eligible_state(db):
    row = db.fetch("SELECT nil_eligible FROM public.nil_state_rules WHERE state = 'FL'")
    assert row[0]["nil_eligible"] is True


def test_nil_state_rules_ineligible_state(db):
    row = db.fetch("SELECT nil_eligible FROM public.nil_state_rules WHERE state = 'NY'")
    assert row[0]["nil_eligible"] is False


# ---------------------------------------------------------------------
# ATHLETICS-2: coach attestation email flow + public verification
# ---------------------------------------------------------------------


def _request_attestation_token(client, db, season_id, talent_headers) -> str:
    resp = client.post(f"/talents/athletics/seasons/{season_id}/request-attestation", headers=talent_headers)
    assert resp.status_code == 200
    row = db.fetch(
        "SELECT token FROM public.coach_attestation_tokens WHERE athletic_season_id = $1", season_id
    )[0]
    return row["token"]


def test_request_attestation_sends_coach_email(client, db, athletics_talent_id, talent_headers, fake_resend_client):
    create_resp = client.post("/talents/athletics/seasons", json=_create_season_body(), headers=talent_headers)
    season_id = create_resp.json()["id"]

    resp = client.post(f"/talents/athletics/seasons/{season_id}/request-attestation", headers=talent_headers)
    assert resp.status_code == 200

    assert len(fake_resend_client.sent) == 1
    email = fake_resend_client.sent[0]
    assert email.to == "coach@example.com"
    assert "2025" in email.subject
    assert "football" in email.subject
    assert "Athlete Test" in email.subject
    # Safety: no talent contact info in the coach attestation email.
    assert "talent@example.com" not in email.html
    assert "Test High" not in email.html
    assert "Austin" not in email.html


def test_get_attestation_token_valid(client, db, athletics_talent_id, talent_headers):
    create_resp = client.post("/talents/athletics/seasons", json=_create_season_body(), headers=talent_headers)
    season_id = create_resp.json()["id"]
    token = _request_attestation_token(client, db, season_id, talent_headers)

    resp = client.get(f"/athletics/attest/{token}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert body["talent_display_name"] == "Athlete Test"
    assert body["sport"] == "football"
    assert body["season_year"] == 2025
    assert body["sport_stats"]["passing_yards"] == 2400
    # Safety: no school/city/grad-year PII in the public verification response.
    for key in ("school_name", "city", "state", "graduation_year"):
        assert key not in body


def test_get_attestation_token_not_found_returns_200(client, db):
    resp = client.get("/athletics/attest/nonexistent-token")
    assert resp.status_code == 200
    assert resp.json() == {
        "valid": False,
        "reason": "not_found",
        "talent_display_name": None,
        "sport": None,
        "season_year": None,
        "team_name": None,
        "level": None,
        "sport_stats": None,
        "coach_name": None,
    }


def test_get_attestation_token_superseded_returns_200(client, db, athletics_talent_id, talent_headers):
    create_resp = client.post("/talents/athletics/seasons", json=_create_season_body(), headers=talent_headers)
    season_id = create_resp.json()["id"]
    old_token = _request_attestation_token(client, db, season_id, talent_headers)

    client.post(f"/talents/athletics/seasons/{season_id}/withdraw-attestation", headers=talent_headers)
    client.post(f"/talents/athletics/seasons/{season_id}/request-attestation", headers=talent_headers)

    resp = client.get(f"/athletics/attest/{old_token}")
    assert resp.status_code == 200
    assert resp.json()["valid"] is False
    assert resp.json()["reason"] == "superseded"


def test_confirm_attestation_marks_season_attested_and_notifies_talent(
    client, db, athletics_talent_id, talent_headers, fake_resend_client
):
    create_resp = client.post("/talents/athletics/seasons", json=_create_season_body(), headers=talent_headers)
    season_id = create_resp.json()["id"]
    token = _request_attestation_token(client, db, season_id, talent_headers)
    fake_resend_client.sent.clear()

    resp = client.post(f"/athletics/attest/{token}/confirm")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["sport"] == "football"
    assert body["season_year"] == 2025

    season_resp = client.get(f"/talents/athletics/seasons/{season_id}", headers=talent_headers)
    assert season_resp.json()["status"] == "attested"
    assert season_resp.json()["coach_attestation_status"] == "attested"

    assert len(fake_resend_client.sent) == 1
    notif = fake_resend_client.sent[0]
    assert notif.to == "talent@example.com"
    assert "coach@example.com" not in notif.html


def test_confirm_attestation_replay_is_idempotent(client, db, athletics_talent_id, talent_headers, fake_resend_client):
    create_resp = client.post("/talents/athletics/seasons", json=_create_season_body(), headers=talent_headers)
    season_id = create_resp.json()["id"]
    token = _request_attestation_token(client, db, season_id, talent_headers)

    first = client.post(f"/athletics/attest/{token}/confirm")
    assert first.json()["success"] is True
    fake_resend_client.sent.clear()

    second = client.post(f"/athletics/attest/{token}/confirm")
    assert second.status_code == 200
    assert second.json()["success"] is False
    assert second.json()["reason"] == "already_resolved"
    assert len(fake_resend_client.sent) == 0


def test_decline_attestation_keeps_season_pending_and_notifies_talent(
    client, db, athletics_talent_id, talent_headers, fake_resend_client
):
    create_resp = client.post("/talents/athletics/seasons", json=_create_season_body(), headers=talent_headers)
    season_id = create_resp.json()["id"]
    token = _request_attestation_token(client, db, season_id, talent_headers)
    fake_resend_client.sent.clear()

    resp = client.post(f"/athletics/attest/{token}/decline")
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    season_resp = client.get(f"/talents/athletics/seasons/{season_id}", headers=talent_headers)
    body = season_resp.json()
    assert body["status"] == "pending_attestation"
    assert body["coach_attestation_status"] == "declined"

    assert len(fake_resend_client.sent) == 1
    notif = fake_resend_client.sent[0]
    assert notif.to == "talent@example.com"
    assert "coach@example.com" not in notif.html
    assert "declined" not in notif.html.lower()


def test_get_attestation_token_expired_returns_200(client, db, athletics_talent_id, talent_headers):
    create_resp = client.post("/talents/athletics/seasons", json=_create_season_body(), headers=talent_headers)
    season_id = create_resp.json()["id"]
    token = _request_attestation_token(client, db, season_id, talent_headers)

    db.execute(
        "UPDATE public.coach_attestation_tokens SET expires_at = now() - interval '1 hour' WHERE token = $1",
        token,
    )

    resp = client.get(f"/athletics/attest/{token}")
    assert resp.status_code == 200
    assert resp.json()["valid"] is False
    assert resp.json()["reason"] == "expired"
