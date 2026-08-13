-- ──────────────────────────────────────────────────────────────────
-- Milestone threshold progress (fills a gap left open in Build
-- Prompt 8B's own "FRONTEND ADDITIONS > UX guidance": "Where a
-- milestone involves a count or threshold the talent controls directly
-- (e.g. 'publish 3 pieces of content'), show real-time progress
-- toward it ('2 of 3 published') rather than a flat pending/done
-- state." 8B shipped only free-text title/description milestones with
-- a binary pending/submitted/confirmed/paid status, correctly leaving
-- this unbuilt rather than faking it -- this migration adds the
-- structured count field that requirement needs.
--
-- Fully additive/backward-compatible: campaign_milestones.threshold_count
-- is nullable and defaults to NULL, so every existing (and every new,
-- non-count-based) milestone is completely unaffected -- it behaves
-- exactly as it did the moment 2a70688/ea897c8 shipped. Only when a
-- brand explicitly sets threshold_count does the new accumulate-until-
-- threshold submit path (app/routers/talents.py submit_milestone) engage.
-- ──────────────────────────────────────────────────────────────────

ALTER TABLE public.campaign_milestones
  ADD COLUMN threshold_count INTEGER CHECK (threshold_count IS NULL OR threshold_count > 0);

ALTER TABLE public.campaign_talent_milestones
  ADD COLUMN current_count INTEGER NOT NULL DEFAULT 0;

-- current_count must never exceed its milestone's threshold_count.
-- Enforced here as a cross-table CHECK isn't possible in Postgres
-- (CHECK can't reference another table), so this follows the same
-- "guard the invariant in application code against the current row
-- state" convention this codebase already uses for state-machine
-- transitions (see 20260812120000_milestone_payments.sql's note on
-- payment_type immutability) -- app/repositories/
-- campaign_milestones_repository.py's increment_count enforces
-- current_count <= threshold_count with a guarded UPDATE ... WHERE
-- clause, the same pattern submit()/confirm() already use to make
-- every other milestone transition atomic and race-safe.
ALTER TABLE public.campaign_talent_milestones
  ADD CONSTRAINT campaign_talent_milestones_current_count_non_negative CHECK (current_count >= 0);
