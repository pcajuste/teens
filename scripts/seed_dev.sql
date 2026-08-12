-- ════════════════════════════════════════════════════════════════════
-- DEV-ONLY SEED DATA. NEVER RUN THIS AGAINST A PRODUCTION DATABASE.
-- Creates one fake user per role (rep x2, brand, recruiter, admin) for
-- local development. Idempotent: every insert is ON CONFLICT DO NOTHING
-- keyed on a fixed, obviously-fake UUID, so re-running is a no-op.
-- ════════════════════════════════════════════════════════════════════

-- auth.users rows: on a real Supabase project these are normally created
-- via the Auth API, but a direct insert with a fake encrypted_password is
-- the standard way to seed local dev fixtures without running the full
-- signup flow. On the local test harness used by this repo's CI/dev
-- Postgres (scripts/local-dev/, not real Supabase), auth.users is a
-- stub table with just an id column -- adjust this block if seeding
-- against an actual Supabase local stack, whose auth.users has the
-- full Supabase Auth column set.

INSERT INTO auth.users (id) VALUES
  ('00000000-0000-0000-0000-000000000001'),
  ('00000000-0000-0000-0000-000000000002'),
  ('00000000-0000-0000-0000-000000000003'),
  ('00000000-0000-0000-0000-000000000004'),
  ('00000000-0000-0000-0000-000000000005')
ON CONFLICT DO NOTHING;

-- public.users

INSERT INTO public.users (id, email, role, account_status, date_of_birth, parent_email, parent_verified_at)
VALUES
  ('00000000-0000-0000-0000-000000000001', 'dev-rep-1@example.test', 'rep', 'active', '2008-05-14', NULL, NULL),
  ('00000000-0000-0000-0000-000000000002', 'dev-rep-2@example.test', 'rep', 'active', '2007-01-02', NULL, NULL),
  ('00000000-0000-0000-0000-000000000003', 'dev-brand-1@example.test', 'brand', 'active', '1990-01-01', NULL, NULL),
  ('00000000-0000-0000-0000-000000000004', 'dev-recruiter-1@example.test', 'recruiter', 'active', '1985-01-01', NULL, NULL),
  ('00000000-0000-0000-0000-000000000005', 'dev-admin-1@example.test', 'admin', 'active', '1980-01-01', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

-- rep_profiles

INSERT INTO public.rep_profiles (id, user_id, display_name, school_name, school_type, city, state, graduation_year, categories, recruiter_visible)
VALUES
  ('10000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 'Dev Rep One', 'Springfield High', 'public', 'Springfield', 'IL', 2026, ARRAY['athletics','gaming'], TRUE),
  ('10000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000002', 'Dev Rep Two', 'Shelbyville High', 'private', 'Shelbyville', 'IL', 2027, ARRAY['fashion'], FALSE)
ON CONFLICT (id) DO NOTHING;

-- brand_profiles

INSERT INTO public.brand_profiles (id, user_id, company_name, industry, target_categories, verified)
VALUES
  ('20000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000003', 'Dev Brand Co', 'apparel', ARRAY['fashion'], TRUE)
ON CONFLICT (id) DO NOTHING;

-- recruiter_profiles

INSERT INTO public.recruiter_profiles (id, user_id, institution_name, institution_type, verified, contact_credits_remaining)
VALUES
  ('30000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000004', 'Dev State University', 'college', TRUE, 10)
ON CONFLICT (id) DO NOTHING;
