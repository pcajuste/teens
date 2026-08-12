"""Build Prompt 14: Intelligence Layer & Anonymization Pipeline.

Covers all 4 acceptance criteria:
  - the anonymized table is structurally unjoinable to any identifying
    table (test_anonymized_table_has_no_identifying_join_path)
  - a group of 8 -> "insufficient sample size" (test_group_below_ten_...)
  - PII-stripping unit test (test_write_job_strips_all_pii)
  - null school_type -> 'unspecified' bucket, still gated at 10
    (test_null_school_type_buckets_to_unspecified_and_is_still_gated)
"""
from __future__ import annotations

import asyncpg
import pytest

ADMIN_USER_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture()
def admin_headers(auth_headers_factory, db):
    db.execute("INSERT INTO auth.users (id, email) VALUES ($1, $2)", ADMIN_USER_ID, "admin@example.com")
    db.execute(
        "INSERT INTO public.users (id, email, role, account_status, date_of_birth) "
        "VALUES ($1, 'admin@example.com', 'admin', 'active', '1985-01-01')",
        ADMIN_USER_ID,
    )
    return auth_headers_factory("admin")


def _run_job(client, settings):
    response = client.post(
        "/internal/jobs/run/write_intelligence_events",
        headers={"X-Jobs-Runner-Secret": settings.jobs_runner_secret},
    )
    assert response.status_code == 200
    return response


# ══════════════════════════════════════════════════════════════════
# Structural anonymization boundary
# ══════════════════════════════════════════════════════════════════


def test_anonymized_table_has_no_identifying_join_path(db, settings):
    """Directly attempts to join intelligence_events_anonymized back to
    rep_profiles/users/campaign_reps on every plausible shared column
    name and asserts each attempt fails at the SQL level with
    "column does not exist" -- i.e. there is no shared key to join on,
    not merely that current app code doesn't perform the join."""

    async def _try_join(column: str, other_table: str):
        conn = await asyncpg.connect(dsn=settings.database_url)
        try:
            await conn.fetch(
                f"SELECT 1 FROM public.intelligence_events_anonymized iea "
                f"JOIN {other_table} t ON t.{column} = iea.{column} LIMIT 1"
            )
        finally:
            await conn.close()

    import asyncio

    # Deliberately excludes "id": every table has its own unrelated
    # primary key named "id" -- joining two tables' PKs together is
    # syntactically legal but not a meaningful identifying join path
    # (the values have no relationship to each other). What matters is
    # that there is no *foreign* key column shared between the tables.
    candidate_columns = ["rep_id", "campaign_id", "campaign_rep_id", "brand_id", "user_id"]
    other_tables = ["public.rep_profiles", "public.users", "public.campaign_reps", "public.campaigns"]

    for other_table in other_tables:
        for column in candidate_columns:
            with pytest.raises(asyncpg.exceptions.UndefinedColumnError):
                asyncio.run(_try_join(column, other_table))

    # Confirm the table's actual columns are exactly the anonymized/
    # bucketed set -- no id-shaped column beyond its own PK exists at all.
    cols = db.fetch(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = 'intelligence_events_anonymized'"
    )
    column_names = {c["column_name"] for c in cols}
    assert column_names == {
        "id", "category", "city", "state", "school_type", "time_period_bucket",
        "status", "payout_bucket", "created_at",
    }


def test_anonymized_table_has_no_foreign_keys(db):
    rows = db.fetch(
        """
        SELECT tc.constraint_type
        FROM information_schema.table_constraints tc
        WHERE tc.table_schema = 'public' AND tc.table_name = 'intelligence_events_anonymized'
          AND tc.constraint_type = 'FOREIGN KEY'
        """
    )
    assert rows == []


# ══════════════════════════════════════════════════════════════════
# PII stripping (write path)
# ══════════════════════════════════════════════════════════════════


def test_write_job_strips_all_pii(client, settings, db, seed_confirmed_campaign_rep):
    seed_confirmed_campaign_rep(status="confirmed", city="Austin", school_type="private")

    _run_job(client, settings)

    rows = db.fetch("SELECT * FROM public.intelligence_events_anonymized")
    assert len(rows) == 1
    row = rows[0]

    # Every PII field the build prompt enumerates is simply absent as a
    # column (see the schema-shape assertion above) -- this test also
    # checks none of the seeded PII *values* leaked into any surviving
    # text column, as a second, value-level guard.
    pii_values = {
        "Jordan PII-Test Rep",       # display_name
        "Identifying High School",    # school_name
        "jordan_ig_handle",           # instagram_handle
        "jordan_tt_handle",           # tiktok_handle
    }
    row_values = {str(v) for v in row.values()}
    assert not (pii_values & row_values)

    assert row["city"] == "Austin"  # aggregate-level city is retained, per spec
    assert row["school_type"] == "private"
    assert row["category"] == "gaming"
    assert row["status"] == "confirmed"
    assert row["payout_bucket"]  # bucketed, never the exact payout_cents


def test_write_job_marks_source_row_processed_and_is_idempotent(client, settings, db, seed_confirmed_campaign_rep):
    seeded = seed_confirmed_campaign_rep(status="paid")

    _run_job(client, settings)
    written_at = db.fetchval(
        "SELECT intelligence_event_written_at FROM public.campaign_reps WHERE id = $1", seeded.campaign_rep_id
    )
    assert written_at is not None

    # Running the job again must not double-write for the same row.
    _run_job(client, settings)
    count = db.fetchval("SELECT COUNT(*) FROM public.intelligence_events_anonymized")
    assert count == 1


def test_write_job_ignores_rows_not_yet_confirmed_or_paid(client, settings, db, seed_pending_campaign, seed_rep_with_parent):
    rep = seed_rep_with_parent()
    seed_pending_campaign(rep_id=rep.rep_id, parent_approval_status="pending")

    _run_job(client, settings)

    count = db.fetchval("SELECT COUNT(*) FROM public.intelligence_events_anonymized")
    assert count == 0


# ══════════════════════════════════════════════════════════════════
# Minimum group size gate (read path)
# ══════════════════════════════════════════════════════════════════


def _seed_n_events(client, settings, seed_confirmed_campaign_rep, n: int, **kwargs):
    for _ in range(n):
        seed_confirmed_campaign_rep(**kwargs)
    _run_job(client, settings)


def test_group_below_ten_returns_insufficient_sample_size(client, settings, db, seed_confirmed_campaign_rep, admin_headers):
    _seed_n_events(client, settings, seed_confirmed_campaign_rep, 8, city="Austin", state="TX", school_type="public")

    resp = client.get("/admin/intelligence/trends/category", headers=admin_headers)
    assert resp.status_code == 200
    buckets = resp.json()
    assert len(buckets) == 1
    bucket = buckets[0]
    assert bucket["sample_size"] == "insufficient sample size"
    assert bucket["completed_share"] == "insufficient sample size"
    assert not isinstance(bucket["sample_size"], (int, float))


def test_group_at_or_above_ten_returns_real_numbers(client, settings, db, seed_confirmed_campaign_rep, admin_headers):
    _seed_n_events(client, settings, seed_confirmed_campaign_rep, 10, city="Dallas", state="TX", school_type="public")

    resp = client.get("/admin/intelligence/trends/region", headers=admin_headers)
    assert resp.status_code == 200
    buckets = resp.json()
    assert len(buckets) == 1
    assert buckets[0]["sample_size"] == 10
    assert isinstance(buckets[0]["completed_share"], float)


# ══════════════════════════════════════════════════════════════════
# null school_type -> 'unspecified' bucket, still gated
# ══════════════════════════════════════════════════════════════════


def test_null_school_type_buckets_to_unspecified_and_is_still_gated(
    client, settings, db, seed_confirmed_campaign_rep, admin_headers
):
    _seed_n_events(client, settings, seed_confirmed_campaign_rep, 8, school_type=None)

    row = db.fetch("SELECT DISTINCT school_type FROM public.intelligence_events_anonymized")
    assert row == [{"school_type": "unspecified"}]

    resp = client.get("/admin/intelligence/trends/school-type", headers=admin_headers)
    assert resp.status_code == 200
    buckets = resp.json()
    assert len(buckets) == 1
    assert buckets[0]["group"] == "unspecified"
    # Still gated at 10 -- 'unspecified' is not exempt from the
    # minimum-group-size rule (build prompt acceptance criterion).
    assert buckets[0]["sample_size"] == "insufficient sample size"


def test_null_school_type_bucket_becomes_real_once_it_reaches_ten(
    client, settings, db, seed_confirmed_campaign_rep, admin_headers
):
    _seed_n_events(client, settings, seed_confirmed_campaign_rep, 10, school_type=None)

    resp = client.get("/admin/intelligence/trends/school-type", headers=admin_headers)
    buckets = resp.json()
    assert len(buckets) == 1
    assert buckets[0]["group"] == "unspecified"
    assert buckets[0]["sample_size"] == 10


# ══════════════════════════════════════════════════════════════════
# Admin-only access
# ══════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("role", ["rep", "brand", "recruiter"])
def test_non_admin_roles_cannot_read_trend_reports(client, auth_headers_factory, role):
    resp = client.get("/admin/intelligence/trends/category", headers=auth_headers_factory(role))
    assert resp.status_code == 403


def test_unauthenticated_cannot_read_trend_reports(client):
    resp = client.get("/admin/intelligence/trends/category")
    assert resp.status_code == 401
