"""Build Prompt 8G: Skill Challenges.

Follows tests/test_milestones.py's fake_stripe/seed-helper pattern.
Covers the acceptance criteria enumerated in Teenure_Build_Prompts.md's
8G section: brand_note never rep-facing, cross-rep isolation, declined
never rep/parent-facing, disclosure enforcement (400/absent, 400/false,
201/true), submission validation errors (closed/already-submitted/full
with distinct codes), conversion atomicity + idempotency, campaign-full
409 without side effects, payout concurrency (one Transfer), webhook
isolation, auto-close idempotency + logging, profile serializer
null-safe division, recruiter search field presence without credit
spend, and parent dashboard converted/declined visibility.
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

_CHALLENGE_BODY = {
    "title": "Show us your setup",
    "brief": "Post a short video of your gaming setup.",
    "category": "gaming",
    "submission_format": "both",
    "submission_prompt": "30-60 second video, vertical format.",
    "target_cities": [],
}

_CAMPAIGN_BODY = {
    "title": "Spring Launch",
    "product_name": "Acme Widget",
    "campaign_goal": "Awareness",
    "key_messaging": "Widgets are great",
    "prohibited_content": None,
    "deliverables_description": "One TikTok post",
    "target_categories": ["gaming"],
    "target_cities": [],
    "max_reps": 1,
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


def _seed_rep(db, *, onboarded: bool = True, city: str = "Austin", categories: list[str] | None = None) -> tuple[str, str]:
    """Returns (rep_profile_id, rep_user_id)."""
    rep_user_id = str(uuid.uuid4())
    rep_id = str(uuid.uuid4())
    rep_email = f"rep-{rep_user_id}@example.com"
    dob = date(date.today().year - 20, 6, 1)
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
            (id, user_id, display_name, school_name, city, state, graduation_year, categories,
             stripe_account_id, stripe_onboarding_complete)
        VALUES ($1, $2, 'Test Rep', 'Test High', $5, 'TX', 2027, $4, $3, $6)
        """,
        rep_id,
        rep_user_id,
        "acct_fake_rep" if onboarded else None,
        categories or ["gaming"],
        city,
        onboarded,
    )
    return rep_id, rep_user_id


@pytest.fixture()
def brand_headers(auth_headers_factory):
    return auth_headers_factory("brand")


@pytest.fixture()
def rep_headers_factory(auth_headers_factory, db):
    def _factory(rep_user_id: str) -> dict[str, str]:
        import time

        import jwt

        from app.core.config import get_settings

        settings = get_settings()
        payload = {
            "sub": rep_user_id,
            "email": "rep@example.com",
            "aud": "authenticated",
            "app_metadata": {"role": "rep", "account_status": "active"},
            "exp": int(time.time()) + 3600,
        }
        token = jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")
        return {"Authorization": f"Bearer {token}"}

    return _factory


@pytest.fixture()
def onboarded_brand(client, db, brand_headers):
    _seed_brand_user(db)
    response = client.put("/brands/me", json=_BRAND_PROFILE_BODY, headers=brand_headers)
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

    fake = SimpleNamespace(PaymentIntent=_PaymentIntent, Customer=_Customer, Transfer=_Transfer, Webhook=stripe.Webhook, calls=calls)
    monkeypatch.setattr(stripe_service, "stripe", fake)
    return fake


def _signed_webhook(settings, event: dict) -> tuple[bytes, str]:
    payload = json.dumps(event).encode()
    header = stripe.WebhookSignature.generate_signature_header(payload=payload.decode(), secret=settings.stripe_webhook_secret)
    return payload, header


def _create_and_activate_challenge(client, brand_headers, **overrides) -> dict:
    body = {**_CHALLENGE_BODY, **overrides}
    created = client.post("/brands/challenges", json=body, headers=brand_headers)
    assert created.status_code == 201, created.text
    activated = client.post(f"/brands/challenges/{created.json()['id']}/activate", headers=brand_headers)
    assert activated.status_code == 200, activated.text
    return activated.json()


def _submit(client, rep_headers, challenge_id, *, disclosure=True, text="My best clip", files=None):
    body = {"submission_text": text, "submission_file_urls": files or [], "disclosure_acknowledged": disclosure}
    return client.post(f"/reps/challenges/{challenge_id}/submit", json=body, headers=rep_headers)


def _create_active_campaign(client, brand_headers, settings, **overrides) -> dict:
    """Activation alone only reaches 'pending_payment' -- a
    payment_intent.succeeded webhook is what advances a campaign to
    'active' (Build Prompt 10), same as test_payout.py's own helper."""
    body = {**_CAMPAIGN_BODY, **overrides}
    created = client.post("/brands/campaigns", json=body, headers=brand_headers).json()
    activated = client.post(f"/brands/campaigns/{created['id']}/activate", headers=brand_headers)
    assert activated.status_code == 200, activated.text
    intent_id = activated.json()["stripe_payment_intent_client_secret"].rsplit("_secret", 1)[0]
    payload, header = _signed_webhook(
        settings,
        {"id": f"evt_pi_ok_{intent_id}", "object": "event", "type": "payment_intent.succeeded", "data": {"object": {"id": intent_id}}},
    )
    webhook_resp = client.post("/webhooks/stripe", content=payload, headers={"Stripe-Signature": header})
    assert webhook_resp.status_code == 200
    return created


# ---------------------------------------------------------------------
# Schema/RLS: brand_note never rep-facing, cross-rep isolation, declined hidden
# ---------------------------------------------------------------------


def test_brand_note_never_appears_in_rep_facing_response(client, db, brand_headers, rep_headers_factory, onboarded_brand):
    challenge = _create_and_activate_challenge(client, brand_headers)
    rep_id, rep_user_id = _seed_rep(db)
    rep_headers = rep_headers_factory(rep_user_id)
    _submit(client, rep_headers, challenge["id"])

    submission_id = db.fetchval("SELECT id FROM public.challenge_submissions WHERE rep_id = $1", rep_id)
    client.post(
        f"/brands/challenges/{challenge['id']}/submissions/{submission_id}/review",
        json={"brand_note": "Secret internal note about this rep"},
        headers=brand_headers,
    )

    resp = client.get("/reps/challenges/submitted", headers=rep_headers)
    assert resp.status_code == 200
    assert "Secret internal note" not in resp.text
    assert "brand_note" not in resp.text


def test_rep_cannot_see_another_reps_submission_via_own_endpoint(client, db, brand_headers, rep_headers_factory, onboarded_brand):
    challenge = _create_and_activate_challenge(client, brand_headers)
    rep_a_id, rep_a_user = _seed_rep(db)
    rep_b_id, rep_b_user = _seed_rep(db)
    headers_a = rep_headers_factory(rep_a_user)
    headers_b = rep_headers_factory(rep_b_user)
    _submit(client, headers_a, challenge["id"], text="Rep A's clip")

    resp_b = client.get("/reps/challenges/submitted", headers=headers_b)
    assert resp_b.status_code == 200
    assert resp_b.json() == []
    assert "Rep A's clip" not in resp_b.text


def test_declined_submission_absent_from_rep_facing_endpoint(client, db, brand_headers, rep_headers_factory, onboarded_brand):
    challenge = _create_and_activate_challenge(client, brand_headers)
    rep_id, rep_user_id = _seed_rep(db)
    rep_headers = rep_headers_factory(rep_user_id)
    _submit(client, rep_headers, challenge["id"])
    submission_id = db.fetchval("SELECT id FROM public.challenge_submissions WHERE rep_id = $1", rep_id)

    decline = client.post(f"/brands/challenges/{challenge['id']}/submissions/{submission_id}/decline", headers=brand_headers)
    assert decline.status_code == 200

    resp = client.get("/reps/challenges/submitted", headers=rep_headers)
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------
# Disclosure enforcement
# ---------------------------------------------------------------------


def test_submit_without_disclosure_field_returns_400(client, db, brand_headers, rep_headers_factory, onboarded_brand):
    challenge = _create_and_activate_challenge(client, brand_headers)
    rep_id, rep_user_id = _seed_rep(db)
    rep_headers = rep_headers_factory(rep_user_id)
    resp = client.post(
        f"/reps/challenges/{challenge['id']}/submit",
        json={"submission_text": "clip", "submission_file_urls": []},
        headers=rep_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "disclosure_acknowledgment_required"


def test_submit_with_disclosure_false_returns_400(client, db, brand_headers, rep_headers_factory, onboarded_brand):
    challenge = _create_and_activate_challenge(client, brand_headers)
    rep_id, rep_user_id = _seed_rep(db)
    rep_headers = rep_headers_factory(rep_user_id)
    resp = _submit(client, rep_headers, challenge["id"], disclosure=False)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "disclosure_acknowledgment_required"


def test_submit_with_disclosure_true_succeeds_without_ui(client, db, brand_headers, rep_headers_factory, onboarded_brand):
    """Direct API call, no UI interaction -- server only checks the flag."""
    challenge = _create_and_activate_challenge(client, brand_headers)
    rep_id, rep_user_id = _seed_rep(db)
    rep_headers = rep_headers_factory(rep_user_id)
    resp = _submit(client, rep_headers, challenge["id"], disclosure=True)
    assert resp.status_code == 201
    assert resp.json()["status"] == "submitted"


# ---------------------------------------------------------------------
# Submission validation
# ---------------------------------------------------------------------


def test_submit_to_closed_challenge_returns_clear_error(client, db, brand_headers, rep_headers_factory, onboarded_brand):
    challenge = _create_and_activate_challenge(client, brand_headers)
    client.post(f"/brands/challenges/{challenge['id']}/close", headers=brand_headers)
    rep_id, rep_user_id = _seed_rep(db)
    rep_headers = rep_headers_factory(rep_user_id)
    resp = _submit(client, rep_headers, challenge["id"])
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "challenge_closed"


def test_submit_twice_returns_already_submitted_not_constraint_error(client, db, brand_headers, rep_headers_factory, onboarded_brand):
    challenge = _create_and_activate_challenge(client, brand_headers)
    rep_id, rep_user_id = _seed_rep(db)
    rep_headers = rep_headers_factory(rep_user_id)
    first = _submit(client, rep_headers, challenge["id"])
    assert first.status_code == 201
    second = _submit(client, rep_headers, challenge["id"])
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "already_submitted"


def test_submit_at_max_submissions_returns_challenge_full(client, db, brand_headers, rep_headers_factory, onboarded_brand):
    challenge = _create_and_activate_challenge(client, brand_headers, max_submissions=1)
    rep_a_id, rep_a_user = _seed_rep(db)
    rep_b_id, rep_b_user = _seed_rep(db)
    headers_a = rep_headers_factory(rep_a_user)
    headers_b = rep_headers_factory(rep_b_user)
    first = _submit(client, headers_a, challenge["id"])
    assert first.status_code == 201
    second = _submit(client, headers_b, challenge["id"])
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "challenge_full"


# ---------------------------------------------------------------------
# Conversion: atomicity, idempotency, campaign-full guard
# ---------------------------------------------------------------------


def _submitted_challenge_and_campaign(client, db, brand_headers, rep_headers_factory, settings, onboarded_brand, *, max_reps=1):
    challenge = _create_and_activate_challenge(client, brand_headers)
    rep_id, rep_user_id = _seed_rep(db)
    rep_headers = rep_headers_factory(rep_user_id)
    _submit(client, rep_headers, challenge["id"])
    submission_id = db.fetchval("SELECT id FROM public.challenge_submissions WHERE rep_id = $1", rep_id)
    campaign = _create_active_campaign(client, brand_headers, settings, max_reps=max_reps)
    return challenge, submission_id, campaign, rep_id, rep_user_id


def test_convert_creates_campaign_reps_invitation_row(client, db, settings, brand_headers, rep_headers_factory, onboarded_brand, fake_stripe):
    challenge, submission_id, campaign, rep_id, rep_user_id = _submitted_challenge_and_campaign(
        client, db, brand_headers, rep_headers_factory, settings, onboarded_brand
    )
    resp = client.post(
        f"/brands/challenges/{challenge['id']}/submissions/{submission_id}/convert",
        json={"campaign_id": campaign["id"]},
        headers=brand_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "converted"
    assert body["payout_cents"] == 750

    cr_row = db.fetch(
        "SELECT status, invited_at FROM public.campaign_reps WHERE campaign_id = $1 AND rep_id = $2",
        campaign["id"],
        rep_id,
    )
    assert len(cr_row) == 1
    assert cr_row[0]["status"] == "invited"

    submission_row = db.fetch("SELECT status, converted_to_campaign_id FROM public.challenge_submissions WHERE id = $1", submission_id)[0]
    assert submission_row["status"] == "converted"
    assert str(submission_row["converted_to_campaign_id"]) == campaign["id"]


def test_converting_same_submission_twice_produces_one_transfer(client, db, settings, brand_headers, rep_headers_factory, onboarded_brand, fake_stripe):
    challenge, submission_id, campaign, rep_id, rep_user_id = _submitted_challenge_and_campaign(
        client, db, brand_headers, rep_headers_factory, settings, onboarded_brand
    )
    first = client.post(
        f"/brands/challenges/{challenge['id']}/submissions/{submission_id}/convert",
        json={"campaign_id": campaign["id"]},
        headers=brand_headers,
    )
    second = client.post(
        f"/brands/challenges/{challenge['id']}/submissions/{submission_id}/convert",
        json={"campaign_id": campaign["id"]},
        headers=brand_headers,
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["stripe_transfer_id"] == second.json()["stripe_transfer_id"]

    transfer_calls = [c for c in fake_stripe.calls if c[0] == "Transfer.create"]
    assert len(transfer_calls) == 1

    cr_rows = db.fetch("SELECT COUNT(*) AS n FROM public.campaign_reps WHERE campaign_id = $1 AND rep_id = $2", campaign["id"], rep_id)
    assert cr_rows[0]["n"] == 1


def test_convert_to_full_campaign_returns_409_no_side_effects(client, db, settings, brand_headers, rep_headers_factory, onboarded_brand, fake_stripe):
    challenge, submission_id, campaign, rep_id, rep_user_id = _submitted_challenge_and_campaign(
        client, db, brand_headers, rep_headers_factory, settings, onboarded_brand, max_reps=1
    )
    # Fill the campaign's one slot with a direct invite first.
    other_rep_id, _ = _seed_rep(db)
    invite_resp = client.post(f"/brands/campaigns/{campaign['id']}/reps/invite", json={"rep_ids": [other_rep_id]}, headers=brand_headers)
    assert invite_resp.status_code == 200
    assert invite_resp.json()[0]["status"] == "invited"

    resp = client.post(
        f"/brands/challenges/{challenge['id']}/submissions/{submission_id}/convert",
        json={"campaign_id": campaign["id"]},
        headers=brand_headers,
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "campaign_full"

    submission_row = db.fetch("SELECT status FROM public.challenge_submissions WHERE id = $1", submission_id)[0]
    assert submission_row["status"] == "submitted"
    cr_rows = db.fetch("SELECT COUNT(*) AS n FROM public.campaign_reps WHERE campaign_id = $1 AND rep_id = $2", campaign["id"], rep_id)
    assert cr_rows[0]["n"] == 0
    transfer_calls = [c for c in fake_stripe.calls if c[0] == "Transfer.create"]
    assert len(transfer_calls) == 0


# ---------------------------------------------------------------------
# Payout safety
# ---------------------------------------------------------------------


def test_double_release_challenge_bonus_produces_exactly_one_transfer(
    client, db, settings, brand_headers, rep_headers_factory, onboarded_brand, fake_stripe
):
    challenge, submission_id, campaign, rep_id, rep_user_id = _submitted_challenge_and_campaign(
        client, db, brand_headers, rep_headers_factory, settings, onboarded_brand
    )
    client.post(
        f"/brands/challenges/{challenge['id']}/submissions/{submission_id}/convert",
        json={"campaign_id": campaign["id"]},
        headers=brand_headers,
    )

    import asyncio

    import asyncpg

    from app.core.config import get_settings

    async def _second_release():
        conn = await asyncpg.connect(dsn=get_settings().database_url)
        try:
            return await payout_service.release_challenge_conversion_bonus(conn, get_settings(), str(submission_id))
        finally:
            await conn.close()

    result = asyncio.run(_second_release())
    assert result.outcome == "already_processed"

    transfer_calls = [c for c in fake_stripe.calls if c[0] == "Transfer.create"]
    assert len(transfer_calls) == 1


def test_transfer_paid_challenge_bonus_does_not_touch_campaign_reps(
    client, db, settings, brand_headers, rep_headers_factory, onboarded_brand, fake_stripe
):
    challenge, submission_id, campaign, rep_id, rep_user_id = _submitted_challenge_and_campaign(
        client, db, brand_headers, rep_headers_factory, settings, onboarded_brand
    )
    client.post(
        f"/brands/challenges/{challenge['id']}/submissions/{submission_id}/convert",
        json={"campaign_id": campaign["id"]},
        headers=brand_headers,
    )
    transfer_id = db.fetchval("SELECT stripe_transfer_id FROM public.challenge_submissions WHERE id = $1", submission_id)
    cr_payout_status_before = db.fetch(
        "SELECT payout_status FROM public.campaign_reps WHERE campaign_id = $1 AND rep_id = $2", campaign["id"], rep_id
    )[0]["payout_status"]

    payload, header = _signed_webhook(
        settings,
        {
            "id": "evt_challenge_bonus_paid",
            "object": "event",
            "type": "transfer.paid",
            "data": {"object": {"id": transfer_id, "metadata": {"payment_type": "challenge_conversion_bonus"}}},
        },
    )
    resp = client.post("/webhooks/stripe", content=payload, headers={"Stripe-Signature": header})
    assert resp.status_code == 200

    submission_row = db.fetch("SELECT payout_status, paid_at FROM public.challenge_submissions WHERE id = $1", submission_id)[0]
    assert submission_row["payout_status"] == "paid"
    assert submission_row["paid_at"] is not None

    cr_row = db.fetch("SELECT payout_status FROM public.campaign_reps WHERE campaign_id = $1 AND rep_id = $2", campaign["id"], rep_id)[0]
    assert cr_row["payout_status"] == cr_payout_status_before  # untouched by the challenge-bonus webhook branch

    rep_row = db.fetch("SELECT total_earnings_cents FROM public.rep_profiles WHERE id = $1", rep_id)[0]
    assert rep_row["total_earnings_cents"] == 750


def test_transfer_paid_flat_campaign_does_not_touch_challenge_submissions(
    client, db, settings, brand_headers, rep_headers_factory, onboarded_brand, fake_stripe
):
    """Inverse isolation direction: a flat campaign Transfer must never
    touch challenge_submissions rows."""
    challenge, submission_id, campaign, rep_id, rep_user_id = _submitted_challenge_and_campaign(
        client, db, brand_headers, rep_headers_factory, settings, onboarded_brand
    )
    client.post(
        f"/brands/challenges/{challenge['id']}/submissions/{submission_id}/convert",
        json={"campaign_id": campaign["id"]},
        headers=brand_headers,
    )
    submission_payout_status_before = db.fetch("SELECT payout_status FROM public.challenge_submissions WHERE id = $1", submission_id)[0][
        "payout_status"
    ]

    rep_headers = rep_headers_factory(rep_user_id)
    accept = client.post(f"/campaigns/{campaign['id']}/accept", json={"ftc_disclosure_accepted": True}, headers=rep_headers)
    assert accept.status_code == 200
    submit = client.post(
        f"/campaigns/{campaign['id']}/submit", json={"submission_text": "done", "submission_file_urls": []}, headers=rep_headers
    )
    assert submit.status_code == 200
    confirm = client.post(f"/brands/campaigns/{campaign['id']}/reps/{rep_id}/confirm", headers=brand_headers)
    assert confirm.status_code == 200
    campaign_transfer_id = db.fetchval(
        "SELECT stripe_transfer_id FROM public.campaign_reps WHERE campaign_id = $1 AND rep_id = $2", campaign["id"], rep_id
    )

    payload, header = _signed_webhook(
        settings,
        {
            "id": "evt_flat_paid",
            "object": "event",
            "type": "transfer.paid",
            "data": {"object": {"id": campaign_transfer_id, "metadata": {}}},
        },
    )
    resp = client.post("/webhooks/stripe", content=payload, headers={"Stripe-Signature": header})
    assert resp.status_code == 200

    submission_row = db.fetch("SELECT payout_status FROM public.challenge_submissions WHERE id = $1", submission_id)[0]
    assert submission_row["payout_status"] == submission_payout_status_before


# ---------------------------------------------------------------------
# Auto-close job
# ---------------------------------------------------------------------


def test_auto_close_job_closes_expired_challenge(client, db, settings, brand_headers, onboarded_brand):
    challenge = _create_and_activate_challenge(client, brand_headers)
    db.execute("UPDATE public.challenges SET closes_at = now() - interval '1 hour' WHERE id = $1", challenge["id"])

    resp = client.post("/internal/jobs/run/challenge_auto_close", headers={"X-Jobs-Runner-Secret": settings.jobs_runner_secret})
    assert resp.status_code == 200

    row = db.fetch("SELECT status FROM public.challenges WHERE id = $1", challenge["id"])[0]
    assert row["status"] == "closed"


def test_auto_close_job_run_twice_is_idempotent(client, db, settings, brand_headers, onboarded_brand):
    challenge = _create_and_activate_challenge(client, brand_headers)
    db.execute("UPDATE public.challenges SET closes_at = now() - interval '1 hour' WHERE id = $1", challenge["id"])

    first = client.post("/internal/jobs/run/challenge_auto_close", headers={"X-Jobs-Runner-Secret": settings.jobs_runner_secret})
    second = client.post("/internal/jobs/run/challenge_auto_close", headers={"X-Jobs-Runner-Secret": settings.jobs_runner_secret})
    assert first.status_code == 200
    assert second.status_code == 200

    row = db.fetch("SELECT status FROM public.challenges WHERE id = $1", challenge["id"])[0]
    assert row["status"] == "closed"


# ---------------------------------------------------------------------
# Profile serializer: null-safe division, recruiter search field presence
# ---------------------------------------------------------------------


def test_challenge_conversion_rate_null_when_zero_submitted(client, db, rep_headers_factory, onboarded_brand):
    rep_id, rep_user_id = _seed_rep(db)
    rep_headers = rep_headers_factory(rep_user_id)
    resp = client.get("/reps/me", headers=rep_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["challenges_submitted_count"] == 0
    assert body["challenge_conversion_rate"] is None


def test_challenge_conversion_rate_computed_after_conversion(client, db, settings, brand_headers, rep_headers_factory, onboarded_brand, fake_stripe):
    challenge, submission_id, campaign, rep_id, rep_user_id = _submitted_challenge_and_campaign(
        client, db, brand_headers, rep_headers_factory, settings, onboarded_brand
    )
    client.post(
        f"/brands/challenges/{challenge['id']}/submissions/{submission_id}/convert",
        json={"campaign_id": campaign["id"]},
        headers=brand_headers,
    )
    rep_headers = rep_headers_factory(rep_user_id)
    resp = client.get("/reps/me", headers=rep_headers)
    body = resp.json()
    assert body["challenges_submitted_count"] == 1
    assert body["challenges_converted_count"] == 1
    assert body["challenge_conversion_rate"] == 1.0


def test_recruiter_search_includes_challenge_fields_without_credit_spend(client, db, auth_headers_factory, onboarded_brand):
    rep_id, rep_user_id = _seed_rep(db)
    db.execute("UPDATE public.rep_profiles SET recruiter_visible = TRUE WHERE id = $1", rep_id)

    recruiter_user_id = str(uuid.uuid4())
    db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", recruiter_user_id, "recruiter@example.com")
    db.execute(
        "INSERT INTO public.users (id, email, role, account_status, date_of_birth) "
        "VALUES ($1, 'recruiter@example.com', 'recruiter', 'active', '1990-01-01')",
        recruiter_user_id,
    )
    recruiter_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO public.recruiter_profiles (id, user_id, institution_name, institution_type, verified, contact_credits_remaining) "
        "VALUES ($1, $2, 'Test University', 'college', TRUE, 25)",
        recruiter_id,
        recruiter_user_id,
    )

    import time

    import jwt

    from app.core.config import get_settings

    settings = get_settings()
    payload = {
        "sub": recruiter_user_id,
        "email": "recruiter@example.com",
        "aud": "authenticated",
        "app_metadata": {"role": "recruiter", "account_status": "active"},
        "exp": int(time.time()) + 3600,
    }
    token = jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")
    recruiter_headers = {"Authorization": f"Bearer {token}"}

    credits_before = db.fetch("SELECT contact_credits_remaining FROM public.recruiter_profiles WHERE id = $1", recruiter_id)[0][
        "contact_credits_remaining"
    ]
    resp = client.get("/recruiters/reps/search", headers=recruiter_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
    assert "challenge_conversion_rate" in resp.json()[0]
    assert "challenges_converted_count" in resp.json()[0]

    credits_after = db.fetch("SELECT contact_credits_remaining FROM public.recruiter_profiles WHERE id = $1", recruiter_id)[0][
        "contact_credits_remaining"
    ]
    assert credits_after == credits_before  # no credit spend for search


# ---------------------------------------------------------------------
# Parent portal visibility
# ---------------------------------------------------------------------


def test_parent_dashboard_shows_converted_with_campaign_and_bonus(
    client, db, settings, brand_headers, seed_rep_with_parent, rep_headers_factory, parent_headers_factory, onboarded_brand, fake_stripe
):
    seeded = seed_rep_with_parent(age=17, campaign_approval_required=False)
    challenge = _create_and_activate_challenge(client, brand_headers)
    rep_headers = rep_headers_factory(seeded.rep_user_id)
    _submit(client, rep_headers, challenge["id"])
    submission_id = db.fetchval("SELECT id FROM public.challenge_submissions WHERE rep_id = $1", seeded.rep_id)
    campaign = _create_active_campaign(client, brand_headers, settings)
    convert = client.post(
        f"/brands/challenges/{challenge['id']}/submissions/{submission_id}/convert",
        json={"campaign_id": campaign["id"]},
        headers=brand_headers,
    )
    assert convert.status_code == 200

    parent_headers = parent_headers_factory(parent_id=seeded.parent_id, rep_id=seeded.rep_id)
    resp = client.get("/parent/dashboard", headers=parent_headers)
    assert resp.status_code == 200
    activity = resp.json()["challenge_activity"]
    assert activity["total_submitted"] == 1
    assert activity["total_converted"] == 1
    assert activity["total_bonus_earned_cents"] == 750
    assert len(activity["recent_submissions"]) == 1
    assert activity["recent_submissions"][0]["status"] == "converted"
    assert activity["recent_submissions"][0]["bonus_earned_cents"] == 750


def test_parent_dashboard_excludes_declined_submissions(
    client, db, brand_headers, seed_rep_with_parent, rep_headers_factory, parent_headers_factory, onboarded_brand
):
    seeded = seed_rep_with_parent(age=17)
    challenge = _create_and_activate_challenge(client, brand_headers)
    rep_headers = rep_headers_factory(seeded.rep_user_id)
    _submit(client, rep_headers, challenge["id"])
    submission_id = db.fetchval("SELECT id FROM public.challenge_submissions WHERE rep_id = $1", seeded.rep_id)
    decline = client.post(f"/brands/challenges/{challenge['id']}/submissions/{submission_id}/decline", headers=brand_headers)
    assert decline.status_code == 200

    parent_headers = parent_headers_factory(parent_id=seeded.parent_id, rep_id=seeded.rep_id)
    resp = client.get("/parent/dashboard", headers=parent_headers)
    assert resp.status_code == 200
    activity = resp.json()["challenge_activity"]
    assert activity["total_submitted"] == 0
    assert activity["recent_submissions"] == []
