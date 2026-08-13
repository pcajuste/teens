-- ──────────────────────────────────────────────────────────────────
-- Stripe Connect columns (Build Prompt 7) -- schema addition beyond
-- Section 7's verbatim talent_profiles table, flagged per that prompt's
-- deliverable 3: talent payouts (Prompt 10) require a Stripe Connect
-- account id per talent, and the onboarding flow needs to know whether
-- that account has finished onboarding (Stripe's account.updated
-- webhook is the source of truth for the latter, not a value we can
-- derive locally).
-- ──────────────────────────────────────────────────────────────────

ALTER TABLE public.talent_profiles
  ADD COLUMN stripe_account_id TEXT UNIQUE,
  ADD COLUMN stripe_onboarding_complete BOOLEAN NOT NULL DEFAULT FALSE;
