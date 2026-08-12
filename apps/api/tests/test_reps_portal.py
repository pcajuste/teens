from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

REP_USER_ID = "00000000-0000-0000-0000-000000000001"

_BASE_PROFILE_BODY = {
    "display_name": "Test Rep",
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


def _seed_rep_user(
    db,
    *,
    age: int = 17,
    parent_email: str | None = None,
    parent_verified: bool = False,
) -> None:
    dob = date(date.today().year - age, 6, 1)
    db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", REP_USER_ID, "rep@example.com")
    verified_at = datetime.now(timezone.utc) if parent_verified else None
    db.execute(
        """
        INSERT INTO public.users (id, email, role, account_status, date_of_birth, parent_email, parent_verified_at)
        VALUES ($1, 'rep@example.com', 'rep', 'active', $2, $3, $4)
        """,
        REP_USER_ID,
        dob,
        parent_email,
        verified_at,
    )


def _seed_campaign(db, *, target_categories=None, target_cities=None, payout_per_rep_cents=5000, status="active") -> str:
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
             rep_pool_cents, payout_per_rep_cents, start_date, end_date)
        VALUES ($1, $2, 'Test Campaign', $3, 'Widget', 'Awareness', 'Widgets are great',
                'One TikTok post', $4, $5, 100000, 35000, 65000, $6, CURRENT_DATE, CURRENT_DATE + 30)
        """,
        campaign_id,
        brand_id,
        status,
        target_categories or ["gaming"],
        target_cities or [],
        payout_per_rep_cents,
    )
    return campaign_id


@pytest.fixture()
def rep_headers(auth_headers_factory):
    return auth_headers_factory("rep")


# ---------------------------------------------------------------------
# rep_profiles / parent_records creation-on-onboarding (deliverable 1)
# ---------------------------------------------------------------------


def test_put_me_creates_profile(client, db, rep_headers):
    _seed_rep_user(db, age=20)
    response = client.put("/reps/me", json=_BASE_PROFILE_BODY, headers=rep_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Test Rep"
    assert body["categories"] == ["gaming"]
    assert body["profile_completeness_score"] > 0

    row = db.fetchrow if hasattr(db, "fetchrow") else None
    count = db.fetchval("SELECT COUNT(*) FROM public.rep_profiles WHERE user_id = $1", REP_USER_ID)
    assert count == 1


def test_put_me_under16_verified_creates_parent_record(client, db, rep_headers):
    _seed_rep_user(db, age=15, parent_email="parent@example.com", parent_verified=True)
    response = client.put("/reps/me", json=_BASE_PROFILE_BODY, headers=rep_headers)
    assert response.status_code == 200

    rep_id = db.fetchval("SELECT id FROM public.rep_profiles WHERE user_id = $1", REP_USER_ID)
    parent_row = db.fetch(
        "SELECT parent_email, campaign_approval_required, digest_enabled, portal_expires_at "
        "FROM public.parent_records WHERE rep_id = $1",
        rep_id,
    )
    assert len(parent_row) == 1
    assert parent_row[0]["parent_email"] == "parent@example.com"
    assert parent_row[0]["campaign_approval_required"] is True
    assert parent_row[0]["digest_enabled"] is True
    # portal_expires_at should be ~ the rep's 18th birthday, i.e. ~3 years out
    expires = parent_row[0]["portal_expires_at"]
    assert expires.year - date.today().year in (2, 3)


def test_put_me_16_17_no_parent_record(client, db, rep_headers):
    _seed_rep_user(db, age=16)
    response = client.put("/reps/me", json=_BASE_PROFILE_BODY, headers=rep_headers)
    assert response.status_code == 200

    rep_id = db.fetchval("SELECT id FROM public.rep_profiles WHERE user_id = $1", REP_USER_ID)
    count = db.fetchval("SELECT COUNT(*) FROM public.parent_records WHERE rep_id = $1", rep_id)
    assert count == 0


def test_put_me_18plus_no_parent_record(client, db, rep_headers):
    _seed_rep_user(db, age=20)
    client.put("/reps/me", json=_BASE_PROFILE_BODY, headers=rep_headers)

    rep_id = db.fetchval("SELECT id FROM public.rep_profiles WHERE user_id = $1", REP_USER_ID)
    count = db.fetchval("SELECT COUNT(*) FROM public.parent_records WHERE rep_id = $1", rep_id)
    assert count == 0


def test_put_me_rejects_invalid_category(client, db, rep_headers):
    _seed_rep_user(db, age=20)
    body = dict(_BASE_PROFILE_BODY, categories=["alcohol_adjacent"])
    response = client.put("/reps/me", json=body, headers=rep_headers)
    assert response.status_code == 422


def test_put_me_updates_existing_profile(client, db, rep_headers):
    _seed_rep_user(db, age=20)
    client.put("/reps/me", json=_BASE_PROFILE_BODY, headers=rep_headers)
    updated_body = dict(_BASE_PROFILE_BODY, bio="Updated bio", tiktok_handle="test_tok")
    response = client.put("/reps/me", json=updated_body, headers=rep_headers)
    assert response.status_code == 200
    assert response.json()["bio"] == "Updated bio"

    count = db.fetchval("SELECT COUNT(*) FROM public.rep_profiles WHERE user_id = $1", REP_USER_ID)
    assert count == 1


# ---------------------------------------------------------------------
# accept/decline/submit/withdraw state machine (deliverables 7-9)
# ---------------------------------------------------------------------


def test_apply_accept_submit_happy_path(client, db, rep_headers):
    _seed_rep_user(db, age=20)
    client.put("/reps/me", json=_BASE_PROFILE_BODY, headers=rep_headers)
    campaign_id = _seed_campaign(db)

    apply_resp = client.post(f"/campaigns/{campaign_id}/apply", headers=rep_headers)
    assert apply_resp.status_code == 201
    assert apply_resp.json()["status"] == "invited"

    accept_resp = client.post(
        f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": True}, headers=rep_headers
    )
    assert accept_resp.status_code == 200
    assert accept_resp.json()["status"] == "accepted"
    assert accept_resp.json()["ftc_disclosure_accepted"] is True

    submit_resp = client.post(
        f"/campaigns/{campaign_id}/submit",
        json={"submission_text": "Posted!", "submission_file_urls": []},
        headers=rep_headers,
    )
    assert submit_resp.status_code == 200
    assert submit_resp.json()["status"] == "submitted"


def test_accept_twice_returns_409(client, db, rep_headers):
    _seed_rep_user(db, age=20)
    client.put("/reps/me", json=_BASE_PROFILE_BODY, headers=rep_headers)
    campaign_id = _seed_campaign(db)
    client.post(f"/campaigns/{campaign_id}/apply", headers=rep_headers)
    client.post(f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": True}, headers=rep_headers)

    second = client.post(f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": True}, headers=rep_headers)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "illegal_transition"


def test_decline_then_decline_again_returns_409(client, db, rep_headers):
    _seed_rep_user(db, age=20)
    client.put("/reps/me", json=_BASE_PROFILE_BODY, headers=rep_headers)
    campaign_id = _seed_campaign(db)
    client.post(f"/campaigns/{campaign_id}/apply", headers=rep_headers)

    first = client.post(f"/campaigns/{campaign_id}/decline", headers=rep_headers)
    assert first.status_code == 200
    assert first.json()["status"] == "declined"

    second = client.post(f"/campaigns/{campaign_id}/decline", headers=rep_headers)
    assert second.status_code == 409


def test_submit_without_ftc_disclosure_returns_403(client, db, rep_headers):
    _seed_rep_user(db, age=20)
    client.put("/reps/me", json=_BASE_PROFILE_BODY, headers=rep_headers)
    campaign_id = _seed_campaign(db)
    client.post(f"/campaigns/{campaign_id}/apply", headers=rep_headers)
    client.post(f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": False}, headers=rep_headers)

    submit_resp = client.post(
        f"/campaigns/{campaign_id}/submit",
        json={"submission_text": "Posted!", "submission_file_urls": []},
        headers=rep_headers,
    )
    assert submit_resp.status_code == 403
    assert submit_resp.json()["error"]["code"] == "ftc_disclosure_required"


def test_submit_before_accept_returns_403_ftc_gate(client, db, rep_headers):
    # A fresh 'invited' row also has ftc_disclosure_accepted=False, so
    # the FTC gate fires before the state-machine check -- both are
    # legitimate 4xx outcomes here, but the FTC gate takes precedence
    # since it's the compliance-critical one.
    _seed_rep_user(db, age=20)
    client.put("/reps/me", json=_BASE_PROFILE_BODY, headers=rep_headers)
    campaign_id = _seed_campaign(db)
    client.post(f"/campaigns/{campaign_id}/apply", headers=rep_headers)

    submit_resp = client.post(
        f"/campaigns/{campaign_id}/submit",
        json={"submission_text": "Posted!", "submission_file_urls": []},
        headers=rep_headers,
    )
    assert submit_resp.status_code == 403
    assert submit_resp.json()["error"]["code"] == "ftc_disclosure_required"


def test_submit_twice_returns_409_illegal_transition(client, db, rep_headers):
    _seed_rep_user(db, age=20)
    client.put("/reps/me", json=_BASE_PROFILE_BODY, headers=rep_headers)
    campaign_id = _seed_campaign(db)
    client.post(f"/campaigns/{campaign_id}/apply", headers=rep_headers)
    client.post(f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": True}, headers=rep_headers)
    first = client.post(
        f"/campaigns/{campaign_id}/submit",
        json={"submission_text": "Posted!", "submission_file_urls": []},
        headers=rep_headers,
    )
    assert first.status_code == 200

    second = client.post(
        f"/campaigns/{campaign_id}/submit",
        json={"submission_text": "Posted again", "submission_file_urls": []},
        headers=rep_headers,
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "illegal_transition"


def test_withdraw_after_submit_preserves_payout_fields(client, db, rep_headers):
    _seed_rep_user(db, age=20)
    client.put("/reps/me", json=_BASE_PROFILE_BODY, headers=rep_headers)
    campaign_id = _seed_campaign(db)
    client.post(f"/campaigns/{campaign_id}/apply", headers=rep_headers)
    client.post(f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": True}, headers=rep_headers)
    client.post(
        f"/campaigns/{campaign_id}/submit",
        json={"submission_text": "Posted!", "submission_file_urls": []},
        headers=rep_headers,
    )

    rep_id = db.fetchval("SELECT id FROM public.rep_profiles WHERE user_id = $1", REP_USER_ID)
    # Simulate the brand having already confirmed + set payout amount
    # before the rep withdraws -- payout eligibility must not be erased.
    db.execute(
        "UPDATE public.campaign_reps SET payout_cents = 5000, payout_status = 'pending' "
        "WHERE rep_id = $1 AND campaign_id = $2",
        rep_id,
        campaign_id,
    )

    withdraw_resp = client.post(f"/campaigns/{campaign_id}/withdraw", headers=rep_headers)
    assert withdraw_resp.status_code == 200
    assert withdraw_resp.json()["status"] == "declined"
    assert withdraw_resp.json()["payout_cents"] == 5000
    assert withdraw_resp.json()["payout_status"] == "pending"


def test_withdraw_already_declined_returns_409(client, db, rep_headers):
    _seed_rep_user(db, age=20)
    client.put("/reps/me", json=_BASE_PROFILE_BODY, headers=rep_headers)
    campaign_id = _seed_campaign(db)
    client.post(f"/campaigns/{campaign_id}/apply", headers=rep_headers)
    client.post(f"/campaigns/{campaign_id}/decline", headers=rep_headers)

    withdraw_resp = client.post(f"/campaigns/{campaign_id}/withdraw", headers=rep_headers)
    assert withdraw_resp.status_code == 409


# ---------------------------------------------------------------------
# parent-approval gate (deliverable 7 / acceptance criterion)
# ---------------------------------------------------------------------


def test_accept_blocked_awaiting_parent_approval(client, db, rep_headers):
    _seed_rep_user(db, age=15, parent_email="parent@example.com", parent_verified=True)
    client.put("/reps/me", json=_BASE_PROFILE_BODY, headers=rep_headers)
    campaign_id = _seed_campaign(db)

    apply_resp = client.post(f"/campaigns/{campaign_id}/apply", headers=rep_headers)
    assert apply_resp.status_code == 201
    assert apply_resp.json()["parent_approval_status"] == "pending"

    accept_resp = client.post(
        f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": True}, headers=rep_headers
    )
    assert accept_resp.status_code == 403
    assert accept_resp.json()["error"]["code"] == "awaiting_parent_approval"


def test_apply_requiring_parent_approval_notifies_the_parent(client, db, rep_headers, fake_resend_client):
    _seed_rep_user(db, age=15, parent_email="parent@example.com", parent_verified=True)
    client.put("/reps/me", json=_BASE_PROFILE_BODY, headers=rep_headers)
    campaign_id = _seed_campaign(db)

    response = client.post(f"/campaigns/{campaign_id}/apply", headers=rep_headers)
    assert response.status_code == 201
    assert response.json()["parent_approval_status"] == "pending"

    # Regression coverage: send_campaign_approval_request existed and
    # was documented as being called on apply, but nothing actually
    # called it until this was noticed while building Prompt 8.
    assert len(fake_resend_client.sent) == 1
    assert fake_resend_client.sent[0].to == "parent@example.com"


def test_apply_not_requiring_parent_approval_sends_no_email(client, db, rep_headers, fake_resend_client):
    _seed_rep_user(db, age=20)
    client.put("/reps/me", json=_BASE_PROFILE_BODY, headers=rep_headers)
    campaign_id = _seed_campaign(db)

    response = client.post(f"/campaigns/{campaign_id}/apply", headers=rep_headers)
    assert response.status_code == 201
    assert response.json()["parent_approval_status"] == "not_required"
    assert fake_resend_client.sent == []


def test_accept_allowed_once_parent_approves(client, db, rep_headers):
    _seed_rep_user(db, age=15, parent_email="parent@example.com", parent_verified=True)
    client.put("/reps/me", json=_BASE_PROFILE_BODY, headers=rep_headers)
    campaign_id = _seed_campaign(db)
    client.post(f"/campaigns/{campaign_id}/apply", headers=rep_headers)

    rep_id = db.fetchval("SELECT id FROM public.rep_profiles WHERE user_id = $1", REP_USER_ID)
    db.execute(
        "UPDATE public.campaign_reps SET parent_approval_status = 'approved' WHERE rep_id = $1 AND campaign_id = $2",
        rep_id,
        campaign_id,
    )

    accept_resp = client.post(
        f"/campaigns/{campaign_id}/accept", json={"ftc_disclosure_accepted": True}, headers=rep_headers
    )
    assert accept_resp.status_code == 200
    assert accept_resp.json()["status"] == "accepted"


# ---------------------------------------------------------------------
# values-filter exclusion in GET /reps/campaigns/available (deliverable 3)
# ---------------------------------------------------------------------


def test_available_campaigns_excludes_parent_blocked_category(client, db, rep_headers):
    _seed_rep_user(db, age=15, parent_email="parent@example.com", parent_verified=True)
    body = dict(_BASE_PROFILE_BODY, categories=["gaming", "music"])
    client.put("/reps/me", json=body, headers=rep_headers)

    rep_id = db.fetchval("SELECT id FROM public.rep_profiles WHERE user_id = $1", REP_USER_ID)
    db.execute(
        "UPDATE public.parent_records SET values_filters = $2::jsonb WHERE rep_id = $1",
        rep_id,
        '["gaming"]',
    )

    blocked_campaign = _seed_campaign(db, target_categories=["gaming"])
    allowed_campaign = _seed_campaign(db, target_categories=["music"])

    response = client.get("/reps/campaigns/available", headers=rep_headers)
    assert response.status_code == 200
    ids = {c["id"] for c in response.json()}
    assert blocked_campaign not in ids
    assert allowed_campaign in ids


def test_available_campaigns_excludes_already_applied(client, db, rep_headers):
    _seed_rep_user(db, age=20)
    client.put("/reps/me", json=_BASE_PROFILE_BODY, headers=rep_headers)
    campaign_id = _seed_campaign(db, target_categories=["gaming"])

    before = client.get("/reps/campaigns/available", headers=rep_headers)
    assert campaign_id in {c["id"] for c in before.json()}

    client.post(f"/campaigns/{campaign_id}/apply", headers=rep_headers)

    after = client.get("/reps/campaigns/available", headers=rep_headers)
    assert campaign_id not in {c["id"] for c in after.json()}


# ---------------------------------------------------------------------
# 48h auto-decline job (deliverable 7 / acceptance criterion -- tested
# directly against the job function, not by waiting on a real clock)
# ---------------------------------------------------------------------


def test_auto_decline_job_expires_lapsed_invitations(client, db, settings, rep_headers):
    _seed_rep_user(db, age=15, parent_email="parent@example.com", parent_verified=True)
    client.put("/reps/me", json=_BASE_PROFILE_BODY, headers=rep_headers)
    campaign_id = _seed_campaign(db)
    client.post(f"/campaigns/{campaign_id}/apply", headers=rep_headers)

    rep_id = db.fetchval("SELECT id FROM public.rep_profiles WHERE user_id = $1", REP_USER_ID)
    # Backdate the deadline so it's already lapsed -- no real clock wait.
    db.execute(
        "UPDATE public.campaign_reps SET parent_approval_deadline = now() - interval '1 hour' "
        "WHERE rep_id = $1 AND campaign_id = $2",
        rep_id,
        campaign_id,
    )

    response = client.post(
        "/internal/jobs/run/auto_decline_expired_parent_approvals",
        headers={"X-Jobs-Runner-Secret": settings.jobs_runner_secret},
    )
    assert response.status_code == 200

    row = db.fetch(
        "SELECT status, parent_approval_status FROM public.campaign_reps WHERE rep_id = $1 AND campaign_id = $2",
        rep_id,
        campaign_id,
    )[0]
    assert row["status"] == "declined"
    # parent_approval_status must move off 'pending' too, or the row
    # keeps surfacing forever in the parent's pending-approval queue
    # (list_pending_for_rep filters on parent_approval_status='pending'
    # alone, not campaign_reps.status) even though it's already terminal.
    assert row["parent_approval_status"] == "blocked"


def test_auto_decline_job_does_not_touch_unexpired_invitations(client, db, settings, rep_headers):
    _seed_rep_user(db, age=15, parent_email="parent@example.com", parent_verified=True)
    client.put("/reps/me", json=_BASE_PROFILE_BODY, headers=rep_headers)
    campaign_id = _seed_campaign(db)
    client.post(f"/campaigns/{campaign_id}/apply", headers=rep_headers)

    rep_id = db.fetchval("SELECT id FROM public.rep_profiles WHERE user_id = $1", REP_USER_ID)

    client.post(
        "/internal/jobs/run/auto_decline_expired_parent_approvals",
        headers={"X-Jobs-Runner-Secret": settings.jobs_runner_secret},
    )

    status_after = db.fetchval(
        "SELECT status FROM public.campaign_reps WHERE rep_id = $1 AND campaign_id = $2", rep_id, campaign_id
    )
    assert status_after == "invited"
