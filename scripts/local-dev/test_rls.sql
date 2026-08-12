-- ══════════════════════════════════════════════════════════════════
-- RLS PROOF SCRIPT (local dev only)
--
-- Run after apply_migrations.sh + seed.sh:
--   docker exec -i teenure_postgres psql -U teenure -d teenure -f - < scripts/local-dev/test_rls.sql
-- (or scripts/local-dev/test_rls.sh)
--
-- Simulates Supabase's request.jwt.claims GUC the way PostgREST does,
-- via SET LOCAL inside each transaction. auth.uid() / auth.parent_record_id()
-- (defined in the RLS migration) read this GUC exactly like Supabase's
-- production auth.uid() reads the real JWT -- so this is a faithful
-- local simulation of the same enforcement path, not a different one.
--
-- IMPORTANT: the seed data was inserted by the `teenure` superuser-ish
-- role, which normally bypasses RLS. To actually exercise RLS we must
-- run these SELECTs as a non-bypassrls role. We create one here,
-- scoped to this script (idempotent -- DROP/CREATE), matching what the
-- Supabase `authenticated` role would be in production.
-- ══════════════════════════════════════════════════════════════════

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    CREATE ROLE authenticated NOLOGIN NOBYPASSRLS;
  END IF;
END$$;

GRANT USAGE ON SCHEMA public TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT USAGE ON SCHEMA auth TO authenticated;
GRANT USAGE ON SCHEMA rls TO authenticated;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA rls TO authenticated;

-- ──────────────────────────────────────────────────────────────────
-- TEST 1: a rep cannot read another rep's row.
-- Session = rep aaaaaaaa-...0002 (Sam, 16yo). Expect to see ONLY their
-- own rep_profiles row (via "Rep owns their profile"), even though
-- rep_profiles has 3 rows total and this session isn't a recruiter, so
-- the recruiter-visibility policy doesn't apply either.
-- ──────────────────────────────────────────────────────────────────

BEGIN;
  SET LOCAL ROLE authenticated;
  SET LOCAL request.jwt.claims = '{"sub":"11111111-1111-1111-1111-111111111102","role":"authenticated"}';

  \echo '--- TEST 1: rep session (Sam, 16yo) selecting from rep_profiles ---'
  SELECT id, display_name FROM public.rep_profiles ORDER BY display_name;
  \echo '--- expected: exactly 1 row, "Sam Okafor (seed)" ---'
ROLLBACK;

-- ──────────────────────────────────────────────────────────────────
-- TEST 2: a recruiter sees only recruiter_visible = TRUE reps.
-- Session = recruiter cccccccc-...0001. Seed data: Jordan (adult,
-- recruiter_visible=TRUE), Sam (16yo, recruiter_visible=TRUE), Casey
-- (15yo, recruiter_visible=FALSE). Expect Jordan + Sam only.
-- ──────────────────────────────────────────────────────────────────

BEGIN;
  SET LOCAL ROLE authenticated;
  SET LOCAL request.jwt.claims = '{"sub":"33333333-3333-3333-3333-333333333301","role":"authenticated"}';

  \echo '--- TEST 2: recruiter session selecting from rep_profiles ---'
  SELECT id, display_name, recruiter_visible FROM public.rep_profiles ORDER BY display_name;
  \echo '--- expected: exactly 2 rows (Jordan, Sam), both recruiter_visible = TRUE; Casey absent ---'
ROLLBACK;

-- ──────────────────────────────────────────────────────────────────
-- TEST 3: a parent can read only their own parent_records row.
-- Session = parent dddddddd-...0001 (Sam's parent), simulated via
-- request.jwt.claims.parent_record_id (not auth.uid() -- parents have
-- no Supabase identity, see the RLS migration's comment block).
-- There are 2 parent_records rows total (Sam's + Casey's). Expect 1.
-- ──────────────────────────────────────────────────────────────────

BEGIN;
  SET LOCAL ROLE authenticated;
  SET LOCAL request.jwt.claims = '{"parent_record_id":"dddddddd-0000-0000-0000-000000000001","role":"parent"}';

  \echo '--- TEST 3: parent session selecting from parent_records ---'
  SELECT parent_id, rep_id, parent_email FROM public.parent_records;
  \echo '--- expected: exactly 1 row, parent_id = dddddddd-...0001 (linked to Sam) ---'

  \echo '--- TEST 3b: same parent session attempting to read the OTHER parent record by id (should be filtered out, not error) ---'
  SELECT parent_id FROM public.parent_records WHERE parent_id = 'dddddddd-0000-0000-0000-000000000002';
  \echo '--- expected: 0 rows ---'
ROLLBACK;

-- ──────────────────────────────────────────────────────────────────
-- TEST 4 (bonus, Build Prompt 2's campaigns addition): a rep whose
-- campaign_reps.parent_approval_status = 'pending' cannot read that
-- campaign row, even though a campaign_reps row links them to it.
-- Session = rep Sam (16yo), whose seed campaign_reps row is 'pending'.
-- ──────────────────────────────────────────────────────────────────

BEGIN;
  SET LOCAL ROLE authenticated;
  SET LOCAL request.jwt.claims = '{"sub":"11111111-1111-1111-1111-111111111102","role":"authenticated"}';

  \echo '--- TEST 4: rep session (Sam, pending parent approval) selecting from campaigns ---'
  SELECT id, title FROM public.campaigns;
  \echo '--- expected: 0 rows (parent_approval_status = pending blocks visibility) ---'
ROLLBACK;

BEGIN;
  SET LOCAL ROLE authenticated;
  SET LOCAL request.jwt.claims = '{"sub":"11111111-1111-1111-1111-111111111101","role":"authenticated"}';

  \echo '--- TEST 4b: rep session (Jordan, adult, not_required) selecting from campaigns ---'
  SELECT id, title FROM public.campaigns;
  \echo '--- expected: 1 row, "Fall Sneaker Launch (seed)" ---'
ROLLBACK;
