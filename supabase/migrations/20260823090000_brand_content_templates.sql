-- ──────────────────────────────────────────────────────────────────
-- Brand Content Templates & Delivery Framework (Build Prompt 8I).
-- Column-level breakdown of docs/Teenure_Brand_Content_Templates.md,
-- expanded from the framework-only prompt the same way 8G/8H were
-- expanded from placeholders before being built. This migration covers
-- the prompt's own stated build sequence, steps 1-3:
--   1. Company Profile + Scholarship template
--   2. Skills Challenge template (content layer over Prompt 8G's
--      existing challenges/challenge_submissions -- no new submission
--      mechanics, just the missing brand-facing fields + moderation gate)
--   3. Insight & Feedback Campaign template (aggregated ratings only,
--      no open-response yet) + the pseudonym system it depends on
-- Steps 4-6 (Internship/Apprenticeship, interactive quiz builder,
-- Premium tier) are explicitly sequenced later in the prompt itself
-- ("fourth," "last," "build later, not on day one") and are not part
-- of this migration.
-- ──────────────────────────────────────────────────────────────────

-- ──────────────────────────────────────────────────────────────────
-- 1. Company Profile template -- the brand's home base, required
-- before any of the other templates can go live (enforced at the API
-- layer: see brands_repository.company_profile_complete).
-- ──────────────────────────────────────────────────────────────────

ALTER TABLE public.brand_profiles
  ADD COLUMN logo_url             TEXT,
  ADD COLUMN brand_color_primary  TEXT,                 -- hex, e.g. '#0D9B7A' -- brand's own color, not a Teenure DS token
  ADD COLUMN about_text           TEXT,                  -- "who we are," <=150 words, enforced at API layer
  ADD COLUMN why_on_teenure_text  TEXT;                  -- "why we're on Teenure," <=100 words, enforced at API layer

-- Insight & Feedback panel eligibility is opt-in, not automatic --
-- unlike Scholarship/Skills Challenge browsing, this template hands a
-- teen pre-release confidential material and a compensation-bearing
-- engagement without them ever choosing to apply (panel selection is
-- system-driven, not a talent-initiated application -- spec: "brand
-- cannot hand-select individual teens," and by the same logic the
-- platform shouldn't auto-enroll them either). Defaults FALSE.
ALTER TABLE public.talent_profiles
  ADD COLUMN insight_feedback_opt_in BOOLEAN NOT NULL DEFAULT FALSE;

-- ──────────────────────────────────────────────────────────────────
-- Shared moderation vocabulary -- every template's content rule is
-- "self-service to build, human review to publish." One enum reused
-- across scholarships, challenges (added below), and insight/feedback
-- campaigns rather than one bespoke enum per table.
-- ──────────────────────────────────────────────────────────────────

CREATE TYPE content_moderation_status AS ENUM ('draft', 'pending_review', 'approved', 'rejected');

-- ──────────────────────────────────────────────────────────────────
-- 2. Scholarship template
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE public.scholarships (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  brand_id               UUID NOT NULL REFERENCES public.brand_profiles(id) ON DELETE RESTRICT,
  title                  TEXT NOT NULL,
  award_amount_cents     INTEGER NOT NULL CHECK (award_amount_cents > 0),
  number_of_awards       INTEGER NOT NULL DEFAULT 1 CHECK (number_of_awards > 0),
  eligibility_criteria   JSONB NOT NULL DEFAULT '[]',   -- structured checklist: [{"label": "...", "required": true}]
  application_requirements TEXT NOT NULL,
  why_text               TEXT NOT NULL,                  -- required <=150-word "why we're offering this"
  image_url              TEXT,                            -- optional, pre-approved before going live
  video_url              TEXT,                            -- optional, pre-approved, <=60s, no autoplay (enforced at API/moderation layer)
  deadline               TIMESTAMPTZ NOT NULL,
  moderation_status      content_moderation_status NOT NULL DEFAULT 'draft',
  reviewed_by            UUID REFERENCES public.users(id),
  reviewed_at            TIMESTAMPTZ,
  rejection_reason       TEXT,
  status                 TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'closed')),
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT scholarships_live_requires_approval
    CHECK (status <> 'active' OR moderation_status = 'approved')
);

CREATE INDEX idx_scholarships_brand ON public.scholarships (brand_id, status);
CREATE INDEX idx_scholarships_moderation_queue ON public.scholarships (moderation_status) WHERE moderation_status = 'pending_review';
CREATE INDEX idx_scholarships_active_deadline ON public.scholarships (deadline) WHERE status = 'active';

CREATE TABLE public.scholarship_applications (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  scholarship_id    UUID NOT NULL REFERENCES public.scholarships(id) ON DELETE RESTRICT,
  talent_id         UUID NOT NULL REFERENCES public.talent_profiles(id) ON DELETE RESTRICT,
  response_text     TEXT NOT NULL,
  status            TEXT NOT NULL DEFAULT 'submitted' CHECK (status IN ('submitted', 'under_review', 'awarded', 'declined')),
  submitted_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  reviewed_at       TIMESTAMPTZ,

  UNIQUE (scholarship_id, talent_id)
);

CREATE INDEX idx_scholarship_applications_talent ON public.scholarship_applications (talent_id);
CREATE INDEX idx_scholarship_applications_scholarship ON public.scholarship_applications (scholarship_id, status);

-- ──────────────────────────────────────────────────────────────────
-- 3. Skills Challenge template -- content layer over Prompt 8G's
-- `challenges` table. No new submission mechanics; these are the
-- 8I-specific fields the 8G build didn't need, plus the moderation
-- gate 8I introduces platform-wide ("self-service to build, human
-- review to publish"), which 8G's activate_challenge endpoint did not
-- previously enforce.
-- ──────────────────────────────────────────────────────────────────

ALTER TABLE public.challenges
  ADD COLUMN goal_text          TEXT,
  ADD COLUMN rules_text         TEXT,
  ADD COLUMN judging_criteria   TEXT,
  ADD COLUMN prize_reward_text  TEXT,
  ADD COLUMN why_text           TEXT,
  ADD COLUMN moderation_status  content_moderation_status NOT NULL DEFAULT 'draft',
  ADD COLUMN reviewed_by        UUID REFERENCES public.users(id),
  ADD COLUMN reviewed_at        TIMESTAMPTZ,
  ADD COLUMN rejection_reason   TEXT;

CREATE INDEX idx_challenges_moderation_queue ON public.challenges (moderation_status) WHERE moderation_status = 'pending_review';

-- Existing rows from before this migration (8G build/tests) are
-- backfilled 'approved' so already-active challenges don't retroactively
-- violate the new activation gate below.
UPDATE public.challenges SET moderation_status = 'approved' WHERE status = 'active';

ALTER TABLE public.challenges
  ADD CONSTRAINT challenges_active_requires_approval
    CHECK (status <> 'active' OR moderation_status = 'approved');

-- ──────────────────────────────────────────────────────────────────
-- Pseudonym system -- reusable infrastructure, not specific to any one
-- template. One persistent handle per talent, generated once
-- (app/services/pseudonym_service.py), never regenerated, never
-- resolvable back to identity through any code path. Its first (and
-- for this migration, only) consumer is the Insight & Feedback
-- template below, but it is deliberately its own table rather than a
-- column on insight_feedback_* so any future brand-facing surface can
-- reuse the same handle per spec ("reusable infrastructure the
-- talents of the platform benefits from").
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE public.talent_pseudonyms (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  talent_id   UUID NOT NULL UNIQUE REFERENCES public.talent_profiles(id) ON DELETE RESTRICT,
  handle      TEXT NOT NULL UNIQUE,   -- e.g. "Contributor_4B7" -- see pseudonym_service.generate_handle
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ──────────────────────────────────────────────────────────────────
-- 4. Insight & Feedback Campaign template (aggregated ratings only --
-- structured open-response is explicitly deferred past this pass per
-- the prompt's own build sequencing).
-- ──────────────────────────────────────────────────────────────────

-- Vetting gate: baseline requirements every brand must clear before
-- their FIRST Insight & Feedback campaign can leave draft, checked at
-- the API layer against this row (app/services/insight_feedback_service.py).
-- One row per brand -- re-checked, never re-created, on each new
-- campaign attempt while any requirement is still false.
CREATE TABLE public.brand_insight_eligibility (
  brand_id                    UUID PRIMARY KEY REFERENCES public.brand_profiles(id) ON DELETE CASCADE,
  legal_entity_verified       BOOLEAN NOT NULL DEFAULT FALSE,
  named_contact_verified      BOOLEAN NOT NULL DEFAULT FALSE,
  business_presence_verified  BOOLEAN NOT NULL DEFAULT FALSE,   -- real site/product + professional email domain
  funding_confirmed           BOOLEAN NOT NULL DEFAULT FALSE,   -- payment clears before go-live
  content_agreement_signed    BOOLEAN NOT NULL DEFAULT FALSE,
  is_early_stage_startup      BOOLEAN NOT NULL DEFAULT FALSE,
  -- Extra bar for early-stage startups only -- ignored when
  -- is_early_stage_startup is FALSE.
  incorporated_3mo_or_backed  BOOLEAN NOT NULL DEFAULT FALSE,
  has_real_product            BOOLEAN NOT NULL DEFAULT FALSE,
  manually_reviewed_by        UUID REFERENCES public.users(id),
  manually_reviewed_at        TIMESTAMPTZ,
  updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE public.insight_feedback_campaigns (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  brand_id              UUID NOT NULL REFERENCES public.brand_profiles(id) ON DELETE RESTRICT,
  title                 TEXT NOT NULL,
  material_url          TEXT NOT NULL,               -- submitted material (file/embedded media)
  business_question     TEXT NOT NULL,                -- structured prompt
  feedback_format       TEXT NOT NULL DEFAULT 'rating_scale'
                           CHECK (feedback_format = 'rating_scale'),  -- structured Q&A / open response deferred past this pass
  panel_size            INTEGER NOT NULL CHECK (panel_size > 0),
  panel_criteria        JSONB NOT NULL DEFAULT '{}',  -- e.g. {"categories": ["gaming"], "min_graduation_year": 2026} -- system-applied, brand cannot hand-pick individuals
  compensation_cents    INTEGER NOT NULL CHECK (compensation_cents >= 0),
  confidentiality_terms TEXT NOT NULL,                -- shown to teen + parent before joining
  is_startup_validation BOOLEAN NOT NULL DEFAULT FALSE,
  opens_at              TIMESTAMPTZ,
  closes_at             TIMESTAMPTZ,
  moderation_status     content_moderation_status NOT NULL DEFAULT 'draft',
  reviewed_by           UUID REFERENCES public.users(id),
  reviewed_at           TIMESTAMPTZ,
  rejection_reason      TEXT,
  status                TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'closed')),
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT insight_feedback_campaigns_live_requires_approval
    CHECK (status <> 'active' OR moderation_status = 'approved')
);

CREATE INDEX idx_insight_campaigns_brand ON public.insight_feedback_campaigns (brand_id, status);
CREATE INDEX idx_insight_campaigns_moderation_queue ON public.insight_feedback_campaigns (moderation_status) WHERE moderation_status = 'pending_review';

-- Panel assignment -- system-selected against panel_criteria, never a
-- brand pick-list of individual teens (spec: "panel size and criteria
-- (brand cannot hand-select individual teens)"). No brand-facing
-- column here identifies the talent by anything but their pseudonym --
-- enforced at the serializer layer (app/schemas/insight_feedback.py
-- has no talent_id/display_name field on any brand-facing response ),
-- not just by omission from this table.
CREATE TABLE public.insight_feedback_panel_members (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id   UUID NOT NULL REFERENCES public.insight_feedback_campaigns(id) ON DELETE RESTRICT,
  talent_id     UUID NOT NULL REFERENCES public.talent_profiles(id) ON DELETE RESTRICT,
  pseudonym_id  UUID NOT NULL REFERENCES public.talent_pseudonyms(id) ON DELETE RESTRICT,
  invited_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  responded_at  TIMESTAMPTZ,

  UNIQUE (campaign_id, talent_id)
);

CREATE INDEX idx_insight_panel_members_talent ON public.insight_feedback_panel_members (talent_id);
CREATE INDEX idx_insight_panel_members_campaign ON public.insight_feedback_panel_members (campaign_id);

-- The response  itself. Brand-facing reads join through
-- pseudonym_id -> talent_pseudonyms.handle only; talent_id exists here
-- (and on panel_members above) purely so the talent's own real-named
-- record can log "Insight Session Completed" against their actual
-- profile (spec: "the teen always knows it's them; the brand never
-- does") and so payout can be processed. No repository function in
-- this build may join this table's talent_id back out through any
-- brand-facing route -- see Prompt 15's planned pseudonym-leak audit.
CREATE TABLE public.insight_feedback_responses (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id       UUID NOT NULL REFERENCES public.insight_feedback_campaigns(id) ON DELETE RESTRICT,
  panel_member_id   UUID NOT NULL UNIQUE REFERENCES public.insight_feedback_panel_members(id) ON DELETE RESTRICT,
  ratings           JSONB NOT NULL,   -- structured: [{"question": "...", "score": 1-5}]
  submitted_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  payout_status     payout_status NOT NULL DEFAULT 'pending',
  stripe_transfer_id TEXT UNIQUE
);

CREATE INDEX idx_insight_responses_campaign ON public.insight_feedback_responses (campaign_id);

-- ──────────────────────────────────────────────────────────────────
-- RLS
-- ──────────────────────────────────────────────────────────────────

ALTER TABLE public.scholarships ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scholarship_applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.talent_pseudonyms ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.brand_insight_eligibility ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.insight_feedback_campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.insight_feedback_panel_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.insight_feedback_responses ENABLE ROW LEVEL SECURITY;

-- Reusable helper, same pattern as rls.talent_id_for_user
-- (20260811210400_rls.sql) -- every new table below owns-checks
-- against a brand_profiles row rather than inlining the same subquery
-- five times.
CREATE OR REPLACE FUNCTION rls.brand_id_for_user(p_user_id UUID) RETURNS UUID
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public
AS $$
  SELECT id FROM public.brand_profiles WHERE user_id = p_user_id;
$$;

CREATE POLICY "Brand manages own scholarships"
  ON public.scholarships FOR ALL
  USING (brand_id = rls.brand_id_for_user(auth.uid()));

CREATE POLICY "Talent reads active scholarships"
  ON public.scholarships FOR SELECT
  USING (status = 'active');

CREATE POLICY "Talent reads/writes own scholarship_applications"
  ON public.scholarship_applications FOR ALL
  USING (talent_id = rls.talent_id_for_user(auth.uid()));

CREATE POLICY "Brand reads applications on own scholarships"
  ON public.scholarship_applications FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.scholarships s
      WHERE s.id = scholarship_applications.scholarship_id
        AND s.brand_id = rls.brand_id_for_user(auth.uid())
    )
  );

-- No policy at all for brand/recruiter/admin roles on
-- talent_pseudonyms -- default-deny. The one brand-facing surface that
-- ever needs a handle (insight_feedback_panel_members /
-- insight_feedback_responses, joined at the application layer) reads
-- through the service-role connection, same as every credit-gated
-- recruiter read (app/db/pool.py). No RLS SELECT policy exposes this
-- table to any authenticated role, brand included.
CREATE POLICY "Talent reads own pseudonym"
  ON public.talent_pseudonyms FOR SELECT
  USING (talent_id = rls.talent_id_for_user(auth.uid()));

CREATE POLICY "Brand manages own insight eligibility"
  ON public.brand_insight_eligibility FOR ALL
  USING (brand_id = rls.brand_id_for_user(auth.uid()));

CREATE POLICY "Brand manages own insight campaigns"
  ON public.insight_feedback_campaigns FOR ALL
  USING (brand_id = rls.brand_id_for_user(auth.uid()));

-- No talent-facing SELECT policy on insight_feedback_campaigns by
-- city/category the way scholarships/challenges have -- panel
-- selection is system-driven (see panel_criteria above), not
-- something a talent browses/opts into directly, so there's nothing
-- for a blanket "talent reads active X" policy to gate here.

CREATE POLICY "Talent reads own panel membership"
  ON public.insight_feedback_panel_members FOR SELECT
  USING (talent_id = rls.talent_id_for_user(auth.uid()));

CREATE POLICY "Talent reads/writes own insight responses"
  ON public.insight_feedback_responses FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM public.insight_feedback_panel_members m
      WHERE m.id = insight_feedback_responses.panel_member_id
        AND m.talent_id = rls.talent_id_for_user(auth.uid())
    )
  );

-- No brand SELECT policy on insight_feedback_panel_members/_responses:
-- brand-facing reads (aggregated ratings + pseudonym handle only) are
-- served exclusively through the service-role connection via
-- app/repositories/insight_feedback_repository.py's brand-facing
-- query, which selects pseudonym handle and never talent_id/display
-- name -- the enforcement point is that repository function's column
-- list, not an RLS policy (mirrors challenge_submissions.brand_note's
-- documented double-enforcement above).
