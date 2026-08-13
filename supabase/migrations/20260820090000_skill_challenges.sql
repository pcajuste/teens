-- ──────────────────────────────────────────────────────────────────
-- Skill Challenges (Build Prompt 8G) -- an open, low-commitment
-- submission surface distinct from campaigns: unpaid, no FTC
-- disclosure, no parent approval gate. See Teenure_Build_Prompts.md
-- "8G. Skill Challenges" for the full design rationale ("THE
-- FUNDAMENTAL DISTINCTION FROM CAMPAIGNS"). DDL + RLS live together in
-- one migration file, matching this codebase's convention (see
-- 20260816090000_admin_portal.sql, 20260812120000_milestone_payments.sql)
-- rather than the separate enums/core_tables/indexes/rls split used
-- only for the original Section 7 schema. Every column/table here is
-- additive -- no existing column is dropped or renamed.
-- ──────────────────────────────────────────────────────────────────

CREATE TYPE challenge_submission_format AS ENUM ('text', 'file', 'both');
CREATE TYPE challenge_status AS ENUM ('draft', 'active', 'closed');
CREATE TYPE challenge_submission_status AS ENUM ('submitted', 'reviewed', 'converted', 'declined');

CREATE TABLE public.challenges (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  brand_id              UUID NOT NULL REFERENCES public.brand_profiles(id) ON DELETE RESTRICT,
  title                 TEXT NOT NULL,
  brief                 TEXT NOT NULL,
  category              TEXT NOT NULL,
  target_cities         TEXT[] NOT NULL DEFAULT '{}',
  submission_format     challenge_submission_format NOT NULL DEFAULT 'both',
  submission_prompt     TEXT NOT NULL,
  status                challenge_status NOT NULL DEFAULT 'draft',
  max_submissions       INTEGER,
  submissions_count     INTEGER NOT NULL DEFAULT 0,
  opens_at              TIMESTAMPTZ,
  closes_at             TIMESTAMPTZ,
  conversion_count      INTEGER NOT NULL DEFAULT 0,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE public.challenge_submissions (
  id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  challenge_id                UUID NOT NULL REFERENCES public.challenges(id) ON DELETE RESTRICT,
  talent_id                      UUID NOT NULL REFERENCES public.talent_profiles(id) ON DELETE RESTRICT,
  submission_text             TEXT,
  submission_file_urls        TEXT[] NOT NULL DEFAULT '{}',
  status                      challenge_submission_status NOT NULL DEFAULT 'submitted',
  -- Internal only -- never returned in any talent-facing endpoint
  -- response . Enforced twice over: RLS below (no talent-facing policy
  -- exposes this column to any role but the owning brand/service
  -- role) AND, per the spec's explicit instruction, as an application-
  -- layer serializer exclusion (see app/repositories/challenges_repository.py
  -- -- the talent-facing dataclass simply has no field for it, so there
  -- is no code path that could leak it even by omission-bug).
  brand_note                  TEXT,
  converted_to_campaign_id    UUID REFERENCES public.campaigns(id),
  payout_cents                INTEGER,
  payout_status               TEXT CHECK (payout_status IN ('pending', 'processing', 'paid', 'failed')),
  stripe_transfer_id          TEXT UNIQUE,
  submitted_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  reviewed_at                 TIMESTAMPTZ,
  converted_at                TIMESTAMPTZ,
  paid_at                     TIMESTAMPTZ,
  UNIQUE (challenge_id, talent_id)
);

ALTER TABLE public.talent_profiles
  ADD COLUMN challenges_submitted_count  INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN challenges_converted_count  INTEGER NOT NULL DEFAULT 0;
-- challenge_conversion_rate is NEVER stored -- always derived at the
-- API layer from these two counts (challenges_converted_count /
-- challenges_submitted_count, null-guarded against divide-by-zero) to
-- avoid drift, per the spec's explicit instruction.

CREATE INDEX idx_challenges_status_category
  ON public.challenges (status, category)
  WHERE status = 'active';
CREATE INDEX idx_challenges_brand
  ON public.challenges (brand_id, status);
CREATE INDEX idx_challenge_submissions_rep
  ON public.challenge_submissions (talent_id, status);
CREATE INDEX idx_challenge_submissions_challenge
  ON public.challenge_submissions (challenge_id, status);
CREATE INDEX idx_challenge_submissions_payout
  ON public.challenge_submissions (payout_status)
  WHERE payout_status IN ('pending', 'processing');

-- ──────────────────────────────────────────────────────────────────
-- RLS
-- ──────────────────────────────────────────────────────────────────

ALTER TABLE public.challenges ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.challenge_submissions ENABLE ROW LEVEL SECURITY;

-- challenges: brands read/write only their own (reuses the same
-- brand-ownership shape as rls.brand_owns_campaign, but challenges has
-- no campaigns FK to piggyback on, so this compares brand_id directly
-- against the brand_profiles row for the authenticated user -- same
-- ownership check rls.brand_owns_campaign performs internally, just
-- inlined here since there's no campaign_id to look up through).
CREATE POLICY "Brand manages own challenges"
  ON public.challenges FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM public.brand_profiles bp
      WHERE bp.id = challenges.brand_id AND bp.user_id = auth.uid()
    )
  );

-- Talents read only active challenges -- no talent can read draft or closed
-- challenges (spec: "No talent can read draft or closed challenges").
CREATE POLICY   "Talent reads active challenges"
  ON public.challenges FOR SELECT
  USING (challenges.status = 'active');

-- challenge_submissions: a talent reads/writes only their own rows.
CREATE POLICY   "Talent reads/writes own challenge_submissions rows"
  ON public.challenge_submissions FOR ALL
  USING (challenge_submissions.talent_id = rls.talent_id_for_user(auth.uid()));

-- Brands read all submissions for challenges they own. Not FOR ALL --
-- brand-side mutation happens through service-role application code
-- (review/convert/decline all run server-side, e.g. to guarantee
-- brand_note is only ever written by the endpoint that's supposed to
-- write it, not directly settable by a raw client UPDATE even from
-- the owning brand) -- matches how campaign_talents' own brand policy is
-- scoped in 20260811210400_rls.sql (also FOR ALL there, but every
-- brand-side mutation in this codebase already goes through
-- application code regardless of the USING clause's own permissiveness;
-- SELECT-only here is the more conservative, spec-literal choice: "Brands
-- read all submissions for challenges they own").
CREATE POLICY "Brand reads challenge_submissions on own challenges"
  ON public.challenge_submissions FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.challenges c
      JOIN public.brand_profiles bp ON bp.id = c.brand_id
      WHERE c.id = challenge_submissions.challenge_id AND bp.user_id = auth.uid()
    )
  );

-- No recruiter or parent policy on either table -- recruiters and
-- parents have no direct table access (spec, deliverable 5). Admin
-- uses the service-role connection, which bypasses RLS entirely.
