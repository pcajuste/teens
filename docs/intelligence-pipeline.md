# Intelligence Layer & Anonymization Pipeline

Build Prompt 14. Implements Section 3.5 ("The Intelligence Layer") and
the Section 9 anonymization requirement: *"Intelligence-layer data must
be anonymized and aggregated (minimum group size of 10) before any
trend report — never derived from individual rep records."*

This document exists so a future auditor can verify the anonymization
boundary by reading this page plus the handful of files it points to,
without having to read the whole codebase. Every claim below names an
exact file and, where useful, a line/function.

## The boundary, in one sentence

`public.intelligence_events_anonymized` has **no foreign key, and no
column that is a plausible foreign key, to any other table** — not
`rep_id`, not `campaign_id`, not `user_id`, nothing. This is enforced
by the table's DDL, not by a promise that application code won't join
it to anything.

- Table definition: `supabase/migrations/20260817090000_intelligence_layer.sql`
  — `CREATE TABLE public.intelligence_events_anonymized`. Its full
  column list is `id, category, city, state, school_type,
  time_period_bucket, status, payout_bucket, created_at`. None of these
  reference another table.
- Verified by a test that *attempts the join* directly against a real
  Postgres connection and asserts it is impossible (`UndefinedColumnError`
  for every plausible shared-key column), plus a second test that
  queries `information_schema.table_constraints` and asserts zero
  `FOREIGN KEY` constraints exist on the table:
  `apps/api/tests/test_intelligence.py::test_anonymized_table_has_no_identifying_join_path`
  and `::test_anonymized_table_has_no_foreign_keys`.

## Stage 1 — Source data (identifying, RLS-protected, unchanged by this prompt)

The pipeline's input is `public.campaign_reps` rows that have reached
`status IN ('confirmed', 'paid')` (`rep_campaign_status` enum,
`supabase/migrations/20260811210100_enums.sql`), joined to:

- `public.campaigns.target_categories` — the categories a row's events
  fan out across.
- `public.rep_profiles.city / state / school_type` — the fields that
  get bucketed into the anonymized row. `rep_profiles.school_type`
  (`supabase/migrations/20260811210200_core_tables.sql`, line ~28) is
  nullable and self-reported; this is the sole source of the
  `school_type` dimension. `rep_profiles` has no location field finer
  than `city`/`state` (no street address, no zip) — that is the
  most granular location this schema has anywhere, so there is nothing
  more identifying to additionally strip beyond what Stage 2 already
  strips.

This join lives in `apps/api/app/repositories/intelligence_repository.py`,
`_PENDING_QUERY` / `list_pending_events()`. It is allowed to see PII —
it runs entirely server-side, before anything is written to the
anonymized table, and its output (`PendingIntelligenceSource`) is never
itself persisted or returned by any API route.

## Stage 2 — PII stripping (the only place PII is dropped)

`apps/api/app/services/intelligence_service.py`, function `anonymize()`.

Explicitly enumerated per the build prompt, and confirmed dropped by
`apps/api/tests/test_intelligence.py::test_write_job_strips_all_pii`
(which seeds a `campaign_reps` row with every one of these fields
populated and asserts none of the values appear anywhere in the
resulting row):

| Source field | What happens to it |
|---|---|
| `campaign_reps.id` / `rep_id` | Dropped entirely — no column carries it |
| `rep_profiles.display_name` | Dropped entirely |
| `rep_profiles.school_name` | Dropped entirely |
| `rep_profiles.instagram_handle` | Dropped entirely |
| `rep_profiles.tiktok_handle` | Dropped entirely |
| `rep_profiles.city` / `state` (individual-level — the only granularity this schema has) | Kept, but only as the aggregate dimension used for the region trend cut — never combined with any other column that could re-identify the rep |
| `campaigns.id` / `brand_id` | Dropped entirely — no column carries it |
| `campaign_reps.payout_cents` | Replaced by `_payout_bucket()`, a 5-bucket range (`under_50`, `50_150`, `150_300`, `300_500`, `500_plus`, in dollars) — the exact cents figure never reaches the anonymized table |
| `campaign_reps.confirmed_at` / `paid_at` | Replaced by `_time_period_bucket()`, a quarter string (`"2026-Q3"`) — no exact timestamp is stored |
| `rep_profiles.school_type` (nullable) | `_school_type_bucket()`: `NULL` → the literal string `"unspecified"`, never dropped |

One `AnonymizedEvent` is produced per category in `target_categories`
(a campaign can target multiple categories — Section 7's
`campaigns.target_categories` is an array), so `category` stays a
single-valued column rather than an array, keeping "trend by category"
a plain `GROUP BY`.

## Stage 3 — Write / trigger mechanism

Registered job: `apps/api/app/jobs/runner.py`,
`@register_job("write_intelligence_events")` /
`write_intelligence_events_job()`.

The Prompt 3 runner (`apps/api/app/jobs/runner.py`) is poll-based —
Railway cron hits `POST /internal/jobs/run/{job_name}`, there is no
per-row database trigger. "Fires when a `campaign_reps` row transitions
to `confirmed`/`paid`" is therefore implemented as: every run, process
every `confirmed`/`paid` row that hasn't been processed yet. The
"not yet processed" marker is `campaign_reps.intelligence_event_written_at`
(added by the same migration, `supabase/migrations/20260817090000_intelligence_layer.sql`,
bottom `ALTER TABLE public.campaign_reps ADD COLUMN
intelligence_event_written_at`) — set once a row's events are written
(`intelligence_repository.mark_written()`), so each transition is
anonymized exactly once. This bookkeeping column lives on the
already-identifying, already-RLS-protected `campaign_reps` table; it is
never copied onto `intelligence_events_anonymized` itself, so it can't
become an accidental join path.

Idempotency is covered by
`apps/api/tests/test_intelligence.py::test_write_job_marks_source_row_processed_and_is_idempotent`.

## Stage 4 — Storage

`public.intelligence_events_anonymized`
(`supabase/migrations/20260817090000_intelligence_layer.sql`). RLS is
enabled with **zero policies** — in Postgres, RLS-enabled + no policy
is default-deny for every role subject to RLS. Rep/brand/recruiter
sessions all authenticate as the Supabase `authenticated` role and get
no access at all, direct or joined. This mirrors the existing
`safety_reports` table's pattern
(`supabase/migrations/20260816090000_admin_portal.sql`) of relying on
the FastAPI app's `DATABASE_URL` connection
(`apps/api/app/db/pool.py`, which bypasses RLS for every table in this
codebase by design — see that module's own docstring) plus
`require_role("admin")` in application code, rather than a
Supabase-level admin RLS policy.

## Stage 5 — Read path (trend reports)

`apps/api/app/repositories/intelligence_repository.py`,
`trend_by_category()` / `trend_by_region()` / `trend_by_school_type()`.
Each queries **only** `public.intelligence_events_anonymized` — no
`JOIN`, no reference to any other table, by construction (read the
three functions; each is a single `SELECT ... FROM
public.intelligence_events_anonymized GROUP BY ...`).

Minimum-group-size-of-10 gate: `intelligence_repository.MIN_GROUP_SIZE
= 10` / `INSUFFICIENT_SAMPLE_SIZE = "insufficient sample size"`,
applied in `_bucket_from_rows()`. Any group with fewer than 10
underlying events returns the literal string `"insufficient sample
size"` for both `sample_size` and `completed_share` — never a real
number, never an empty/missing result. This applies uniformly to every
dimension value, including the `"unspecified"` school_type bucket (no
special-casing — same function, same gate).

Covered by:
- `test_group_below_ten_returns_insufficient_sample_size` (a group of
  8 → the marker)
- `test_group_at_or_above_ten_returns_real_numbers` (a group of 10 →
  real numbers)
- `test_null_school_type_buckets_to_unspecified_and_is_still_gated` (a
  `"unspecified"` group of 8 → still the marker, not exempt)
- `test_null_school_type_bucket_becomes_real_once_it_reaches_ten`

API surface: `apps/api/app/routers/admin.py`, the "Build Prompt 14
deliverable 4" section near the bottom —
`GET /admin/intelligence/trends/category`,
`GET /admin/intelligence/trends/region`,
`GET /admin/intelligence/trends/school-type`. All three sit under
`admin_router`, which carries `dependencies=[Depends(require_role("admin"))]`
at the router level (declared once, at the top of `admin.py`), so
no route in this file — these included — is reachable by any role
other than `admin`. Response shape:
`apps/api/app/schemas/intelligence.py`, `TrendBucketResponse` —
`sample_size: int | Literal["insufficient sample size"]` (and the same
union for `completed_share`), which makes the "never a real number
below 10" rule a type-level guarantee, not just a runtime check.

## What this pipeline deliberately does not do

- It does not report on individual reps, individual campaigns, or
  individual brands under any circumstance — there is no route, no
  repository function, and no column that could produce a
  single-row/single-entity result from this table.
- It does not use exact dollar amounts or exact timestamps anywhere in
  the anonymized table — everything is bucketed at write time
  (Stage 2), not at read time, so there's no raw-precision data sitting
  in storage waiting for a future query to leak it.
- It does not special-case the `"unspecified"` school_type bucket to
  bypass the minimum-group-size gate — it is gated exactly like every
  other value of every other dimension.
