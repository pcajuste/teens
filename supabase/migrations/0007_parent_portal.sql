-- ────────────────────────────────────────────────────────────────────
-- Prompt 4A: Parent Portal.
--
-- Adds parent_records / parent_auth_tokens (Section 7 / Section 9A) and
-- the parent-approval-gate columns on campaign_reps. Parents are not
-- auth.users -- they authenticate via a separate magic-link + signed
-- session token flow (app.core.parent_security), never via Supabase
-- Auth, so there is no auth.uid() to write RLS policies against for the
-- two new tables (see the RLS section below).
-- ────────────────────────────────────────────────────────────────────

CREATE TYPE parent_approval_status AS ENUM ('not_required', 'pending', 'approved', 'blocked');

ALTER TABLE public.campaign_reps
  ADD COLUMN parent_approval_status   parent_approval_status NOT NULL DEFAULT 'not_required',
  ADD COLUMN parent_approval_deadline TIMESTAMPTZ,
  ADD COLUMN parent_decided_at        TIMESTAMPTZ;

CREATE INDEX idx_campaign_reps_parent_approval
  ON public.campaign_reps (parent_approval_status, parent_approval_deadline)
  WHERE parent_approval_status = 'pending';

-- ──────────────────────────────────────────────────────────────────
-- PARENT RECORDS -- one row per parent-of-a-minor-rep link.
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE public.parent_records (
  id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rep_id                      UUID NOT NULL UNIQUE REFERENCES public.rep_profiles(id) ON DELETE CASCADE,
  parent_email                TEXT NOT NULL,
  campaign_approval_required  BOOLEAN NOT NULL DEFAULT TRUE,
  values_filters              TEXT[] NOT NULL DEFAULT '{}',
  digest_enabled              BOOLEAN NOT NULL DEFAULT TRUE,
  portal_expires_at           TIMESTAMPTZ NOT NULL,
  suspended_by_parent_at      TIMESTAMPTZ,
  created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ──────────────────────────────────────────────────────────────────
-- PARENT AUTH TOKENS -- magic-link login, single-use, 15-minute expiry.
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE public.parent_auth_tokens (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  parent_record_id  UUID NOT NULL REFERENCES public.parent_records(id) ON DELETE CASCADE,
  token_hash        TEXT NOT NULL UNIQUE,
  expires_at        TIMESTAMPTZ NOT NULL,
  used_at           TIMESTAMPTZ,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_parent_records_rep ON public.parent_records (rep_id);
CREATE INDEX idx_parent_auth_tokens_expiry ON public.parent_auth_tokens (expires_at) WHERE used_at IS NULL;

-- ──────────────────────────────────────────────────────────────────
-- ROW LEVEL SECURITY
-- ──────────────────────────────────────────────────────────────────

ALTER TABLE public.parent_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.parent_auth_tokens ENABLE ROW LEVEL SECURITY;
-- Parents have no auth.uid() of their own (Section 9A) -- access is
-- enforced entirely at the application layer via the signed parent
-- session token (app.core.parent_security + app/routers/parent.py).
-- RLS is enabled with no policies, so the default-deny applies to any
-- connection that isn't the service-role key the API uses.
--
-- A rep must never be able to read their own parent_records row
-- directly (per the task spec) -- no policy is added granting
-- `rep_id`-owner access, intentionally.
