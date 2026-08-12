-- ──────────────────────────────────────────────────────────────────
-- Intelligence Layer & Anonymization Pipeline (Build Prompt 14) --
-- Section 3.5 / Section 9. Not in Section 7 -- a new, separately-
-- numbered migration, per the prompt's own instruction not to alter
-- already-applied migrations.
--
-- public.intelligence_events_anonymized is the sole read surface for
-- Stream Two ("Intelligence Subscription", Section 4) trend reports.
-- The anonymization boundary here is structural, not a convention:
--   - No column in this table is a foreign key to any other table.
--     There is no campaign_id, rep_id, brand_id, campaign_rep_id, or
--     user_id column at all -- not even an unconstrained one -- so no
--     join back to rep_profiles/users/campaign_reps/campaigns can ever
--     be expressed, structurally, regardless of what future
--     application code tries to do. See
--     apps/api/tests/test_intelligence.py::test_anonymized_table_has_no_identifying_join_path
--     for the test that proves this by attempting the join directly.
--   - Every column is either an aggregate/bucketed dimension (category,
--     city, state, school_type, time_period_bucket, payout_bucket) or a
--     coarse outcome flag (status) -- nothing that, combined, narrows
--     to a single identifiable person the way e.g. rep_id + exact
--     payout_cents + exact timestamp could.
--   - school_type is nullable at the source (rep_profiles.school_type,
--     self-reported at onboarding) but is NEVER written NULL here --
--     the write path (app/services/intelligence_service.py) buckets a
--     NULL source value into the literal 'unspecified' group so the
--     row is still counted in trend reports instead of silently
--     dropped, and 'unspecified' is still subject to the same
--     minimum-group-size-of-10 gate as every other school_type value
--     (enforced in app/repositories/intelligence_repository.py, not
--     here -- the gate is aggregation-time logic, not a DB constraint).
--
-- rep_profiles has no location field finer than city/state (see
-- 20260811210200_core_tables.sql -- there is no street address or zip
-- column in this schema), so "city at individual level" and the
-- aggregate/bucketable city referenced by the build prompt are the
-- same rep_profiles.city/state values; there is nothing more granular
-- to additionally strip.
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE public.intelligence_events_anonymized (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Dimensions (all bucketed/aggregate -- never an identifying id)
  category            TEXT NOT NULL,
  -- One row is written per campaign target category (a campaign can
  -- target multiple categories -- Section 7's campaigns.target_categories
  -- is an array); exploding to one row per category keeps this column a
  -- single value so "trend report by category" is a plain GROUP BY.
  city                TEXT NOT NULL,
  state               TEXT NOT NULL,
  school_type         TEXT NOT NULL
                         CHECK (school_type IN ('public','private','charter','homeschool','unspecified')),
  time_period_bucket  TEXT NOT NULL,
  -- Quarterly bucket, e.g. '2026-Q3' -- matches Section 4's "quarterly
  -- trend reports" cadence. Derived from the campaign_reps transition
  -- timestamp (confirmed_at/paid_at), never from a raw timestamp
  -- column on this table, so no event can be pinpointed to a specific
  -- day/time.

  -- Campaign-performance metrics needed for trend reports (Section
  -- 3.5/4) -- all bucketed or coarse, never an exact dollar figure or
  -- a link back to which campaign/brand produced them.
  status              rep_campaign_status NOT NULL CHECK (status IN ('confirmed','paid')),
  payout_bucket       TEXT NOT NULL,
  -- Bucketed payout_per_rep amount (see intelligence_service.py's
  -- _payout_bucket for the exact ranges) -- never payout_cents itself,
  -- which combined with a category/city/quarter could otherwise narrow
  -- to a specific campaign.

  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.intelligence_events_anonymized IS
  'Anonymized/aggregated intelligence-layer events (Build Prompt 14). '
  'Deliberately has no foreign key to any other table -- see migration '
  'header comment. Never insert an identifying column here.';

CREATE INDEX idx_intelligence_events_category ON public.intelligence_events_anonymized (category);
CREATE INDEX idx_intelligence_events_region ON public.intelligence_events_anonymized (city, state);
CREATE INDEX idx_intelligence_events_school_type ON public.intelligence_events_anonymized (school_type);

ALTER TABLE public.intelligence_events_anonymized ENABLE ROW LEVEL SECURITY;

-- No policies: RLS-enabled with zero policies is default-deny for
-- every Postgres role subject to RLS (anon/authenticated), so rep,
-- brand, and recruiter sessions -- which all go through PostgREST/
-- Supabase Auth as 'authenticated' -- get no access whatsoever, direct
-- or joined. The FastAPI app's admin routes read this table over
-- app/db/pool.py's DATABASE_URL connection, which (like every other
-- table in this codebase -- see that module's own docstring) connects
-- as a role that bypasses RLS entirely and enforces authorization in
-- application code (require_role("admin")) instead. This mirrors
-- 20260816090000_admin_portal.sql's safety_reports table, which
-- likewise defines no admin-specific policy for the same reason.

-- ──────────────────────────────────────────────────────────────────
-- Write-path bookkeeping: which campaign_reps rows have already been
-- turned into an intelligence_events_anonymized batch, so the
-- poll-based job (Prompt 3's runner has no per-row DB trigger --
-- see app/jobs/runner.py) doesn't double-write on every run. This
-- column lives on campaign_reps (the source-of-truth table, already
-- FK-protected and RLS-protected) -- it is never copied onto the
-- anonymized table itself, so it cannot become a join path back.
-- ──────────────────────────────────────────────────────────────────

ALTER TABLE public.campaign_reps
  ADD COLUMN intelligence_event_written_at TIMESTAMPTZ;

CREATE INDEX idx_campaign_reps_intelligence_pending
  ON public.campaign_reps (status)
  WHERE intelligence_event_written_at IS NULL AND status IN ('confirmed', 'paid');
