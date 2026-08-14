from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

talent_USER_ID = "00000000-0000-0000-0000-000000000001"

_BASE_PROFILE_BODY = {
    "display_name": "Test Talent",
    "school_name": "Test High",
    "school_type": "public",
    "city": "Austin",
    "state": "TX",
    "graduation_year": 2027,
    "bio": "I make things.",
    "categories": ["gaming"],
    "instagram_handle": "test_rep",
    "tiktok_handle": None,
}


def _seed_talent_user(
    db,
    *,
    age: int = 17,
    parent_email: str | None = None,
    parent_verified: bool = False,
) -> None:
    dob = date(date.today().year - age, 6, 1)
    db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", talent_USER_ID, "talent@example.com")
    verified_at = datetime.now(timezone.utc) if parent_verified else None
    db.execute(
        """
        INSERT INTO public.users (id, email, role, account_status, date_of_birth, parent_email, parent_verified_at)
        VALUES ($1, 'talent@example.com', 'talent', 'active', $2, $3, $4)
        """,
        talent_USER_ID,
        dob,
        parent_email,
        verified_at,
    )


def _seed_campaign(db, *, target_categories=None, target_cities=None, payout_per_talent_cents=5000, status="active") -> str:
    brand_user_id = str(uuid.uuid4())
    brand_id = str(uuid.uuid4())
    campaign_id = str(uuid.uuid4())
    brand_email = f"brand-{brand_user_id}@example.com"

    db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", brand_user_id, brand_email)
    db.execute(
        "INSERT INTO public.users (id, email, role, account_status, date_of_birth) "
        "VALUES ($1, $2, 'brand', 'active', '1990-01-01')",
        brand_user_id,
        brand_email,
    )
    db.execute(
        "INSERT INTO public.brand_profiles (id, user_id, company_name) VALUES ($1, $2, 'Acme Co')",
        brand_id,
        brand_user_id,
    )
    db.execute(
        """
        INSERT INTO public.campaigns
            (id, brand_id, title, status, product_name, campaign_goal, key_messaging,
             deliverables_description, target_categories, target_cities, budget_cents, platform_fee_cents,
             talent_pool_cents, payout_per_talent_cents, start_date, end_date)
        VALUES ($1, $2, 'Test Campaign', $3, 'Widget', 'Awareness', 'Widgets are great',
                'One TikTok post', $4, $5, 100000, 35000, 65000, $6, CURRENT_DATE, CURRENT_DATE + 30)
        """,
        campaign_id,
        brand_id,
        status,
        target_categories or ["gaming"],
        target_cities or [],
        payout_per_talent_cents,
    )
    return campaign_id


@pytest.fixture()
def talent_headers(auth_headers_factory):
    return auth_headers_factory("talent")


# ---------------------------------------------------------------------
# talent_profiles / parent_records creation-on-onboarding (deliverable 1)
# ---------------------------------------------------------------------


def test_put_me_creates_profile(client, db, talent_headers):
    _seed_talent_user(db, age=20)
    response  = client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)
    assert response .status_code == 200
    body = response .json()
    assert body["display_name"] == "Test Talent"
    assert body["categories"] == ["gaming"]
    assert body["profile_completeness_score"] > 0

    row = db.fetchrow if hasattr(db, "fetchrow") else None
    count = db.fetchval("SELECT COUNT(*) FROM public.talent_profiles WHERE user_id = $1", talent_USER_ID)
    assert count == 1


def test_put_me_under16_verified_creates_parent_record(client, db, talent_headers):
    _seed_talent_user(db, age=15, parent_email="parent@example.com", parent_verified=True)
    response  = client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)
    assert response .status_code == 200

    talent_id = db.fetchval("SELECT id FROM public.talent_profiles WHERE user_id = $1", talent_USER_ID)
    parent_row = db.fetch(
        "SELECT parent_email, campaign_approval_required, digest_enabled, portal_expires_at "
        "FROM public.parent_records WHERE talent_id = $1",
        talent_id,
    )
    assert len(parent_row) == 1
    assert parent_row[0]["parent_email"] == "parent@example.com"
    assert parent_row[0]["campaign_approval_required"] is True
    assert parent_row[0]["digest_enabled"] is True
    # portal_expires_at should be ~ the talent's 18th birthday, i.e. ~3 years out
    expires = parent_row[0]["portal_expires_at"]
    assert expires.year - date.today().year in (2, 3)


def test_put_me_16_17_no_parent_record(client, db, talent_headers):
    _seed_talent_user(db, age=16)
    response  = client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)
    assert response .status_code == 200

    talent_id = db.fetchval("SELECT id FROM public.talent_profiles WHERE user_id = $1", talent_USER_ID)
    count = db.fetchval("SELECT COUNT(*) FROM public.parent_records WHERE talent_id = $1", talent_id)
    assert count == 0


def test_put_me_18plus_no_parent_record(client, db, talent_headers):
    _seed_talent_user(db, age=20)
    client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)

    talent_id = db.fetchval("SELECT id FROM public.talent_profiles WHERE user_id = $1", talent_USER_ID)
    count = db.fetchval("SELECT COUNT(*) FROM public.parent_records WHERE talent_id = $1", talent_id)
    assert count == 0


def test_put_me_rejects_invalid_category(client, db, talent_headers):
    _seed_talent_user(db, age=20)
    body = dict(_BASE_PROFILE_BODY, categories=["alcohol_adjacent"])
    response  = client.put("/talents/me", json=body, headers=talent_headers)
    assert response .status_code == 422


def test_put_me_updates_existing_profile(client, db, talent_headers):
    _seed_talent_user(db, age=20)
    client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)
    updated_body = dict(_BASE_PROFILE_BODY, bio="Updated bio", tiktok_handle="test_tok")
    response  = client.put("/talents/me", json=updated_body, headers=talent_headers)
    assert response .status_code == 200
    assert response .json()["bio"] == "Updated bio"

    count = db.fetchval("SELECT COUNT(*) FROM public.talent_profiles WHERE user_id = $1", talent_USER_ID)
    assert count == 1


# ---------------------------------------------------------------------
# accept/decline/submit/withdraw state machine (deliverables 7-9)
# ---------------------------------------------------------------------


def test_apply_accept_submit_happy_path(client, db, talent_headers):
    _seed_talent_user(db, age=20)
    client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)
    campaign_id = _seed_campaign(db)

    apply_resp = client.post(f"/campaigns/{campaign_id}/apply", headers=talent_headers)
    assert apply_resp.status_code == 201
    assert apply_resp.json()["status"] == "invited"

    accept_resp = client.post(
        f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": True}, headers=talent_headers
    )
    assert accept_resp.status_code == 200
    assert accept_resp.json()["status"] == "accepted"
    assert accept_resp.json()["ftc_disclosure_accepted"] is True

    submit_resp = client.post(
        f"/campaigns/{campaign_id}/submit",
        json={"submission_text": "Posted!", "submission_file_urls": []},
        headers=talent_headers,
    )
    assert submit_resp.status_code == 200
    assert submit_resp.json()["status"] == "submitted"


def test_accept_twice_returns_409(client, db, talent_headers):
    _seed_talent_user(db, age=20)
    client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)
    campaign_id = _seed_campaign(db)
    client.post(f"/campaigns/{campaign_id}/apply", headers=talent_headers)
    client.post(f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": True}, headers=talent_headers)

    second = client.post(f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": True}, headers=talent_headers)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "illegal_transition"


def test_decline_then_decline_again_returns_409(client, db, talent_headers):
    _seed_talent_user(db, age=20)
    client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)
    campaign_id = _seed_campaign(db)
    client.post(f"/campaigns/{campaign_id}/apply", headers=talent_headers)

    first = client.post(f"/campaigns/{campaign_id}/decline", headers=talent_headers)
    assert first.status_code == 200
    assert first.json()["status"] == "declined"

    second = client.post(f"/campaigns/{campaign_id}/decline", headers=talent_headers)
    assert second.status_code == 409


def test_submit_without_ftc_disclosure_returns_403(client, db, talent_headers):
    _seed_talent_user(db, age=20)
    client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)
    campaign_id = _seed_campaign(db)
    client.post(f"/campaigns/{campaign_id}/apply", headers=talent_headers)
    client.post(f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": False}, headers=talent_headers)

    submit_resp = client.post(
        f"/campaigns/{campaign_id}/submit",
        json={"submission_text": "Posted!", "submission_file_urls": []},
        headers=talent_headers,
    )
    assert submit_resp.status_code == 403
    assert submit_resp.json()["error"]["code"] == "ftc_disclosure_required"


def test_submit_before_accept_returns_403_ftc_gate(client, db, talent_headers):
    # A fresh 'invited' row also has ftc_disclosure_accepted=False, so
    # the FTC gate fires before the state-machine check -- both are
    # legitimate 4xx outcomes here, but the FTC gate takes precedence
    # since it's the compliance-critical one.
    _seed_talent_user(db, age=20)
    client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)
    campaign_id = _seed_campaign(db)
    client.post(f"/campaigns/{campaign_id}/apply", headers=talent_headers)

    submit_resp = client.post(
        f"/campaigns/{campaign_id}/submit",
        json={"submission_text": "Posted!", "submission_file_urls": []},
        headers=talent_headers,
    )
    assert submit_resp.status_code == 403
    assert submit_resp.json()["error"]["code"] == "ftc_disclosure_required"


def test_submit_twice_returns_409_illegal_transition(client, db, talent_headers):
    _seed_talent_user(db, age=20)
    client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)
    campaign_id = _seed_campaign(db)
    client.post(f"/campaigns/{campaign_id}/apply", headers=talent_headers)
    client.post(f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": True}, headers=talent_headers)
    first = client.post(
        f"/campaigns/{campaign_id}/submit",
        json={"submission_text": "Posted!", "submission_file_urls": []},
        headers=talent_headers,
    )
    assert first.status_code == 200

    second = client.post(
        f"/campaigns/{campaign_id}/submit",
        json={"submission_text": "Posted again", "submission_file_urls": []},
        headers=talent_headers,
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "illegal_transition"


def test_withdraw_after_submit_preserves_payout_fields(client, db, talent_headers):
    _seed_talent_user(db, age=20)
    client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)
    campaign_id = _seed_campaign(db)
    client.post(f"/campaigns/{campaign_id}/apply", headers=talent_headers)
    client.post(f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": True}, headers=talent_headers)
    client.post(
        f"/campaigns/{campaign_id}/submit",
        json={"submission_text": "Posted!", "submission_file_urls": []},
        headers=talent_headers,
    )

    talent_id = db.fetchval("SELECT id FROM public.talent_profiles WHERE user_id = $1", talent_USER_ID)
    # Simulate the brand having already confirmed + set payout amount
    # before the talent withdraws -- payout eligibility must not be erased.
    db.execute(
        "UPDATE public.campaign_talents SET payout_cents = 5000, payout_status = 'pending' "
        "WHERE talent_id = $1 AND campaign_id = $2",
        talent_id,
        campaign_id,
    )

    withdraw_resp = client.post(f"/campaigns/{campaign_id}/withdraw", headers=talent_headers)
    assert withdraw_resp.status_code == 200
    assert withdraw_resp.json()["status"] == "declined"
    assert withdraw_resp.json()["payout_cents"] == 5000
    assert withdraw_resp.json()["payout_status"] == "pending"


def test_withdraw_already_declined_returns_409(client, db, talent_headers):
    _seed_talent_user(db, age=20)
    client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)
    campaign_id = _seed_campaign(db)
    client.post(f"/campaigns/{campaign_id}/apply", headers=talent_headers)
    client.post(f"/campaigns/{campaign_id}/decline", headers=talent_headers)

    withdraw_resp = client.post(f"/campaigns/{campaign_id}/withdraw", headers=talent_headers)
    assert withdraw_resp.status_code == 409


# ---------------------------------------------------------------------
# parent-approval gate (deliverable 7 / acceptance criterion)
# ---------------------------------------------------------------------


def test_accept_blocked_awaiting_parent_approval(client, db, talent_headers):
    _seed_talent_user(db, age=15, parent_email="parent@example.com", parent_verified=True)
    client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)
    campaign_id = _seed_campaign(db)

    apply_resp = client.post(f"/campaigns/{campaign_id}/apply", headers=talent_headers)
    assert apply_resp.status_code == 201
    assert apply_resp.json()["parent_approval_status"] == "pending"

    accept_resp = client.post(
        f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": True}, headers=talent_headers
    )
    assert accept_resp.status_code == 403
    assert accept_resp.json()["error"]["code"] == "awaiting_parent_approval"


def test_apply_requiring_parent_approval_notifies_the_parent(client, db, talent_headers, fake_resend_client):
    _seed_talent_user(db, age=15, parent_email="parent@example.com", parent_verified=True)
    client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)
    campaign_id = _seed_campaign(db)

    response  = client.post(f"/campaigns/{campaign_id}/apply", headers=talent_headers)
    assert response .status_code == 201
    assert response .json()["parent_approval_status"] == "pending"

    # Regression coverage: send_campaign_approval_request existed and
    # was documented as being called on apply, but nothing actually
    # called it until this was noticed while building Prompt 8.
    assert len(fake_resend_client.sent) == 1
    assert fake_resend_client.sent[0].to == "parent@example.com"


def test_apply_not_requiring_parent_approval_sends_no_email(client, db, talent_headers, fake_resend_client):
    _seed_talent_user(db, age=20)
    client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)
    campaign_id = _seed_campaign(db)

    response  = client.post(f"/campaigns/{campaign_id}/apply", headers=talent_headers)
    assert response .status_code == 201
    assert response .json()["parent_approval_status"] == "not_required"
    assert fake_resend_client.sent == []


def test_accept_allowed_once_parent_approves(client, db, talent_headers):
    _seed_talent_user(db, age=15, parent_email="parent@example.com", parent_verified=True)
    client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)
    campaign_id = _seed_campaign(db)
    client.post(f"/campaigns/{campaign_id}/apply", headers=talent_headers)

    talent_id = db.fetchval("SELECT id FROM public.talent_profiles WHERE user_id = $1", talent_USER_ID)
    db.execute(
        "UPDATE public.campaign_talents SET parent_approval_status = 'approved' WHERE talent_id = $1 AND campaign_id = $2",
        talent_id,
        campaign_id,
    )

    accept_resp = client.post(
        f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": True}, headers=talent_headers
    )
    assert accept_resp.status_code == 200
    assert accept_resp.json()["status"] == "accepted"


# ---------------------------------------------------------------------
# values-filter exclusion in GET /talents/campaigns/available (deliverable 3)
# ---------------------------------------------------------------------


def test_available_campaigns_excludes_parent_blocked_category(client, db, talent_headers):
    _seed_talent_user(db, age=15, parent_email="parent@example.com", parent_verified=True)
    body = dict(_BASE_PROFILE_BODY, categories=["gaming", "music"])
    client.put("/talents/me", json=body, headers=talent_headers)

    talent_id = db.fetchval("SELECT id FROM public.talent_profiles WHERE user_id = $1", talent_USER_ID)
    db.execute(
        "UPDATE public.parent_records SET values_filters = $2::jsonb WHERE talent_id = $1",
        talent_id,
        '["gaming"]',
    )

    blocked_campaign = _seed_campaign(db, target_categories=["gaming"])
    allowed_campaign = _seed_campaign(db, target_categories=["music"])

    response  = client.get("/talents/campaigns/available", headers=talent_headers)
    assert response .status_code == 200
    ids = {c["id"] for c in response .json()}
    assert blocked_campaign not in ids
    assert allowed_campaign in ids


def test_available_campaigns_excludes_already_applied(client, db, talent_headers):
    _seed_talent_user(db, age=20)
    client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)
    campaign_id = _seed_campaign(db, target_categories=["gaming"])

    before = client.get("/talents/campaigns/available", headers=talent_headers)
    assert campaign_id in {c["id"] for c in before.json()}

    client.post(f"/campaigns/{campaign_id}/apply", headers=talent_headers)

    after = client.get("/talents/campaigns/available", headers=talent_headers)
    assert campaign_id not in {c["id"] for c in after.json()}


# ---------------------------------------------------------------------
# 48h auto-decline job (deliverable 7 / acceptance criterion -- tested
# directly against the job function, not by waiting on a real clock)
# ---------------------------------------------------------------------


def test_auto_decline_job_expires_lapsed_invitations(client, db, settings, talent_headers):
    _seed_talent_user(db, age=15, parent_email="parent@example.com", parent_verified=True)
    client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)
    campaign_id = _seed_campaign(db)
    client.post(f"/campaigns/{campaign_id}/apply", headers=talent_headers)

    talent_id = db.fetchval("SELECT id FROM public.talent_profiles WHERE user_id = $1", talent_USER_ID)
    # Backdate the deadline so it's already lapsed -- no real clock wait.
    db.execute(
        "UPDATE public.campaign_talents SET parent_approval_deadline = now() - interval '1 hour' "
        "WHERE talent_id = $1 AND campaign_id = $2",
        talent_id,
        campaign_id,
    )

    response  = client.post(
        "/internal/jobs/run/auto_decline_expired_parent_approvals",
        headers={"X-Jobs-Runner-Secret": settings.jobs_runner_secret},
    )
    assert response .status_code == 200

    row = db.fetch(
        "SELECT status, parent_approval_status FROM public.campaign_talents WHERE talent_id = $1 AND campaign_id = $2",
        talent_id,
        campaign_id,
    )[0]
    assert row["status"] == "declined"
    # parent_approval_status must move off 'pending' too, or the row
    # keeps surfacing forever in the parent's pending-approval queue
    # (list_pending_for_rep filters on parent_approval_status='pending'
    # alone, not campaign_talents.status) even though it's already terminal.
    assert row["parent_approval_status"] == "blocked"


def test_auto_decline_job_does_not_touch_unexpired_invitations(client, db, settings, talent_headers):
    _seed_talent_user(db, age=15, parent_email="parent@example.com", parent_verified=True)
    client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)
    campaign_id = _seed_campaign(db)
    client.post(f"/campaigns/{campaign_id}/apply", headers=talent_headers)

    talent_id = db.fetchval("SELECT id FROM public.talent_profiles WHERE user_id = $1", talent_USER_ID)

    client.post(
        "/internal/jobs/run/auto_decline_expired_parent_approvals",
        headers={"X-Jobs-Runner-Secret": settings.jobs_runner_secret},
    )

    status_after = db.fetchval(
        "SELECT status FROM public.campaign_talents WHERE talent_id = $1 AND campaign_id = $2", talent_id, campaign_id
    )
    assert status_after == "invited"


# ---------------------------------------------------------------------
# GET /talents/me, /talents/me/profile-preview, /talents/campaigns/active,
# /talents/campaigns/history, /talents/earnings (Prompt 16 coverage gap fill --
# these were only ever exercised indirectly via PUT /talents/me before)
# ---------------------------------------------------------------------


def test_get_me_returns_own_profile(client, db, talent_headers):
    _seed_talent_user(db, age=20)
    client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)

    response  = client.get("/talents/me", headers=talent_headers)
    assert response .status_code == 200
    assert response .json()["display_name"] == "Test Talent"


def test_get_me_role_enforcement_rejects_non_rep(client, db, auth_headers_factory):
    response  = client.get("/talents/me", headers=auth_headers_factory("brand"))
    assert response .status_code == 403
    assert response .json()["error"]["code"] == "role_mismatch"


def test_profile_preview_reflects_completeness(client, db, talent_headers):
    _seed_talent_user(db, age=20)
    client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)

    response  = client.get("/talents/me/profile-preview", headers=talent_headers)
    assert response .status_code == 200
    assert response .json()["display_name"] == "Test Talent"


def test_achievement_record_matches_profile_preview(client, db, talent_headers):
    """The achievement record must never drift from GET
    /talents/me/profile-preview -- both are built from the same
    _to_preview_response serializer, so their field values should be
    identical for the same talent."""
    _seed_talent_user(db, age=20)
    client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)

    preview = client.get("/talents/me/profile-preview", headers=talent_headers)
    record = client.get("/talents/me/achievement-record", headers=talent_headers)

    assert preview.status_code == 200
    assert record.status_code == 200
    body = record.json()
    assert "generated_at" in body
    assert body["record"] == preview.json()


def test_achievement_record_reflects_only_confirmed_totals(client, db, talent_headers):
    """brand_campaigns_completed/brand_average_rating are cached fields that
    recompute_cached_totals only updates from confirmed campaign_talents
    rows -- an unconfirmed/in-progress campaign must not move them."""
    _seed_talent_user(db, age=20)
    client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)
    campaign_id = _seed_campaign(db)
    client.post(f"/campaigns/{campaign_id}/apply", headers=talent_headers)
    client.post(f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": True}, headers=talent_headers)

    response  = client.get("/talents/me/achievement-record", headers=talent_headers)
    assert response .status_code == 200
    assert response .json()["record"]["brand_campaigns_completed"] == 0


def test_achievement_record_role_enforcement_rejects_non_rep(client, db, auth_headers_factory):
    response  = client.get("/talents/me/achievement-record", headers=auth_headers_factory("brand"))
    assert response .status_code == 403
    assert response .json()["error"]["code"] == "role_mismatch"


def test_achievement_record_requires_own_onboarded_profile(client, db, talent_headers):
    """Every /talents/me/* route resolves the talent from the authenticated
    user's own id -- there is no talent_id parameter anywhere in the URL
    or body, so a talent can never request another talent's record. A talent
    who hasn't onboarded (no talent_profiles row tied to their user id --
    the same situation a would-be cross-talent request would land in,
    since a mismatched id also resolves to no row) gets 404, never
    someone else's data."""
    _seed_talent_user(db, age=20)
    response  = client.get("/talents/me/achievement-record", headers=talent_headers)
    assert response .status_code == 404
    assert response .json()["error"]["code"] == "talent_profile_not_found"


def test_campaigns_active_lists_accepted_campaign(client, db, talent_headers):
    _seed_talent_user(db, age=20)
    client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)
    campaign_id = _seed_campaign(db)
    client.post(f"/campaigns/{campaign_id}/apply", headers=talent_headers)
    client.post(f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": True}, headers=talent_headers)

    response  = client.get("/talents/campaigns/active", headers=talent_headers)
    assert response .status_code == 200
    assert campaign_id in {c["campaign_id"] for c in response .json()}


def test_campaigns_history_excludes_still_active_campaign(client, db, talent_headers):
    _seed_talent_user(db, age=20)
    client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)
    campaign_id = _seed_campaign(db)
    client.post(f"/campaigns/{campaign_id}/apply", headers=talent_headers)
    client.post(f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": True}, headers=talent_headers)

    response  = client.get("/talents/campaigns/history", headers=talent_headers)
    assert response .status_code == 200
    assert campaign_id not in {c["campaign_id"] for c in response .json()}


def test_earnings_reflects_no_activity_as_zero(client, db, talent_headers):
    _seed_talent_user(db, age=20)
    client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)

    response  = client.get("/talents/earnings", headers=talent_headers)
    assert response .status_code == 200
    body = response .json()
    assert body["pending_cents"] == 0
    assert body["confirmed_cents"] == 0
    assert body["paid_cents"] == 0


# ---------------------------------------------------------------------
# POST /campaigns/:id/submission-files (Build Prompt 5 deliverable 11)
# ---------------------------------------------------------------------


def test_submission_file_upload_happy_path(client, db, talent_headers):
    _seed_talent_user(db, age=20)
    client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)
    campaign_id = _seed_campaign(db)
    client.post(f"/campaigns/{campaign_id}/apply", headers=talent_headers)

    response  = client.post(
        f"/campaigns/{campaign_id}/submission-files",
        files={"file": ("proof.jpg", b"fake-image-bytes", "image/jpeg")},
        headers=talent_headers,
    )
    assert response .status_code == 201
    assert response .json()["url"]


def test_submission_file_upload_rejects_unsupported_content_type(client, db, talent_headers):
    _seed_talent_user(db, age=20)
    client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)
    campaign_id = _seed_campaign(db)
    client.post(f"/campaigns/{campaign_id}/apply", headers=talent_headers)

    response  = client.post(
        f"/campaigns/{campaign_id}/submission-files",
        files={"file": ("proof.exe", b"fake-bytes", "application/octet-stream")},
        headers=talent_headers,
    )
    assert response .status_code == 400
    assert response .json()["error"]["code"] == "unsupported_file_type"


def test_submission_file_upload_requires_existing_invitation(client, db, talent_headers):
    _seed_talent_user(db, age=20)
    client.put("/talents/me", json=_BASE_PROFILE_BODY, headers=talent_headers)
    campaign_id = _seed_campaign(db)
    # Never applied -- no campaign_talents row exists for this talent/campaign.

    response  = client.post(
        f"/campaigns/{campaign_id}/submission-files",
        files={"file": ("proof.jpg", b"fake-image-bytes", "image/jpeg")},
        headers=talent_headers,
    )
    assert response .status_code == 404
    assert response .json()["error"]["code"] == "campaign_invitation_not_found"
