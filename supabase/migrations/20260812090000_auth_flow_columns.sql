-- ──────────────────────────────────────────────────────────────────
-- Auth-flow columns (Build Prompt 4) -- not anticipated by Section 7's
-- verbatim users table, but required to literally implement its
-- Section 8/9 behavior:
--   - consent_token's 72-hour expiry must be "checked at verification,
--     not just at generation" (Prompt 4 deliverable 1), which requires
--     knowing when the current token was issued.
--   - POST /auth/resend-consent must be rate-limited (Prompt 4
--     deliverable 3); tracking the last send time in Postgres (rather
--     than in-process memory) keeps the limit correct if apps/api ever
--     runs more than one instance, without introducing a new piece of
--     infrastructure (e.g. Redis) not in Section 6's stack.
-- ──────────────────────────────────────────────────────────────────

ALTER TABLE public.users
  ADD COLUMN consent_token_issued_at TIMESTAMPTZ,
  ADD COLUMN consent_email_last_sent_at TIMESTAMPTZ;
