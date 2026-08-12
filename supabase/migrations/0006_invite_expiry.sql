-- ────────────────────────────────────────────────────────────────────
-- Addition beyond Section 7's literal schema (Prompt 5).
--
-- Section 3.2/Section 5 give campaign invites a 48-hour accept/decline
-- deadline, but Section 7's campaign_reps has no column to hold it.
-- Storing an explicit expiry (set at invite/apply time) rather than
-- computing "invited_at + 48h" on every read keeps the scheduled
-- expiry job (app/jobs/runner.py's `expire_invites`) a single indexed
-- range scan instead of a function-on-column scan.
-- ────────────────────────────────────────────────────────────────────

ALTER TABLE public.campaign_reps
  ADD COLUMN invite_expires_at TIMESTAMPTZ;

CREATE INDEX idx_campaign_reps_invited_expiry
  ON public.campaign_reps (status, invite_expires_at)
  WHERE status = 'invited';
