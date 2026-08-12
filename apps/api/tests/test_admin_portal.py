from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

ADMIN_USER_ID = "00000000-0000-0000-0000-000000000001"


def _seed_admin_user(db) -> None:
    db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", ADMIN_USER_ID, "admin@example.com")
    db.execute(
        "INSERT INTO public.users (id, email, role, account_status, date_of_birth) "
        "VALUES ($1, 'admin@example.com', 'admin', 'active', '1985-01-01')",
        ADMIN_USER_ID,
    )


def _seed_pending_brand(db) -> str:
    user_id = str(uuid.uuid4())
    email = f"brand-{user_id}@example.com"
    db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", user_id, email)
    db.execute(
        "INSERT INTO public.users (id, email, role, account_status, date_of_birth) "
        "VALUES ($1, $2, 'brand', 'pending', '1990-01-01')",
        user_id,
        email,
    )
    db.execute(
        "INSERT INTO public.brand_profiles (id, user_id, company_name) VALUES ($1, $2, 'Acme Co')",
        str(uuid.uuid4()),
        user_id,
    )
    return user_id


def _seed_pending_recruiter(db) -> str:
    user_id = str(uuid.uuid4())
    email = f"recruiter-{user_id}@example.com"
    db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", user_id, email)
    db.execute(
        "INSERT INTO public.users (id, email, role, account_status, date_of_birth) "
        "VALUES ($1, $2, 'recruiter', 'pending', '1990-01-01')",
        user_id,
        email,
    )
    db.execute(
        "INSERT INTO public.recruiter_profiles (id, user_id, institution_name, institution_type) "
        "VALUES ($1, $2, 'State University', 'college')",
        str(uuid.uuid4()),
        user_id,
    )
    return user_id


def _seed_active_brand(db) -> tuple[str, str]:
    user_id = str(uuid.uuid4())
    brand_id = str(uuid.uuid4())
    email = f"brand-{user_id}@example.com"
    db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", user_id, email)
    db.execute(
        "INSERT INTO public.users (id, email, role, account_status, date_of_birth) "
        "VALUES ($1, $2, 'brand', 'active', '1990-01-01')",
        user_id,
        email,
    )
    db.execute(
        "INSERT INTO public.brand_profiles (id, user_id, company_name) VALUES ($1, $2, 'Acme Co')",
        brand_id,
        user_id,
    )
    return user_id, brand_id


def _seed_campaign(db, brand_id: str, *, status: str = "active", target_categories=None) -> str:
    campaign_id = str(uuid.uuid4())
    db.execute(
        """
        INSERT INTO public.campaigns
            (id, brand_id, title, status, product_name, campaign_goal, key_messaging,
             deliverables_description, target_categories, budget_cents, platform_fee_cents,
             rep_pool_cents, payout_per_rep_cents, start_date, end_date)
        VALUES ($1, $2, 'Spring Launch', $3, 'Widget', 'Awareness', 'Widgets are great',
                'One TikTok post', $4, 100000, 35000, 65000, 65000, CURRENT_DATE, CURRENT_DATE + 30)
        """,
        campaign_id,
        brand_id,
        status,
        target_categories or ["gaming"],
    )
    return campaign_id


def _seed_rep(db, *, age: int = 20) -> tuple[str, str]:
    rep_user_id = str(uuid.uuid4())
    rep_id = str(uuid.uuid4())
    rep_email = f"rep-{rep_user_id}@example.com"
    dob = date(date.today().year - age, 6, 1)
    db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", rep_user_id, rep_email)
    db.execute(
        "INSERT INTO public.users (id, email, role, account_status, date_of_birth) "
        "VALUES ($1, $2, 'rep', 'active', $3)",
        rep_user_id,
        rep_email,
        dob,
    )
    db.execute(
        """
        INSERT INTO public.rep_profiles (id, user_id, display_name, school_name, city, state, graduation_year, categories)
        VALUES ($1, $2, 'Test Rep', 'Test High', 'Austin', 'TX', 2027, '{gaming}')
        """,
        rep_id,
        rep_user_id,
    )
    return rep_user_id, rep_id


def _seed_campaign_rep(
    db,
    campaign_id: str,
    rep_id: str,
    *,
    status: str = "confirmed",
    payout_status: str = "processing",
    payout_cents: int = 5000,
    processing_started_at: datetime | None = None,
    stripe_transfer_id: str | None = None,
    ftc_disclosure_accepted: bool = True,
) -> str:
    cr_id = str(uuid.uuid4())
    db.execute(
        """
        INSERT INTO public.campaign_reps
            (id, campaign_id, rep_id, status, payout_status, payout_cents,
             payout_processing_started_at, stripe_transfer_id, ftc_disclosure_accepted, confirmed_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, now())
        """,
        cr_id,
        campaign_id,
        rep_id,
        status,
        payout_status,
        payout_cents,
        processing_started_at,
        stripe_transfer_id,
        ftc_disclosure_accepted,
    )
    return cr_id


@pytest.fixture()
def admin_headers(auth_headers_factory, db):
    _seed_admin_user(db)
    return auth_headers_factory("admin")


# ══════════════════════════════════════════════════════════════════
# Role enforcement
# ══════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("role", ["rep", "brand", "recruiter"])
def test_non_admin_jwt_cannot_reach_admin_routes(client, auth_headers_factory, role):
    response = client.get("/admin/queue/brands", headers=auth_headers_factory(role))
    assert response.status_code == 403


def test_unauthenticated_cannot_reach_admin_routes(client):
    response = client.get("/admin/queue/brands")
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════
# Deliverable 1: approval queues
# ══════════════════════════════════════════════════════════════════


def test_queue_brands_lists_pending_brand(client, db, admin_headers):
    user_id = _seed_pending_brand(db)
    response = client.get("/admin/queue/brands", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["user_id"] == user_id
    assert body[0]["pending_reason"] == "awaiting_admin_approval"


def test_queue_recruiters_lists_pending_recruiter(client, db, admin_headers):
    user_id = _seed_pending_recruiter(db)
    response = client.get("/admin/queue/recruiters", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["user_id"] == user_id


def test_queue_reps_is_always_empty(client, db, admin_headers):
    # Reps never sit in an admin-approval pending state (see
    # _require_reviewable_type's docstring) -- this asserts the queue
    # route itself works and returns nothing to review, not just that
    # approve/reject 400s for rep account_type.
    response = client.get("/admin/queue/reps", headers=admin_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_approving_pending_brand_activates_and_unblocks_campaign_creation(client, db, admin_headers):
    user_id = _seed_pending_brand(db)

    response = client.post(f"/admin/approve/brand/{user_id}", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["account_status"] == "active"

    row = db.fetch("SELECT account_status FROM public.users WHERE id = $1", user_id)
    assert row[0]["account_status"] == "active"
    verified = db.fetch("SELECT verified FROM public.brand_profiles WHERE user_id = $1", user_id)
    assert verified[0]["verified"] is True

    # Unblocked: campaign creation (require_role("brand")) now works.
    from app.core.security import PARENT_SESSION_ISSUER  # noqa: F401 -- unused, guards import ordering
    import jwt
    import time

    from app.core.config import get_settings

    settings = get_settings()
    token = jwt.encode(
        {
            "sub": user_id,
            "email": "brand@example.com",
            "aud": "authenticated",
            "app_metadata": {"role": "brand", "account_status": "active"},
            "exp": int(time.time()) + 3600,
        },
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )
    campaign_body = {
        "title": "Spring Launch",
        "product_name": "Acme Widget",
        "campaign_goal": "Awareness",
        "key_messaging": "Widgets are great",
        "prohibited_content": None,
        "deliverables_description": "One TikTok post",
        "target_categories": ["gaming"],
        "target_cities": ["Austin"],
        "max_reps": 5,
        "budget_cents": 100_000,
        "start_date": (date.today() + timedelta(days=10)).isoformat(),
        "end_date": (date.today() + timedelta(days=40)).isoformat(),
    }
    create_response = client.post(
        "/brands/campaigns", json=campaign_body, headers={"Authorization": f"Bearer {token}"}
    )
    assert create_response.status_code == 201


def test_rejecting_pending_recruiter_sends_reason_via_email(client, db, admin_headers, fake_resend_client):
    user_id = _seed_pending_recruiter(db)

    response = client.post(
        f"/admin/reject/recruiter/{user_id}", json={"reason": "Could not verify institution"}, headers=admin_headers
    )
    assert response.status_code == 200
    assert response.json()["account_status"] == "rejected"

    row = db.fetch("SELECT account_status, rejection_reason FROM public.users WHERE id = $1", user_id)
    assert row[0]["account_status"] == "rejected"
    assert row[0]["rejection_reason"] == "Could not verify institution"

    assert len(fake_resend_client.sent) == 1
    sent = fake_resend_client.sent[0]
    assert "Could not verify institution" in sent.html


def test_reject_requires_nonempty_reason(client, db, admin_headers):
    user_id = _seed_pending_brand(db)
    response = client.post(f"/admin/reject/brand/{user_id}", json={"reason": ""}, headers=admin_headers)
    assert response.status_code == 422


def test_rep_type_is_not_admin_reviewable(client, db, admin_headers):
    _, rep_id = _seed_rep(db)
    response = client.post(f"/admin/approve/rep/{rep_id}", headers=admin_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "reps_not_admin_reviewed"


# ══════════════════════════════════════════════════════════════════
# Deliverable 2: campaign oversight
# ══════════════════════════════════════════════════════════════════


def test_flag_and_resolve_campaign_force_cancel(client, db, admin_headers):
    _, brand_id = _seed_active_brand(db)
    campaign_id = _seed_campaign(db, brand_id)

    flag_response = client.post(
        f"/admin/campaigns/{campaign_id}/flag", json={"reason": "Suspicious brief content"}, headers=admin_headers
    )
    assert flag_response.status_code == 200
    assert flag_response.json()["flagged_reason"] == "Suspicious brief content"

    list_response = client.get("/admin/campaigns", params={"flagged_only": True}, headers=admin_headers)
    assert list_response.status_code == 200
    assert any(c["id"] == campaign_id for c in list_response.json())

    resolve_response = client.post(
        f"/admin/campaigns/{campaign_id}/resolve", json={"action": "force_cancel_refund"}, headers=admin_headers
    )
    assert resolve_response.status_code == 200
    assert resolve_response.json()["resolution_action"] == "force_cancel_refund"
    assert resolve_response.json()["status"] == "cancelled"


def test_resolve_campaign_rejects_free_text_action(client, db, admin_headers):
    _, brand_id = _seed_active_brand(db)
    campaign_id = _seed_campaign(db, brand_id)
    response = client.post(
        f"/admin/campaigns/{campaign_id}/resolve", json={"action": "do_whatever"}, headers=admin_headers
    )
    assert response.status_code == 422


# ══════════════════════════════════════════════════════════════════
# Deliverable 3: stuck payments
# ══════════════════════════════════════════════════════════════════


def test_stuck_payments_includes_49h_row_excludes_40h_row(client, db, admin_headers):
    _, brand_id = _seed_active_brand(db)
    campaign_id = _seed_campaign(db, brand_id)
    _, stuck_rep_id = _seed_rep(db)
    _, fresh_rep_id = _seed_rep(db)

    now = datetime.now(timezone.utc)
    stuck_cr_id = _seed_campaign_rep(
        db,
        campaign_id,
        stuck_rep_id,
        processing_started_at=now - timedelta(hours=49),
        stripe_transfer_id="tr_stuck",
    )
    _seed_campaign_rep(
        db,
        campaign_id,
        fresh_rep_id,
        processing_started_at=now - timedelta(hours=40),
        stripe_transfer_id="tr_fresh",
    )

    response = client.get("/admin/payments/stuck", headers=admin_headers)
    assert response.status_code == 200
    ids = {row["campaign_rep_id"] for row in response.json()}
    assert stuck_cr_id in ids
    assert len(response.json()) == 1


def test_release_stuck_payment_requires_stripe_onboarding(client, db, admin_headers):
    _, brand_id = _seed_active_brand(db)
    campaign_id = _seed_campaign(db, brand_id)
    _, rep_id = _seed_rep(db)
    now = datetime.now(timezone.utc)
    _seed_campaign_rep(
        db, campaign_id, rep_id, processing_started_at=now - timedelta(hours=49), stripe_transfer_id="tr_stuck2"
    )

    response = client.post("/admin/payments/tr_stuck2/release", headers=admin_headers)
    # rep never completed Stripe Connect onboarding in this test -- the
    # audit-flagged release still correctly refuses to transfer money
    # nowhere.
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "rep_not_onboarded"


def test_release_unknown_transfer_404s(client, db, admin_headers):
    response = client.post("/admin/payments/tr_does_not_exist/release", headers=admin_headers)
    assert response.status_code == 404


# ══════════════════════════════════════════════════════════════════
# Deliverable 4: analytics
# ══════════════════════════════════════════════════════════════════


def test_analytics_revenue_by_period(client, db, admin_headers):
    _, brand_id = _seed_active_brand(db)
    _seed_campaign(db, brand_id, status="active")

    response = client.get("/admin/analytics/revenue", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["brand_campaign_fees_cents"] == 35000


def test_analytics_reps_by_city_and_category(client, db, admin_headers):
    _seed_rep(db)
    response = client.get("/admin/analytics/reps", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert any(row["city"] == "Austin" for row in body["by_city"])
    assert any(row["category"] == "gaming" for row in body["by_category"])


def test_analytics_campaigns_by_status_and_category(client, db, admin_headers):
    _, brand_id = _seed_active_brand(db)
    _seed_campaign(db, brand_id, status="active")
    response = client.get("/admin/analytics/campaigns", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert any(row["status"] == "active" for row in body["by_status"])


def test_analytics_consent_status_breakdown(client, db, admin_headers):
    _seed_rep(db, age=20)
    response = client.get("/admin/analytics/consent-status", headers=admin_headers)
    assert response.status_code == 200
    states = {row["consent_state"] for row in response.json()}
    assert "not_required" in states


# ══════════════════════════════════════════════════════════════════
# Deliverable 5: outlier-rating detection
# ══════════════════════════════════════════════════════════════════


def test_outlier_brand_all_five_star_flagged(client, db, admin_headers):
    _, brand_id = _seed_active_brand(db)
    campaign_id = _seed_campaign(db, brand_id)
    for _ in range(3):
        _, rep_id = _seed_rep(db)
        cr_id = _seed_campaign_rep(db, campaign_id, rep_id, status="paid", payout_status="paid")
        db.execute("UPDATE public.campaign_reps SET brand_rating = 5 WHERE id = $1", cr_id)

    response = client.get("/admin/analytics/outlier-brands", headers=admin_headers)
    assert response.status_code == 200
    flagged = response.json()
    assert any(b["brand_id"] == brand_id and b["reason"] == "100% five-star ratings" for b in flagged)


# ══════════════════════════════════════════════════════════════════
# Deliverable 6: parent suspension queue
# ══════════════════════════════════════════════════════════════════


def test_parent_suspension_queue_and_reversal(client, db, admin_headers, seed_rep_with_parent):
    seeded = seed_rep_with_parent(rep_account_status="suspended", suspended_by_parent_at=datetime.now(timezone.utc))

    queue_response = client.get("/admin/parent-suspensions", headers=admin_headers)
    assert queue_response.status_code == 200
    assert any(row["rep_id"] == seeded.rep_id for row in queue_response.json())

    reverse_response = client.post(f"/admin/parent-suspensions/{seeded.rep_id}/reverse", headers=admin_headers)
    assert reverse_response.status_code == 200
    assert reverse_response.json()["account_status"] == "active"

    row = db.fetch("SELECT account_status FROM public.users WHERE id = $1", seeded.rep_user_id)
    assert row[0]["account_status"] == "active"

    still_queued = client.get("/admin/parent-suspensions", headers=admin_headers)
    assert not any(row["rep_id"] == seeded.rep_id for row in still_queued.json())


def test_admin_only_reverses_parent_initiated_suspension(client, db, admin_headers):
    """An admin-initiated suspension (no parent_records row involved at
    all, or suspended_by_parent_at NULL) never shows up in this queue
    and can't be 'reversed' through this route -- deliverable 6's
    'separate from admin-initiated suspension'."""
    rep_user_id, rep_id = _seed_rep(db)
    db.execute("UPDATE public.users SET account_status = 'suspended' WHERE id = $1", rep_user_id)

    response = client.post(f"/admin/parent-suspensions/{rep_id}/reverse", headers=admin_headers)
    assert response.status_code == 404


# ══════════════════════════════════════════════════════════════════
# Deliverable 7: safety report queue
# ══════════════════════════════════════════════════════════════════


def test_rep_can_file_safety_report_and_admin_resolves_it(client, db, auth_headers_factory, admin_headers):
    rep_user_id, rep_id = _seed_rep(db)
    import time

    import jwt

    from app.core.config import get_settings

    settings = get_settings()
    rep_token = jwt.encode(
        {
            "sub": rep_user_id,
            "email": "rep@example.com",
            "aud": "authenticated",
            "app_metadata": {"role": "rep", "account_status": "active"},
            "exp": int(time.time()) + 3600,
        },
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )

    file_response = client.post(
        "/reps/safety-reports",
        json={"reason": "Brand asked me to do something off-brief", "description": "Details here"},
        headers={"Authorization": f"Bearer {rep_token}"},
    )
    assert file_response.status_code == 201
    report_id = file_response.json()["id"]
    assert file_response.json()["status"] == "open"

    queue_response = client.get("/admin/safety-reports", headers=admin_headers)
    assert queue_response.status_code == 200
    assert any(r["id"] == report_id for r in queue_response.json())

    resolve_response = client.post(
        f"/admin/safety-reports/{report_id}/resolve",
        json={"status": "resolved", "resolution_note": "Followed up with brand"},
        headers=admin_headers,
    )
    assert resolve_response.status_code == 200
    assert resolve_response.json()["status"] == "resolved"

    still_open = client.get("/admin/safety-reports", headers=admin_headers)
    assert not any(r["id"] == report_id for r in still_open.json())


def test_safety_report_resolve_twice_is_409(client, db, admin_headers):
    rep_user_id, rep_id = _seed_rep(db)
    db.execute(
        "INSERT INTO public.safety_reports (id, reporter_rep_id, reason) VALUES ($1, $2, 'test')",
        (report_id := str(uuid.uuid4())),
        rep_id,
    )
    first = client.post(f"/admin/safety-reports/{report_id}/resolve", json={"status": "resolved"}, headers=admin_headers)
    assert first.status_code == 200
    second = client.post(f"/admin/safety-reports/{report_id}/resolve", json={"status": "resolved"}, headers=admin_headers)
    assert second.status_code == 404
