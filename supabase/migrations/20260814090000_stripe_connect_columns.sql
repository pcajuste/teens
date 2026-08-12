-- ──────────────────────────────────────────────────────────────────
-- Stripe Connect columns (Build Prompt 7) -- schema addition beyond
-- Section 7's verbatim rep_profiles table, flagged per that prompt's
-- deliverable 3: rep payouts (Prompt 10) require a Stripe Connect
-- account id per rep, and the onboarding flow needs to know whether
-- that account has finished onboarding (Stripe's account.updated
-- webhook is the source of truth for the latter, not a value we can
-- derive locally).
-- ──────────────────────────────────────────────────────────────────

ALTER TABLE public.rep_profiles
  ADD COLUMN stripe_account_id TEXT UNIQUE,
  ADD COLUMN stripe_onboarding_complete BOOLEAN NOT NULL DEFAULT FALSE;
