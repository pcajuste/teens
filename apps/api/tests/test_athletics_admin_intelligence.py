"""ATHLETICS-8 tests: admin athletic queue, coach attestation expiry
sweep, athletic intelligence pipeline, parent portal athletic
extension, and the public /verified/:token athletic extension."""
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


def _seed_talent_user(db) -> None:
    db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", TALENT_USER_ID, "talent@example.com")
    db.execute(
        "INSERT INTO public.users (id, email, role, account_status, date_of_birth) "
        "VALUES ($1, 'talent@example.com', 'talent', 'active', '2008-06-01')",
        TALENT_USER_ID,
    )


@pytest.fixture()
def admin_headers(auth_headers_factory):
    # No DB row needed -- admin routes gate on the JWT role claim only
    # (same pattern as tests/test_athletics.py's ATHLETICS-3 admin tests).
    return auth_headers_factory("admin")


@pytest.fixture()
def talent_headers(auth_headers_factory):
    return auth_headers_factory("talent")


@pytest.fixture()
def athletics_talent_id(client, db, talent_headers) -> str:
    _seed_talent_user(db)
    resp = client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)
    assert resp.status_code == 200
    talent_id = resp.json()["id"]
    enable_resp = client.post("/talents/athletics/enable", headers=talent_headers)
    assert enable_resp.status_code == 200
    return talent_id


def _create_attested_season(client, db, talent_id, talent_headers, fake_resend_client, *, sport="football") -> str:
    body = {
        "sport": sport,
        "season_year": 2025,
        "season_type": "high_school",
        "team_name": "Wildcats",
        "level": "varsity",
        "sport_stats": {"passing_yards": 2400, "achievements": [{"title": "MVP", "type": "award", "season_year": 2025}]},
        "coach_name": "Coach Smith",
        "coach_email": "coach@example.com",
    }
    create_resp = client.post("/talents/athletics/seasons", json=body, headers=talent_headers)
    assert create_resp.status_code == 201
    season_id = create_resp.json()["id"]
    client.post(f"/talents/athletics/seasons/{season_id}/request-attestation", headers=talent_headers)
    token = db.fetch("SELECT token FROM public.coach_attestation_tokens WHERE athletic_season_id = $1", season_id)[0]["token"]
    confirm_resp = client.post(f"/athletics/attest/{token}/confirm")
    assert confirm_resp.status_code == 200
    return season_id


# ---------------------------------------------------------------------
# Admin athletic queue
# ---------------------------------------------------------------------


def test_pending_verification_only_attested_unverified(client, db, admin_headers, athletics_talent_id, talent_headers, fake_resend_client):
    season_id = _create_attested_season(client, db, athletics_talent_id, talent_headers, fake_resend_client)

    resp = client.get("/admin/athletics/seasons/pending-verification", headers=admin_headers)
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert season_id in ids
    for s in resp.json():
        assert s["status"] == "attested"
        assert s["admin_verified"] is False


def test_admin_verify_season(client, db, admin_headers, athletics_talent_id, talent_headers, fake_resend_client):
    season_id = _create_attested_season(client, db, athletics_talent_id, talent_headers, fake_resend_client)

    resp = client.post(f"/admin/athletics/seasons/{season_id}/verify", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "verified"
    assert resp.json()["admin_verified"] is True
    assert resp.json()["admin_verified_at"] is not None

    get_resp = client.get(f"/talents/athletics/seasons/{season_id}", headers=talent_headers)
    assert get_resp.json()["status"] == "verified"


def test_admin_flag_season(client, db, admin_headers, athletics_talent_id, talent_headers, fake_resend_client):
    season_id = _create_attested_season(client, db, athletics_talent_id, talent_headers, fake_resend_client)
    client.post(f"/admin/athletics/seasons/{season_id}/verify", headers=admin_headers)

    resp = client.post(f"/admin/athletics/seasons/{season_id}/flag", json={"reason": "passing_yards looks wrong"}, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["admin_verified"] is False

    row = db.fetch("SELECT admin_flag_reason FROM public.athletic_seasons WHERE id = $1", season_id)
    assert row[0]["admin_flag_reason"] == "passing_yards looks wrong"


def test_admin_flag_season_non_admin_forbidden(client, db, athletics_talent_id, talent_headers, fake_resend_client):
    season_id = _create_attested_season(client, db, athletics_talent_id, talent_headers, fake_resend_client)
    resp = client.post(f"/athletics/seasons/{season_id}/flag", json={"reason": "x"}, headers=talent_headers)
    assert resp.status_code == 404  # not an admin route at all under /athletics


def test_admin_verify_non_admin_jwt_forbidden(client, db, athletics_talent_id, talent_headers, fake_resend_client):
    season_id = _create_attested_season(client, db, athletics_talent_id, talent_headers, fake_resend_client)
    resp = client.post(f"/admin/athletics/seasons/{season_id}/verify", headers=talent_headers)
    assert resp.status_code == 403


def test_admin_list_nil_rules_includes_last_updated_at(client, db, admin_headers):
    resp = client.get("/admin/nil-rules", headers=admin_headers)
    assert resp.status_code == 200
    assert len(resp.json()) > 0
    assert "last_updated_at" in resp.json()[0]


# ---------------------------------------------------------------------
# Coach attestation expiry sweep
# ---------------------------------------------------------------------


def _run_job(client, settings, job_name):
    return client.post(f"/internal/jobs/run/{job_name}", headers={"X-Jobs-Runner-Secret": settings.jobs_runner_secret})


def test_expiry_sweep_reverts_expired_pending_attestation(client, db, athletics_talent_id, talent_headers, settings):
    body = {
        "sport": "football", "season_year": 2025, "season_type": "high_school",
        "team_name": "Wildcats", "level": "varsity", "sport_stats": {"passing_yards": 2000},
        "coach_name": "Coach Smith", "coach_email": "coach@example.com",
    }
    create_resp = client.post("/talents/athletics/seasons", json=body, headers=talent_headers)
    season_id = create_resp.json()["id"]
    client.post(f"/talents/athletics/seasons/{season_id}/request-attestation", headers=talent_headers)

    db.execute(
        "UPDATE public.coach_attestation_tokens SET expires_at = $2 WHERE athletic_season_id = $1",
        season_id,
        datetime.now(timezone.utc) - timedelta(hours=1),
    )

    resp = _run_job(client, settings, "athletics_attestation_expiry_sweep")
    assert resp.status_code == 200

    get_resp = client.get(f"/talents/athletics/seasons/{season_id}", headers=talent_headers)
    assert get_resp.json()["status"] == "draft"
    assert get_resp.json()["coach_attestation_status"] == "not_requested"


def test_expiry_sweep_idempotent(client, db, athletics_talent_id, talent_headers, settings):
    body = {
        "sport": "football", "season_year": 2025, "season_type": "high_school",
        "team_name": "Wildcats", "level": "varsity", "sport_stats": {"passing_yards": 2000},
        "coach_name": "Coach Smith", "coach_email": "coach@example.com",
    }
    create_resp = client.post("/talents/athletics/seasons", json=body, headers=talent_headers)
    season_id = create_resp.json()["id"]
    client.post(f"/talents/athletics/seasons/{season_id}/request-attestation", headers=talent_headers)
    db.execute(
        "UPDATE public.coach_attestation_tokens SET expires_at = $2 WHERE athletic_season_id = $1",
        season_id,
        datetime.now(timezone.utc) - timedelta(hours=1),
    )

    first = _run_job(client, settings, "athletics_attestation_expiry_sweep")
    second = _run_job(client, settings, "athletics_attestation_expiry_sweep")
    assert first.status_code == 200
    assert second.status_code == 200

    get_resp = client.get(f"/talents/athletics/seasons/{season_id}", headers=talent_headers)
    assert get_resp.json()["status"] == "draft"


# ---------------------------------------------------------------------
# Athletic intelligence pipeline
# ---------------------------------------------------------------------


def test_intelligence_job_writes_anonymized_event(client, db, athletics_talent_id, talent_headers, fake_resend_client, settings):
    season_id = _create_attested_season(client, db, athletics_talent_id, talent_headers, fake_resend_client)

    row = db.fetch("SELECT intelligence_event_written_at FROM public.athletic_seasons WHERE id = $1", season_id)
    assert row[0]["intelligence_event_written_at"] is None

    resp = _run_job(client, settings, "athletics_intelligence_pipeline")
    assert resp.status_code == 200
    assert resp.json()["events_written"] == 1

    row = db.fetch("SELECT intelligence_event_written_at FROM public.athletic_seasons WHERE id = $1", season_id)
    assert row[0]["intelligence_event_written_at"] is not None

    events = db.fetch(
        "SELECT track, category FROM public.intelligence_events_anonymized WHERE track = 'athletics'"
    )
    assert len(events) == 1
    assert events[0]["category"] == "football"


def test_intelligence_job_idempotent(client, db, athletics_talent_id, talent_headers, fake_resend_client, settings):
    _create_attested_season(client, db, athletics_talent_id, talent_headers, fake_resend_client)

    _run_job(client, settings, "athletics_intelligence_pipeline")
    resp = _run_job(client, settings, "athletics_intelligence_pipeline")
    assert resp.json()["events_written"] == 0

    events = db.fetch("SELECT COUNT(*) AS c FROM public.intelligence_events_anonymized WHERE track = 'athletics'")
    assert events[0]["c"] == 1


def test_intelligence_event_has_no_identifying_fields(client, db, athletics_talent_id, talent_headers, fake_resend_client, settings):
    _create_attested_season(client, db, athletics_talent_id, talent_headers, fake_resend_client)
    _run_job(client, settings, "athletics_intelligence_pipeline")

    columns = db.fetch(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'intelligence_events_anonymized'"
    )
    column_names = {c["column_name"] for c in columns}
    assert "talent_id" not in column_names
    assert "coach_email" not in column_names
    assert "coach_name" not in column_names


# ---------------------------------------------------------------------
# Parent portal athletic extension
# ---------------------------------------------------------------------


def test_parent_get_athletics_disabled(client, db, parent_headers_factory, seed_talent_with_parent):
    seeded = seed_talent_with_parent()
    headers = parent_headers_factory(parent_id=seeded.parent_id, talent_id=seeded.talent_id)

    resp = client.get("/parent/athletics", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["athletics_enabled"] is False


def test_parent_get_athletics_enabled(client, db, parent_headers_factory, seed_talent_with_parent):
    seeded = seed_talent_with_parent()
    db.execute(
        "UPDATE public.talent_profiles SET enabled_tracks = ARRAY['brand','athletics'] WHERE id = $1",
        seeded.talent_id,
    )
    db.execute(
        "INSERT INTO public.sport_profiles (talent_id, sport, positions) VALUES ($1, 'football', ARRAY['QB'])",
        seeded.talent_id,
    )
    headers = parent_headers_factory(parent_id=seeded.parent_id, talent_id=seeded.talent_id)

    resp = client.get("/parent/athletics", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["athletics_enabled"] is True
    assert len(body["sport_profiles"]) == 1


def test_parent_has_no_athletic_season_approval_route(client, db):
    resp = client.post("/parent/athletics/seasons/some-id/approve", headers={})
    assert resp.status_code == 404


# ---------------------------------------------------------------------
# Public /verified/:token athletic extension
# ---------------------------------------------------------------------


def _get_achievement_link_token(client, talent_headers) -> str:
    """achievement_link_token is lazily generated on first call to
    GET /talents/me/achievement-link -- it's NULL until then."""
    resp = client.get("/talents/me/achievement-link", headers=talent_headers)
    assert resp.status_code == 200
    return resp.json()["token"]


def test_public_verified_includes_attested_season(client, db, athletics_talent_id, talent_headers, fake_resend_client):
    _create_attested_season(client, db, athletics_talent_id, talent_headers, fake_resend_client)
    token = _get_achievement_link_token(client, talent_headers)
    db.execute(
        "UPDATE public.talent_profiles SET verified_profile_public = TRUE WHERE id = $1", athletics_talent_id
    )

    resp = client.get(f"/verified/{token}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["athletic_tracks_enabled"] is True
    assert len(body["attested_seasons"]) == 1
    season = body["attested_seasons"][0]
    assert season["sport"] == "football"
    assert season["season_year"] == 2025
    assert "passing_yards" in season["selected_stats"]
    # Coach-attested but not admin-verified -- achievements withheld.
    assert season["admin_verified"] is False
    assert season["achievements"] is None


def test_public_verified_admin_verified_includes_achievements(client, db, admin_headers, athletics_talent_id, talent_headers, fake_resend_client):
    season_id = _create_attested_season(client, db, athletics_talent_id, talent_headers, fake_resend_client)
    client.post(f"/admin/athletics/seasons/{season_id}/verify", headers=admin_headers)
    token = _get_achievement_link_token(client, talent_headers)
    db.execute(
        "UPDATE public.talent_profiles SET verified_profile_public = TRUE WHERE id = $1", athletics_talent_id
    )

    resp = client.get(f"/verified/{token}")
    season = resp.json()["attested_seasons"][0]
    assert season["admin_verified"] is True
    assert season["achievements"] is not None
    assert season["achievements"][0]["title"] == "MVP"


def test_public_verified_draft_seasons_never_shown(client, db, athletics_talent_id, talent_headers):
    body = {
        "sport": "football", "season_year": 2025, "season_type": "high_school",
        "team_name": "Wildcats", "level": "varsity", "sport_stats": {"passing_yards": 2000},
    }
    client.post("/talents/athletics/seasons", json=body, headers=talent_headers)
    token = _get_achievement_link_token(client, talent_headers)
    db.execute(
        "UPDATE public.talent_profiles SET verified_profile_public = TRUE WHERE id = $1", athletics_talent_id
    )

    resp = client.get(f"/verified/{token}")
    body = resp.json()
    assert body["athletic_tracks_enabled"] is True
    assert body["attested_seasons"] == []


def test_public_verified_earnings_are_brand_only(client, db, athletics_talent_id, talent_headers):
    token = _get_achievement_link_token(client, talent_headers)
    db.execute(
        "UPDATE public.talent_profiles SET verified_profile_public = TRUE, earnings_visible_on_public_profile = TRUE "
        "WHERE id = $1",
        athletics_talent_id,
    )

    resp = client.get(f"/verified/{token}")
    assert resp.json()["total_earnings_cents"] == 0