-- ──────────────────────────────────────────────────────────────────
-- Parent portal columns (Build Prompt 4A) -- not anticipated by
-- Section 7's verbatim parent_records table, but required to
-- literally implement its Section 9A behavior:
--   - POST /parent/auth/request-link must be rate-limited (deliverable
--     1), same DB-backed-cooldown reasoning as the auth-flow columns
--     migration for /auth/resend-consent.
--   - GET /parent/digest/preview and the monthly digest job need to
--     report "profile completeness change ... since last digest",
--     which requires remembering the score and send time of the last
--     digest.
-- ──────────────────────────────────────────────────────────────────

ALTER TABLE public.parent_records
  ADD COLUMN magic_link_last_requested_at TIMESTAMPTZ,
  ADD COLUMN digest_last_sent_at TIMESTAMPTZ,
  ADD COLUMN last_digest_profile_completeness_score INTEGER;
