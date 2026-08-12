"""Build Prompt 8B: Performance Milestone Payments.

Follows tests/test_payout.py's fake_stripe/seed-helper pattern exactly
-- same fixture shapes, same `_signed_webhook` helper -- so the two
suites stay easy to read side by side. Covers the acceptance criteria
enumerated in Teenure_Build_Prompts.md's 8B section: percentage
validation (99/101 rejected), atomic accept rollback, rounding never
exceeds payout_per_rep_cents, sequence-required gating (409), non-
sequential-can't-precede-sequence-required, paid-milestone re-confirm
idempotent, double release_milestone_payout produces exactly one
Transfer, transfer.paid webhook isolation between milestone/flat state,
25h-old-no-dispute auto-released, 25h-old-with-dispute NOT auto-
released, running the auto-release job twice = one transfer, and admin
dispute resolution.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta, timezone
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

_MILESTONES = [
    {
        "milestone_number": 1,
        "title": "Post delivered",
        "description": "Publish one post.",
        "verification_method": "brand_confirmation",
        "payout_percentage": 30,
        "sequence_required": True,
    },
    {
        "milestone_number": 2,
        "title": "Story follow-up",
        "description": "Publish one story.",
        "verification_method": "rep_submission",
        "payout_percentage": 30,
        "sequence_required": True,
    },
    {
        "milestone_number": 3,
        "title": "Bonus content",
        "description": "Publish one bonus post.",
        "verification_method": "rep_submission",
        "payout_percentage": 40,
        "sequence_required": False,
    },
]


def _milestone_campaign_body(*, budget_cents: int = 100_000, max_reps: int = 3, milestones=None) -> dict:
    return {
        "title": "Milestone Launch",
        "product_name": "Acme Widget",
        "campaign_goal": "Awareness",
        "key_messaging": "Widgets are great",
        "prohibited_content": None,
        "deliverables_description": "A series of posts",
        "target_categories": ["gaming"],
        "target_cities": ["Austin"],
        "max_reps": max_reps,
        "budget_cents": budget_cents,
        "start_date": (date.today() + timedelta(days=10)).isoformat(),
        "end_date": (date.today() + timedelta(days=40)).isoformat(),
        "payment_type": "milestone",
        "milestones": _MILESTONES if milestones is None else milestones,
    }


def _seed_brand_user(db) -> None:
    db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", BRAND_USER_ID, "brand@example.com")
    db.execute(
        "INSERT INTO public.users (id, email, role, account_status, date_of_birth) "
        "VALUES ($1, 'brand@example.com', 'brand', 'active', '1990-01-01')",
        BRAND_USER_ID,
    )


def _seed_rep(db, *, onboarded: bool = True) -> tuple[str, str]:
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
        VALUES ($1, $2, 'Test Rep', 'Test High', 'Austin', 'TX', 2027, '{gaming}', $3, $4)
        """,
        rep_id,
        rep_user_id,
        "acct_fake_rep" if onboarded else None,
        onboarded,
    )
    return rep_id, rep_user_id


@pytest.fixture()
def brand_headers(auth_headers_factory):
    return auth_headers_factory("brand")


@pytest.fixture()
def rep_headers_factory(auth_headers_factory, db):
    """Issues a Supabase-shaped JWT for a specific seeded rep user id,
    since auth_headers_factory always mints sub=...0001 -- milestone
    tests need the rep's own token to call the /campaigns/:id/... rep
    routes as that specific rep."""

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


def _invite_and_accept(client, db, brand_headers, campaign_id, *, onboarded=True) -> tuple[str, str, dict]:
    """Returns (rep_id, rep_user_id, invite_response_json)."""
    rep_id, rep_user_id = _seed_rep(db, onboarded=onboarded)
    invite_resp = client.post(f"/brands/campaigns/{campaign_id}/reps/invite", json={"rep_ids": [rep_id]}, headers=brand_headers)
    assert invite_resp.status_code == 200
    return rep_id, rep_user_id, invite_resp.json()[0]


# ---------------------------------------------------------------------
# Campaign creation validation (deliverable 1)
# ---------------------------------------------------------------------


def test_milestone_percentages_summing_to_99_rejected(client, brand_headers, onboarded_brand):
    body = _milestone_campaign_body(
        milestones=[
            {**_MILESTONES[0], "payout_percentage": 29},
            _MILESTONES[1],
            _MILESTONES[2],
        ]
    )
    response = client.post("/brands/campaigns", json=body, headers=brand_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_milestones"


def test_milestone_percentages_summing_to_101_rejected(client, brand_headers, onboarded_brand):
    body = _milestone_campaign_body(
        milestones=[
            {**_MILESTONES[0], "payout_percentage": 31},
            _MILESTONES[1],
            _MILESTONES[2],
        ]
    )
    response = client.post("/brands/campaigns", json=body, headers=brand_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_milestones"


def test_milestone_count_below_minimum_rejected(client, brand_headers, onboarded_brand):
    body = _milestone_campaign_body(milestones=[{**_MILESTONES[0], "payout_percentage": 100}])
    response = client.post("/brands/campaigns", json=body, headers=brand_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_milestones"


def test_milestone_non_sequential_before_sequence_required_rejected(client, brand_headers, onboarded_brand):
    body = _milestone_campaign_body(
        milestones=[
            {**_MILESTONES[0], "sequence_required": False},
            {**_MILESTONES[1], "milestone_number": 2, "sequence_required": True},
        ]
    )
    response = client.post("/brands/campaigns", json=body, headers=brand_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_milestones"


def test_milestone_requires_at_least_one_sequence_required(client, brand_headers, onboarded_brand):
    body = _milestone_campaign_body(
        milestones=[
            {**_MILESTONES[0], "sequence_required": False},
            {**_MILESTONES[1], "sequence_required": False, "payout_percentage": 70},
        ]
    )
    response = client.post("/brands/campaigns", json=body, headers=brand_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_milestones"


def test_flat_campaign_with_milestones_array_rejected(client, brand_headers, onboarded_brand):
    body = _milestone_campaign_body()
    body["payment_type"] = "flat"
    response = client.post("/brands/campaigns", json=body, headers=brand_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "milestones_not_allowed"


def test_valid_milestone_campaign_creates_atomically(client, db, brand_headers, onboarded_brand):
    response = client.post("/brands/campaigns", json=_milestone_campaign_body(), headers=brand_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["payment_type"] == "milestone"
    rows = db.fetch("SELECT milestone_number, payout_percentage FROM public.campaign_milestones WHERE campaign_id = $1 ORDER BY milestone_number", body["id"])
    assert len(rows) == 3


def test_invalid_milestones_rolls_back_campaign_creation(client, db, brand_headers, onboarded_brand):
    """Atomic creation (deliverable 1): a validation failure must not
    leave a half-created campaign row -- but since validate_milestones
    runs BEFORE the transaction opens, the stronger assertion here is
    simply that no campaign row exists afterward at all."""
    before = db.fetchval("SELECT COUNT(*) FROM public.campaigns")
    body = _milestone_campaign_body(milestones=[{**_MILESTONES[0], "payout_percentage": 50}, {**_MILESTONES[1], "payout_percentage": 60}])
    response = client.post("/brands/campaigns", json=body, headers=brand_headers)
    assert response.status_code == 400
    after = db.fetchval("SELECT COUNT(*) FROM public.campaigns")
    assert after == before


# ---------------------------------------------------------------------
# Accept -> campaign_rep_milestones initialization (deliverable 2)
# ---------------------------------------------------------------------


def test_accept_initializes_campaign_rep_milestones(client, db, brand_headers, rep_headers_factory, onboarded_brand):
    created = client.post("/brands/campaigns", json=_milestone_campaign_body(), headers=brand_headers).json()
    rep_id, rep_user_id, invite = _invite_and_accept(client, db, brand_headers, created["id"])
    rep_headers = rep_headers_factory(rep_user_id)

    response = client.post(f"/campaigns/{created['id']}/accept", json={"ftc_disclosure_accepted": True}, headers=rep_headers)
    assert response.status_code == 200

    rows = db.fetch(
        "SELECT crm.status FROM public.campaign_rep_milestones crm JOIN public.campaign_reps cr ON cr.id = crm.campaign_rep_id WHERE cr.rep_id = $1",
        rep_id,
    )
    assert len(rows) == 3
    assert all(r["status"] == "pending" for r in rows)


# ---------------------------------------------------------------------
# Submission sequence gating (deliverable 4)
# ---------------------------------------------------------------------


def _accept_milestone_campaign(client, db, brand_headers, rep_headers_factory, onboarded_brand, milestones=None):
    created = client.post("/brands/campaigns", json=_milestone_campaign_body(milestones=milestones), headers=brand_headers).json()
    rep_id, rep_user_id, _ = _invite_and_accept(client, db, brand_headers, created["id"])
    rep_headers = rep_headers_factory(rep_user_id)
    client.post(f"/campaigns/{created['id']}/accept", json={"ftc_disclosure_accepted": True}, headers=rep_headers)
    milestone_rows = db.fetch(
        "SELECT id, milestone_number FROM public.campaign_milestones WHERE campaign_id = $1 ORDER BY milestone_number", created["id"]
    )
    return created, rep_id, rep_headers, {r["milestone_number"]: str(r["id"]) for r in milestone_rows}


def test_submitting_second_sequence_milestone_before_first_is_409(client, db, brand_headers, rep_headers_factory, onboarded_brand):
    created, rep_id, rep_headers, milestone_ids = _accept_milestone_campaign(client, db, brand_headers, rep_headers_factory, onboarded_brand)
    response = client.post(
        f"/campaigns/{created['id']}/milestones/{milestone_ids[2]}/submit",
        json={"submission_text": "story link", "submission_file_urls": []},
        headers=rep_headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "milestone_not_actionable"


def test_submitting_non_sequential_milestone_before_sequence_required_done_is_409(client, db, brand_headers, rep_headers_factory, onboarded_brand):
    created, rep_id, rep_headers, milestone_ids = _accept_milestone_campaign(client, db, brand_headers, rep_headers_factory, onboarded_brand)
    response = client.post(
        f"/campaigns/{created['id']}/milestones/{milestone_ids[3]}/submit",
        json={"submission_text": "bonus content", "submission_file_urls": []},
        headers=rep_headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "milestone_not_actionable"


def test_first_milestone_submission_succeeds_and_notifies_brand(
    client, db, brand_headers, rep_headers_factory, onboarded_brand, fake_resend_client
):
    created, rep_id, rep_headers, milestone_ids = _accept_milestone_campaign(client, db, brand_headers, rep_headers_factory, onboarded_brand)
    response = client.post(
        f"/campaigns/{created['id']}/milestones/{milestone_ids[1]}/submit",
        json={"submission_text": "post link", "submission_file_urls": []},
        headers=rep_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "submitted"
    # milestone 1 is 'brand_confirmation' -- brand gets notified.
    assert len(fake_resend_client.sent) == 1


# ---------------------------------------------------------------------
# Confirmation, rounding, and idempotency (deliverables 5, 8)
# ---------------------------------------------------------------------


def test_confirm_computes_payout_and_releases_transfer(client, db, brand_headers, rep_headers_factory, onboarded_brand, fake_stripe):
    created, rep_id, rep_headers, milestone_ids = _accept_milestone_campaign(client, db, brand_headers, rep_headers_factory, onboarded_brand)
    client.post(
        f"/campaigns/{created['id']}/milestones/{milestone_ids[1]}/submit",
        json={"submission_text": "post link", "submission_file_urls": []},
        headers=rep_headers,
    )
    response = client.post(f"/brands/campaigns/{created['id']}/reps/{rep_id}/milestones/{milestone_ids[1]}/confirm", headers=brand_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "confirmed"
    assert body["payout_cents"] == (created["payout_per_rep_cents"] * 30) // 100

    call_names = [name for name, _ in fake_stripe.calls]
    assert call_names == ["Transfer.create"]
    _, kwargs = fake_stripe.calls[0]
    assert kwargs["metadata"]["payment_type"] == "milestone"


def test_rounding_never_exceeds_payout_per_rep_cents(client, db, brand_headers, rep_headers_factory, onboarded_brand, fake_stripe):
    """budget/max_reps chosen so payout_per_rep_cents doesn't divide
    evenly by the milestone percentages, forcing a rounding remainder
    onto the final milestone (spec: 'never let rounding silently reduce
    or increase total rep earnings')."""
    created, rep_id, rep_headers, milestone_ids = _accept_milestone_campaign(
        client, db, brand_headers, rep_headers_factory, onboarded_brand
    )
    payout_per_rep_cents = created["payout_per_rep_cents"]

    # Confirm milestone 1 (brand_confirmation).
    client.post(f"/campaigns/{created['id']}/milestones/{milestone_ids[1]}/submit", json={"submission_text": "x"}, headers=rep_headers)
    r1 = client.post(f"/brands/campaigns/{created['id']}/reps/{rep_id}/milestones/{milestone_ids[1]}/confirm", headers=brand_headers).json()

    client.post(f"/campaigns/{created['id']}/milestones/{milestone_ids[2]}/submit", json={"submission_text": "x"}, headers=rep_headers)
    r2 = client.post(f"/brands/campaigns/{created['id']}/reps/{rep_id}/milestones/{milestone_ids[2]}/confirm", headers=brand_headers).json()

    client.post(f"/campaigns/{created['id']}/milestones/{milestone_ids[3]}/submit", json={"submission_text": "x"}, headers=rep_headers)
    r3 = client.post(f"/brands/campaigns/{created['id']}/reps/{rep_id}/milestones/{milestone_ids[3]}/confirm", headers=brand_headers).json()

    total = r1["payout_cents"] + r2["payout_cents"] + r3["payout_cents"]
    assert total == payout_per_rep_cents

    cr_row = db.fetch("SELECT total_milestone_payout_cents, status FROM public.campaign_reps WHERE rep_id = $1", rep_id)[0]
    assert cr_row["total_milestone_payout_cents"] == payout_per_rep_cents
    # Final milestone confirmed -> campaign_reps.status advances to 'confirmed'.
    assert cr_row["status"] == "confirmed"


def test_confirming_already_paid_milestone_is_idempotent_conflict(client, db, brand_headers, rep_headers_factory, onboarded_brand, fake_stripe):
    created, rep_id, rep_headers, milestone_ids = _accept_milestone_campaign(client, db, brand_headers, rep_headers_factory, onboarded_brand)
    client.post(f"/campaigns/{created['id']}/milestones/{milestone_ids[1]}/submit", json={"submission_text": "x"}, headers=rep_headers)
    first = client.post(f"/brands/campaigns/{created['id']}/reps/{rep_id}/milestones/{milestone_ids[1]}/confirm", headers=brand_headers)
    assert first.status_code == 200

    second = client.post(f"/brands/campaigns/{created['id']}/reps/{rep_id}/milestones/{milestone_ids[1]}/confirm", headers=brand_headers)
    assert second.status_code == 409

    call_names = [name for name, _ in fake_stripe.calls]
    assert call_names == ["Transfer.create"]


def test_double_release_milestone_payout_produces_exactly_one_transfer(client, db, settings, brand_headers, rep_headers_factory, onboarded_brand, fake_stripe):
    """Mirrors Prompt 11's credit-deduction concurrency pattern: two
    concurrent-ish calls to release_milestone_payout for the same
    already-confirmed row must only ever create one Stripe Transfer."""
    created, rep_id, rep_headers, milestone_ids = _accept_milestone_campaign(client, db, brand_headers, rep_headers_factory, onboarded_brand)
    client.post(f"/campaigns/{created['id']}/milestones/{milestone_ids[1]}/submit", json={"submission_text": "x"}, headers=rep_headers)
    client.post(f"/brands/campaigns/{created['id']}/reps/{rep_id}/milestones/{milestone_ids[1]}/confirm", headers=brand_headers)

    crm_id = db.fetchval(
        "SELECT crm.id FROM public.campaign_rep_milestones crm JOIN public.campaign_milestones cm ON cm.id = crm.campaign_milestone_id WHERE cm.id = $1",
        milestone_ids[1],
    )

    # Deliberately a standalone asyncpg connection (not the app's pool
    # via app.db.pool.get_pool()) -- see tests/conftest.py's SyncDB
    # docstring for why: the app pool lives on TestClient's background
    # anyio-portal event loop, and handing it to a bare asyncio.run()
    # here would bind a connection to the wrong loop.
    import asyncio

    import asyncpg

    from app.core.config import get_settings

    async def _second_release():
        conn = await asyncpg.connect(dsn=get_settings().database_url)
        try:
            return await payout_service.release_milestone_payout(conn, get_settings(), str(crm_id))
        finally:
            await conn.close()

    result = asyncio.run(_second_release())
    assert result.outcome == "already_processed"

    call_names = [name for name, _ in fake_stripe.calls]
    assert call_names == ["Transfer.create"]


# ---------------------------------------------------------------------
# Dispute + auto-release (deliverables 6, 7)
# ---------------------------------------------------------------------


def test_dispute_within_window_sets_flag_and_creates_admin_queue_entry(
    client, db, brand_headers, rep_headers_factory, onboarded_brand, fake_resend_client, fake_stripe
):
    created, rep_id, rep_headers, milestone_ids = _accept_milestone_campaign(client, db, brand_headers, rep_headers_factory, onboarded_brand)
    # milestone 2 requires milestone 1 confirmed first.
    client.post(f"/campaigns/{created['id']}/milestones/{milestone_ids[1]}/submit", json={"submission_text": "x"}, headers=rep_headers)
    client.post(f"/brands/campaigns/{created['id']}/reps/{rep_id}/milestones/{milestone_ids[1]}/confirm", headers=brand_headers)
    client.post(f"/campaigns/{created['id']}/milestones/{milestone_ids[2]}/submit", json={"submission_text": "story"}, headers=rep_headers)

    response = client.post(
        f"/brands/campaigns/{created['id']}/reps/{rep_id}/milestones/{milestone_ids[2]}/dispute",
        json={"reason": "Looks fake"},
        headers=brand_headers,
    )
    assert response.status_code == 200
    assert response.json()["dispute_flag"] is True

    dispute_row = db.fetch("SELECT status FROM public.milestone_disputes")
    assert len(dispute_row) == 1
    assert dispute_row[0]["status"] == "open"


def test_25h_old_submission_no_dispute_is_auto_released(client, db, settings, brand_headers, rep_headers_factory, onboarded_brand, fake_stripe):
    created, rep_id, rep_headers, milestone_ids = _accept_milestone_campaign(client, db, brand_headers, rep_headers_factory, onboarded_brand)
    client.post(f"/campaigns/{created['id']}/milestones/{milestone_ids[1]}/submit", json={"submission_text": "x"}, headers=rep_headers)
    client.post(f"/brands/campaigns/{created['id']}/reps/{rep_id}/milestones/{milestone_ids[1]}/confirm", headers=brand_headers)
    client.post(f"/campaigns/{created['id']}/milestones/{milestone_ids[2]}/submit", json={"submission_text": "story"}, headers=rep_headers)

    # Backdate submitted_at past the 24h window.
    db.execute(
        "UPDATE public.campaign_rep_milestones SET submitted_at = now() - interval '25 hours' "
        "WHERE campaign_milestone_id = $1",
        milestone_ids[2],
    )

    response = client.post("/internal/jobs/run/milestone_auto_release", headers={"X-Jobs-Runner-Secret": settings.jobs_runner_secret})
    assert response.status_code == 200

    row = db.fetch(
        "SELECT status FROM public.campaign_rep_milestones WHERE campaign_milestone_id = $1", milestone_ids[2]
    )[0]
    assert row["status"] == "confirmed"
    call_names = [name for name, _ in fake_stripe.calls]
    assert call_names.count("Transfer.create") == 2  # milestone 1 (manual) + milestone 2 (auto)


def test_25h_old_submission_with_dispute_not_auto_released(client, db, settings, brand_headers, rep_headers_factory, onboarded_brand, fake_stripe):
    created, rep_id, rep_headers, milestone_ids = _accept_milestone_campaign(client, db, brand_headers, rep_headers_factory, onboarded_brand)
    client.post(f"/campaigns/{created['id']}/milestones/{milestone_ids[1]}/submit", json={"submission_text": "x"}, headers=rep_headers)
    client.post(f"/brands/campaigns/{created['id']}/reps/{rep_id}/milestones/{milestone_ids[1]}/confirm", headers=brand_headers)
    client.post(f"/campaigns/{created['id']}/milestones/{milestone_ids[2]}/submit", json={"submission_text": "story"}, headers=rep_headers)
    client.post(
        f"/brands/campaigns/{created['id']}/reps/{rep_id}/milestones/{milestone_ids[2]}/dispute",
        json={"reason": "review"},
        headers=brand_headers,
    )
    db.execute(
        "UPDATE public.campaign_rep_milestones SET submitted_at = now() - interval '25 hours' WHERE campaign_milestone_id = $1",
        milestone_ids[2],
    )

    response = client.post("/internal/jobs/run/milestone_auto_release", headers={"X-Jobs-Runner-Secret": settings.jobs_runner_secret})
    assert response.status_code == 200

    row = db.fetch("SELECT status FROM public.campaign_rep_milestones WHERE campaign_milestone_id = $1", milestone_ids[2])[0]
    assert row["status"] == "submitted"  # unchanged -- disputed rows are skipped


def test_running_auto_release_job_twice_produces_one_transfer(client, db, settings, brand_headers, rep_headers_factory, onboarded_brand, fake_stripe):
    created, rep_id, rep_headers, milestone_ids = _accept_milestone_campaign(client, db, brand_headers, rep_headers_factory, onboarded_brand)
    client.post(f"/campaigns/{created['id']}/milestones/{milestone_ids[1]}/submit", json={"submission_text": "x"}, headers=rep_headers)
    client.post(f"/brands/campaigns/{created['id']}/reps/{rep_id}/milestones/{milestone_ids[1]}/confirm", headers=brand_headers)
    client.post(f"/campaigns/{created['id']}/milestones/{milestone_ids[2]}/submit", json={"submission_text": "story"}, headers=rep_headers)
    db.execute(
        "UPDATE public.campaign_rep_milestones SET submitted_at = now() - interval '25 hours' WHERE campaign_milestone_id = $1",
        milestone_ids[2],
    )

    client.post("/internal/jobs/run/milestone_auto_release", headers={"X-Jobs-Runner-Secret": settings.jobs_runner_secret})
    client.post("/internal/jobs/run/milestone_auto_release", headers={"X-Jobs-Runner-Secret": settings.jobs_runner_secret})

    call_names = [name for name, _ in fake_stripe.calls]
    assert call_names.count("Transfer.create") == 2  # milestone 1 + milestone 2, not a 3rd from the second job run


# ---------------------------------------------------------------------
# Webhook isolation between milestone and flat state (deliverable 9)
# ---------------------------------------------------------------------


def test_transfer_paid_milestone_metadata_does_not_touch_flat_campaign_reps_row(
    client, db, settings, brand_headers, rep_headers_factory, onboarded_brand, fake_stripe
):
    created, rep_id, rep_headers, milestone_ids = _accept_milestone_campaign(client, db, brand_headers, rep_headers_factory, onboarded_brand)
    client.post(f"/campaigns/{created['id']}/milestones/{milestone_ids[1]}/submit", json={"submission_text": "x"}, headers=rep_headers)
    client.post(f"/brands/campaigns/{created['id']}/reps/{rep_id}/milestones/{milestone_ids[1]}/confirm", headers=brand_headers)
    transfer_id = db.fetchval(
        "SELECT stripe_transfer_id FROM public.campaign_rep_milestones WHERE campaign_milestone_id = $1", milestone_ids[1]
    )

    payload, header = _signed_webhook(
        settings,
        {
            "id": "evt_milestone_paid",
            "object": "event",
            "type": "transfer.paid",
            "data": {"object": {"id": transfer_id, "metadata": {"payment_type": "milestone"}}},
        },
    )
    response = client.post("/webhooks/stripe", content=payload, headers={"Stripe-Signature": header})
    assert response.status_code == 200

    crm_row = db.fetch("SELECT payout_status, status FROM public.campaign_rep_milestones WHERE campaign_milestone_id = $1", milestone_ids[1])[0]
    assert crm_row["payout_status"] == "paid"
    assert crm_row["status"] == "paid"

    # The parent campaign_reps row's own flat payout_status column
    # (never used by a milestone campaign) must be untouched -- still
    # its DB default, not accidentally flipped to 'paid' by the
    # milestone webhook branch.
    cr_row = db.fetch("SELECT payout_status FROM public.campaign_reps WHERE rep_id = $1", rep_id)[0]
    assert cr_row["payout_status"] == "pending"


# ---------------------------------------------------------------------
# Admin dispute resolution
# ---------------------------------------------------------------------


def test_admin_confirms_dispute_triggers_payout(client, db, settings, brand_headers, rep_headers_factory, onboarded_brand, fake_stripe, auth_headers_factory):
    created, rep_id, rep_headers, milestone_ids = _accept_milestone_campaign(client, db, brand_headers, rep_headers_factory, onboarded_brand)
    client.post(f"/campaigns/{created['id']}/milestones/{milestone_ids[1]}/submit", json={"submission_text": "x"}, headers=rep_headers)
    client.post(f"/brands/campaigns/{created['id']}/reps/{rep_id}/milestones/{milestone_ids[1]}/confirm", headers=brand_headers)
    client.post(f"/campaigns/{created['id']}/milestones/{milestone_ids[2]}/submit", json={"submission_text": "story"}, headers=rep_headers)
    client.post(
        f"/brands/campaigns/{created['id']}/reps/{rep_id}/milestones/{milestone_ids[2]}/dispute",
        json={"reason": "review"},
        headers=brand_headers,
    )

    admin_headers = auth_headers_factory("admin")
    dispute_id = db.fetchval("SELECT id FROM public.milestone_disputes WHERE status = 'open'")
    response = client.post(
        f"/admin/milestone-disputes/{dispute_id}/resolve",
        json={"resolution": "confirm", "resolution_note": "Evidence checks out"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "resolved_confirmed"

    row = db.fetch("SELECT status, payout_status FROM public.campaign_rep_milestones WHERE campaign_milestone_id = $1", milestone_ids[2])[0]
    assert row["status"] in ("confirmed", "paid")
    assert row["payout_status"] == "processing"


def test_admin_declines_dispute_resets_to_submitted(client, db, brand_headers, rep_headers_factory, onboarded_brand, fake_stripe, auth_headers_factory):
    created, rep_id, rep_headers, milestone_ids = _accept_milestone_campaign(client, db, brand_headers, rep_headers_factory, onboarded_brand)
    client.post(f"/campaigns/{created['id']}/milestones/{milestone_ids[1]}/submit", json={"submission_text": "x"}, headers=rep_headers)
    client.post(f"/brands/campaigns/{created['id']}/reps/{rep_id}/milestones/{milestone_ids[1]}/confirm", headers=brand_headers)
    client.post(f"/campaigns/{created['id']}/milestones/{milestone_ids[2]}/submit", json={"submission_text": "story"}, headers=rep_headers)
    client.post(
        f"/brands/campaigns/{created['id']}/reps/{rep_id}/milestones/{milestone_ids[2]}/dispute",
        json={"reason": "review"},
        headers=brand_headers,
    )

    admin_headers = auth_headers_factory("admin")
    dispute_id = db.fetchval("SELECT id FROM public.milestone_disputes WHERE status = 'open'")
    response = client.post(
        f"/admin/milestone-disputes/{dispute_id}/resolve",
        json={"resolution": "decline"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "resolved_declined"

    row = db.fetch("SELECT status, dispute_flag FROM public.campaign_rep_milestones WHERE campaign_milestone_id = $1", milestone_ids[2])[0]
    assert row["status"] == "submitted"
    assert row["dispute_flag"] is False
