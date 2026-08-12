from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

import pytest

TODAY = date.today()


def _dob_for_age(age: int) -> str:
    # Safely under `age` by a month so age computation is stable
    # regardless of what day-of-month `today` happens to be.
    d = date(TODAY.year - age, TODAY.month, 1)
    return d.isoformat()


def _signup_body(*, age: int, role: str = "rep", parent_email: str | None = None, email: str | None = None) -> dict:
    return {
        "email": email or f"user-{age}-{role}@example.com",
        "password": "correct-horse-battery",
        "role": role,
        "date_of_birth": _dob_for_age(age),
        "parent_email": parent_email,
    }


def _extract_consent_token(html: str) -> str:
    match = re.search(r"/parent/consent/([^\"'<]+)", html)
    assert match, f"no consent link found in email html: {html}"
    return match.group(1)


def test_signup_age_12_returns_400_and_creates_no_row(client, db):
    response = client.post("/auth/signup", json=_signup_body(age=12))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "age_not_permitted"

    count = db.fetchval("SELECT count(*) FROM public.users")
    assert count == 0


def test_signup_age_15_without_parent_email_returns_400(client):
    response = client.post("/auth/signup", json=_signup_body(age=15, parent_email=None))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "parent_email_required"


def test_signup_age_15_is_pending_and_sends_consent_email(client, fake_resend_client):
    response = client.post("/auth/signup", json=_signup_body(age=15, parent_email="parent@example.com"))
    assert response.status_code == 201
    body = response.json()
    assert body["account_status"] == "pending"

    assert len(fake_resend_client.sent) == 1
    sent = fake_resend_client.sent[0]
    assert sent.to == "parent@example.com"
    assert "72 hours" in sent.html


def test_signup_age_16_activates_immediately(client, fake_resend_client):
    response = client.post("/auth/signup", json=_signup_body(age=16))
    assert response.status_code == 201
    assert response.json()["account_status"] == "active"
    assert fake_resend_client.sent == []


def test_signup_age_18_activates_immediately_no_parent_email_needed(client):
    response = client.post("/auth/signup", json=_signup_body(age=18))
    assert response.status_code == 201
    assert response.json()["account_status"] == "active"


@pytest.mark.parametrize("role", ["brand", "recruiter"])
def test_brand_and_recruiter_always_pending_regardless_of_age(client, role):
    response = client.post("/auth/signup", json=_signup_body(age=30, role=role))
    assert response.status_code == 201
    assert response.json()["account_status"] == "pending"


def test_duplicate_email_signup_returns_400(client):
    body = _signup_body(age=20, email="dupe@example.com")
    first = client.post("/auth/signup", json=body)
    assert first.status_code == 201

    second = client.post("/auth/signup", json=body)
    assert second.status_code == 400
    assert second.json()["error"]["code"] == "email_already_registered"


def test_parent_verify_activates_account(client, fake_resend_client):
    signup = client.post("/auth/signup", json=_signup_body(age=14, parent_email="parent2@example.com"))
    assert signup.json()["account_status"] == "pending"
    token = _extract_consent_token(fake_resend_client.sent[0].html)

    response = client.post(f"/auth/parent-verify/{token}")
    assert response.status_code == 200
    assert response.json()["account_status"] == "active"


def test_parent_verify_token_used_twice_returns_already_used(client, fake_resend_client):
    client.post("/auth/signup", json=_signup_body(age=14, parent_email="parent3@example.com"))
    token = _extract_consent_token(fake_resend_client.sent[0].html)

    first = client.post(f"/auth/parent-verify/{token}")
    assert first.status_code == 200

    second = client.post(f"/auth/parent-verify/{token}")
    assert second.status_code == 400
    assert second.json()["error"]["code"] == "token_already_used"


def test_parent_verify_expired_token_returns_expired(client, fake_resend_client, db):
    client.post("/auth/signup", json=_signup_body(age=14, parent_email="parent4@example.com"))
    token = _extract_consent_token(fake_resend_client.sent[0].html)

    stale_issued_at = datetime.now(timezone.utc) - timedelta(hours=73)
    db.execute(
        "UPDATE public.users SET consent_token_issued_at = $1 WHERE consent_token = $2",
        stale_issued_at,
        token,
    )

    response = client.post(f"/auth/parent-verify/{token}")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "token_expired"


def test_parent_verify_invalid_token_returns_invalid(client):
    response = client.post("/auth/parent-verify/not-a-real-token")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "invalid_token"


def test_resend_consent_sends_new_email_and_rotates_token(client, fake_resend_client, db):
    client.post("/auth/signup", json=_signup_body(age=14, email="resend@example.com", parent_email="parentR@example.com"))
    old_token = _extract_consent_token(fake_resend_client.sent[0].html)

    # Signup's own send already set consent_email_last_sent_at -- back
    # it out of the cooldown window so this test exercises rotation,
    # not the rate limit (covered separately below).
    stale = datetime.now(timezone.utc) - timedelta(minutes=10)
    db.execute(
        "UPDATE public.users SET consent_email_last_sent_at = $1 WHERE email = $2",
        stale,
        "resend@example.com",
    )

    response = client.post("/auth/resend-consent", json={"email": "resend@example.com"})
    assert response.status_code == 200
    assert response.json()["status"] == "sent"
    assert len(fake_resend_client.sent) == 2
    new_token = _extract_consent_token(fake_resend_client.sent[1].html)
    assert new_token != old_token

    # old token no longer works
    stale_response = client.post(f"/auth/parent-verify/{old_token}")
    assert stale_response.status_code == 404


def test_resend_consent_rate_limited_immediately_after_signup(client, fake_resend_client):
    # Signup itself just sent the consent email, so an immediate resend
    # must be rejected rather than emailing the parent again right away.
    client.post("/auth/signup", json=_signup_body(age=14, email="rl@example.com", parent_email="parentRL@example.com"))

    response = client.post("/auth/resend-consent", json={"email": "rl@example.com"})
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "resend_rate_limited"


def test_resend_consent_unknown_email_still_returns_sent(client, fake_resend_client):
    # No enumeration: unknown email gets the same response as a real one.
    response = client.post("/auth/resend-consent", json={"email": "nobody@example.com"})
    assert response.status_code == 200
    assert response.json()["status"] == "sent"
    assert fake_resend_client.sent == []


def test_me_returns_pending_reason_for_awaiting_consent_rep(client, auth_headers_factory):
    headers = auth_headers_factory("rep", account_status="pending")
    response = client.get("/auth/me", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["account_status"] == "pending"
    assert body["pending_reason"] == "awaiting_parental_consent"


def test_me_returns_pending_reason_for_pending_brand(client, auth_headers_factory):
    headers = auth_headers_factory("brand", account_status="pending")
    response = client.get("/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["pending_reason"] == "pending_admin_approval"


def test_me_active_rep_has_no_pending_reason(client, auth_headers_factory):
    headers = auth_headers_factory("rep", account_status="active")
    response = client.get("/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["pending_reason"] is None


def test_me_without_auth_returns_401(client):
    response = client.get("/auth/me")
    assert response.status_code == 401
