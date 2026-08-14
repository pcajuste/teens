-- Migration: widen_intelligence_events_status
--
-- ATHLETICS-8: intelligence_events_anonymized.status was a strict
-- talent_campaign_status enum (CHECK'd to 'confirmed'/'paid') -- correct
-- for the brand track, but athletic_seasons uses a different lifecycle
-- vocabulary ('attested'/'verified'). Rather than overload the brand
-- enum with athletic-only values, widen the column to TEXT and gate
-- the two vocabularies by the existing `track` discriminator column
-- (added in 20260828090000_add_track_to_intelligence_events_anonymized.sql).
BEGIN;

ALTER TABLE public.intelligence_events_anonymized
    DROP CONSTRAINT intelligence_events_anonymized_status_check;

ALTER TABLE public.intelligence_events_anonymized
    ALTER COLUMN status TYPE TEXT USING status::text;

ALTER TABLE public.intelligence_events_anonymized
    ADD CONSTRAINT intelligence_events_status_by_track CHECK (
        (track = 'brand' AND status IN ('confirmed', 'paid'))
        OR (track = 'athletics' AND status IN ('attested', 'verified'))
    );

COMMIT;
