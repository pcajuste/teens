from __future__ import annotations

import threading
import uuid
from datetime import date
from types import SimpleNamespace

import pytest
import stripe

from app.services import stripe_service

RECRUITER_USER_ID = "00000000-0000-0000-0000-000000000001"

_BASE_PROFILE_BODY = {
    "institution_name": "State University",
    "institution_type": "college",
    "website": "https://stateu.example.edu",
}


def _seed_recruiter_user(db, *, account_status: str = "active") -> None:
    db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", RECRUITER_USER_ID, "recruiter@example.com")
    db.execute(
        "INSERT INTO public.users (id, email, role, account_status, date_of_birth) "
        "VALUES ($1, 'recruiter@example.com', 'recruiter', $2, '1990-01-01')",
        RECRUITER_USER_ID,
        account_status,
    )


def _seed_rep(db, *, recruiter_visible: bool = True, categories=None, city="Austin", state="TX", graduation_year=2027,
              brand_campaigns_completed=0, brand_average_rating=None) -> str:
    talent_user_id = str(uuid.uuid4())
    talent_id = str(uuid.uuid4())
    talent_email = f"talent-{talent_user_id}@example.com"
    db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", talent_user_id, talent_email)
    db.execute(
        "INSERT INTO public.users (id, email, role, account_status, date_of_birth) "
        "VALUES ($1, $2, 'talent', 'active', '2008-06-01')",
        talent_user_id,
        talent_email,
    )
    db.execute(
        """
        INSERT INTO public.talent_profiles
            (id, user_id, display_name, school_name, city, state, graduation_year, categories,
             recruiter_visible, brand_campaigns_completed, brand_average_rating, instagram_handle)
        VALUES ($1, $2, 'Test Talent', 'Test High', $3, $4, $5, $6, $7, $8, $9, 'test_talent_ig')
        """,
        talent_id,
        talent_user_id,
        city,
        state,
        graduation_year,
        categories or ["gaming"],
        recruiter_visible,
        brand_campaigns_completed,
        brand_average_rating,
    )
    return talent_id


@pytest.fixture()
def recruiter_headers(auth_headers_factory):
    return auth_headers_factory("recruiter")


@pytest.fixture()
def onboarded_recruiter(client, db, recruiter_headers):
    _seed_recruiter_user(db)
    response  = client.put("/recruiters/me", json=_BASE_PROFILE_BODY, headers=recruiter_headers)
    assert response .status_code == 200
    return response .json()


def _grant_credits(db, recruiter_id: str, *, credits: int = 5) -> None:
    db.execute(
        "UPDATE public.recruiter_profiles SET contact_credits_remaining = $2, stripe_subscription_id = 'sub_test123' WHERE id = $1",
        recruiter_id,
        credits,
    )


def _recruiter_id(db) -> str:
    return db.fetch("SELECT id FROM public.recruiter_profiles WHERE user_id = $1", RECRUITER_USER_ID)[0]["id"]


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

    class _Customer:
        @staticmethod
        def create(**kwargs):
            counter["n"] += 1
            calls.append(("Customer.create", kwargs))
            return SimpleNamespace(id=f"cus_fake{counter['n']}")

    fake = SimpleNamespace(PaymentIntent=_PaymentIntent, Customer=_Customer, Webhook=stripe.Webhook, calls=calls)
    monkeypatch.setattr(stripe_service, "stripe", fake)
    return fake


def _webhook_payload(event_type: str, obj: dict) -> dict:
    return {"id": f"evt_{uuid.uuid4()}", "type": event_type, "data": {"object": obj}}


# ---------------------------------------------------------------------
# GET/PUT /recruiters/me
# ---------------------------------------------------------------------


def test_put_me_creates_then_updates_profile(client, db, recruiter_headers):
    _seed_recruiter_user(db)
    created = client.put("/recruiters/me", json=_BASE_PROFILE_BODY, headers=recruiter_headers)
    assert created.status_code == 200
    body = created.json()
    assert body["institution_name"] == "State University"
    assert body["institution_type"] == "college"
    assert body["verified"] is False

    updated = client.put(
        "/recruiters/me",
        json={**_BASE_PROFILE_BODY, "institution_name": "Renamed University"},
        headers=recruiter_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["institution_name"] == "Renamed University"
    assert updated.json()["id"] == body["id"]


def test_get_me_requires_onboarding_first(client, recruiter_headers):
    _ = recruiter_headers  # no seed -- account exists via JWT claims only, no DB row
    response  = client.get("/recruiters/me", headers=recruiter_headers)
    assert response .status_code == 404
    assert response .json()["error"]["code"] == "recruiter_profile_not_found"


def test_pending_recruiter_can_reach_put_me(client, db, auth_headers_factory):
    """require_role_any_status -- a freshly signed-up recruiter
    (account_status='pending') must still be able to submit their
    profile, mirroring brands.py's PUT /brands/me fix."""
    _seed_recruiter_user(db, account_status="pending")
    headers = auth_headers_factory("recruiter", account_status="pending")
    response  = client.put("/recruiters/me", json=_BASE_PROFILE_BODY, headers=headers)
    assert response .status_code == 200


# ---------------------------------------------------------------------
# GET /recruiters/talents/search -- no credit cost, no PII
# ---------------------------------------------------------------------


def test_search_never_returns_pii_fields(client, db, recruiter_headers, onboarded_recruiter):
    _seed_rep(db, city="Austin", state="TX", categories=["gaming"])
    response  = client.get("/recruiters/talents/search", headers=recruiter_headers)
    assert response .status_code == 200
    results = response .json()
    assert len(results) == 1
    card = results[0]
    assert "display_name" not in card
    assert "instagram_handle" not in card
    assert "bio" not in card
    assert card["city"] == "Austin"


def test_search_does_not_cost_a_credit(client, db, recruiter_headers, onboarded_recruiter):
    _seed_rep(db)
    recruiter_id = _recruiter_id(db)
    _grant_credits(db, recruiter_id, credits=3)
    client.get("/recruiters/talents/search", headers=recruiter_headers)
    after = client.get("/recruiters/credits", headers=recruiter_headers).json()
    assert after["contact_credits_remaining"] == 3


def test_search_filters_by_params(client, db, recruiter_headers, onboarded_recruiter):
    _seed_rep(db, city="Austin", state="TX", graduation_year=2027, categories=["gaming"])
    _seed_rep(db, city="Dallas", state="TX", graduation_year=2028, categories=["fashion"])

    response  = client.get("/recruiters/talents/search", params={"city": "Austin"}, headers=recruiter_headers)
    assert len(response .json()) == 1
    assert response .json()[0]["city"] == "Austin"

    response  = client.get("/recruiters/talents/search", params={"categories": "fashion"}, headers=recruiter_headers)
    assert len(response .json()) == 1
    assert response .json()[0]["city"] == "Dallas"

    response  = client.get("/recruiters/talents/search", params={"graduation_year": 2027}, headers=recruiter_headers)
    assert len(response .json()) == 1


def test_search_excludes_non_recruiter_visible_reps(client, db, recruiter_headers, onboarded_recruiter):
    _seed_rep(db, recruiter_visible=False)
    response  = client.get("/recruiters/talents/search", headers=recruiter_headers)
    assert response .json() == []


# ---------------------------------------------------------------------
# GET /recruiters/talents/:id -- costs 1 credit
# ---------------------------------------------------------------------


def test_view_profile_deducts_one_credit(client, db, recruiter_headers, onboarded_recruiter):
    talent_id = _seed_rep(db)
    recruiter_id = _recruiter_id(db)
    _grant_credits(db, recruiter_id, credits=2)

    response  = client.get(f"/recruiters/talents/{talent_id}", headers=recruiter_headers)
    assert response .status_code == 200
    body = response .json()
    assert body["display_name"] == "Test Talent"
    assert body["instagram_handle"] == "test_talent_ig"

    credits = client.get("/recruiters/credits", headers=recruiter_headers).json()
    assert credits["contact_credits_remaining"] == 1


def test_view_profile_at_zero_credits_returns_402(client, db, recruiter_headers, onboarded_recruiter):
    talent_id = _seed_rep(db)
    recruiter_id = _recruiter_id(db)
    _grant_credits(db, recruiter_id, credits=0)

    response  = client.get(f"/recruiters/talents/{talent_id}", headers=recruiter_headers)
    assert response .status_code == 402
    assert response .json()["error"]["code"] == "insufficient_credits"


def test_view_profile_requires_active_subscription(client, db, recruiter_headers, onboarded_recruiter):
    talent_id = _seed_rep(db)
    recruiter_id = _recruiter_id(db)
    # Credits present but no stripe_subscription_id set (default state
    # after onboarding, before any subscription webhook lands).
    db.execute("UPDATE public.recruiter_profiles SET contact_credits_remaining = 5 WHERE id = $1", recruiter_id)

    response  = client.get(f"/recruiters/talents/{talent_id}", headers=recruiter_headers)
    assert response .status_code == 403
    assert response .json()["error"]["code"] == "subscription_inactive"


def test_view_profile_concurrent_requests_with_exactly_one_credit(client, db, recruiter_headers, onboarded_recruiter):
    """Build Prompt 11 acceptance criterion: concurrent requests with
    exactly 1 credit -> exactly one success, one 'insufficient credits'."""
    talent_id = _seed_rep(db)
    recruiter_id = _recruiter_id(db)
    _grant_credits(db, recruiter_id, credits=1)

    results = []
    lock = threading.Lock()

    def _call():
        response  = client.get(f"/recruiters/talents/{talent_id}", headers=recruiter_headers)
        with lock:
            results.append(response .status_code)

    threads = [threading.Thread(target=_call) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count(200) == 1
    assert results.count(402) == 7

    final = client.get("/recruiters/credits", headers=recruiter_headers).json()
    assert final["contact_credits_remaining"] == 0


# ---------------------------------------------------------------------
# POST /recruiters/talents/:id/contact
# ---------------------------------------------------------------------


def test_contact_talent_deducts_credit_and_notifies_talent_inbox(client, db, recruiter_headers, onboarded_recruiter):
    talent_id = _seed_rep(db)
    recruiter_id = _recruiter_id(db)
    _grant_credits(db, recruiter_id, credits=2)

    response  = client.post(
        f"/recruiters/talents/{talent_id}/contact", json={"message_text": "Interested in your work!"}, headers=recruiter_headers
    )
    assert response .status_code == 200
    body = response .json()
    assert body["talent_id"] == talent_id

    credits = client.get("/recruiters/credits", headers=recruiter_headers).json()
    assert credits["contact_credits_remaining"] == 1

    row = db.fetch("SELECT read_at FROM public.recruiter_contacts WHERE talent_id = $1", talent_id)
    assert len(row) == 1
    assert row[0]["read_at"] is None


def test_second_contact_to_same_talent_is_rejected(client, db, recruiter_headers, onboarded_recruiter):
    talent_id = _seed_rep(db)
    recruiter_id = _recruiter_id(db)
    _grant_credits(db, recruiter_id, credits=5)

    first = client.post(f"/recruiters/talents/{talent_id}/contact", json={"message_text": "Hi!"}, headers=recruiter_headers)
    assert first.status_code == 200

    second = client.post(f"/recruiters/talents/{talent_id}/contact", json={"message_text": "Hi again!"}, headers=recruiter_headers)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "already_contacted"

    # Rejected duplicate never spent a second credit.
    credits = client.get("/recruiters/credits", headers=recruiter_headers).json()
    assert credits["contact_credits_remaining"] == 4


def test_contact_at_zero_credits_returns_402(client, db, recruiter_headers, onboarded_recruiter):
    talent_id = _seed_rep(db)
    recruiter_id = _recruiter_id(db)
    _grant_credits(db, recruiter_id, credits=0)

    response  = client.post(f"/recruiters/talents/{talent_id}/contact", json={"message_text": "Hi!"}, headers=recruiter_headers)
    assert response .status_code == 402


# ---------------------------------------------------------------------
# GET /talents/inbox, POST /talents/inbox/:id/read
# ---------------------------------------------------------------------


def test_talent_inbox_shows_recruiter_message_and_can_be_marked_read(client, db, recruiter_headers, onboarded_recruiter, auth_headers_factory):
    talent_user_id = str(uuid.uuid4())
    talent_id = str(uuid.uuid4())
    db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", talent_user_id, "talent-inbox@example.com")
    db.execute(
        "INSERT INTO public.users (id, email, role, account_status, date_of_birth) "
        "VALUES ($1, 'talent-inbox@example.com', 'talent', 'active', '2008-06-01')",
        talent_user_id,
    )
    db.execute(
        "INSERT INTO public.talent_profiles (id, user_id, display_name, school_name, city, state, graduation_year, categories, recruiter_visible) "
        "VALUES ($1, $2, 'Inbox Talent', 'Test High', 'Austin', 'TX', 2027, $3, TRUE)",
        talent_id,
        talent_user_id,
        ["gaming"],
    )
    recruiter_id = _recruiter_id(db)
    _grant_credits(db, recruiter_id, credits=2)
    client.post(f"/recruiters/talents/{talent_id}/contact", json={"message_text": "Hi there!"}, headers=recruiter_headers)

    # auth_headers_factory always signs sub=RECRUITER_USER_ID's constant
    # -- but that's a *fixed* subject id shared by every role fixture in
    # conftest.py, not scoped to this talent_id. Point the talent row's user_id
    # at that same fixed id so /talents/inbox's own-profile lookup resolves.
    db.execute("UPDATE public.talent_profiles SET user_id = $1 WHERE id = $2", RECRUITER_USER_ID, talent_id)
    talent_headers = auth_headers_factory("talent")

    inbox = client.get("/talents/inbox", headers=talent_headers)
    assert inbox.status_code == 200
    messages = inbox.json()
    assert len(messages) == 1
    assert messages[0]["message_text"] == "Hi there!"
    assert messages[0]["read_at"] is None

    marked = client.post(f"/talents/inbox/{messages[0]['id']}/read", headers=talent_headers)
    assert marked.status_code == 200
    assert marked.json()["read_at"] is not None

    # Idempotent re-mark.
    again = client.post(f"/talents/inbox/{messages[0]['id']}/read", headers=talent_headers)
    assert again.status_code == 200


# ---------------------------------------------------------------------
# POST/DELETE /recruiters/talents/:id/save, GET /recruiters/saved
# ---------------------------------------------------------------------


def test_save_unsave_and_list_saved(client, db, recruiter_headers, onboarded_recruiter):
    talent_id = _seed_rep(db)

    saved = client.post(f"/recruiters/talents/{talent_id}/save", json={"list_name": "Shortlist"}, headers=recruiter_headers)
    assert saved.status_code == 200
    assert saved.json()["list_name"] == "Shortlist"

    listed = client.get("/recruiters/saved", headers=recruiter_headers)
    assert len(listed.json()) == 1
    assert listed.json()[0]["talent_id"] == talent_id

    deleted = client.delete(f"/recruiters/talents/{talent_id}/save", headers=recruiter_headers)
    assert deleted.status_code == 204

    listed_after = client.get("/recruiters/saved", headers=recruiter_headers)
    assert listed_after.json() == []


def test_saving_does_not_cost_a_credit(client, db, recruiter_headers, onboarded_recruiter):
    talent_id = _seed_rep(db)
    recruiter_id = _recruiter_id(db)
    _grant_credits(db, recruiter_id, credits=3)
    client.post(f"/recruiters/talents/{talent_id}/save", headers=recruiter_headers)
    credits = client.get("/recruiters/credits", headers=recruiter_headers).json()
    assert credits["contact_credits_remaining"] == 3


# ---------------------------------------------------------------------
# GET /recruiters/credits -- low-credit warning
# ---------------------------------------------------------------------


def test_low_credit_warning_flag(client, db, recruiter_headers, onboarded_recruiter, settings):
    recruiter_id = _recruiter_id(db)
    allotment = settings.recruiter_plan_credits_allotment

    _grant_credits(db, recruiter_id, credits=allotment)
    full = client.get("/recruiters/credits", headers=recruiter_headers).json()
    assert full["low_credit_warning"] is False

    low_amount = max(1, int(allotment * 0.1))
    _grant_credits(db, recruiter_id, credits=low_amount)
    low = client.get("/recruiters/credits", headers=recruiter_headers).json()
    assert low["low_credit_warning"] is True


# ---------------------------------------------------------------------
# Credit top-up: POST /recruiters/credits/top-up + payment_intent.succeeded
# ---------------------------------------------------------------------


def test_top_up_creates_payment_intent_tagged_for_credits(client, db, recruiter_headers, onboarded_recruiter, fake_stripe, settings):
    response  = client.post("/recruiters/credits/top-up", json={"credits": 10}, headers=recruiter_headers)
    assert response .status_code == 200
    assert "stripe_payment_intent_client_secret" in response .json()

    name, kwargs = [c for c in fake_stripe.calls if c[0] == "PaymentIntent.create"][0]
    assert kwargs["amount"] == settings.recruiter_credit_topup_price_cents * 10
    assert kwargs["metadata"]["type"] == "recruiter_credit_topup"
    assert kwargs["metadata"]["credits"] == "10"


def test_payment_intent_succeeded_webhook_credits_recruiter(client, db, monkeypatch, recruiter_headers, onboarded_recruiter):
    recruiter_id = _recruiter_id(db)
    db.execute("UPDATE public.recruiter_profiles SET contact_credits_remaining = 2 WHERE id = $1", recruiter_id)

    event = _webhook_payload(
        "payment_intent.succeeded",
        {"id": "pi_topup_1", "metadata": {"type": "recruiter_credit_topup", "recruiter_id": recruiter_id, "credits": "10"}},
    )
    from app.services import stripe_service as svc

    monkeypatch.setattr(svc, "verify_webhook_signature", lambda settings, *, payload, signature_header: event)
    response  = client.post("/webhooks/stripe", content=b"{}", headers={"Stripe-Signature": "test"})
    assert response .status_code == 200

    credits = client.get("/recruiters/credits", headers=recruiter_headers).json()
    assert credits["contact_credits_remaining"] == 12


def test_payment_intent_succeeded_webhook_idempotent_for_credits(client, db, monkeypatch, recruiter_headers, onboarded_recruiter):
    recruiter_id = _recruiter_id(db)
    db.execute("UPDATE public.recruiter_profiles SET contact_credits_remaining = 0 WHERE id = $1", recruiter_id)

    event = _webhook_payload(
        "payment_intent.succeeded",
        {"id": "pi_topup_dup", "metadata": {"type": "recruiter_credit_topup", "recruiter_id": recruiter_id, "credits": "5"}},
    )
    from app.services import stripe_service as svc

    monkeypatch.setattr(svc, "verify_webhook_signature", lambda settings, *, payload, signature_header: event)
    client.post("/webhooks/stripe", content=b"{}", headers={"Stripe-Signature": "test"})
    client.post("/webhooks/stripe", content=b"{}", headers={"Stripe-Signature": "test"})

    credits = client.get("/recruiters/credits", headers=recruiter_headers).json()
    assert credits["contact_credits_remaining"] == 5


# ---------------------------------------------------------------------
# Subscription lifecycle webhooks
# ---------------------------------------------------------------------


def test_subscription_created_activates_verified_recruiter(client, db, monkeypatch, recruiter_headers, onboarded_recruiter, settings):
    recruiter_id = _recruiter_id(db)
    db.execute("UPDATE public.recruiter_profiles SET verified = TRUE, stripe_customer_id = 'cus_sub1' WHERE id = $1", recruiter_id)

    event = _webhook_payload(
        "customer.subscription.created",
        {"id": "sub_new1", "customer": "cus_sub1", "current_period_end": 4102444800},
    )
    from app.services import stripe_service as svc

    monkeypatch.setattr(svc, "verify_webhook_signature", lambda settings, *, payload, signature_header: event)
    response  = client.post("/webhooks/stripe", content=b"{}", headers={"Stripe-Signature": "test"})
    assert response .status_code == 200

    credits = client.get("/recruiters/credits", headers=recruiter_headers).json()
    assert credits["contact_credits_remaining"] == settings.recruiter_plan_credits_allotment
    assert credits["credits_reset_date"] == date(2100, 1, 1).isoformat()

    status_row = db.fetch("SELECT account_status FROM public.users WHERE id = $1", RECRUITER_USER_ID)
    assert status_row[0]["account_status"] == "active"


def test_subscription_created_does_not_activate_unverified_recruiter(client, db, monkeypatch, recruiter_headers, onboarded_recruiter):
    recruiter_id = _recruiter_id(db)
    db.execute(
        "UPDATE public.recruiter_profiles SET verified = FALSE, stripe_customer_id = 'cus_sub2' WHERE id = $1", recruiter_id
    )
    db.execute("UPDATE public.users SET account_status = 'pending' WHERE id = $1", RECRUITER_USER_ID)

    event = _webhook_payload(
        "customer.subscription.created", {"id": "sub_new2", "customer": "cus_sub2", "current_period_end": 4102444800}
    )
    from app.services import stripe_service as svc

    monkeypatch.setattr(svc, "verify_webhook_signature", lambda settings, *, payload, signature_header: event)
    client.post("/webhooks/stripe", content=b"{}", headers={"Stripe-Signature": "test"})

    status_row = db.fetch("SELECT account_status FROM public.users WHERE id = $1", RECRUITER_USER_ID)
    assert status_row[0]["account_status"] == "pending"
    # Credits are still granted even though account isn't active yet --
    # the dual gate is about account_status, not credit issuance.
    credits_row = db.fetch("SELECT contact_credits_remaining FROM public.recruiter_profiles WHERE id = $1", recruiter_id)
    assert credits_row[0]["contact_credits_remaining"] > 0


def test_subscription_updated_resets_credits_and_does_not_roll_over(client, db, monkeypatch, recruiter_headers, onboarded_recruiter, settings):
    recruiter_id = _recruiter_id(db)
    db.execute(
        "UPDATE public.recruiter_profiles SET stripe_customer_id = 'cus_sub3', stripe_subscription_id = 'sub3', "
        "contact_credits_remaining = 1 WHERE id = $1",
        recruiter_id,
    )

    event = _webhook_payload(
        "customer.subscription.updated", {"id": "sub3", "customer": "cus_sub3", "current_period_end": 4102444800}
    )
    from app.services import stripe_service as svc

    monkeypatch.setattr(svc, "verify_webhook_signature", lambda settings, *, payload, signature_header: event)
    client.post("/webhooks/stripe", content=b"{}", headers={"Stripe-Signature": "test"})

    credits = client.get("/recruiters/credits", headers=recruiter_headers).json()
    # Reset to full allotment, NOT 1 (existing) + allotment -- unused
    # credits are lost on renewal (explicit MVP decision).
    assert credits["contact_credits_remaining"] == settings.recruiter_plan_credits_allotment


def test_duplicated_subscription_updated_event_resets_exactly_once(client, db, monkeypatch, recruiter_headers, onboarded_recruiter, settings):
    recruiter_id = _recruiter_id(db)
    db.execute(
        "UPDATE public.recruiter_profiles SET stripe_customer_id = 'cus_sub4', stripe_subscription_id = 'sub4' WHERE id = $1",
        recruiter_id,
    )

    event = _webhook_payload(
        "customer.subscription.updated", {"id": "sub4", "customer": "cus_sub4", "current_period_end": 4102444800}
    )
    from app.services import stripe_service as svc

    monkeypatch.setattr(svc, "verify_webhook_signature", lambda settings, *, payload, signature_header: event)
    first = client.post("/webhooks/stripe", content=b"{}", headers={"Stripe-Signature": "test"})
    second = client.post("/webhooks/stripe", content=b"{}", headers={"Stripe-Signature": "test"})
    assert first.status_code == 200
    assert second.status_code == 200

    row = db.fetch("SELECT contact_credits_remaining FROM public.recruiter_profiles WHERE id = $1", recruiter_id)
    assert row[0]["contact_credits_remaining"] == settings.recruiter_plan_credits_allotment


def test_subscription_deleted_deactivates_and_blocks_credit_spend(client, db, monkeypatch, recruiter_headers, onboarded_recruiter):
    talent_id = _seed_rep(db)
    recruiter_id = _recruiter_id(db)
    db.execute(
        "UPDATE public.recruiter_profiles SET stripe_customer_id = 'cus_sub5', stripe_subscription_id = 'sub5', "
        "contact_credits_remaining = 5, verified = TRUE WHERE id = $1",
        recruiter_id,
    )
    db.execute("UPDATE public.users SET account_status = 'active' WHERE id = $1", RECRUITER_USER_ID)

    # Recruiter saves and contacts a talent before the subscription is cancelled.
    _grant_credits(db, recruiter_id, credits=5)
    client.post(f"/recruiters/talents/{talent_id}/save", headers=recruiter_headers)

    event = _webhook_payload("customer.subscription.deleted", {"id": "sub5", "customer": "cus_sub5"})
    from app.services import stripe_service as svc

    monkeypatch.setattr(svc, "verify_webhook_signature", lambda settings, *, payload, signature_header: event)
    response  = client.post("/webhooks/stripe", content=b"{}", headers={"Stripe-Signature": "test"})
    assert response .status_code == 200

    status_row = db.fetch("SELECT account_status FROM public.users WHERE id = $1", RECRUITER_USER_ID)
    assert status_row[0]["account_status"] == "pending"

    # Saved profiles retained.
    saved = client.get("/recruiters/saved", headers=recruiter_headers)
    assert len(saved.json()) == 1

    # Credit-spending endpoint now rejects.
    rejected = client.get(f"/recruiters/talents/{talent_id}", headers=recruiter_headers)
    assert rejected.status_code == 403
    assert rejected.json()["error"]["code"] == "subscription_inactive"


# ---------------------------------------------------------------------
# POST /recruiters/subscribe, GET /recruiters/messages (Prompt 16
# coverage gap fill)
# ---------------------------------------------------------------------


def test_subscribe_returns_checkout_url(client, db, recruiter_headers, onboarded_recruiter, settings, monkeypatch):
    monkeypatch.setattr(settings, "recruiter_price_id_monthly", "price_test_monthly")

    class _Session:
        @staticmethod
        def create(**kwargs):
            return SimpleNamespace(url="https://checkout.stripe.example.com/session_test")

    fake = SimpleNamespace(checkout=SimpleNamespace(Session=_Session), Customer=SimpleNamespace(create=lambda **kw: SimpleNamespace(id="cus_fake_sub")))
    monkeypatch.setattr(stripe_service, "stripe", fake)

    response  = client.post("/recruiters/subscribe", json={"plan": "monthly"}, headers=recruiter_headers)
    assert response .status_code == 200
    assert response .json()["checkout_url"] == "https://checkout.stripe.example.com/session_test"


def test_subscribe_rejects_unconfigured_plan(client, db, recruiter_headers, onboarded_recruiter, settings, monkeypatch):
    monkeypatch.setattr(settings, "recruiter_price_id_annual", None)
    response  = client.post("/recruiters/subscribe", json={"plan": "annual"}, headers=recruiter_headers)
    assert response .status_code == 500
    assert response .json()["error"]["code"] == "plan_not_configured"


def test_subscribe_role_enforcement_rejects_non_recruiter(client, auth_headers_factory):
    response  = client.post("/recruiters/subscribe", json={"plan": "monthly"}, headers=auth_headers_factory("talent"))
    assert response .status_code == 403
    assert response .json()["error"]["code"] == "role_mismatch"


def test_messages_lists_sent_contact(client, db, recruiter_headers, onboarded_recruiter):
    talent_id = _seed_rep(db)
    recruiter_id = _recruiter_id(db)
    _grant_credits(db, recruiter_id, credits=2)
    client.post(f"/recruiters/talents/{talent_id}/contact", json={"message_text": "Hi!"}, headers=recruiter_headers)

    response  = client.get("/recruiters/messages", headers=recruiter_headers)
    assert response .status_code == 200
    assert response .json()[0]["talent_id"] == talent_id


def test_messages_role_enforcement_rejects_non_recruiter(client, auth_headers_factory):
    response  = client.get("/recruiters/messages", headers=auth_headers_factory("brand"))
    assert response .status_code == 403
    assert response .json()["error"]["code"] == "role_mismatch"


# ---------------------------------------------------------------------
# ATHLETICS-5: athletic recruiter backend
# ---------------------------------------------------------------------


def _seed_athletic_talent(
    db, *, sport="football", positions=None, gpa=None, hudl_url=None, attested_seasons=0,
    athletic_completeness_score=50, recruiter_visible=True, enabled_tracks=None,
) -> str:
    talent_user_id = str(uuid.uuid4())
    talent_id = str(uuid.uuid4())
    talent_email = f"athlete-{talent_user_id}@example.com"
    db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", talent_user_id, talent_email)
    db.execute(
        "INSERT INTO public.users (id, email, role, account_status, date_of_birth) "
        "VALUES ($1, $2, 'talent', 'active', '2008-06-01')",
        talent_user_id,
        talent_email,
    )
    db.execute(
        """
        INSERT INTO public.talent_profiles
            (id, user_id, display_name, school_name, city, state, graduation_year, categories,
             recruiter_visible, enabled_tracks, athletic_completeness_score)
        VALUES ($1, $2, 'Test Athlete', 'Test High', 'Austin', 'TX', 2027, ARRAY['gaming'],
                $3, $4, $5)
        """,
        talent_id,
        talent_user_id,
        recruiter_visible,
        enabled_tracks if enabled_tracks is not None else ["brand", "athletics"],
        athletic_completeness_score,
    )
    if sport is not None:
        db.execute(
            "INSERT INTO public.sport_profiles (talent_id, sport, positions, gpa, hudl_url) "
            "VALUES ($1, $2, $3, $4, $5)",
            talent_id,
            sport,
            positions or ["QB"],
            gpa,
            hudl_url,
        )
    for i in range(attested_seasons):
        db.execute(
            "INSERT INTO public.athletic_seasons (talent_id, sport, season_year, season_type, team_name, level, status) "
            "VALUES ($1, $2, $3, 'high_school', 'Wildcats', 'varsity', 'attested')",
            talent_id,
            sport,
            2020 + i,
        )
    db.execute(
        "UPDATE public.talent_profiles SET athletic_seasons_completed = $2 WHERE id = $1",
        talent_id,
        attested_seasons,
    )
    return talent_id


def test_athletic_search_only_returns_athletics_enabled_talents(client, db, recruiter_headers, onboarded_recruiter):
    brand_only_id = _seed_rep(db)
    athletic_id = _seed_athletic_talent(db)

    response = client.get("/recruiters/talents/search", params={"track": "athletics"}, headers=recruiter_headers)
    assert response.status_code == 200
    ids = [r["talent_id"] for r in response.json()]
    assert athletic_id in ids
    assert brand_only_id not in ids


def test_athletic_search_filters_by_sport(client, db, recruiter_headers, onboarded_recruiter):
    football_id = _seed_athletic_talent(db, sport="football")
    soccer_id = _seed_athletic_talent(db, sport="soccer")

    response = client.get(
        "/recruiters/talents/search", params={"track": "athletics", "sports": "football"}, headers=recruiter_headers
    )
    assert response.status_code == 200
    ids = [r["talent_id"] for r in response.json()]
    assert football_id in ids
    assert soccer_id not in ids


def test_athletic_search_auto_populates_from_sports_of_interest(client, db, recruiter_headers, onboarded_recruiter):
    recruiter_id = _recruiter_id(db)
    client.put("/recruiters/me/sports-of-interest", json={"sports_of_interest": ["basketball"]}, headers=recruiter_headers)

    basketball_id = _seed_athletic_talent(db, sport="basketball")
    football_id = _seed_athletic_talent(db, sport="football")

    response = client.get("/recruiters/talents/search", params={"track": "athletics"}, headers=recruiter_headers)
    assert response.status_code == 200
    ids = [r["talent_id"] for r in response.json()]
    assert basketball_id in ids
    assert football_id not in ids


def test_athletic_search_ordered_by_athletic_completeness_desc(client, db, recruiter_headers, onboarded_recruiter):
    low_id = _seed_athletic_talent(db, athletic_completeness_score=20)
    high_id = _seed_athletic_talent(db, athletic_completeness_score=80)

    response = client.get("/recruiters/talents/search", params={"track": "athletics"}, headers=recruiter_headers)
    ids = [r["talent_id"] for r in response.json()]
    assert ids.index(high_id) < ids.index(low_id)


def test_athletic_search_never_returns_pii(client, db, recruiter_headers, onboarded_recruiter):
    _seed_athletic_talent(db)
    response = client.get("/recruiters/talents/search", params={"track": "athletics"}, headers=recruiter_headers)
    for card in response.json():
        for key in ("display_name", "school_name", "bio", "instagram_handle", "tiktok_handle"):
            assert key not in card


def test_athletic_detail_costs_one_credit_and_excludes_earnings(client, db, recruiter_headers, onboarded_recruiter):
    talent_id = _seed_athletic_talent(db, gpa=3.5, attested_seasons=1)
    recruiter_id = _recruiter_id(db)
    _grant_credits(db, recruiter_id, credits=2)

    response = client.get(f"/recruiters/talents/{talent_id}", params={"track": "athletics"}, headers=recruiter_headers)
    assert response.status_code == 200
    body = response.json()
    assert "total_earnings_cents" not in body
    assert len(body["sport_profiles"]) == 1
    assert len(body["recent_seasons"]) == 1
    assert body["nil_acknowledged"] is False

    credits = client.get("/recruiters/credits", headers=recruiter_headers).json()
    assert credits["contact_credits_remaining"] == 1

    talent_row = db.fetch("SELECT athletic_recruiter_interest_count FROM public.talent_profiles WHERE id = $1", talent_id)
    assert talent_row[0]["athletic_recruiter_interest_count"] == 1


def test_athletic_detail_at_zero_credits_returns_402(client, db, recruiter_headers, onboarded_recruiter):
    talent_id = _seed_athletic_talent(db)
    recruiter_id = _recruiter_id(db)
    _grant_credits(db, recruiter_id, credits=0)
    db.execute("UPDATE public.recruiter_profiles SET stripe_subscription_id = 'sub_test123' WHERE id = $1", recruiter_id)

    response = client.get(f"/recruiters/talents/{talent_id}", params={"track": "athletics"}, headers=recruiter_headers)
    assert response.status_code == 402


def test_put_sports_of_interest_rejects_unsupported_sport(client, db, recruiter_headers, onboarded_recruiter):
    response = client.put("/recruiters/me/sports-of-interest", json={"sports_of_interest": ["fencing"]}, headers=recruiter_headers)
    assert response.status_code == 422


def test_put_sports_of_interest_succeeds_for_college(client, db, recruiter_headers, onboarded_recruiter):
    response = client.put("/recruiters/me/sports-of-interest", json={"sports_of_interest": ["football", "basketball"]}, headers=recruiter_headers)
    assert response.status_code == 200

    get_resp = client.get("/recruiters/me/sports-of-interest", headers=recruiter_headers)
    assert get_resp.status_code == 200
    assert set(get_resp.json()["sports_of_interest"]) == {"football", "basketball"}


def test_put_sports_of_interest_rejects_employer_type(client, db, recruiter_headers):
    _seed_recruiter_user(db)
    client.put(
        "/recruiters/me",
        json={"institution_name": "Acme Inc", "institution_type": "employer", "website": None},
        headers=recruiter_headers,
    )
    response = client.put("/recruiters/me/sports-of-interest", json={"sports_of_interest": ["football"]}, headers=recruiter_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_applicable"
