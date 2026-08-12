"""Build Prompt 16 deliverables 2-3: multi-step integration tests that
walk real endpoint calls across portals, rather than exercising one
route in isolation the way the per-portal unit-test files do.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from datetime import date, timedelta
from types import SimpleNamespace

import jwt
import pytest
import stripe

from app.core.security import PARENT_SESSION_ISSUER
from app.services import stripe_service

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
    "max_reps": 5,
    "budget_cents": 100_000,
    "start_date": (date.today() + timedelta(days=10)).isoformat(),
    "end_date": (date.today() + timedelta(days=40)).isoformat(),
}

_REP_PROFILE_BODY = {
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


def _rep_jwt(settings, *, sub: str, account_status: str = "active") -> dict[str, str]:
    payload = {
        "sub": sub,
        "email": f"{sub}@example.com",
        "aud": "authenticated",
        "app_metadata": {"role": "rep", "account_status": account_status},
        "exp": int(time.time()) + 3600,
    }
    token = jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def _extract_consent_token(html: str) -> str:
    match = re.search(r"/parent/consent/([^\"'<]+)", html)
    assert match, f"no consent link found in email html: {html}"
    return match.group(1)


def _dob_for_age(age: int) -> str:
    today = date.today()
    return date(today.year - age, today.month, 1).isoformat()


def _seed_onboarded_rep_direct(db, *, age: int = 20) -> tuple[str, str]:
    """Directly seed a rep with an active account (no parental consent
    needed) -- used as a participant in the campaign lifecycle test,
    where the thing under test is the campaign flow, not signup."""
    rep_user_id = str(uuid.uuid4())
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
    return rep_user_id, rep_email


@pytest.fixture()
def brand_headers(auth_headers_factory):
    return auth_headers_factory("brand")


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


# ---------------------------------------------------------------------
# 1. Full campaign lifecycle: create -> activate (Stripe charge) ->
#    invite -> accept -> submit -> confirm (Stripe transfer) -> paid.
# ---------------------------------------------------------------------


def test_full_campaign_lifecycle_creation_to_paid_out_rep(client, db, settings, fake_stripe, brand_headers, auth_headers_factory):
    # Brand onboards and creates+activates a campaign (real PaymentIntent
    # via the faked Stripe client, exercised through /activate).
    db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", BRAND_USER_ID, "brand@example.com")
    db.execute(
        "INSERT INTO public.users (id, email, role, account_status, date_of_birth) "
        "VALUES ($1, 'brand@example.com', 'brand', 'active', '1990-01-01')",
        BRAND_USER_ID,
    )
    onboarded = client.put("/brands/me", json=_BRAND_PROFILE_BODY, headers=brand_headers)
    assert onboarded.status_code == 200

    created = client.post("/brands/campaigns", json=_CAMPAIGN_BODY, headers=brand_headers).json()
    activate = client.post(f"/brands/campaigns/{created['id']}/activate", headers=brand_headers)
    assert activate.status_code == 200
    assert activate.json()["status"] == "pending_payment"

    intent_id = db.fetchval("SELECT stripe_payment_intent_id FROM public.campaigns WHERE id = $1", created["id"])
    assert intent_id is not None

    # Stripe confirms the charge -- webhook flips the campaign active.
    payload = json.dumps(
        {"id": "evt_lifecycle_pi_ok", "object": "event", "type": "payment_intent.succeeded", "data": {"object": {"id": intent_id}}}
    ).encode()
    header = stripe.WebhookSignature.generate_signature_header(payload=payload.decode(), secret=settings.stripe_webhook_secret)
    webhook_resp = client.post("/webhooks/stripe", content=payload, headers={"Stripe-Signature": header})
    assert webhook_resp.status_code == 200
    assert db.fetchval("SELECT status FROM public.campaigns WHERE id = $1", created["id"]) == "active"

    # Rep onboards, discovers the now-active campaign, applies, and is
    # accepted (FTC disclosure required to unlock submission).
    rep_user_id, _ = _seed_onboarded_rep_direct(db)
    rep_headers = _rep_jwt(settings, sub=rep_user_id)

    profile = client.put("/reps/me", json=_REP_PROFILE_BODY, headers=rep_headers)
    assert profile.status_code == 200

    available = client.get("/reps/campaigns/available", headers=rep_headers)
    assert created["id"] in [c["id"] for c in available.json()]

    apply_resp = client.post(f"/campaigns/{created['id']}/apply", headers=rep_headers)
    assert apply_resp.status_code == 201
    assert apply_resp.json()["status"] == "invited"

    accept_resp = client.post(
        f"/campaigns/{created['id']}/accept", json={"ftc_disclosure_accepted": True}, headers=rep_headers
    )
    assert accept_resp.status_code == 200
    assert accept_resp.json()["status"] == "accepted"

    submit_resp = client.post(
        f"/campaigns/{created['id']}/submit",
        json={"submission_text": "Posted!", "submission_file_urls": []},
        headers=rep_headers,
    )
    assert submit_resp.status_code == 200
    assert submit_resp.json()["status"] == "submitted"

    # Rep completes Stripe Connect onboarding so confirm() can pay them out.
    rep_id = db.fetchval("SELECT id FROM public.rep_profiles WHERE user_id = $1", rep_user_id)
    db.execute(
        "UPDATE public.rep_profiles SET stripe_account_id = 'acct_fake_lifecycle', stripe_onboarding_complete = TRUE WHERE id = $1",
        rep_id,
    )

    fake_stripe.calls.clear()
    confirm_resp = client.post(f"/brands/campaigns/{created['id']}/reps/{rep_id}/confirm", headers=brand_headers)
    assert confirm_resp.status_code == 200
    confirm_body = confirm_resp.json()
    assert confirm_body["status"] == "confirmed"
    assert confirm_body["payout_status"] == "processing"

    call_names = [name for name, _ in fake_stripe.calls]
    assert call_names == ["Transfer.create"]
    transfer_id = db.fetchval("SELECT stripe_transfer_id FROM public.campaign_reps WHERE rep_id = $1 AND campaign_id = $2", rep_id, created["id"])
    assert transfer_id is not None

    # Stripe reports the transfer paid -- rep's campaign_reps row and
    # cached rep_profiles totals reflect a completed, paid-out engagement.
    payload2 = json.dumps(
        {"id": "evt_lifecycle_tr_paid", "object": "event", "type": "transfer.paid", "data": {"object": {"id": transfer_id}}}
    ).encode()
    header2 = stripe.WebhookSignature.generate_signature_header(payload=payload2.decode(), secret=settings.stripe_webhook_secret)
    webhook_resp2 = client.post("/webhooks/stripe", content=payload2, headers={"Stripe-Signature": header2})
    assert webhook_resp2.status_code == 200

    final = db.fetch(
        "SELECT status, payout_status, paid_at FROM public.campaign_reps WHERE rep_id = $1 AND campaign_id = $2",
        rep_id,
        created["id"],
    )[0]
    assert final["status"] == "paid"
    assert final["payout_status"] == "paid"
    assert final["paid_at"] is not None

    rep_totals = db.fetch(
        "SELECT total_campaigns_completed, total_earnings_cents FROM public.rep_profiles WHERE id = $1", rep_id
    )[0]
    assert rep_totals["total_campaigns_completed"] == 1
    assert rep_totals["total_earnings_cents"] == created["payout_per_rep_cents"]


# ---------------------------------------------------------------------
# 2. Parental-consent signup-to-active flow, end to end through real
#    endpoints, finishing with an authenticated rep-only call.
# ---------------------------------------------------------------------


def test_parental_consent_signup_to_active_rep_can_use_authenticated_endpoint(client, db, settings, fake_resend_client):
    signup_resp = client.post(
        "/auth/signup",
        json={
            "email": "under16@example.com",
            "password": "correct-horse-battery",
            "role": "rep",
            "date_of_birth": _dob_for_age(15),
            "parent_email": "parent-of-under16@example.com",
        },
    )
    assert signup_resp.status_code == 201
    signup_body = signup_resp.json()
    assert signup_body["account_status"] == "pending"
    rep_user_id = signup_body["id"]

    # Pending account cannot yet use a rep-only endpoint.
    pending_headers = _rep_jwt(settings, sub=rep_user_id, account_status="pending")
    blocked = client.put("/reps/me", json=_REP_PROFILE_BODY, headers=pending_headers)
    assert blocked.status_code == 403

    # Parent receives the consent email and clicks the verify link.
    assert len(fake_resend_client.sent) == 1
    sent = fake_resend_client.sent[0]
    assert sent.to == "parent-of-under16@example.com"
    token = _extract_consent_token(sent.html)

    verify_resp = client.post(f"/auth/parent-verify/{token}")
    assert verify_resp.status_code == 200
    assert verify_resp.json()["account_status"] == "active"
    assert db.fetchval("SELECT account_status FROM public.users WHERE id = $1", rep_user_id) == "active"

    # Account is now active -- the rep can hit an authenticated,
    # rep-only endpoint successfully.
    active_headers = _rep_jwt(settings, sub=rep_user_id, account_status="active")
    profile_resp = client.put("/reps/me", json=_REP_PROFILE_BODY, headers=active_headers)
    assert profile_resp.status_code == 200
    assert profile_resp.json()["display_name"] == "Test Rep"


# ---------------------------------------------------------------------
# 3. Parent portal campaign approval flow: approve unlocks accept,
#    block keeps a campaign out of the rep's available list.
# ---------------------------------------------------------------------


def test_parent_portal_approval_flow_approve_unlocks_accept_and_block_hides_campaign(
    client, db, settings, fake_resend_client, seed_rep_with_parent, seed_pending_campaign, auth_headers_factory
):
    seeded = seed_rep_with_parent(age=15, campaign_approval_required=True)
    rep_headers = _rep_jwt(settings, sub=seeded.rep_user_id)

    parent_payload = {
        "parent_id": seeded.parent_id,
        "rep_id": seeded.rep_id,
        "iss": PARENT_SESSION_ISSUER,
        "exp": int(time.time()) + 3600,
    }
    parent_token = jwt.encode(parent_payload, settings.parent_session_secret, algorithm="HS256")
    parent_headers = {"Authorization": f"Bearer {parent_token}"}

    # Campaign 1: rep is invited to a campaign requiring parent approval.
    campaign_id_1 = seed_pending_campaign(rep_id=seeded.rep_id, target_categories=["gaming"])

    pending = client.get("/parent/campaigns/pending", headers=parent_headers)
    assert pending.status_code == 200
    assert len(pending.json()) == 1

    # Rep cannot accept while parent approval is still pending.
    blocked_accept = client.post(
        f"/campaigns/{campaign_id_1}/accept", json={"ftc_disclosure_accepted": True}, headers=rep_headers
    )
    assert blocked_accept.status_code == 403
    assert blocked_accept.json()["error"]["code"] == "awaiting_parent_approval"

    approve_resp = client.post(f"/parent/campaigns/{campaign_id_1}/approve", headers=parent_headers)
    assert approve_resp.status_code == 200
    assert approve_resp.json()["parent_approval_status"] == "approved"

    accept_resp = client.post(
        f"/campaigns/{campaign_id_1}/accept", json={"ftc_disclosure_accepted": True}, headers=rep_headers
    )
    assert accept_resp.status_code == 200
    assert accept_resp.json()["status"] == "accepted"

    # Campaign 2: rep applies to a different campaign requiring approval,
    # visible in "available" until applied, then parent blocks it.
    campaign_id_2 = seed_pending_campaign(rep_id=seeded.rep_id, target_categories=["gaming"])
    # seed_pending_campaign always creates its own campaign_reps invite
    # row for `rep_id` -- delete it so we can drive the "apply" step
    # through the real endpoint instead, matching the flow under test.
    db.execute("DELETE FROM public.campaign_reps WHERE campaign_id = $1", campaign_id_2)

    available_before = client.get("/reps/campaigns/available", headers=rep_headers)
    assert available_before.status_code == 200
    assert campaign_id_2 in [c["id"] for c in available_before.json()]

    apply_resp = client.post(f"/campaigns/{campaign_id_2}/apply", headers=rep_headers)
    assert apply_resp.status_code == 201
    assert apply_resp.json()["parent_approval_status"] == "pending"

    block_resp = client.post(f"/parent/campaigns/{campaign_id_2}/block", headers=parent_headers)
    assert block_resp.status_code == 200
    assert block_resp.json()["parent_approval_status"] == "blocked"

    available_after = client.get("/reps/campaigns/available", headers=rep_headers)
    assert available_after.status_code == 200
    assert campaign_id_2 not in [c["id"] for c in available_after.json()]
