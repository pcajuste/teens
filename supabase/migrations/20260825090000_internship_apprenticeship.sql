-- ──────────────────────────────────────────────────────────────────
-- Internship / Apprenticeship template (Build Prompt 8I, step 4 --
-- issue #50). Fourth of the five 8I templates, sequenced after
-- Company Profile + Scholarship, Skills Challenge, and Insight &
-- Feedback (20260823090000_brand_content_templates.sql) specifically
-- because it carries the most legal weight of the five: minors plus
-- labor/earnings questions. Mirrors the Scholarship table shape
-- exactly (same moderation vocabulary, same live-requires-approval
-- gate, same brand-owns/talent-applies RLS split) -- see
-- docs/Teenure_Brand_Content_Templates.md Section 2C for the field
-- list this table implements.
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE public.internships (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  brand_id                 UUID NOT NULL REFERENCES public.brand_profiles(id) ON DELETE RESTRICT,
  role_title               TEXT NOT NULL,
  description              TEXT NOT NULL,
  time_commitment          TEXT NOT NULL,                 -- e.g. "10 hrs/week, 8 weeks" -- free text, not a structured schedule
  -- Compensation is a closed set (paid/stipend/unpaid) plus a required
  -- "why" when unpaid or stipend-only -- content rule parallels every
  -- other template's required why_text, but scoped here to the one
  -- field the legal brief flags (earnings/labor, not tone).
  compensation_type        TEXT NOT NULL CHECK (compensation_type IN ('paid', 'stipend', 'unpaid')),
  compensation_why          TEXT NOT NULL,
  -- Brand-authored free text, not a platform-enforced numeric gate --
  -- the platform-wide hard age gate (under-13 blocked at signup,
  -- under-16 double opt-in) already governs who can ever hold a
  -- Teenure account at all; this field is the role's own stated
  -- minimum within that population, same as any other requirement.
  requirements_text        TEXT NOT NULL,
  application_process_text TEXT NOT NULL,                 -- must stay on-platform; no off-platform redirect (content rule, enforced at API layer)
  why_text                 TEXT NOT NULL,                  -- required <=150-word "why we're offering this", same as every other template
  deadline                 TIMESTAMPTZ NOT NULL,
  moderation_status        content_moderation_status NOT NULL DEFAULT 'draft',
  reviewed_by               UUID REFERENCES public.users(id),
  reviewed_at               TIMESTAMPTZ,
  rejection_reason          TEXT,
  status                    TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'closed')),
  created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT internships_live_requires_approval
    CHECK (status <> 'active' OR moderation_status = 'approved')
);

CREATE INDEX idx_internships_brand ON public.internships (brand_id, status);
CREATE INDEX idx_internships_moderation_queue ON public.internships (moderation_status) WHERE moderation_status = 'pending_review';
CREATE INDEX idx_internships_active_deadline ON public.internships (deadline) WHERE status = 'active';

CREATE TABLE public.internship_applications (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  internship_id     UUID NOT NULL REFERENCES public.internships(id) ON DELETE RESTRICT,
  talent_id         UUID NOT NULL REFERENCES public.talent_profiles(id) ON DELETE RESTRICT,
  response_text     TEXT NOT NULL,
  status            TEXT NOT NULL DEFAULT 'submitted' CHECK (status IN ('submitted', 'under_review', 'accepted', 'declined')),
  submitted_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  reviewed_at       TIMESTAMPTZ,

  UNIQUE (internship_id, talent_id)
);

CREATE INDEX idx_internship_applications_talent ON public.internship_applications (talent_id);
CREATE INDEX idx_internship_applications_internship ON public.internship_applications (internship_id, status);

-- ──────────────────────────────────────────────────────────────────
-- RLS
-- ──────────────────────────────────────────────────────────────────

ALTER TABLE public.internships ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.internship_applications ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Brand manages own internships"
  ON public.internships FOR ALL
  USING (brand_id = rls.brand_id_for_user(auth.uid()));

CREATE POLICY "Talent reads active internships"
  ON public.internships FOR SELECT
  USING (status = 'active');

CREATE POLICY "Talent reads/writes own internship_applications"
  ON public.internship_applications FOR ALL
  USING (talent_id = rls.talent_id_for_user(auth.uid()));

CREATE POLICY "Brand reads applications on own internships"
  ON public.internship_applications FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.internships i
      WHERE i.id = internship_applications.internship_id
        AND i.brand_id = rls.brand_id_for_user(auth.uid())
    )
  );
