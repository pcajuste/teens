-- Migration: add_athletic_seasons_goal_type
--
-- ATHLETICS-4: talent_goals.goal_type is a Postgres enum. A talent must
-- be able to set an athletic_seasons_completed goal (e.g. "complete 3
-- seasons") once the athletic track is enabled -- add the enum value.
-- ALTER TYPE ... ADD VALUE cannot run inside a transaction block that
-- also uses the new value, so it is its own statement (same pattern as
-- 20260827090000_add_track_architecture_to_talent_profiles.sql).
ALTER TYPE public.goal_type ADD VALUE IF NOT EXISTS 'athletic_seasons_completed';
