from __future__ import annotations

import uuid


def _seed_talent(db, *, recruiter_visible: bool = True, categories=None, city="Austin", state="TX") -> str:
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
        "INSERT INTO public.talent_profiles "
        "(id, user_id, display_name, school_name, city, state, graduation_year, categories, recruiter_visible) "
        "VALUES ($1, $2, 'Demo Fixture', 'Fixture High', $3, $4, 2027, $5, $6)",
        talent_id,
        talent_user_id,
        city,
        state,
        categories or [],
        recruiter_visible,
    )
    return talent_id


# GET /demo/recruiter-search -- Build Prompt 12A part 1: same repository
# query as the authenticated GET /recruiters/talents/search, but reachable
# with no session and no credit cost.


def test_demo_search_requires_no_auth(client, db):
    _seed_talent(db, city="Austin", state="TX", categories=["gaming"])
    response = client.get("/demo/recruiter-search")
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["city"] == "Austin"


def test_demo_search_returns_no_pii(client, db):
    _seed_talent(db)
    response = client.get("/demo/recruiter-search")
    card = response.json()[0]
    assert "display_name" not in card
    assert "instagram_handle" not in card
    assert "bio" not in card


def test_demo_search_filters_by_city(client, db):
    _seed_talent(db, city="Austin", state="TX")
    _seed_talent(db, city="Dallas", state="TX")
    response = client.get("/demo/recruiter-search", params={"city": "Dallas"})
    results = response.json()
    assert len(results) == 1
    assert results[0]["city"] == "Dallas"


def test_demo_search_excludes_non_recruiter_visible(client, db):
    _seed_talent(db, recruiter_visible=False)
    response = client.get("/demo/recruiter-search")
    assert response.json() == []
