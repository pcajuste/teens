"""Build Prompt 10: Campaign Lifecycle & Payout Engine.

Covers calculate_platform_fee_split's rounding/invariant (acceptance
criterion), release_payout's outcomes, and the payment_intent.*/
transfer.* webhook handlers (activation, payment failure, payout
completion + talent_profiles cached-total recompute, payout failure).
"""
from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
import stripe

from app.services import payout_service, stripe_service

BRAND_USER_ID = "00000000-0000-0000-0000-000000000001"

_BRAND_PROFILE_BODY = {
    "company_name": "Acme Co",
    "website": "https://acme.example.com",
    "ein": "12-3456789",
    "industry": "apparel",
    "target_categories": ["gaming"],
}

_CAMPAIGN_BODY = {
    "title": "Spring Launch",
    "product_name": "Acme Widget",
    "campaign_goal": "Awareness",
    "key_messaging": "Widgets are great",
    "prohibited_content": None,
    "deliverables_description": "One TikTok post",
    "target_categories": ["gaming"],
    "target_cities": ["Austin"],
    "max_talents": 5,
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


def _seed_rep(db, *, onboarded: bool = True) -> tuple[str, str]:
    """Returns (talent_profile_id, talent_user_id)."""
    talent_user_id = str(uuid.uuid4())
    talent_id = str(uuid.uuid4())
    talent_email = f"talent-{talent_user_id}@example.com"
    dob = date(date.today().year - 20, 6, 1)
    db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", talent_user_id, talent_email)
    db.execute(
        "INSERT INTO public.users (id, email, role, account_status, date_of_birth) "
        "VALUES ($1, $2, 'talent', 'active', $3)",
        talent_user_id,
        talent_email,
        dob,
    )
    db.execute(
        """
        INSERT INTO public.talent_profiles
            (id, user_id, display_name, school_name, city, state, graduation_year, categories,
             stripe_account_id, stripe_onboarding_complete)
        VALUES ($1, $2, 'Test Talent', 'Test High', 'Austin', 'TX', 2027, '{gaming}', $3, $4)
        """,
        talent_id,
        talent_user_id,
        "acct_fake_rep" if onboarded else None,
        onboarded,
    )
    return talent_id, talent_user_id


@pytest.fixture()
def brand_headers(auth_headers_factory):
    return auth_headers_factory("brand")


@pytest.fixture()
def onboarded_brand(client, db, brand_headers):
    _seed_brand_user(db)
    response  = client.put("/brands/me", json=_BRAND_PROFILE_BODY, headers=brand_headers)
    assert response .status_code == 200
    return response .json()


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

    class _Transfer:
        @staticmethod
        def create(**kwargs):
            counter["n"] += 1
            calls.append(("Transfer.create", kwargs))
            return SimpleNamespace(id=f"tr_fake{counter['n']}")

    class _Refund:
        @staticmethod
        def create(**kwargs):
            counter["n"] += 1
            calls.append(("Refund.create", kwargs))
            return SimpleNamespace(id=f"re_fake{counter['n']}")

    fake = SimpleNamespace(
        PaymentIntent=_PaymentIntent, Customer=_Customer, Transfer=_Transfer, Refund=_Refund,
        Webhook=stripe.Webhook, calls=calls,
    )
    monkeypatch.setattr(stripe_service, "stripe", fake)
    return fake


def _create_and_activate_campaign(client, brand_headers) -> dict:
    created = client.post("/brands/campaigns", json=_CAMPAIGN_BODY, headers=brand_headers).json()
    client.post(f"/brands/campaigns/{created['id']}/activate", headers=brand_headers)
    return created


def _signed_webhook(settings, event: dict) -> tuple[bytes, str]:
    payload = json.dumps(event).encode()
    header = stripe.WebhookSignature.generate_signature_header(payload=payload.decode(), secret=settings.stripe_webhook_secret)
    return payload, header


# ---------------------------------------------------------------------
# calculate_platform_fee_split -- rounding + invariant
# ---------------------------------------------------------------------


def test_calculate_platform_fee_split_invariant_holds_across_values():
    for amount_cents in [0, 1, 33, 99, 100, 1_000_000, 12_345_679]:
        for percent in [0, 1, 35, 50, 99, 100]:
            platform_cut, talent_payout = payout_service.calculate_platform_fee_split(amount_cents, percent)
            assert platform_cut + talent_payout == amount_cents
            assert platform_cut >= 0
            assert talent_payout >= 0


def test_calculate_platform_fee_split_rounds_half_up():
    # 100 * 35.5 == impossible with int percent, but exercise a case
    # where the raw division lands exactly on .5 before the +50 nudge.
    platform_cut, talent_payout = payout_service.calculate_platform_fee_split(1, 50)
    assert platform_cut == 1  # (1*50+50)//100 == 1, rounds up rather than truncating to 0
    assert talent_payout == 0


def test_calculate_platform_fee_split_rejects_negative_amount():
    with pytest.raises(ValueError):
        payout_service.calculate_platform_fee_split(-1, 35)


# ---------------------------------------------------------------------
# /activate wired to a real Stripe Customer + PaymentIntent
# ---------------------------------------------------------------------


def test_activate_reuses_stripe_customer_id_on_retry(client, db, brand_headers, onboarded_brand, fake_stripe):
    created = client.post("/brands/campaigns", json=_CAMPAIGN_BODY, headers=brand_headers).json()
    client.post(f"/brands/campaigns/{created['id']}/activate", headers=brand_headers)
    db.execute("UPDATE public.campaigns SET status = 'payment_failed' WHERE id = $1", created["id"])
    fake_stripe.calls.clear()

    client.post(f"/brands/campaigns/{created['id']}/retry-payment", headers=brand_headers)
    call_names = [name for name, _ in fake_stripe.calls]
    assert call_names == ["PaymentIntent.create"]  # no second Customer.create


# ---------------------------------------------------------------------
# payment_intent.succeeded / payment_intent.payment_failed
# ---------------------------------------------------------------------


def test_payment_intent_succeeded_activates_campaign(client, db, brand_headers, onboarded_brand, settings, fake_stripe):
    created = _create_and_activate_campaign(client, brand_headers)
    intent_id = db.fetchval("SELECT stripe_payment_intent_id FROM public.campaigns WHERE id = $1", created["id"])

    payload, header = _signed_webhook(
        settings, {"id": "evt_pi_ok", "object": "event", "type": "payment_intent.succeeded", "data": {"object": {"id": intent_id}}}
    )
    response  = client.post("/webhooks/stripe", content=payload, headers={"Stripe-Signature": header})
    assert response .status_code == 200

    status_after = db.fetchval("SELECT status FROM public.campaigns WHERE id = $1", created["id"])
    assert status_after == "active"


def test_payment_intent_failed_reverts_campaign_and_notifies_brand(
    client, db, brand_headers, onboarded_brand, settings, fake_stripe, fake_resend_client
):
    created = _create_and_activate_campaign(client, brand_headers)
    intent_id = db.fetchval("SELECT stripe_payment_intent_id FROM public.campaigns WHERE id = $1", created["id"])

    payload, header = _signed_webhook(
        settings, {"id": "evt_pi_fail", "object": "event", "type": "payment_intent.payment_failed", "data": {"object": {"id": intent_id}}}
    )
    response  = client.post("/webhooks/stripe", content=payload, headers={"Stripe-Signature": header})
    assert response .status_code == 200

    status_after = db.fetchval("SELECT status FROM public.campaigns WHERE id = $1", created["id"])
    assert status_after == "payment_failed"
    assert len(fake_resend_client.sent) == 1
    assert fake_resend_client.sent[0].to == "brand@example.com"


def test_payment_intent_events_for_unknown_intent_are_noop(client, settings):
    payload, header = _signed_webhook(
        settings,
        {"id": "evt_pi_unknown", "object": "event", "type": "payment_intent.succeeded", "data": {"object": {"id": "pi_does_not_exist"}}},
    )
    response  = client.post("/webhooks/stripe", content=payload, headers={"Stripe-Signature": header})
    assert response .status_code == 200


# ---------------------------------------------------------------------
# release_payout (called by POST .../confirm)
# ---------------------------------------------------------------------


def _invited_and_submitted_campaign_rep(client, db, brand_headers, campaign_id, *, onboarded=True) -> tuple[str, str]:
    talent_id, _ = _seed_rep(db, onboarded=onboarded)
    invite_resp = client.post(f"/brands/campaigns/{campaign_id}/talents/invite", json={"talent_ids": [talent_id]}, headers=brand_headers)
    campaign_talent_id = invite_resp.json()[0]["campaign_talent_id"]
    db.execute("UPDATE public.campaign_talents SET status = 'submitted' WHERE id = $1", campaign_talent_id)
    return talent_id, campaign_talent_id


def test_confirm_creates_transfer_for_onboarded_rep(client, db, brand_headers, onboarded_brand, fake_stripe):
    created = client.post("/brands/campaigns", json=_CAMPAIGN_BODY, headers=brand_headers).json()
    talent_id, campaign_talent_id = _invited_and_submitted_campaign_rep(client, db, brand_headers, created["id"], onboarded=True)

    response  = client.post(f"/brands/campaigns/{created['id']}/talents/{talent_id}/confirm", headers=brand_headers)
    assert response .status_code == 200
    body = response .json()
    assert body["status"] == "confirmed"
    assert body["payout_status"] == "processing"

    call_names = [name for name, _ in fake_stripe.calls]
    assert call_names == ["Transfer.create"]
    _, kwargs = fake_stripe.calls[0]
    assert kwargs["destination"] == "acct_fake_rep"
    assert kwargs["amount"] == created["payout_per_talent_cents"]

    stored_transfer_id = db.fetchval("SELECT stripe_transfer_id FROM public.campaign_talents WHERE id = $1", campaign_talent_id)
    assert stored_transfer_id == "tr_fake1"


def test_confirm_leaves_payout_pending_for_non_onboarded_rep(client, db, brand_headers, onboarded_brand, fake_stripe):
    created = client.post("/brands/campaigns", json=_CAMPAIGN_BODY, headers=brand_headers).json()
    talent_id, campaign_talent_id = _invited_and_submitted_campaign_rep(client, db, brand_headers, created["id"], onboarded=False)

    response  = client.post(f"/brands/campaigns/{created['id']}/talents/{talent_id}/confirm", headers=brand_headers)
    assert response .status_code == 200
    body = response .json()
    assert body["status"] == "confirmed"
    assert body["payout_status"] == "pending"
    assert fake_stripe.calls == []


def test_confirm_is_idempotent_against_a_retried_call(client, db, brand_headers, onboarded_brand, fake_stripe):
    created = client.post("/brands/campaigns", json=_CAMPAIGN_BODY, headers=brand_headers).json()
    talent_id, campaign_talent_id = _invited_and_submitted_campaign_rep(client, db, brand_headers, created["id"], onboarded=True)

    first = client.post(f"/brands/campaigns/{created['id']}/talents/{talent_id}/confirm", headers=brand_headers)
    assert first.status_code == 200

    # confirm() itself already guards against a second call (status is
    # no longer 'submitted'), so this must 409 -- and must not create a
    # second Transfer.
    second = client.post(f"/brands/campaigns/{created['id']}/talents/{talent_id}/confirm", headers=brand_headers)
    assert second.status_code == 409

    call_names = [name for name, _ in fake_stripe.calls]
    assert call_names == ["Transfer.create"]


# ---------------------------------------------------------------------
# transfer.paid / transfer.failed
# ---------------------------------------------------------------------


def test_transfer_paid_marks_paid_and_recomputes_talent_totals(client, db, brand_headers, onboarded_brand, settings, fake_stripe):
    created = client.post("/brands/campaigns", json=_CAMPAIGN_BODY, headers=brand_headers).json()
    talent_id, campaign_talent_id = _invited_and_submitted_campaign_rep(client, db, brand_headers, created["id"], onboarded=True)
    client.post(f"/brands/campaigns/{created['id']}/talents/{talent_id}/confirm", headers=brand_headers)
    client.post(f"/brands/campaigns/{created['id']}/talents/{talent_id}/rate", json={"brand_rating": 4}, headers=brand_headers)
    transfer_id = db.fetchval("SELECT stripe_transfer_id FROM public.campaign_talents WHERE id = $1", campaign_talent_id)

    payload, header = _signed_webhook(
        settings, {"id": "evt_tr_paid", "object": "event", "type": "transfer.paid", "data": {"object": {"id": transfer_id}}}
    )
    response  = client.post("/webhooks/stripe", content=payload, headers={"Stripe-Signature": header})
    assert response .status_code == 200

    row = db.fetch(
        "SELECT status, payout_status, paid_at FROM public.campaign_talents WHERE id = $1", campaign_talent_id
    )[0]
    assert row["status"] == "paid"
    assert row["payout_status"] == "paid"
    assert row["paid_at"] is not None

    talent = db.fetch(
        "SELECT brand_campaigns_completed, total_earnings_cents, brand_average_rating FROM public.talent_profiles WHERE id = $1",
        talent_id,
    )[0]
    assert talent["brand_campaigns_completed"] == 1
    assert talent["total_earnings_cents"] == created["payout_per_talent_cents"]
    assert float(talent["brand_average_rating"]) == 4.0


def test_transfer_paid_for_unknown_transfer_is_noop(client, settings):
    payload, header = _signed_webhook(
        settings, {"id": "evt_tr_paid_unknown", "object": "event", "type": "transfer.paid", "data": {"object": {"id": "tr_does_not_exist"}}}
    )
    response  = client.post("/webhooks/stripe", content=payload, headers={"Stripe-Signature": header})
    assert response .status_code == 200


def test_transfer_failed_marks_payout_status_failed(client, db, brand_headers, onboarded_brand, settings, fake_stripe):
    created = client.post("/brands/campaigns", json=_CAMPAIGN_BODY, headers=brand_headers).json()
    talent_id, campaign_talent_id = _invited_and_submitted_campaign_rep(client, db, brand_headers, created["id"], onboarded=True)
    client.post(f"/brands/campaigns/{created['id']}/talents/{talent_id}/confirm", headers=brand_headers)
    transfer_id = db.fetchval("SELECT stripe_transfer_id FROM public.campaign_talents WHERE id = $1", campaign_talent_id)

    payload, header = _signed_webhook(
        settings, {"id": "evt_tr_failed", "object": "event", "type": "transfer.failed", "data": {"object": {"id": transfer_id}}}
    )
    response  = client.post("/webhooks/stripe", content=payload, headers={"Stripe-Signature": header})
    assert response .status_code == 200

    payout_status = db.fetchval("SELECT payout_status FROM public.campaign_talents WHERE id = $1", campaign_talent_id)
    assert payout_status == "failed"
