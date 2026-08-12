-- ──────────────────────────────────────────────────────────────────
-- Stripe webhook idempotency table (Build Prompt 10) -- schema
-- addition beyond Section 7's verbatim tables, flagged per that
-- prompt's own acceptance criterion: "Same webhook payload twice -> no
-- duplicate side effects." Stripe's event id is globally unique and
-- guaranteed stable across retries, so a PRIMARY KEY insert-or-skip on
-- it is the dedup mechanism -- no separate lock table needed.
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE public.stripe_events (
  event_id     TEXT PRIMARY KEY,
  event_type   TEXT NOT NULL,
  processed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- RLS enabled on every table from the first migration (Section 9). No
-- policies needed -- this table is only ever touched by app/routers/
-- webhooks.py's service-role connection, never by an end-user session.
ALTER TABLE public.stripe_events ENABLE ROW LEVEL SECURITY;
