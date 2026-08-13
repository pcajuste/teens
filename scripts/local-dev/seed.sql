-- ══════════════════════════════════════════════════════════════════
-- DEV-ONLY SEED SCRIPT -- NEVER RUN AGAINST PRODUCTION.
--
-- Idempotent: every INSERT uses a fixed, hardcoded UUID and
-- ON CONFLICT (id) DO NOTHING (or DO UPDATE where a value might
-- legitimately need refreshing), so running this script twice creates
-- no duplicate rows and raises no errors.
--
-- Creates fake users across all roles (talent, brand, recruiter, admin),
-- including a parent_records row linked to each under-18 talent, per
-- Build Prompt 2 deliverable 5.
--
-- Usage: psql -U teenure -d teenure -f scripts/local-dev/seed.sql
-- (or scripts/local-dev/seed.sh, which wraps this for the docker
-- container).
-- ══════════════════════════════════════════════════════════════════

BEGIN;

-- Guard rail: refuse to run if this doesn't look like a local dev DB.
-- Real Supabase projects have a populated auth.users managed by
-- GoTrue; this script inserts directly into auth.users, which only
-- exists as a real table on the local shim (see
-- 20260811210000_extensions_and_auth_shim.sql) -- on a real Supabase
-- project auth.users is a view/foreign table you cannot insert into
-- this way, so this script would simply fail there rather than
-- silently corrupting anything. Documented here as the actual safety
-- mechanism, not just a comment.

-- ──────────────────────────────────────────────────────────────────
-- auth.users shim rows (local-dev only -- a real Supabase project
-- creates these via GoTrue signup, never direct insert)
-- ──────────────────────────────────────────────────────────────────

INSERT INTO auth.users (id, email) VALUES
  ('11111111-1111-1111-1111-111111111101', 'talent.adult@seed.teenure.dev'),
  ('11111111-1111-1111-1111-111111111102', 'talent.minor16@seed.teenure.dev'),
  ('11111111-1111-1111-1111-111111111103', 'talent.minor15@seed.teenure.dev'),
  ('22222222-2222-2222-2222-222222222201', 'brand.acme@seed.teenure.dev'),
  ('33333333-3333-3333-3333-333333333301', 'recruiter.state-u@seed.teenure.dev'),
  ('44444444-4444-4444-4444-444444444401', 'admin@seed.teenure.dev')
ON CONFLICT (id) DO NOTHING;

-- ──────────────────────────────────────────────────────────────────
-- public.users
-- ──────────────────────────────────────────────────────────────────

INSERT INTO public.users (id, email, role, account_status, date_of_birth, parent_email, parent_verified_at)
VALUES
  ('11111111-1111-1111-1111-111111111101', 'talent.adult@seed.teenure.dev', 'talent', 'active',
    (CURRENT_DATE - INTERVAL '19 years')::date, NULL, NULL),
  ('11111111-1111-1111-1111-111111111102', 'talent.minor16@seed.teenure.dev', 'talent', 'active',
    (CURRENT_DATE - INTERVAL '16 years')::date, 'parent.of16@seed.teenure.dev', now()),
  ('11111111-1111-1111-1111-111111111103', 'talent.minor15@seed.teenure.dev', 'talent', 'active',
    (CURRENT_DATE - INTERVAL '15 years')::date, 'parent.of15@seed.teenure.dev', now()),
  ('22222222-2222-2222-2222-222222222201', 'brand.acme@seed.teenure.dev', 'brand', 'active',
    (CURRENT_DATE - INTERVAL '30 years')::date, NULL, NULL),
  ('33333333-3333-3333-3333-333333333301', 'recruiter.state-u@seed.teenure.dev', 'recruiter', 'active',
    (CURRENT_DATE - INTERVAL '35 years')::date, NULL, NULL),
  ('44444444-4444-4444-4444-444444444401', 'admin@seed.teenure.dev', 'admin', 'active',
    (CURRENT_DATE - INTERVAL '40 years')::date, NULL, NULL)
ON CONFLICT (id) DO UPDATE SET
  account_status = EXCLUDED.account_status,
  updated_at = now();

-- ──────────────────────────────────────────────────────────────────
-- talent_profiles (one adult, one 16yo, one 15yo -- both minors get a
-- parent_records row below; the 16yo demonstrates the toggleable
-- campaign_approval_required case, the 15yo demonstrates the
-- always-TRUE case)
-- ──────────────────────────────────────────────────────────────────

INSERT INTO public.talent_profiles (
  id, user_id, display_name, school_name, school_type, city, state,
  graduation_year, bio, categories, recruiter_visible
) VALUES
  ('aaaaaaaa-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111101',
    'Jordan Rivera (seed)', 'Lincoln High School', 'public', 'Austin', 'TX', 2025,
    'Adult talent seed fixture.', ARRAY['athletics','gaming'], TRUE),
  ('aaaaaaaa-0000-0000-0000-000000000002', '11111111-1111-1111-1111-111111111102',
    'Sam Okafor (seed)', 'Riverside Academy', 'private', 'Denver', 'CO', 2027,
    '16-year-old talent seed fixture.', ARRAY['fashion'], TRUE),
  ('aaaaaaaa-0000-0000-0000-000000000003', '11111111-1111-1111-1111-111111111103',
    'Casey Nguyen (seed)', 'Home Learning Collective', 'homeschool', 'Seattle', 'WA', 2028,
    '15-year-old talent seed fixture.', ARRAY['music'], FALSE)
ON CONFLICT (id) DO UPDATE SET
  display_name = EXCLUDED.display_name,
  updated_at = now();

-- ──────────────────────────────────────────────────────────────────
-- brand_profiles / recruiter_profiles
-- ──────────────────────────────────────────────────────────────────

INSERT INTO public.brand_profiles (id, user_id, company_name, website, industry, verified)
VALUES ('bbbbbbbb-0000-0000-0000-000000000001', '22222222-2222-2222-2222-222222222201',
  'Acme Sneaker Co (seed)', 'https://acme-seed.example.com', 'apparel', TRUE)
ON CONFLICT (id) DO UPDATE SET company_name = EXCLUDED.company_name, updated_at = now();

INSERT INTO public.recruiter_profiles (id, user_id, institution_name, institution_type, website, verified, contact_credits_remaining)
VALUES ('cccccccc-0000-0000-0000-000000000001', '33333333-3333-3333-3333-333333333301',
  'State University (seed)', 'college', 'https://stateu-seed.example.edu', TRUE, 25)
ON CONFLICT (id) DO UPDATE SET institution_name = EXCLUDED.institution_name, updated_at = now();

-- ──────────────────────────────────────────────────────────────────
-- parent_records -- linked to each under-18 talent (16yo and 15yo above).
-- portal_expires_at = talent's 18th birthday, derived from users.date_of_birth.
-- ──────────────────────────────────────────────────────────────────

INSERT INTO public.parent_records (
  parent_id, talent_id, parent_email, campaign_approval_required, values_filters,
  digest_enabled, portal_expires_at
)
SELECT
  'dddddddd-0000-0000-0000-000000000001', rp.id, u.parent_email,
  TRUE, '["gambling","alcohol_adjacent"]'::jsonb, TRUE,
  (u.date_of_birth + INTERVAL '18 years')::timestamptz
FROM public.talent_profiles rp
JOIN public.users u ON u.id = rp.user_id
WHERE rp.id = 'aaaaaaaa-0000-0000-0000-000000000002'
ON CONFLICT (talent_id) DO UPDATE SET
  values_filters = EXCLUDED.values_filters,
  updated_at = now();

INSERT INTO public.parent_records (
  parent_id, talent_id, parent_email, campaign_approval_required, values_filters,
  digest_enabled, portal_expires_at
)
SELECT
  'dddddddd-0000-0000-0000-000000000002', rp.id, u.parent_email,
  TRUE, '[]'::jsonb, TRUE,
  (u.date_of_birth + INTERVAL '18 years')::timestamptz
FROM public.talent_profiles rp
JOIN public.users u ON u.id = rp.user_id
WHERE rp.id = 'aaaaaaaa-0000-0000-0000-000000000003'
ON CONFLICT (talent_id) DO UPDATE SET
  values_filters = EXCLUDED.values_filters,
  updated_at = now();

-- ──────────────────────────────────────────────────────────────────
-- One sample campaign + campaign_talents row, useful for RLS/API testing.
-- ──────────────────────────────────────────────────────────────────

INSERT INTO public.campaigns (
  id, brand_id, title, status, product_name, campaign_goal, key_messaging,
  deliverables_description, target_categories, target_cities, max_talents,
  budget_cents, platform_fee_cents, talent_pool_cents, payout_per_talent_cents,
  start_date, end_date
) VALUES (
  'eeeeeeee-0000-0000-0000-000000000001', 'bbbbbbbb-0000-0000-0000-000000000001',
  'Fall Sneaker Launch (seed)', 'active', 'Acme Runner X', 'Drive awareness among HS athletes',
  'Highlight comfort and durability', 'One Instagram Reel + one TikTok',
  ARRAY['athletics'], ARRAY['Austin'], 5,
  100000, 35000, 65000, 13000,
  CURRENT_DATE, (CURRENT_DATE + INTERVAL '30 days')::date
)
ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, updated_at = now();

INSERT INTO public.campaign_talents (id, campaign_id, talent_id, status, parent_approval_status)
VALUES
  ('ffffffff-0000-0000-0000-000000000001', 'eeeeeeee-0000-0000-0000-000000000001',
    'aaaaaaaa-0000-0000-0000-000000000001', 'accepted', 'not_required'),
  ('ffffffff-0000-0000-0000-000000000002', 'eeeeeeee-0000-0000-0000-000000000001',
    'aaaaaaaa-0000-0000-0000-000000000002', 'invited', 'pending')
ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status, invited_at = campaign_talents.invited_at;

COMMIT;
