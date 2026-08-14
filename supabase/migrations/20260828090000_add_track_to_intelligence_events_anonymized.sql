-- Migration: add_track_to_intelligence_events_anonymized
BEGIN;

ALTER TABLE public.intelligence_events_anonymized
    ADD COLUMN track TEXT NOT NULL DEFAULT 'brand';

-- For athletics, category = sport name (football, basketball, etc.)
-- The existing category values remain brand-category vocab for brand events.
-- Track discriminator makes the semantic difference structurally enforceable.

CREATE INDEX IF NOT EXISTS idx_intelligence_events_track
    ON public.intelligence_events_anonymized (track, category);

COMMIT;
