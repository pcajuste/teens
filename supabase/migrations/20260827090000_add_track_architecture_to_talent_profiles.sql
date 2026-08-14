-- Migration: add_track_architecture_to_talent_profiles
--
-- goal_type is a Postgres enum. ALTER TYPE ... ADD VALUE cannot run inside
-- the same transaction block that later uses the new value (Postgres
-- restriction pre-v12 semantics still enforced for safety), so it is
-- committed on its own before the main transactional block below.
ALTER TYPE public.goal_type ADD VALUE IF NOT EXISTS 'brand_campaigns_completed';

BEGIN;

-- 1. Rename brand-specific cached fields
ALTER TABLE public.talent_profiles
    RENAME COLUMN total_campaigns_completed TO brand_campaigns_completed;

ALTER TABLE public.talent_profiles
    RENAME COLUMN average_rating TO brand_average_rating;

-- total_earnings_cents stays: it is the cross-track aggregate
-- (brand flat + milestones + challenge bonuses + future athletic NIL)

-- 2. Track registry
ALTER TABLE public.talent_profiles
    ADD COLUMN enabled_tracks TEXT[] NOT NULL DEFAULT '{"brand"}';

-- 3. Athletic cached fields (D1, D2 decisions)
--    No athletic_average_rating — removed per D2
ALTER TABLE public.talent_profiles
    ADD COLUMN athletic_seasons_completed INTEGER NOT NULL DEFAULT 0;

ALTER TABLE public.talent_profiles
    ADD COLUMN athletic_recruiter_interest_count INTEGER NOT NULL DEFAULT 0;

-- 4. Profile completeness split (D1 decision)
ALTER TABLE public.talent_profiles
    ADD COLUMN brand_completeness_score INTEGER NOT NULL DEFAULT 0;

ALTER TABLE public.talent_profiles
    ADD COLUMN athletic_completeness_score INTEGER NOT NULL DEFAULT 0;

-- profile_completeness_score already exists — semantics change:
-- it is now always = GREATEST(brand_completeness_score, athletic_completeness_score)
-- Application code enforces this; no DB constraint (see playbook D1).

-- 5. Backfill: existing profile_completeness_score -> brand_completeness_score
UPDATE public.talent_profiles
    SET brand_completeness_score = profile_completeness_score;
-- athletic_completeness_score stays 0 for all existing talents (correct —
-- no one has athletic data yet)

-- 6. GoalType data migration (D1 decision — schemas/talents.py GoalType rename)
UPDATE public.talent_goals
    SET goal_type = 'brand_campaigns_completed'
    WHERE goal_type = 'campaigns_completed';

-- 7. Indexes
CREATE INDEX IF NOT EXISTS idx_talent_profiles_enabled_tracks
    ON public.talent_profiles USING GIN (enabled_tracks);

CREATE INDEX IF NOT EXISTS idx_talent_profiles_brand_completeness
    ON public.talent_profiles (brand_completeness_score DESC)
    WHERE recruiter_visible = TRUE;

CREATE INDEX IF NOT EXISTS idx_talent_profiles_athletic_completeness
    ON public.talent_profiles (athletic_completeness_score DESC)
    WHERE recruiter_visible = TRUE
      AND 'athletics' = ANY(enabled_tracks);

COMMIT;
