from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone

import pytest


def _extract_magic_link_token(html: str) -> str:
    match = re.search(r"/parent/verify/([^\"'<]+)", html)
    assert match, f"no magic link found in email html: {html}"
    return match.group(1)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------
# Deliverable 1: magic-link auth
# ---------------------------------------------------------------------


def test_request_link_unknown_email_does_not_reveal_existence(client, fake_resend_client):
    response  = client.post("/parent/auth/request-link", json={"parent_email": "nobody@example.com"})
    assert response .status_code == 200
    assert response .json()["status"] == "sent"
    assert fake_resend_client.sent == []


def test_request_link_known_email_sends_magic_link(client, fake_resend_client, seed_talent_with_parent):
    seeded = seed_talent_with_parent(parent_email="knownparent@example.com")

    response  = client.post("/parent/auth/request-link", json={"parent_email": seeded.parent_email})
    assert response .status_code == 200
    assert len(fake_resend_client.sent) == 1
    assert fake_resend_client.sent[0].to == seeded.parent_email


def test_request_link_rate_limited_does_not_reveal_via_status_code(client, fake_resend_client, seed_talent_with_parent):
    seeded = seed_talent_with_parent(parent_email="rl-parent@example.com")

    first = client.post("/parent/auth/request-link", json={"parent_email": seeded.parent_email})
    assert first.status_code == 200

    second = client.post("/parent/auth/request-link", json={"parent_email": seeded.parent_email})
    # Still 200 "sent" -- a 429 here would itself confirm the email is linked.
    assert second.status_code == 200
    assert len(fake_resend_client.sent) == 1


def test_verify_valid_token_issues_session(client, fake_resend_client, seed_talent_with_parent):
    seeded = seed_talent_with_parent(parent_email="verify-ok@example.com")
    client.post("/parent/auth/request-link", json={"parent_email": seeded.parent_email})
    token = _extract_magic_link_token(fake_resend_client.sent[0].html)

    response  = client.get(f"/parent/auth/verify/{token}")
    assert response .status_code == 200
    assert "session_token" in response .json()


def test_verify_token_used_twice_fails_second_time(client, fake_resend_client, seed_talent_with_parent):
    seeded = seed_talent_with_parent(parent_email="verify-reuse@example.com")
    client.post("/parent/auth/request-link", json={"parent_email": seeded.parent_email})
    token = _extract_magic_link_token(fake_resend_client.sent[0].html)

    first = client.get(f"/parent/auth/verify/{token}")
    assert first.status_code == 200
    second = client.get(f"/parent/auth/verify/{token}")
    assert second.status_code == 401
    assert second.json()["error"]["code"] == "magic_link_already_used"


def test_verify_invalid_token(client):
    response  = client.get("/parent/auth/verify/not-a-real-token")
    assert response .status_code == 401
    assert response .json()["error"]["code"] == "invalid_magic_link"


def test_verify_after_portal_expired_returns_portal_closed(client, db, seed_talent_with_parent):
    seeded = seed_talent_with_parent(age=18, portal_expires_in_days=-1)
    raw_token = "test-raw-token-for-expired-portal"
    db.execute(
        "INSERT INTO public.parent_auth_tokens (parent_record_id, token_hash, expires_at) VALUES ($1, $2, $3)",
        seeded.parent_id,
        _hash(raw_token),
        datetime.now(timezone.utc) + timedelta(minutes=10),
    )

    response  = client.get(f"/parent/auth/verify/{raw_token}")
    assert response .status_code == 403
    assert response .json()["error"]["code"] == "portal_closed"


# ---------------------------------------------------------------------
# Portal expiry enforced on every request, not just verify (deliverable 8)
# ---------------------------------------------------------------------


def test_expired_portal_session_rejected_on_every_request(client, parent_headers_factory, seed_talent_with_parent):
    seeded = seed_talent_with_parent(age=19, portal_expires_in_days=-30)
    headers = parent_headers_factory(parent_id=seeded.parent_id, talent_id=seeded.talent_id)

    response  = client.get("/parent/dashboard", headers=headers)
    assert response .status_code == 403
    assert response .json()["error"]["code"] == "portal_closed"


# ---------------------------------------------------------------------
# Deliverable 2: dashboard
# ---------------------------------------------------------------------


def test_dashboard_returns_talent_summary(client, parent_headers_factory, seed_talent_with_parent):
    seeded = seed_talent_with_parent(
        categories=["gaming", "tech"], profile_completeness_score=80, total_earnings_cents=99900, total_campaigns_completed=4
    )
    headers = parent_headers_factory(parent_id=seeded.parent_id, talent_id=seeded.talent_id)

    response  = client.get("/parent/dashboard", headers=headers)
    assert response .status_code == 200
    body = response .json()
    assert body["display_name"] == "Test Talent"
    assert body["categories"] == ["gaming", "tech"]
    assert body["profile_completeness_score"] == 80
    assert body["total_earnings_cents"] == 99900
    assert body["total_campaigns_completed"] == 4


def test_dashboard_without_session_returns_401(client):
    response  = client.get("/parent/dashboard")
    assert response .status_code == 401


def test_dashboard_includes_scholarship_and_insight_feedback_activity(client, db, parent_headers_factory, seed_talent_with_parent):
    """#54: parent dashboard has no visibility into Scholarships or
    Insight & Feedback -- these blocks close that gap, including
    confidentiality_terms per that column's own "shown to teen + parent
    before joining" comment."""
    import uuid

    seeded = seed_talent_with_parent()
    headers = parent_headers_factory(parent_id=seeded.parent_id, talent_id=seeded.talent_id)

    brand_user_id, brand_id = str(uuid.uuid4()), str(uuid.uuid4())
    brand_email = f"brand-{brand_user_id}@example.com"
    db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", brand_user_id, brand_email)
    db.execute(
        "INSERT INTO public.users (id, email, role, account_status, date_of_birth) VALUES ($1, $2, 'brand', 'active', '1990-01-01')",
        brand_user_id,
        brand_email,
    )
    db.execute(
        "INSERT INTO public.brand_profiles (id, user_id, company_name) VALUES ($1, $2, 'Acme Co')",
        brand_id,
        brand_user_id,
    )

    scholarship_id = str(uuid.uuid4())
    db.execute(
        """
        INSERT INTO public.scholarships (id, brand_id, title, award_amount_cents, number_of_awards, application_requirements, why_text, deadline, status, moderation_status)
        VALUES ($1, $2, 'Future Coders Award', 200000, 1, 'A short essay.', 'why', CURRENT_DATE + 30, 'active', 'approved')
        """,
        scholarship_id,
        brand_id,
    )
    db.execute(
        """
        INSERT INTO public.scholarship_applications (scholarship_id, talent_id, response_text, status)
        VALUES ($1, $2, 'my response', 'awarded')
        """,
        scholarship_id,
        seeded.talent_id,
    )

    campaign_id = str(uuid.uuid4())
    db.execute(
        """
        INSERT INTO public.insight_feedback_campaigns
            (id, brand_id, title, material_url, business_question, panel_size, compensation_cents,
             confidentiality_terms, status, moderation_status)
        VALUES ($1, $2, 'New App Concept', 'https://example.com/concept', 'What do you think?', 1, 5000,
                'Keep this concept confidential until public launch.', 'active', 'approved')
        """,
        campaign_id,
        brand_id,
    )
    pseudonym_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO public.talent_pseudonyms (id, talent_id, handle) VALUES ($1, $2, 'Contributor_TEST')",
        pseudonym_id,
        seeded.talent_id,
    )
    panel_member_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO public.insight_feedback_panel_members (id, campaign_id, talent_id, pseudonym_id, responded_at) VALUES ($1, $2, $3, $4, now())",
        panel_member_id,
        campaign_id,
        seeded.talent_id,
        pseudonym_id,
    )
    db.execute(
        "INSERT INTO public.insight_feedback_responses (campaign_id, panel_member_id, ratings) VALUES ($1, $2, $3)",
        campaign_id,
        panel_member_id,
        '[{"question": "Overall rating", "score": 5}]',
    )

    response = client.get("/parent/dashboard", headers=headers)
    assert response.status_code == 200
    body = response.json()

    assert body["scholarship_activity"]["total_applied"] == 1
    assert body["scholarship_activity"]["total_awarded"] == 1
    assert body["scholarship_activity"]["total_awarded_cents"] == 200000
    assert body["scholarship_activity"]["recent_applications"][0]["scholarship_title"] == "Future Coders Award"

    assert body["insight_feedback_activity"]["total_invited"] == 1
    assert body["insight_feedback_activity"]["total_responded"] == 1
    assert body["insight_feedback_activity"]["total_earned_cents"] == 5000
    invitation = body["insight_feedback_activity"]["recent_invitations"][0]
    assert invitation["campaign_title"] == "New App Concept"
    assert invitation["confidentiality_terms"] == "Keep this concept confidential until public launch."


# ---------------------------------------------------------------------
# Deliverable 3: campaign approval queue
# ---------------------------------------------------------------------


def test_pending_campaigns_returns_full_brief(client, parent_headers_factory, seed_talent_with_parent, seed_pending_campaign):
    seeded = seed_talent_with_parent()
    seed_pending_campaign(talent_id=seeded.talent_id)
    headers = parent_headers_factory(parent_id=seeded.parent_id, talent_id=seeded.talent_id)

    response  = client.get("/parent/campaigns/pending", headers=headers)
    assert response .status_code == 200
    campaigns = response .json()
    assert len(campaigns) == 1
    brief = campaigns[0]
    assert brief["brand_name"] == "Acme Co"
    assert brief["title"] == "Test Campaign"
    assert brief["payout_per_talent_cents"] == 5000
    assert brief["deliverables_description"] == "One TikTok post"


def test_approve_campaign_is_idempotent(client, db, parent_headers_factory, seed_talent_with_parent, seed_pending_campaign):
    seeded = seed_talent_with_parent()
    campaign_id = seed_pending_campaign(talent_id=seeded.talent_id)
    headers = parent_headers_factory(parent_id=seeded.parent_id, talent_id=seeded.talent_id)

    first = client.post(f"/parent/campaigns/{campaign_id}/approve", headers=headers)
    assert first.status_code == 200
    assert first.json()["parent_approval_status"] == "approved"

    second = client.post(f"/parent/campaigns/{campaign_id}/approve", headers=headers)
    assert second.status_code == 200
    assert second.json()["parent_approval_status"] == "approved"

    rows = db.fetch("SELECT parent_approval_status FROM public.campaign_talents WHERE campaign_id = $1", campaign_id)
    assert rows[0]["parent_approval_status"] == "approved"


def test_block_campaign_auto_declines_without_exposing_reason_to_brand(
    client, db, fake_resend_client, parent_headers_factory, seed_talent_with_parent, seed_pending_campaign
):
    seeded = seed_talent_with_parent()
    campaign_id = seed_pending_campaign(talent_id=seeded.talent_id)
    headers = parent_headers_factory(parent_id=seeded.parent_id, talent_id=seeded.talent_id)

    response  = client.post(f"/parent/campaigns/{campaign_id}/block", headers=headers)
    assert response .status_code == 200
    assert response .json()["parent_approval_status"] == "blocked"

    rows = db.fetch(
        "SELECT status, parent_approval_status FROM public.campaign_talents WHERE campaign_id = $1", campaign_id
    )
    # 'declined' is exactly what a talent's own decline produces -- nothing
    # brand-visible distinguishes a parent block from a talent decline.
    assert rows[0]["status"] == "declined"
    assert rows[0]["parent_approval_status"] == "blocked"

    # The talent is told a campaign was declined on their behalf (that's
    # fine -- they know their own parent is involved). NOTE: the
    # brand-facing side of this ("neutral message to the brand") can't
    # be exercised end-to-end yet since GET /brands/campaigns/:id/talents
    # doesn't exist until Prompt 8; the 'declined' status assertion
    # above -- the same value a talent's own decline produces, with
    # nothing brand-visible distinguishing the two -- is the
    # enforceable part today.
    assert len(fake_resend_client.sent) == 1


def test_approve_unknown_campaign_returns_404(client, parent_headers_factory, seed_talent_with_parent):
    seeded = seed_talent_with_parent()
    headers = parent_headers_factory(parent_id=seeded.parent_id, talent_id=seeded.talent_id)

    response  = client.post("/parent/campaigns/00000000-0000-0000-0000-000000000099/approve", headers=headers)
    assert response .status_code == 404


# ---------------------------------------------------------------------
# Deliverable 4: values filters + approval-required toggle
# ---------------------------------------------------------------------


def test_get_settings_returns_current_state(client, parent_headers_factory, seed_talent_with_parent):
    seeded = seed_talent_with_parent(values_filters=["alcohol_adjacent"], campaign_approval_required=True, digest_enabled=False)
    headers = parent_headers_factory(parent_id=seeded.parent_id, talent_id=seeded.talent_id)

    response  = client.get("/parent/settings", headers=headers)
    assert response .status_code == 200
    body = response .json()
    assert body["values_filters"] == ["alcohol_adjacent"]
    assert body["campaign_approval_required"] is True
    assert body["digest_enabled"] is False


def test_update_values_filters_accepts_valid_categories(client, parent_headers_factory, seed_talent_with_parent):
    seeded = seed_talent_with_parent()
    headers = parent_headers_factory(parent_id=seeded.parent_id, talent_id=seeded.talent_id)

    response  = client.put(
        "/parent/settings/values-filters",
        headers=headers,
        json={"values_filters": ["political", "gambling"]},
    )
    assert response .status_code == 200
    assert sorted(response .json()["values_filters"]) == ["gambling", "political"]


def test_update_values_filters_rejects_unknown_category(client, parent_headers_factory, seed_talent_with_parent):
    seeded = seed_talent_with_parent()
    headers = parent_headers_factory(parent_id=seeded.parent_id, talent_id=seeded.talent_id)

    response  = client.put(
        "/parent/settings/values-filters",
        headers=headers,
        json={"values_filters": ["not_a_real_category"]},
    )
    assert response .status_code == 422


def test_approval_required_toggle_locked_under_16(client, parent_headers_factory, seed_talent_with_parent):
    seeded = seed_talent_with_parent(age=15)
    headers = parent_headers_factory(parent_id=seeded.parent_id, talent_id=seeded.talent_id)

    response  = client.put("/parent/settings/approval-required", headers=headers, json={"enabled": False})
    assert response .status_code == 403
    assert response .json()["error"]["code"] == "approval_required_locked_under_16"


def test_approval_required_toggle_allowed_at_16(client, parent_headers_factory, seed_talent_with_parent):
    seeded = seed_talent_with_parent(age=16)
    headers = parent_headers_factory(parent_id=seeded.parent_id, talent_id=seeded.talent_id)

    response  = client.put("/parent/settings/approval-required", headers=headers, json={"enabled": False})
    assert response .status_code == 200
    assert response .json()["campaign_approval_required"] is False


# ---------------------------------------------------------------------
# Deliverable 5: digest
# ---------------------------------------------------------------------


def test_digest_setting_toggle(client, parent_headers_factory, seed_talent_with_parent):
    seeded = seed_talent_with_parent(digest_enabled=True)
    headers = parent_headers_factory(parent_id=seeded.parent_id, talent_id=seeded.talent_id)

    response  = client.put("/parent/settings/digest", headers=headers, json={"enabled": False})
    assert response .status_code == 200
    assert response .json()["digest_enabled"] is False


def test_digest_preview_first_time_has_no_completeness_change(client, parent_headers_factory, seed_talent_with_parent):
    seeded = seed_talent_with_parent(profile_completeness_score=70, total_earnings_cents=5000)
    headers = parent_headers_factory(parent_id=seeded.parent_id, talent_id=seeded.talent_id)

    response  = client.get("/parent/digest/preview", headers=headers)
    assert response .status_code == 200
    body = response .json()
    assert body["lifetime_earnings_cents"] == 5000
    assert body["profile_completeness_change"] is None


def test_monthly_digest_job_excludes_recruiter_and_submission_content(
    client, db, fake_resend_client, seed_talent_with_parent, monkeypatch
):
    seed_talent_with_parent(digest_enabled=True)
    monkeypatch.setattr("app.jobs.runner.get_resend_client", lambda settings: fake_resend_client)

    response  = client.post(
        "/internal/jobs/run/send_monthly_parent_digests",
        headers={"X-Jobs-Runner-Secret": "test-jobs-runner-secret"},
    )
    assert response .status_code == 200
    assert len(fake_resend_client.sent) == 1

    html_lower = fake_resend_client.sent[0].html.lower()
    for forbidden_term in ("recruiter", "submission", "brand contact", "message content"):
        assert forbidden_term not in html_lower


# ---------------------------------------------------------------------
# Deliverable 6: account controls
# ---------------------------------------------------------------------


def test_suspend_account_sets_status_and_notifies_rep(client, db, fake_resend_client, parent_headers_factory, seed_talent_with_parent):
    seeded = seed_talent_with_parent()
    headers = parent_headers_factory(parent_id=seeded.parent_id, talent_id=seeded.talent_id)

    response  = client.post("/parent/account/suspend", headers=headers)
    assert response .status_code == 200
    assert response .json()["account_status"] == "suspended"

    row = db.fetch("SELECT account_status FROM public.users WHERE id = $1", seeded.talent_user_id)
    assert row[0]["account_status"] == "suspended"
    row = db.fetch("SELECT suspended_by_parent_at FROM public.parent_records WHERE parent_id = $1", seeded.parent_id)
    assert row[0]["suspended_by_parent_at"] is not None
    assert len(fake_resend_client.sent) == 1


def test_unsuspend_reverses_parent_initiated_suspension(client, db, parent_headers_factory, seed_talent_with_parent):
    seeded = seed_talent_with_parent(talent_account_status="suspended", suspended_by_parent_at=datetime.now(timezone.utc))
    headers = parent_headers_factory(parent_id=seeded.parent_id, talent_id=seeded.talent_id)

    response  = client.post("/parent/account/unsuspend", headers=headers)
    assert response .status_code == 200
    assert response .json()["account_status"] == "active"


def test_unsuspend_rejects_admin_initiated_suspension(client, parent_headers_factory, seed_talent_with_parent):
    seeded = seed_talent_with_parent(talent_account_status="suspended", suspended_by_parent_at=None)
    headers = parent_headers_factory(parent_id=seeded.parent_id, talent_id=seeded.talent_id)

    response  = client.post("/parent/account/unsuspend", headers=headers)
    assert response .status_code == 403
    assert response .json()["error"]["code"] == "admin_suspension_not_reversible_by_parent"
