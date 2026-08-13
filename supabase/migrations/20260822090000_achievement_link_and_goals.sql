-- ──────────────────────────────────────────────────────────────────
-- Living Achievement Link + Goal Setting (Build Prompt 5 deliverables
-- 12 & 13). New migration per this codebase's post-Prompt-20 rule of
-- ALTER/CREATE-only forward-only migrations rather than editing past
-- ones.
-- ──────────────────────────────────────────────────────────────────

ALTER TABLE public.talent_profiles
  ADD COLUMN achievement_link_token          TEXT UNIQUE,
  ADD COLUMN verified_profile_public         BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN earnings_visible_on_public_profile BOOLEAN NOT NULL DEFAULT FALSE;

-- verified_profile_public defaults to recruiter_visible's current value
-- for existing rows (spec: "default true when recruiter_visible = true,
-- default false otherwise") -- new rows get FALSE above, matching
-- recruiter_visible's own default, then this backfill only affects
-- talents who were already recruiter_visible before this migration ran.
UPDATE public.talent_profiles SET verified_profile_public = TRUE WHERE recruiter_visible = TRUE;

CREATE TYPE goal_type AS ENUM (
  'campaigns_completed', 'earnings_total', 'categories_active', 'badges_earned', 'profile_completeness'
);
CREATE TYPE goal_status AS ENUM ('active', 'completed', 'abandoned');

CREATE TABLE public.talent_goals (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  talent_id       UUID NOT NULL REFERENCES public.talent_profiles(id) ON DELETE CASCADE,
  goal_type       goal_type NOT NULL,
  target_value    INTEGER NOT NULL CHECK (target_value > 0),
  target_date     DATE,
  current_value   INTEGER NOT NULL DEFAULT 0,
  status          goal_status NOT NULL DEFAULT 'active',
  completed_at    TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_talent_goals_talent_status ON public.talent_goals (talent_id, status);

-- Enforces "maximum 3 active goals per talent" atomically at the DB
-- layer, not just in application code -- a partial unique index can't
-- express a count constraint directly, so this is a trigger rather
-- than a CHECK/EXCLUDE constraint. Mirrors this codebase's existing
-- preference for enforcing invariants close to the data when a simple
-- SQL constraint can express them (see e.g. campaign_milestones'
-- UNIQUE (campaign_id, milestone_number)); a count-based limit isn't
-- expressible that way, so a trigger is the least-worse option, kept
-- deliberately small (COUNT + RAISE, no other side effects).
CREATE OR REPLACE FUNCTION rls.enforce_max_active_goals() RETURNS TRIGGER AS $$
DECLARE
  active_count INTEGER;
BEGIN
  IF NEW.status = 'active' THEN
    SELECT COUNT(*) INTO active_count
    FROM public.talent_goals
    WHERE talent_id = NEW.talent_id AND status = 'active' AND id != NEW.id;
    IF active_count >= 3 THEN
      RAISE EXCEPTION 'max_active_goals_exceeded' USING ERRCODE = 'check_violation';
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_enforce_max_active_goals
  BEFORE INSERT OR UPDATE ON public.talent_goals
  FOR EACH ROW EXECUTE FUNCTION rls.enforce_max_active_goals();

-- ──────────────────────────────────────────────────────────────────
-- RLS
-- ──────────────────────────────────────────────────────────────────

ALTER TABLE public.talent_goals ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Talent reads/writes own goals"
  ON public.talent_goals FOR ALL
  USING (talent_id = rls.talent_id_for_user(auth.uid()));

-- No policy grants brand/recruiter/parent/anon access to talent_goals
-- or to the achievement-link columns on talent_profiles beyond what
-- the existing talent_profiles policies already allow -- default-deny
-- applies. The public /verified/:token route is served from
-- application code via the service-role connection (same pattern as
-- the intelligence layer and admin routes), never from an
-- authenticated-anon RLS policy, so there is deliberately no "anon can
-- read talent_profiles where verified_profile_public" policy here --
-- that would also leak non-public columns (Instagram/TikTok handles,
-- bio) to any authenticated Postgres role, not just the public
-- serializer's allow-listed fields.
