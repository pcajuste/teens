-- ──────────────────────────────────────────────────────────────────
-- Performance Milestone Payments (Build Prompt 8B) -- an optional
-- campaign payment type that coexists with the existing flat payment
-- model (Prompt 8/10). Every column/table added here is additive: no
-- existing column is dropped or renamed, and payment_type defaults to
-- 'flat' so every campaign created before this migration is
-- unaffected. DDL + RLS live together in this one migration file,
-- matching this codebase's convention of a single migration per
-- feature (see 20260816090000_admin_portal.sql) rather than the
-- separate enums/core_tables/indexes/rls split used only for the
-- original Section 7 schema.
-- ──────────────────────────────────────────────────────────────────

CREATE TYPE campaign_payment_type AS ENUM ('flat', 'milestone');
CREATE TYPE milestone_verification_method AS ENUM ('brand_confirmation', 'rep_submission');
CREATE TYPE campaign_rep_milestone_status AS ENUM ('pending', 'submitted', 'confirmed', 'paid');

ALTER TABLE public.campaigns
  ADD COLUMN payment_type campaign_payment_type NOT NULL DEFAULT 'flat';
-- Immutable after activation -- enforced at the API layer (POST
-- /brands/campaigns/:id/activate and PUT /brands/campaigns/:id both
-- reject a payment_type change once status has ever left 'draft'),
-- not via a DB trigger, matching how every other campaign state
-- transition in this codebase is guarded in application code against
-- the current `status` value rather than in SQL.

CREATE TABLE public.campaign_milestones (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id         UUID NOT NULL REFERENCES public.campaigns(id) ON DELETE RESTRICT,
  milestone_number    INTEGER NOT NULL,
  title               TEXT NOT NULL,
  description         TEXT,
  verification_method milestone_verification_method NOT NULL,
  payout_percentage   INTEGER NOT NULL CHECK (payout_percentage BETWEEN 1 AND 100),
  sequence_required   BOOLEAN NOT NULL DEFAULT TRUE,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (campaign_id, milestone_number)
);

ALTER TABLE public.campaign_reps
  ADD COLUMN milestones_completed_count     INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN total_milestone_payout_cents   INTEGER NOT NULL DEFAULT 0;

CREATE TABLE public.campaign_rep_milestones (
  id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_rep_id             UUID NOT NULL REFERENCES public.campaign_reps(id) ON DELETE RESTRICT,
  campaign_milestone_id       UUID NOT NULL REFERENCES public.campaign_milestones(id) ON DELETE RESTRICT,
  status                      campaign_rep_milestone_status NOT NULL DEFAULT 'pending',
  rep_submission_text         TEXT,
  rep_submission_file_urls    TEXT[] NOT NULL DEFAULT '{}',
  brand_confirmation_note     TEXT,
  payout_cents                INTEGER,
  stripe_transfer_id          TEXT UNIQUE,
  payout_status               payout_status NOT NULL DEFAULT 'pending',
  dispute_flag                BOOLEAN NOT NULL DEFAULT FALSE,
  submitted_at                TIMESTAMPTZ,
  confirmed_at                TIMESTAMPTZ,
  paid_at                     TIMESTAMPTZ,
  UNIQUE (campaign_rep_id, campaign_milestone_id)
);

CREATE INDEX idx_campaign_rep_milestones_status ON public.campaign_rep_milestones (campaign_rep_id, status);
CREATE INDEX idx_campaign_milestones_campaign ON public.campaign_milestones (campaign_id, milestone_number);

-- ──────────────────────────────────────────────────────────────────
-- Milestone disputes: a new admin-queue category, distinct from the
-- whole-campaign disputes (public.campaigns.flagged_*) and stuck
-- payment-transfer disputes (payout_status='failed'/'processing')
-- already surfaced by the Admin Portal (Prompt 13). Modeled as its
-- own table, following the safety_reports precedent
-- (20260816090000_admin_portal.sql) rather than shoehorning a new
-- literal into admin_repository.QueueEntry.pending_reason: a milestone
-- dispute has its own resolution shape (confirm-triggers-payout vs.
-- decline-resets-to-submitted) that doesn't fit the
-- approve/reject-account queue's binary outcome, and, like
-- safety_reports, needs its own resolved_at/resolved_by/resolution_note
-- audit trail plus a direct FK to the disputed row.
-- ──────────────────────────────────────────────────────────────────

CREATE TYPE milestone_dispute_status AS ENUM ('open', 'resolved_confirmed', 'resolved_declined');

CREATE TABLE public.milestone_disputes (
  id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_rep_milestone_id UUID NOT NULL REFERENCES public.campaign_rep_milestones(id) ON DELETE RESTRICT,
  raised_by                 UUID NOT NULL REFERENCES public.users(id),
  reason                    TEXT,
  status                    milestone_dispute_status NOT NULL DEFAULT 'open',
  created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at               TIMESTAMPTZ,
  resolved_by               UUID REFERENCES public.users(id),
  resolution_note           TEXT
);

CREATE INDEX idx_milestone_disputes_status ON public.milestone_disputes (status, created_at);

-- ──────────────────────────────────────────────────────────────────
-- RLS
-- ──────────────────────────────────────────────────────────────────

ALTER TABLE public.campaign_milestones ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.campaign_rep_milestones ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.milestone_disputes ENABLE ROW LEVEL SECURITY;

-- campaign_milestones: brands read/write only their own campaigns'
-- milestones (reuses rls.brand_owns_campaign from 20260811210400_rls.sql
-- rather than inventing an equivalent). Reps can read milestones only
-- for campaigns they have a campaign_reps row for (any status -- a rep
-- invited to a milestone campaign needs to see the milestone list
-- before accepting, same as they can already read the campaign brief
-- itself). No direct rep write access at all -- reps only ever write
-- through campaign_rep_milestones (their own submission), never the
-- campaign-level milestone definitions.
CREATE POLICY "Brand manages own campaign milestones"
  ON public.campaign_milestones FOR ALL
  USING (rls.brand_owns_campaign(campaign_milestones.campaign_id, auth.uid()));

CREATE POLICY "Rep reads milestones for campaigns they're invited to"
  ON public.campaign_milestones FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.campaign_reps cr
      WHERE cr.campaign_id = campaign_milestones.campaign_id
        AND cr.rep_id = rls.rep_id_for_user(auth.uid())
    )
  );

-- campaign_rep_milestones: a rep reads/writes only their own rows
-- (via the parent campaign_reps.rep_id); a brand reads/writes only
-- rows for campaign_reps belonging to their own campaigns (reuses
-- rls.brand_owns_campaign through the campaign_reps -> campaigns join,
-- same pattern as the existing "Brand reads/updates campaign_reps on
-- own campaigns" policy).
CREATE POLICY "Rep reads/writes own campaign_rep_milestones rows"
  ON public.campaign_rep_milestones FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM public.campaign_reps cr
      WHERE cr.id = campaign_rep_milestones.campaign_rep_id
        AND cr.rep_id = rls.rep_id_for_user(auth.uid())
    )
  );

CREATE POLICY "Brand reads/writes campaign_rep_milestones on own campaigns"
  ON public.campaign_rep_milestones FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM public.campaign_reps cr
      WHERE cr.id = campaign_rep_milestones.campaign_rep_id
        AND rls.brand_owns_campaign(cr.campaign_id, auth.uid())
    )
  );

-- milestone_disputes: no end-user-facing policy -- disputes are
-- created and resolved exclusively through server-side routes running
-- on the service-role connection (brand raises via POST .../dispute,
-- admin resolves via POST /admin/milestone-disputes/:id/resolve; the
-- spec is explicit that "all disputes go through admin at MVP", i.e.
-- no self-serve brand/rep resolution UI reads this table directly).
-- RLS is enabled with no policies, so default-deny applies to any
-- non-service-role connection, matching this codebase's
-- parent_auth_tokens convention (20260811210400_rls.sql's final note).
