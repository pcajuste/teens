-- Migration: add_athletic_season_admin_flag_reason
--
-- ATHLETICS-8: admin flags an attested season for a sanity-check issue
-- (e.g. an obviously wrong stat) without notifying the talent. This is
-- an admin-internal note, separate from admin_verified/admin_verified_at.
ALTER TABLE public.athletic_seasons
    ADD COLUMN admin_flag_reason TEXT;
