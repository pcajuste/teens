-- ──────────────────────────────────────────────────────────────────
-- Learning Modules and Verified Badges (Build Prompt 8H) -- short,
-- platform-curated educational content that talents complete to earn
-- verified profile badges. Modules are admin-created only; badges are
-- issued by Teenure, never self-reported. See
-- Teenure_Build_Prompts.md's "8H. Learning Modules and Verified
-- Badges" for the full design rationale. Follows this codebase's
-- convention of DDL + RLS living together in one migration file (see
-- 20260820090000_skill_challenges.sql). Every column/table here is
-- additive -- no existing column is dropped or renamed.
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE public.learning_modules (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title                 TEXT NOT NULL,
  description           TEXT NOT NULL,
  category              TEXT,
  -- Ordered array of content blocks. Quiz question objects within
  -- contain a correct_index field that is stored/evaluated
  -- server-side only -- it must NEVER appear in any client-facing API
  -- response , including admin preview mode. RLS cannot protect a jsonb
  -- sub-field, so this is enforced at the serializer layer (see
  -- ModulePublicSerializer in app/repositories/learning_modules_repository.py),
  -- not here.
  content_blocks        JSONB NOT NULL DEFAULT '[]',
  passing_score         INTEGER CHECK (passing_score IS NULL OR (passing_score BETWEEN 1 AND 100)),
  badge_title           TEXT NOT NULL,
  badge_description     TEXT NOT NULL,
  badge_color           TEXT NOT NULL,
  badge_icon            TEXT,
  estimated_minutes     INTEGER NOT NULL,
  status                TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'archived')),
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE public.talent_module_completions (
  id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  talent_id                      UUID NOT NULL REFERENCES public.talent_profiles(id) ON DELETE RESTRICT,
  module_id                   UUID NOT NULL REFERENCES public.learning_modules(id) ON DELETE RESTRICT,
  status                      TEXT NOT NULL DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'passed', 'failed')),
  quiz_score                  INTEGER,
  attempts                    INTEGER NOT NULL DEFAULT 1,
  last_attempt_at             TIMESTAMPTZ,
  passed_at                   TIMESTAMPTZ,
  -- Same as passed_at at MVP -- kept as a separate field anticipating a
  -- future where badge issuance could be decoupled from completion.
  badge_issued_at             TIMESTAMPTZ,
  disclosure_acknowledged_at  TIMESTAMPTZ,
  -- Unpaid at MVP (null). Exists so a future district-funded
  -- completion stipend can be added without a schema migration -- do
  -- not implement the payment logic yet, only the field (spec).
  payout_cents                INTEGER,
  payout_status               TEXT CHECK (payout_status IN ('pending', 'processing', 'paid', 'failed')),
  stripe_transfer_id          TEXT UNIQUE,
  UNIQUE (talent_id, module_id)
);

ALTER TABLE public.talent_profiles
  ADD COLUMN badges JSONB NOT NULL DEFAULT '[]',
  ADD COLUMN badges_earned_count INTEGER NOT NULL DEFAULT 0;

CREATE INDEX idx_learning_modules_status
  ON public.learning_modules (status) WHERE status = 'active';
CREATE INDEX idx_talent_module_completions_rep
  ON public.talent_module_completions (talent_id, status);
CREATE INDEX idx_talent_module_completions_ftc
  ON public.talent_module_completions (module_id, talent_id, status)
  WHERE status = 'passed';

-- ──────────────────────────────────────────────────────────────────
-- RLS
-- ──────────────────────────────────────────────────────────────────

ALTER TABLE public.learning_modules ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.talent_module_completions ENABLE ROW LEVEL SECURITY;

-- All authenticated users can read active modules. Draft/archived
-- modules are readable only via the service-role connection (admin
-- application code) -- no policy grants a non-service role access to
-- them.
CREATE POLICY "Authenticated users read active modules"
  ON public.learning_modules FOR SELECT
  TO authenticated
  USING (learning_modules.status = 'active');

-- talent_module_completions: talents read/insert/update only their own rows.
-- No other role has direct table access (admin uses service role).
CREATE POLICY   "Talent reads own module completions"
  ON public.talent_module_completions FOR SELECT
  USING (talent_module_completions.talent_id = rls.talent_id_for_user(auth.uid()));

CREATE POLICY   "Talent inserts own module completions"
  ON public.talent_module_completions FOR INSERT
  WITH CHECK (talent_module_completions.talent_id = rls.talent_id_for_user(auth.uid()));

CREATE POLICY   "Talent updates own module completions"
  ON public.talent_module_completions FOR UPDATE
  USING (talent_module_completions.talent_id = rls.talent_id_for_user(auth.uid()));
