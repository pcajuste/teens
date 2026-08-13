"""Build Prompt 8I: Company Profile, Scholarship, Skills Challenge
content layer, pseudonym system, and Insight & Feedback template.
"""
from __future__ import annotations

import time
import uuid
from datetime import date, datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import get_settings

BRAND_USER_ID = "00000000-0000-0000-0000-000000000001"
ADMIN_USER_ID = "00000000-0000-0000-0000-000000000099"

_BRAND_PROFILE_BODY = {
    "company_name": "Acme Co",
    "website": "https://acme.example.com",
    "ein": "12-3456789",
    "industry": "apparel",
    "target_categories": ["gaming"],
}

_COMPANY_PROFILE_BODY = {
    "logo_url": "https://acme.example.com/logo.png",
    "brand_color_primary": "#0D9B7A",
    "about_text": "Acme makes gear for teen gamers.",
    "why_on_teenure_text": "We want authentic feedback from real teens.",
}

_SCHOLARSHIP_BODY = {
    "title": "Acme Future Builders Scholarship",
    "award_amount_cents": 500000,
    "number_of_awards": 2,
    "eligibility_criteria": [{"label": "Enrolled in high school", "required": True}],
    "application_requirements": "Submit a 300-word essay.",
    "why_text": "We believe in investing in the next generation of builders.",
    "deadline": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
}


def _seed_brand_user(db) -> None:
    db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", BRAND_USER_ID, "brand@example.com")
    db.execute(
        "INSERT INTO public.users (id, email, role, account_status, date_of_birth) "
        "VALUES ($1, 'brand@example.com', 'brand', 'active', '1990-01-01')",
        BRAND_USER_ID,
    )


def _seed_admin_user(db) -> None:
    db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", ADMIN_USER_ID, "admin@example.com")
    db.execute(
        "INSERT INTO public.users (id, email, role, account_status, date_of_birth) "
        "VALUES ($1, 'admin@example.com', 'admin', 'active', '1980-01-01')",
        ADMIN_USER_ID,
    )


def _seed_talent(db, *, opt_in: bool = False, categories: list[str] | None = None, graduation_year: int = 2027) -> tuple[str, str]:
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
            (id, user_id, display_name, school_name, city, state, graduation_year, categories, insight_feedback_opt_in)
        VALUES ($1, $2, 'Test Talent', 'Test High', 'Austin', 'TX', $3, $4, $5)
        """,
        talent_id,
        talent_user_id,
        graduation_year,
        categories or ["gaming"],
        opt_in,
    )
    return talent_id, talent_user_id


@pytest.fixture()
def brand_headers(auth_headers_factory):
    return auth_headers_factory("brand")


@pytest.fixture()
def admin_headers(auth_headers_factory):
    return auth_headers_factory("admin")


@pytest.fixture()
def talent_headers_factory(auth_headers_factory, db):
    def _factory(talent_user_id: str) -> dict[str, str]:
        settings = get_settings()
        payload = {
            "sub": talent_user_id,
            "email": "talent@example.com",
            "aud": "authenticated",
            "app_metadata": {"role": "talent", "account_status": "active"},
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
def onboarded_admin(db, admin_headers):
    _seed_admin_user(db)
    return admin_headers


def _complete_company_profile(client, brand_headers) -> None:
    response = client.put("/brands/me/company-profile", json=_COMPANY_PROFILE_BODY, headers=brand_headers)
    assert response.status_code == 200, response.text
    assert response.json()["complete"] is True


# ---------------------------------------------------------------------
# Company Profile
# ---------------------------------------------------------------------


def test_company_profile_word_count_validation(client, brand_headers, onboarded_brand):
    over_limit = " ".join(["word"] * 151)
    response = client.put(
        "/brands/me/company-profile",
        json={**_COMPANY_PROFILE_BODY, "about_text": over_limit},
        headers=brand_headers,
    )
    assert response.status_code == 422


def test_company_profile_starts_incomplete(client, brand_headers, onboarded_brand):
    response = client.get("/brands/me/company-profile", headers=brand_headers)
    assert response.status_code == 200
    assert response.json()["complete"] is False


def test_scholarship_creation_blocked_without_company_profile(client, brand_headers, onboarded_brand):
    response = client.post("/brands/scholarships", json=_SCHOLARSHIP_BODY, headers=brand_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "company_profile_incomplete"


# ---------------------------------------------------------------------
# Scholarships
# ---------------------------------------------------------------------


def test_scholarship_full_lifecycle(client, db, brand_headers, talent_headers_factory, onboarded_brand, onboarded_admin):
    _complete_company_profile(client, brand_headers)
    created = client.post("/brands/scholarships", json=_SCHOLARSHIP_BODY, headers=brand_headers)
    assert created.status_code == 201, created.text
    scholarship_id = created.json()["id"]
    assert created.json()["moderation_status"] == "draft"

    # Cannot activate before approval
    premature = client.post(f"/brands/scholarships/{scholarship_id}/activate", headers=brand_headers)
    assert premature.status_code == 400
    assert premature.json()["error"]["code"] == "not_approved"

    submitted = client.post(f"/brands/scholarships/{scholarship_id}/submit-for-review", headers=brand_headers)
    assert submitted.status_code == 200
    assert submitted.json()["moderation_status"] == "pending_review"

    queue = client.get("/admin/content-templates/scholarships/queue", headers=onboarded_admin)
    assert queue.status_code == 200
    assert any(s["id"] == scholarship_id for s in queue.json())

    approved = client.post(f"/admin/content-templates/scholarships/{scholarship_id}/approve", headers=onboarded_admin)
    assert approved.status_code == 200
    assert approved.json()["moderation_status"] == "approved"

    activated = client.post(f"/brands/scholarships/{scholarship_id}/activate", headers=brand_headers)
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"

    talent_id, talent_user_id = _seed_talent(db)
    talent_headers = talent_headers_factory(talent_user_id)

    available = client.get("/talents/scholarships/available", headers=talent_headers)
    assert available.status_code == 200
    assert any(s["id"] == scholarship_id for s in available.json())

    apply = client.post(
        f"/talents/scholarships/{scholarship_id}/apply", json={"response_text": "My essay."}, headers=talent_headers
    )
    assert apply.status_code == 201, apply.text

    duplicate = client.post(
        f"/talents/scholarships/{scholarship_id}/apply", json={"response_text": "Again."}, headers=talent_headers
    )
    assert duplicate.status_code == 400
    assert duplicate.json()["error"]["code"] == "already_applied"

    my_apps = client.get("/talents/scholarships/applications", headers=talent_headers)
    assert my_apps.status_code == 200
    assert len(my_apps.json()) == 1

    brand_apps = client.get(f"/brands/scholarships/{scholarship_id}/applications", headers=brand_headers)
    assert brand_apps.status_code == 200
    application_id = brand_apps.json()[0]["id"]

    award = client.post(
        f"/brands/scholarships/{scholarship_id}/applications/{application_id}/award", headers=brand_headers
    )
    assert award.status_code == 200
    assert award.json()["status"] == "awarded"


def test_scholarship_rejection_records_reason(client, brand_headers, onboarded_brand, onboarded_admin):
    _complete_company_profile(client, brand_headers)
    created = client.post("/brands/scholarships", json=_SCHOLARSHIP_BODY, headers=brand_headers)
    scholarship_id = created.json()["id"]
    client.post(f"/brands/scholarships/{scholarship_id}/submit-for-review", headers=brand_headers)

    rejected = client.post(
        f"/admin/content-templates/scholarships/{scholarship_id}/reject",
        json={"reason": "Missing eligibility detail."},
        headers=onboarded_admin,
    )
    assert rejected.status_code == 200
    assert rejected.json()["moderation_status"] == "rejected"
    assert rejected.json()["rejection_reason"] == "Missing eligibility detail."


# ---------------------------------------------------------------------
# Skills Challenge content layer (Build Prompt 8I extending 8G)
# ---------------------------------------------------------------------

_CHALLENGE_BODY = {
    "title": "Show us your setup",
    "brief": "Post a short video of your gaming setup.",
    "category": "gaming",
    "submission_format": "both",
    "submission_prompt": "30-60 second video, vertical format.",
    "target_cities": [],
}


def test_challenge_activation_requires_moderation_approval(client, brand_headers, onboarded_brand, onboarded_admin):
    created = client.post("/brands/challenges", json=_CHALLENGE_BODY, headers=brand_headers)
    challenge_id = created.json()["id"]
    assert created.json()["moderation_status"] == "draft"

    content = client.put(
        f"/brands/challenges/{challenge_id}/content",
        json={
            "goal_text": "Show off your setup.",
            "rules_text": "Must be your own space.",
            "judging_criteria": "Creativity and cleanliness.",
            "prize_reward_text": "$50 gift card",
            "why_text": "We want to see real teen gaming setups.",
        },
        headers=brand_headers,
    )
    assert content.status_code == 200
    assert content.json()["why_text"] == "We want to see real teen gaming setups."

    premature = client.post(f"/brands/challenges/{challenge_id}/activate", headers=brand_headers)
    assert premature.status_code == 400
    assert premature.json()["error"]["code"] == "not_approved"

    client.post(f"/brands/challenges/{challenge_id}/submit-for-review", headers=brand_headers)
    queue = client.get("/admin/content-templates/challenges/queue", headers=onboarded_admin)
    assert any(c["id"] == challenge_id for c in queue.json())

    client.post(f"/admin/content-templates/challenges/{challenge_id}/approve", headers=onboarded_admin)
    activated = client.post(f"/brands/challenges/{challenge_id}/activate", headers=brand_headers)
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"


# ---------------------------------------------------------------------
# Insight & Feedback template + pseudonym system
# ---------------------------------------------------------------------

_ELIGIBILITY_BODY = {
    "legal_entity_verified": True,
    "named_contact_verified": True,
    "business_presence_verified": True,
    "funding_confirmed": True,
    "content_agreement_signed": True,
    "is_early_stage_startup": False,
    "incorporated_3mo_or_backed": False,
    "has_real_product": False,
}

_INSIGHT_CAMPAIGN_BODY = {
    "title": "New sneaker concept feedback",
    "material_url": "https://acme.example.com/concept.pdf",
    "business_question": "Would you buy this sneaker at $80?",
    "panel_size": 2,
    "panel_criteria": {"categories": ["gaming"]},
    "compensation_cents": 2500,
    "confidentiality_terms": "Do not share this material with anyone.",
}


def test_insight_campaign_creation_blocked_until_vetted(client, brand_headers, onboarded_brand):
    _complete_company_profile(client, brand_headers)
    response = client.post("/brands/insight/campaigns", json=_INSIGHT_CAMPAIGN_BODY, headers=brand_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "not_vetted"


def test_insight_full_pseudonymous_flow(client, db, brand_headers, talent_headers_factory, onboarded_brand, onboarded_admin):
    _complete_company_profile(client, brand_headers)
    elig = client.put("/brands/insight/eligibility", json=_ELIGIBILITY_BODY, headers=brand_headers)
    assert elig.status_code == 200
    assert elig.json()["eligible"] is True

    created = client.post("/brands/insight/campaigns", json=_INSIGHT_CAMPAIGN_BODY, headers=brand_headers)
    assert created.status_code == 201, created.text
    campaign_id = created.json()["id"]

    client.post(f"/brands/insight/campaigns/{campaign_id}/submit-for-review", headers=brand_headers)
    queue = client.get("/admin/content-templates/insight-campaigns/queue", headers=onboarded_admin)
    assert any(c["id"] == campaign_id for c in queue.json())
    approved = client.post(f"/admin/content-templates/insight-campaigns/{campaign_id}/approve", headers=onboarded_admin)
    assert approved.status_code == 200

    # Not enough opted-in talents yet -> panel fill fails
    insufficient = client.post(f"/brands/insight/campaigns/{campaign_id}/activate", headers=brand_headers)
    assert insufficient.status_code == 400
    assert insufficient.json()["error"]["code"] == "insufficient_panel"

    talent_a_id, talent_a_user = _seed_talent(db, opt_in=True, categories=["gaming"])
    talent_b_id, talent_b_user = _seed_talent(db, opt_in=True, categories=["gaming"])
    # Not opted in -- must never be selected
    _seed_talent(db, opt_in=False, categories=["gaming"])

    activated = client.post(f"/brands/insight/campaigns/{campaign_id}/activate", headers=brand_headers)
    assert activated.status_code == 200, activated.text
    assert activated.json()["status"] == "active"

    talent_a_headers = talent_headers_factory(talent_a_user)
    invitations = client.get("/talents/insight/invitations", headers=talent_a_headers)
    assert invitations.status_code == 200
    assert len(invitations.json()) == 1
    panel_member_id = invitations.json()[0]["panel_member_id"]
    assert invitations.json()[0]["campaign_title"] == _INSIGHT_CAMPAIGN_BODY["title"]

    respond = client.post(
        f"/talents/insight/invitations/{panel_member_id}/respond",
        json={"ratings": [{"question": "Would you buy this?", "score": 4}]},
        headers=talent_a_headers,
    )
    assert respond.status_code == 200, respond.text

    already = client.post(
        f"/talents/insight/invitations/{panel_member_id}/respond",
        json={"ratings": [{"question": "Would you buy this?", "score": 4}]},
        headers=talent_a_headers,
    )
    assert already.status_code == 400
    assert already.json()["error"]["code"] == "already_responded"

    # Brand-facing results are pseudonymous -- no talent identity anywhere
    results = client.get(f"/brands/insight/campaigns/{campaign_id}/results", headers=brand_headers)
    assert results.status_code == 200
    assert len(results.json()) == 1
    result = results.json()[0]
    assert "pseudonym_handle" in result
    assert result["pseudonym_handle"].startswith("Contributor_")
    assert "talent_id" not in result
    assert "display_name" not in result
    assert result["ratings"] == [{"question": "Would you buy this?", "score": 4}]

    # The talent's own real-named record still shows the session
    handle = db.fetchval("SELECT handle FROM public.talent_pseudonyms WHERE talent_id = $1", talent_a_id)
    assert handle == result["pseudonym_handle"]


def test_pseudonym_is_persistent_and_unique_per_talent(client, db, brand_headers, talent_headers_factory, onboarded_brand, onboarded_admin):
    _complete_company_profile(client, brand_headers)
    client.put("/brands/insight/eligibility", json=_ELIGIBILITY_BODY, headers=brand_headers)
    talent_a_id, talent_a_user = _seed_talent(db, opt_in=True, categories=["gaming"])
    talent_b_id, talent_b_user = _seed_talent(db, opt_in=True, categories=["gaming"])

    campaign_1 = client.post(
        "/brands/insight/campaigns", json={**_INSIGHT_CAMPAIGN_BODY, "panel_size": 2}, headers=brand_headers
    ).json()
    client.post(f"/brands/insight/campaigns/{campaign_1['id']}/submit-for-review", headers=brand_headers)
    client.post(f"/admin/content-templates/insight-campaigns/{campaign_1['id']}/approve", headers=onboarded_admin)
    client.post(f"/brands/insight/campaigns/{campaign_1['id']}/activate", headers=brand_headers)

    campaign_2 = client.post(
        "/brands/insight/campaigns", json={**_INSIGHT_CAMPAIGN_BODY, "title": "Round 2", "panel_size": 2}, headers=brand_headers
    ).json()
    client.post(f"/brands/insight/campaigns/{campaign_2['id']}/submit-for-review", headers=brand_headers)
    client.post(f"/admin/content-templates/insight-campaigns/{campaign_2['id']}/approve", headers=onboarded_admin)
    client.post(f"/brands/insight/campaigns/{campaign_2['id']}/activate", headers=brand_headers)

    rows = db.fetch("SELECT talent_id, handle FROM public.talent_pseudonyms ORDER BY talent_id")
    handles = {str(r["talent_id"]): r["handle"] for r in rows}
    # Exactly one pseudonym per talent, reused across both campaigns.
    assert len(handles) == 2
    assert handles[talent_a_id] != handles[talent_b_id]


def test_insight_opt_out_talent_never_selected(client, db, brand_headers, onboarded_brand, onboarded_admin):
    _complete_company_profile(client, brand_headers)
    client.put("/brands/insight/eligibility", json=_ELIGIBILITY_BODY, headers=brand_headers)
    for _ in range(3):
        _seed_talent(db, opt_in=False, categories=["gaming"])

    created = client.post(
        "/brands/insight/campaigns", json={**_INSIGHT_CAMPAIGN_BODY, "panel_size": 1}, headers=brand_headers
    )
    campaign_id = created.json()["id"]
    client.post(f"/brands/insight/campaigns/{campaign_id}/submit-for-review", headers=brand_headers)
    client.post(f"/admin/content-templates/insight-campaigns/{campaign_id}/approve", headers=onboarded_admin)

    activated = client.post(f"/brands/insight/campaigns/{campaign_id}/activate", headers=brand_headers)
    assert activated.status_code == 400
    assert activated.json()["error"]["code"] == "insufficient_panel"
