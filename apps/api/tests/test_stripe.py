from __future__ import annotations

import asyncio
import json
from datetime import date
from types import SimpleNamespace

import pytest
import stripe

from app.services import stripe_service

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


def _seed_rep_user(db, *, age: int = 20) -> None:
    dob = date(date.today().year - age, 6, 1)
    db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", REP_USER_ID, "rep@example.com")
    db.execute(
        "INSERT INTO public.users (id, email, role, account_status, date_of_birth) "
        "VALUES ($1, 'rep@example.com', 'rep', 'active', $2)",
        REP_USER_ID,
        dob,
    )


@pytest.fixture()
def rep_headers(auth_headers_factory):
    return auth_headers_factory("rep")


class FakeStripeAccount:
    def __init__(self, id: str):
        self.id = id


class FakeStripeAccountLink:
    def __init__(self, url: str):
        self.url = url


class FakeStripeCustomer:
    def __init__(self, id: str):
        self.id = id


@pytest.fixture()
def fake_stripe(monkeypatch):
    """Records every call made through app.services.stripe_service's
    `stripe` module reference and returns scripted resource objects,
    mirroring the shape of real stripe.Account/.Customer/.AccountLink
    responses (an `.id`/`.url` attribute) without any network call."""
    calls: list[tuple[str, dict]] = []

    class _Account:
        @staticmethod
        def create(**kwargs):
            calls.append(("Account.create", kwargs))
            return FakeStripeAccount("acct_fake123")

    class _AccountLink:
        @staticmethod
        def create(**kwargs):
            calls.append(("AccountLink.create", kwargs))
            return FakeStripeAccountLink("https://connect.stripe.com/setup/fake")

    class _Customer:
        @staticmethod
        def create(**kwargs):
            calls.append(("Customer.create", kwargs))
            return FakeStripeCustomer("cus_fake123")

    # Webhook is the real stripe.Webhook -- only Account/AccountLink/
    # Customer creation is faked here, so signature verification in
    # tests that exercise both onboarding and a webhook in one flow
    # still does real HMAC verification, not a stub.
    fake = SimpleNamespace(
        Account=_Account, AccountLink=_AccountLink, Customer=_Customer, Webhook=stripe.Webhook, calls=calls
    )
    monkeypatch.setattr(stripe_service, "stripe", fake)
    return fake


# ---------------------------------------------------------------------
# stripe_service unit tests
# ---------------------------------------------------------------------


def test_create_customer_passes_email_and_metadata(settings, fake_stripe):
    customer_id = asyncio.run(
        stripe_service.create_customer(settings, email="brand@example.com", metadata={"role": "brand"})
    )
    assert customer_id == "cus_fake123"
    name, kwargs = fake_stripe.calls[0]
    assert name == "Customer.create"
    assert kwargs["email"] == "brand@example.com"
    assert kwargs["metadata"] == {"role": "brand"}


def test_create_connect_account_is_individual_express_with_transfers(settings, fake_stripe):
    account_id = asyncio.run(
        stripe_service.create_connect_account(settings, email="rep@example.com", metadata={"user_id": "u1"})
    )
    assert account_id == "acct_fake123"
    name, kwargs = fake_stripe.calls[0]
    assert name == "Account.create"
    assert kwargs["type"] == "express"
    assert kwargs["business_type"] == "individual"
    assert kwargs["capabilities"] == {"transfers": {"requested": True}}
    # No date of birth collected here -- see docs/stripe-minors-policy.md:
    # Stripe's hosted onboarding collects DOB and surfaces the
    # Representative requirement itself.
    assert "dob" not in kwargs
    assert "individual" not in kwargs


def test_create_connect_onboarding_link_returns_url(settings, fake_stripe):
    url = asyncio.run(
        stripe_service.create_connect_onboarding_link(
            settings,
            account_id="acct_fake123",
            refresh_url="https://app.example.com/onboard",
            return_url="https://app.example.com/done",
        )
    )
    assert url == "https://connect.stripe.com/setup/fake"
    name, kwargs = fake_stripe.calls[0]
    assert kwargs["account"] == "acct_fake123"
    assert kwargs["type"] == "account_onboarding"


def test_verify_webhook_signature_accepts_validly_signed_payload(settings):
    payload = json.dumps({"id": "evt_1", "object": "event", "type": "account.updated", "data": {"object": {}}}).encode()
    header = stripe.WebhookSignature.generate_signature_header(payload=payload.decode(), secret=settings.stripe_webhook_secret)
    event = stripe_service.verify_webhook_signature(settings, payload=payload, signature_header=header)
    assert event["type"] == "account.updated"


def test_verify_webhook_signature_rejects_forged_payload(settings):
    payload = json.dumps({"id": "evt_1", "object": "event", "type": "account.updated", "data": {"object": {}}}).encode()
    header = stripe.WebhookSignature.generate_signature_header(payload=payload.decode(), secret="wrong-secret-entirely")
    with pytest.raises(stripe.SignatureVerificationError):
        stripe_service.verify_webhook_signature(settings, payload=payload, signature_header=header)


# ---------------------------------------------------------------------
# POST /reps/stripe/onboarding
# ---------------------------------------------------------------------


def test_stripe_onboarding_creates_account_on_first_call(client, db, rep_headers, fake_stripe):
    _seed_rep_user(db)
    client.put("/reps/me", json=_BASE_PROFILE_BODY, headers=rep_headers)

    response = client.post("/reps/stripe/onboarding", headers=rep_headers)
    assert response.status_code == 200
    assert response.json()["url"] == "https://connect.stripe.com/setup/fake"

    stored = db.fetchval("SELECT stripe_account_id FROM public.rep_profiles WHERE user_id = $1", REP_USER_ID)
    assert stored == "acct_fake123"
    call_names = [name for name, _ in fake_stripe.calls]
    assert call_names == ["Account.create", "AccountLink.create"]


def test_stripe_onboarding_reuses_existing_account_on_second_call(client, db, rep_headers, fake_stripe):
    _seed_rep_user(db)
    client.put("/reps/me", json=_BASE_PROFILE_BODY, headers=rep_headers)

    client.post("/reps/stripe/onboarding", headers=rep_headers)
    fake_stripe.calls.clear()

    response = client.post("/reps/stripe/onboarding", headers=rep_headers)
    assert response.status_code == 200
    # Second call must not create a second Stripe account -- only a
    # fresh onboarding link for the account created on the first call.
    call_names = [name for name, _ in fake_stripe.calls]
    assert call_names == ["AccountLink.create"]
    name, kwargs = fake_stripe.calls[0]
    assert kwargs["account"] == "acct_fake123"


def test_stripe_onboarding_requires_rep_profile_first(client, db, rep_headers, fake_stripe):
    _seed_rep_user(db)
    # No PUT /reps/me -- onboarding not completed, no rep_profiles row yet.
    response = client.post("/reps/stripe/onboarding", headers=rep_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "rep_profile_not_found"


# ---------------------------------------------------------------------
# POST /webhooks/stripe
# ---------------------------------------------------------------------


def _signed_webhook(settings, event: dict) -> tuple[bytes, str]:
    payload = json.dumps(event).encode()
    header = stripe.WebhookSignature.generate_signature_header(payload=payload.decode(), secret=settings.stripe_webhook_secret)
    return payload, header


def test_webhook_rejects_invalid_signature_before_business_logic(client, db, settings):
    payload, _ = _signed_webhook(
        settings, {"id": "evt_1", "object": "event", "type": "account.updated", "data": {"object": {"id": "acct_x"}}}
    )
    response = client.post(
        "/webhooks/stripe", content=payload, headers={"Stripe-Signature": "t=1,v1=deadbeef"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_signature"


def test_webhook_rejects_missing_signature_header(client):
    response = client.post("/webhooks/stripe", content=b"{}")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "missing_signature"


def test_webhook_account_updated_marks_onboarding_complete(client, db, rep_headers, settings, fake_stripe):
    _seed_rep_user(db)
    client.put("/reps/me", json=_BASE_PROFILE_BODY, headers=rep_headers)
    client.post("/reps/stripe/onboarding", headers=rep_headers)  # creates acct_fake123

    before = db.fetchval("SELECT stripe_onboarding_complete FROM public.rep_profiles WHERE user_id = $1", REP_USER_ID)
    assert before is False

    payload, header = _signed_webhook(
        settings,
        {
            "id": "evt_1",
            "object": "event",
            "type": "account.updated",
            "data": {"object": {"id": "acct_fake123", "charges_enabled": True, "payouts_enabled": True}},
        },
    )
    response = client.post("/webhooks/stripe", content=payload, headers={"Stripe-Signature": header})
    assert response.status_code == 200

    after = db.fetchval("SELECT stripe_onboarding_complete FROM public.rep_profiles WHERE user_id = $1", REP_USER_ID)
    assert after is True


def test_webhook_account_updated_for_unknown_account_is_a_noop(client, settings):
    payload, header = _signed_webhook(
        settings,
        {
            "id": "evt_1",
            "object": "event",
            "type": "account.updated",
            "data": {"object": {"id": "acct_does_not_exist", "charges_enabled": True, "payouts_enabled": True}},
        },
    )
    response = client.post("/webhooks/stripe", content=payload, headers={"Stripe-Signature": header})
    assert response.status_code == 200


def test_webhook_unregistered_event_type_returns_200(client, settings):
    payload, header = _signed_webhook(settings, {"id": "evt_1", "object": "event", "type": "some.future.event", "data": {"object": {}}})
    response = client.post("/webhooks/stripe", content=payload, headers={"Stripe-Signature": header})
    assert response.status_code == 200


def test_webhook_stub_events_return_200_without_error(client, settings):
    for event_type in ["payment_intent.succeeded", "transfer.failed", "customer.subscription.created"]:
        payload, header = _signed_webhook(settings, {"id": "evt_1", "object": "event", "type": event_type, "data": {"object": {}}})
        response = client.post("/webhooks/stripe", content=payload, headers={"Stripe-Signature": header})
        assert response.status_code == 200, event_type
