-- ────────────────────────────────────────────────────────────────────
-- Addition beyond Section 7's literal schema (Prompt 4).
--
-- Section 7's public.users has `consent_token TEXT UNIQUE` but no way
-- to tell when it was issued (needed for the 72-hour expiry check) or
-- whether it has already been consumed (needed to return a distinct
-- "already used" error instead of a generic 400/404 on token replay,
-- per Prompt 4's acceptance criteria). Both are required to implement
-- Section 9's parental-consent flow as specified, not a discretionary
-- extension.
-- ────────────────────────────────────────────────────────────────────

ALTER TABLE public.users
  ADD COLUMN consent_token_created_at TIMESTAMPTZ,
  ADD COLUMN consent_token_expires_at TIMESTAMPTZ,
  ADD COLUMN consent_token_used_at    TIMESTAMPTZ;
