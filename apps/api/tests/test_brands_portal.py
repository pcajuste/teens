from __future__ import annotations

import uuid
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.services import stripe_service

BRAND_USER_ID = "00000000-0000-0000-0000-000000000001"

_BASE_PROFILE_BODY = {
    "company_name": "Acme Co",
    "website": "https://acme.example.com",
    "ein": "12-3456789",
    "industry": "apparel",
    "target_categories": ["gaming"],
}

_BASE_CAMPAIGN_BODY = {
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


def _seed_brand_user(db) -> None:
    db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", BRAND_USER_ID, "brand@example.com")
    db.execute(
        "INSERT INTO public.users (id, email, role, account_status, date_of_birth) "
        "VALUES ($1, 'brand@example.com', 'brand', 'active', '1990-01-01')",
        BRAND_USER_ID,
    )


def _seed_rep(db, *, age: int = 20, recruiter_visible: bool = True, categories=None, city="Austin", state="TX") -> str:
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
        INSERT INTO public.rep_profiles
            (id, user_id, display_name, school_name, city, state, graduation_year, categories, recruiter_visible)
        VALUES ($1, $2, 'Test Rep', 'Test High', $3, $4, 2027, $5, $6)
        """,
        rep_id,
        rep_user_id,
        city,
        state,
        categories or ["gaming"],
        recruiter_visible,
    )
    return rep_id


@pytest.fixture()
def brand_headers(auth_headers_factory):
    return auth_headers_factory("brand")


@pytest.fixture()
def onboarded_brand(client, db, brand_headers):
    """Seeds the brand user and completes PUT /brands/me -- almost
    every test in this file needs this exact precondition, so it's a
    fixture rather than a helper every test remembers to call."""
    _seed_brand_user(db)
    response = client.put("/brands/me", json=_BASE_PROFILE_BODY, headers=brand_headers)
    assert response.status_code == 200
    return response.json()


@pytest.fixture()
def fake_stripe(monkeypatch):
    calls: list[tuple[str, dict]] = []
    counter = {"n": 0}

    class _PaymentIntent:
        @staticmethod
        def create(**kwargs):
            counter["n"] += 1
            calls.append(("PaymentIntent.create", kwargs))
            pi_id = f"pi_fake{counter['n']}"
            return SimpleNamespace(id=pi_id, client_secret=f"{pi_id}_secret")

        @staticmethod
        def retrieve(id, **kwargs):
            calls.append(("PaymentIntent.retrieve", {"id": id, **kwargs}))
            return {"latest_charge": {"receipt_url": f"https://stripe.example.com/receipts/{id}"}}

    class _Customer:
        @staticmethod
        def create(**kwargs):
            counter["n"] += 1
            calls.append(("Customer.create", kwargs))
            return SimpleNamespace(id=f"cus_fake{counter['n']}")

    class _Refund:
        @staticmethod
        def create(**kwargs):
            counter["n"] += 1
            calls.append(("Refund.create", kwargs))
            return SimpleNamespace(id=f"re_fake{counter['n']}")

    class _Transfer:
        @staticmethod
        def create(**kwargs):
            counter["n"] += 1
            calls.append(("Transfer.create", kwargs))
            return SimpleNamespace(id=f"tr_fake{counter['n']}")

    fake = SimpleNamespace(PaymentIntent=_PaymentIntent, Customer=_Customer, Refund=_Refund, Transfer=_Transfer, calls=calls)
    monkeypatch.setattr(stripe_service, "stripe", fake)
    return fake


# ---------------------------------------------------------------------
# GET/PUT /brands/me -- EIN encryption at rest (deliverable 1)
# ---------------------------------------------------------------------


def test_put_me_creates_profile_and_encrypts_ein(db, brand_headers, settings, onboarded_brand):
    assert onboarded_brand["company_name"] == "Acme Co"
    assert onboarded_brand["has_ein_on_file"] is True
    assert "ein" not in onboarded_brand  # never returned in plaintext, not even to the owning brand

    stored_ein = db.fetchval("SELECT ein FROM public.brand_profiles WHERE user_id = $1", BRAND_USER_ID)
    assert stored_ein is not None
    assert stored_ein != "12-3456789"  # ciphertext, not plaintext

    from app.core.crypto import decrypt_ein

    assert decrypt_ein(settings, stored_ein) == "12-3456789"


def test_put_me_update_without_ein_keeps_existing_ein(client, db, brand_headers, onboarded_brand):
    before = db.fetchval("SELECT ein FROM public.brand_profiles WHERE user_id = $1", BRAND_USER_ID)

    update_body = {**_BASE_PROFILE_BODY, "company_name": "Acme Co Renamed", "ein": None}
    response = client.put("/brands/me", json=update_body, headers=brand_headers)
    assert response.status_code == 200
    assert response.json()["company_name"] == "Acme Co Renamed"

    after = db.fetchval("SELECT ein FROM public.brand_profiles WHERE user_id = $1", BRAND_USER_ID)
    assert after == before


def test_get_me_requires_onboarding_first(client, brand_headers):
    response = client.get("/brands/me", headers=brand_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "brand_profile_not_found"


def test_pending_brand_can_still_submit_profile_for_review(client, db, auth_headers_factory):
    # Regression: every brand signup lands account_status='pending' (no
    # admin-approval flow exists yet), and require_role("brand") used to
    # gate GET/PUT /brands/me too -- meaning a freshly signed-up brand
    # could never submit a profile for review at all. GET/PUT /brands/me
    # must work pre-approval; other brand routes must not.
    _seed_brand_user(db)
    db.execute("UPDATE public.users SET account_status = 'pending' WHERE id = $1", BRAND_USER_ID)
    pending_headers = auth_headers_factory("brand", account_status="pending")

    put_response = client.put("/brands/me", json=_BASE_PROFILE_BODY, headers=pending_headers)
    assert put_response.status_code == 200

    get_response = client.get("/brands/me", headers=pending_headers)
    assert get_response.status_code == 200
    assert get_response.json()["company_name"] == "Acme Co"

    # Campaign creation (money-moving territory) must still require 'active'.
    campaign_response = client.post("/brands/campaigns", json=_BASE_CAMPAIGN_BODY, headers=pending_headers)
    assert campaign_response.status_code == 403
    assert campaign_response.json()["error"]["code"] == "account_not_active"


# ---------------------------------------------------------------------
# Campaign CRUD + fee split (deliverables 2-3)
# ---------------------------------------------------------------------


def test_create_campaign_computes_fee_split_server_side(client, brand_headers, settings, onboarded_brand):
    response = client.post("/brands/campaigns", json=_BASE_CAMPAIGN_BODY, headers=brand_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "draft"
    assert body["platform_fee_cents"] + body["rep_pool_cents"] == body["budget_cents"]
    expected_fee = (100_000 * settings.stripe_platform_fee_percent + 50) // 100
    assert body["platform_fee_cents"] == expected_fee
    assert body["payout_per_rep_cents"] == (100_000 - expected_fee) // 5


def test_create_campaign_ignores_any_client_submitted_fee_fields(client, brand_headers, onboarded_brand):
    tampered = {**_BASE_CAMPAIGN_BODY, "platform_fee_cents": 1, "rep_pool_cents": 99_999, "payout_per_rep_cents": 99_999}
    response = client.post("/brands/campaigns", json=tampered, headers=brand_headers)
    assert response.status_code == 201
    body = response.json()
    # Client-submitted fee fields aren't even accepted fields on the
    # request schema -- extra keys are silently ignored by pydantic,
    # and the server-computed split wins regardless.
    assert body["platform_fee_cents"] != 1
    assert body["rep_pool_cents"] != 99_999


def test_create_campaign_rejects_end_date_before_start_date(client, brand_headers, onboarded_brand):
    bad = {**_BASE_CAMPAIGN_BODY, "start_date": "2030-01-10", "end_date": "2030-01-01"}
    response = client.post("/brands/campaigns", json=bad, headers=brand_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_dates"


def test_create_campaign_rejects_max_reps_not_positive(client, brand_headers, onboarded_brand):
    bad = {**_BASE_CAMPAIGN_BODY, "max_reps": 0}
    response = client.post("/brands/campaigns", json=bad, headers=brand_headers)
    assert response.status_code == 422


def test_update_campaign_legal_only_in_draft(client, brand_headers, onboarded_brand, fake_stripe):
    created = client.post("/brands/campaigns", json=_BASE_CAMPAIGN_BODY, headers=brand_headers).json()

    ok = client.put(f"/brands/campaigns/{created['id']}", json=_BASE_CAMPAIGN_BODY, headers=brand_headers)
    assert ok.status_code == 200

    client.post(f"/brands/campaigns/{created['id']}/activate", headers=brand_headers)
    blocked = client.put(f"/brands/campaigns/{created['id']}", json=_BASE_CAMPAIGN_BODY, headers=brand_headers)
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "campaign_not_draft"


def test_brand_cannot_see_or_edit_another_brands_campaign(client, db, brand_headers, onboarded_brand):
    other_brand_id = str(uuid.uuid4())
    other_user_id = str(uuid.uuid4())
    db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", other_user_id, "other@example.com")
    db.execute(
        "INSERT INTO public.users (id, email, role, account_status, date_of_birth) "
        "VALUES ($1, 'other@example.com', 'brand', 'active', '1990-01-01')",
        other_user_id,
    )
    db.execute(
        "INSERT INTO public.brand_profiles (id, user_id, company_name) VALUES ($1, $2, 'Other Co')",
        other_brand_id,
        other_user_id,
    )
    other_campaign_id = str(uuid.uuid4())
    db.execute(
        """
        INSERT INTO public.campaigns
            (id, brand_id, title, status, product_name, campaign_goal, key_messaging,
             deliverables_description, target_categories, target_cities, budget_cents,
             platform_fee_cents, rep_pool_cents, payout_per_rep_cents, start_date, end_date)
        VALUES ($1, $2, 'Other Campaign', 'draft', 'Widget', 'Awareness', 'msg',
                'One post', '{}', '{}', 1000, 350, 650, 650, CURRENT_DATE, CURRENT_DATE + 30)
        """,
        other_campaign_id,
        other_brand_id,
    )

    response = client.get(f"/brands/campaigns/{other_campaign_id}", headers=brand_headers)
    assert response.status_code == 404


# ---------------------------------------------------------------------
# activate / retry-payment (deliverables 4-5, acceptance criteria)
# ---------------------------------------------------------------------


def test_activate_creates_payment_intent_and_transitions_to_pending_payment(client, brand_headers, onboarded_brand, fake_stripe):
    created = client.post("/brands/campaigns", json=_BASE_CAMPAIGN_BODY, headers=brand_headers).json()

    response = client.post(f"/brands/campaigns/{created['id']}/activate", headers=brand_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending_payment"
    assert body["stripe_payment_intent_client_secret"].startswith("pi_fake")

    call_names = [name for name, _ in fake_stripe.calls]
    # First activation lazily creates the brand's Stripe Customer (Build
    # Prompt 10 deliverable 2), then the PaymentIntent against it.
    assert call_names == ["Customer.create", "PaymentIntent.create"]
    intent_kwargs = fake_stripe.calls[1][1]
    assert intent_kwargs["amount"] == 100_000
    assert intent_kwargs["customer"] == "cus_fake1"


def test_activate_rejects_start_date_not_in_future(client, brand_headers, onboarded_brand, fake_stripe):
    bad = {**_BASE_CAMPAIGN_BODY, "start_date": date.today().isoformat()}
    created = client.post("/brands/campaigns", json=bad, headers=brand_headers).json()

    response = client.post(f"/brands/campaigns/{created['id']}/activate", headers=brand_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "start_date_not_future"


def test_activate_on_payment_failed_returns_use_retry_payment(client, db, brand_headers, onboarded_brand, fake_stripe):
    created = client.post("/brands/campaigns", json=_BASE_CAMPAIGN_BODY, headers=brand_headers).json()
    client.post(f"/brands/campaigns/{created['id']}/activate", headers=brand_headers)
    db.execute("UPDATE public.campaigns SET status = 'payment_failed' WHERE id = $1", created["id"])

    response = client.post(f"/brands/campaigns/{created['id']}/activate", headers=brand_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "use_retry_payment"


def test_activate_on_non_draft_non_payment_failed_returns_409(client, db, brand_headers, onboarded_brand, fake_stripe):
    created = client.post("/brands/campaigns", json=_BASE_CAMPAIGN_BODY, headers=brand_headers).json()
    db.execute("UPDATE public.campaigns SET status = 'active' WHERE id = $1", created["id"])

    response = client.post(f"/brands/campaigns/{created['id']}/activate", headers=brand_headers)
    assert response.status_code == 409


def test_retry_payment_on_non_payment_failed_returns_409(client, brand_headers, onboarded_brand, fake_stripe):
    created = client.post("/brands/campaigns", json=_BASE_CAMPAIGN_BODY, headers=brand_headers).json()  # status='draft'

    response = client.post(f"/brands/campaigns/{created['id']}/retry-payment", headers=brand_headers)
    assert response.status_code == 409


def test_retry_payment_produces_new_distinct_payment_intent(client, db, brand_headers, onboarded_brand, fake_stripe):
    created = client.post("/brands/campaigns", json=_BASE_CAMPAIGN_BODY, headers=brand_headers).json()
    client.post(f"/brands/campaigns/{created['id']}/activate", headers=brand_headers)
    failed_intent_id = db.fetchval("SELECT stripe_payment_intent_id FROM public.campaigns WHERE id = $1", created["id"])
    db.execute("UPDATE public.campaigns SET status = 'payment_failed' WHERE id = $1", created["id"])

    response = client.post(f"/brands/campaigns/{created['id']}/retry-payment", headers=brand_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "pending_payment"

    new_intent_id = db.fetchval("SELECT stripe_payment_intent_id FROM public.campaigns WHERE id = $1", created["id"])
    assert new_intent_id != failed_intent_id


# ---------------------------------------------------------------------
# pause / cancel (deliverable 6)
# ---------------------------------------------------------------------


def test_pause_only_legal_from_active(client, db, brand_headers, onboarded_brand):
    created = client.post("/brands/campaigns", json=_BASE_CAMPAIGN_BODY, headers=brand_headers).json()  # draft

    response = client.post(f"/brands/campaigns/{created['id']}/pause", headers=brand_headers)
    assert response.status_code == 409

    db.execute("UPDATE public.campaigns SET status = 'active' WHERE id = $1", created["id"])
    response = client.post(f"/brands/campaigns/{created['id']}/pause", headers=brand_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "paused"


def test_cancel_draft_reports_no_refund_pending(client, brand_headers, onboarded_brand):
    created = client.post("/brands/campaigns", json=_BASE_CAMPAIGN_BODY, headers=brand_headers).json()

    response = client.post(f"/brands/campaigns/{created['id']}/cancel", headers=brand_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "cancelled"
    assert body["refund_pending"] is False


def test_cancel_active_campaign_refunds_full_budget_when_no_reps_paid(client, db, brand_headers, onboarded_brand, fake_stripe):
    created = client.post("/brands/campaigns", json=_BASE_CAMPAIGN_BODY, headers=brand_headers).json()
    client.post(f"/brands/campaigns/{created['id']}/activate", headers=brand_headers)  # sets a real stripe_payment_intent_id
    db.execute("UPDATE public.campaigns SET status = 'active' WHERE id = $1", created["id"])
    fake_stripe.calls.clear()

    response = client.post(f"/brands/campaigns/{created['id']}/cancel", headers=brand_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "cancelled"
    assert body["refund_pending"] is True
    # No rep has been paid yet, so the entire budget is refundable --
    # see docs/campaign-cancellation-refund-policy.md.
    assert body["refund_amount_cents"] == 100_000

    name, kwargs = fake_stripe.calls[0]
    assert name == "Refund.create"
    assert kwargs["amount"] == 100_000


def test_cancel_active_campaign_only_refunds_unpaid_remainder(client, db, brand_headers, onboarded_brand, fake_stripe):
    created = client.post("/brands/campaigns", json=_BASE_CAMPAIGN_BODY, headers=brand_headers).json()
    client.post(f"/brands/campaigns/{created['id']}/activate", headers=brand_headers)
    rep_id, campaign_rep_id = _invited_campaign_rep(client, db, brand_headers, created["id"])
    db.execute("UPDATE public.campaign_reps SET status = 'submitted' WHERE id = $1", campaign_rep_id)
    client.post(f"/brands/campaigns/{created['id']}/reps/{rep_id}/confirm", headers=brand_headers)
    # Rep isn't Connect-onboarded in this test, so release_payout leaves
    # payout_status='pending' -- simulate a completed transfer directly
    # so the refund math has something committed to exclude.
    db.execute("UPDATE public.campaign_reps SET payout_status = 'paid' WHERE id = $1", campaign_rep_id)
    db.execute("UPDATE public.campaigns SET status = 'active' WHERE id = $1", created["id"])
    fake_stripe.calls.clear()

    response = client.post(f"/brands/campaigns/{created['id']}/cancel", headers=brand_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["refund_amount_cents"] == 100_000 - created["payout_per_rep_cents"]


def test_cancel_already_cancelled_returns_409(client, brand_headers, onboarded_brand):
    created = client.post("/brands/campaigns", json=_BASE_CAMPAIGN_BODY, headers=brand_headers).json()
    client.post(f"/brands/campaigns/{created['id']}/cancel", headers=brand_headers)

    response = client.post(f"/brands/campaigns/{created['id']}/cancel", headers=brand_headers)
    assert response.status_code == 409


# ---------------------------------------------------------------------
# rep browse (no PII) + invite (deliverable 7)
# ---------------------------------------------------------------------


def test_browse_returns_no_pii(client, db, brand_headers, onboarded_brand):
    _seed_rep(db, categories=["gaming"], city="Austin")
    created = client.post("/brands/campaigns", json=_BASE_CAMPAIGN_BODY, headers=brand_headers).json()

    response = client.get(f"/brands/campaigns/{created['id']}/reps/browse", headers=brand_headers)
    assert response.status_code == 200
    cards = response.json()
    assert len(cards) == 1
    card = cards[0]
    forbidden_keys = {"display_name", "school_name", "bio", "instagram_handle", "tiktok_handle", "email"}
    assert forbidden_keys.isdisjoint(card.keys())
    assert set(card.keys()) == {
        "rep_id",
        "city",
        "state",
        "graduation_year",
        "school_type",
        "categories",
        "profile_completeness_score",
        "average_rating",
        "total_campaigns_completed",
    }


def test_browse_excludes_non_recruiter_visible_reps(client, db, brand_headers, onboarded_brand):
    _seed_rep(db, categories=["gaming"], city="Austin", recruiter_visible=False)
    created = client.post("/brands/campaigns", json=_BASE_CAMPAIGN_BODY, headers=brand_headers).json()

    response = client.get(f"/brands/campaigns/{created['id']}/reps/browse", headers=brand_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_invite_creates_campaign_rep_and_notifies_parent_when_required(client, db, brand_headers, onboarded_brand, fake_resend_client):
    rep_id = _seed_rep(db, age=15, categories=["gaming"])
    parent_id = str(uuid.uuid4())
    rep_user_id = db.fetchval("SELECT user_id FROM public.rep_profiles WHERE id = $1", rep_id)
    db.execute(
        "UPDATE public.users SET parent_email = 'parent@example.com', parent_verified_at = now() WHERE id = $1",
        rep_user_id,
    )
    db.execute(
        """
        INSERT INTO public.parent_records (parent_id, rep_id, parent_email, campaign_approval_required, portal_expires_at)
        VALUES ($1, $2, 'parent@example.com', TRUE, now() + interval '10 years')
        """,
        parent_id,
        rep_id,
    )

    created = client.post("/brands/campaigns", json=_BASE_CAMPAIGN_BODY, headers=brand_headers).json()

    response = client.post(
        f"/brands/campaigns/{created['id']}/reps/invite", json={"rep_ids": [rep_id]}, headers=brand_headers
    )
    assert response.status_code == 200
    results = response.json()
    assert results[0]["status"] == "invited"
    assert results[0]["campaign_rep_id"] is not None

    row = db.fetch("SELECT parent_approval_status FROM public.campaign_reps WHERE id = $1", results[0]["campaign_rep_id"])[0]
    assert row["parent_approval_status"] == "pending"
    assert len(fake_resend_client.sent) == 1
    assert fake_resend_client.sent[0].to == "parent@example.com"


def test_invite_twice_is_already_invited(client, db, brand_headers, onboarded_brand):
    rep_id = _seed_rep(db, categories=["gaming"])
    created = client.post("/brands/campaigns", json=_BASE_CAMPAIGN_BODY, headers=brand_headers).json()

    client.post(f"/brands/campaigns/{created['id']}/reps/invite", json={"rep_ids": [rep_id]}, headers=brand_headers)
    response = client.post(f"/brands/campaigns/{created['id']}/reps/invite", json={"rep_ids": [rep_id]}, headers=brand_headers)
    assert response.json()[0]["status"] == "already_invited"


def test_invite_respects_campaign_capacity(client, db, brand_headers, onboarded_brand):
    small_campaign = {**_BASE_CAMPAIGN_BODY, "max_reps": 1}
    created = client.post("/brands/campaigns", json=small_campaign, headers=brand_headers).json()

    rep_a = _seed_rep(db, categories=["gaming"])
    rep_b = _seed_rep(db, categories=["gaming"])

    response = client.post(
        f"/brands/campaigns/{created['id']}/reps/invite", json={"rep_ids": [rep_a, rep_b]}, headers=brand_headers
    )
    results = {r["rep_id"]: r["status"] for r in response.json()}
    assert results[rep_a] == "invited"
    assert results[rep_b] == "campaign_full"


def test_invite_unknown_rep_id(client, brand_headers, onboarded_brand):
    created = client.post("/brands/campaigns", json=_BASE_CAMPAIGN_BODY, headers=brand_headers).json()

    response = client.post(
        f"/brands/campaigns/{created['id']}/reps/invite",
        json={"rep_ids": [str(uuid.uuid4())]},
        headers=brand_headers,
    )
    assert response.json()[0]["status"] == "rep_not_found"


# ---------------------------------------------------------------------
# submission review / confirm / revision / rate (deliverables 8-9)
# ---------------------------------------------------------------------


def _invited_campaign_rep(client, db, brand_headers, created_campaign_id: str) -> tuple[str, str]:
    rep_id = _seed_rep(db, categories=["gaming"])
    invite_resp = client.post(
        f"/brands/campaigns/{created_campaign_id}/reps/invite", json={"rep_ids": [rep_id]}, headers=brand_headers
    )
    campaign_rep_id = invite_resp.json()[0]["campaign_rep_id"]
    return rep_id, campaign_rep_id


def test_confirm_requires_submitted_status(client, db, brand_headers, onboarded_brand):
    created = client.post("/brands/campaigns", json=_BASE_CAMPAIGN_BODY, headers=brand_headers).json()
    rep_id, campaign_rep_id = _invited_campaign_rep(client, db, brand_headers, created["id"])

    response = client.post(f"/brands/campaigns/{created['id']}/reps/{rep_id}/confirm", headers=brand_headers)
    assert response.status_code == 409

    db.execute("UPDATE public.campaign_reps SET status = 'submitted' WHERE id = $1", campaign_rep_id)
    response = client.post(f"/brands/campaigns/{created['id']}/reps/{rep_id}/confirm", headers=brand_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "confirmed"
    assert body["payout_cents"] == created["payout_per_rep_cents"]


def test_revision_requires_submitted_status_and_sets_note(client, db, brand_headers, onboarded_brand):
    created = client.post("/brands/campaigns", json=_BASE_CAMPAIGN_BODY, headers=brand_headers).json()
    rep_id, campaign_rep_id = _invited_campaign_rep(client, db, brand_headers, created["id"])
    db.execute("UPDATE public.campaign_reps SET status = 'submitted' WHERE id = $1", campaign_rep_id)

    response = client.post(
        f"/brands/campaigns/{created['id']}/reps/{rep_id}/revision", json={"note": "Please retake the photo"}, headers=brand_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "revision_requested"
    assert body["revision_note"] == "Please retake the photo"


def test_rate_write_once_after_confirmation(client, db, brand_headers, onboarded_brand):
    created = client.post("/brands/campaigns", json=_BASE_CAMPAIGN_BODY, headers=brand_headers).json()
    rep_id, campaign_rep_id = _invited_campaign_rep(client, db, brand_headers, created["id"])

    # Cannot rate before confirmation.
    response = client.post(f"/brands/campaigns/{created['id']}/reps/{rep_id}/rate", json={"brand_rating": 5}, headers=brand_headers)
    assert response.status_code == 409

    db.execute("UPDATE public.campaign_reps SET status = 'confirmed' WHERE id = $1", campaign_rep_id)
    response = client.post(f"/brands/campaigns/{created['id']}/reps/{rep_id}/rate", json={"brand_rating": 5}, headers=brand_headers)
    assert response.status_code == 200
    assert response.json()["brand_rating"] == 5

    # Second call is rejected -- write-once, no PUT/PATCH route exists at all.
    response = client.post(f"/brands/campaigns/{created['id']}/reps/{rep_id}/rate", json={"brand_rating": 1}, headers=brand_headers)
    assert response.status_code == 409


def test_rate_rejects_out_of_range_value(client, db, brand_headers, onboarded_brand):
    created = client.post("/brands/campaigns", json=_BASE_CAMPAIGN_BODY, headers=brand_headers).json()
    rep_id, _ = _invited_campaign_rep(client, db, brand_headers, created["id"])

    response = client.post(f"/brands/campaigns/{created['id']}/reps/{rep_id}/rate", json={"brand_rating": 6}, headers=brand_headers)
    assert response.status_code == 422


def test_get_submission_returns_narrow_shape(client, db, brand_headers, onboarded_brand):
    created = client.post("/brands/campaigns", json=_BASE_CAMPAIGN_BODY, headers=brand_headers).json()
    rep_id, campaign_rep_id = _invited_campaign_rep(client, db, brand_headers, created["id"])
    db.execute(
        "UPDATE public.campaign_reps SET status = 'submitted', submission_text = 'done!' WHERE id = $1",
        campaign_rep_id,
    )

    response = client.get(f"/brands/campaigns/{created['id']}/reps/{rep_id}/submission", headers=brand_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["submission_text"] == "done!"
    assert set(body.keys()) == {
        "campaign_rep_id",
        "rep_id",
        "status",
        "submission_text",
        "submission_file_urls",
        "submitted_at",
    }


# ---------------------------------------------------------------------
# billing / receipt (deliverable 10)
# ---------------------------------------------------------------------


def test_receipt_is_none_before_activation(client, brand_headers, onboarded_brand):
    created = client.post("/brands/campaigns", json=_BASE_CAMPAIGN_BODY, headers=brand_headers).json()

    response = client.get(f"/brands/campaigns/{created['id']}/receipt", headers=brand_headers)
    assert response.status_code == 200
    assert response.json()["receipt_url"] is None


def test_receipt_returns_stripe_hosted_url_once_payment_intent_exists(client, brand_headers, onboarded_brand, fake_stripe):
    created = client.post("/brands/campaigns", json=_BASE_CAMPAIGN_BODY, headers=brand_headers).json()
    client.post(f"/brands/campaigns/{created['id']}/activate", headers=brand_headers)

    response = client.get(f"/brands/campaigns/{created['id']}/receipt", headers=brand_headers)
    assert response.status_code == 200
    assert response.json()["receipt_url"].startswith("https://stripe.example.com/receipts/pi_fake")


# ---------------------------------------------------------------------
# GET /brands/campaigns (list), GET /brands/campaigns/:id/reps (list)
# (Prompt 16 coverage gap fill -- only the single-campaign GET and the
# /reps/browse variant were previously exercised)
# ---------------------------------------------------------------------


def test_list_campaigns_returns_only_own_campaigns(client, db, brand_headers, onboarded_brand):
    created = client.post("/brands/campaigns", json=_BASE_CAMPAIGN_BODY, headers=brand_headers).json()

    response = client.get("/brands/campaigns", headers=brand_headers)
    assert response.status_code == 200
    ids = {c["id"] for c in response.json()}
    assert created["id"] in ids


def test_list_campaigns_role_enforcement_rejects_non_brand(client, auth_headers_factory):
    response = client.get("/brands/campaigns", headers=auth_headers_factory("rep"))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "role_mismatch"


def test_list_campaign_reps_returns_invited_rep(client, db, brand_headers, onboarded_brand):
    created = client.post("/brands/campaigns", json=_BASE_CAMPAIGN_BODY, headers=brand_headers).json()
    rep_id = _seed_rep(db)
    client.post(f"/brands/campaigns/{created['id']}/reps/invite", json={"rep_ids": [rep_id]}, headers=brand_headers)

    response = client.get(f"/brands/campaigns/{created['id']}/reps", headers=brand_headers)
    assert response.status_code == 200
    assert rep_id in {r["rep_id"] for r in response.json()}
