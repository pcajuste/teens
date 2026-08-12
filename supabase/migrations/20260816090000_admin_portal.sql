-- ──────────────────────────────────────────────────────────────────
-- Admin Portal (Build Prompt 13) -- schema additions beyond Section 7's
-- verbatim tables:
--   - users.rejection_reason/reviewed_by/reviewed_at: POST
--     /admin/reject/:type/:id requires a reason (deliverable 1), and
--     approve/reject need an audit trail of which admin acted.
--   - campaigns.flagged_*/resolved_*: campaign oversight (deliverable
--     2). resolution_action is an enum, not free text, per the
--     acceptance criterion.
--   - campaign_reps.payout_processing_started_at: Section 7's
--     campaign_reps has no timestamp for when a transfer entered
--     'processing', which the stuck-payments query (deliverable 3)
--     needs to compute an age. admin_released_*: audit flag for an
--     admin-initiated manual release, distinct from the normal
--     webhook-driven path.
--   - parent_records.suspension_reversed_*: audit trail for admin
--     reversing a parent-initiated suspension (deliverable 6).
--   - safety_reports: new table entirely. Section 7 has no table for
--     the rep portal's one-tap report mechanism (deliverable 7) -- this
--     is the queue admin reviews, ranked above campaign disputes/
--     payment issues in the admin UI by construction (its own page,
--     rendered first).
-- ──────────────────────────────────────────────────────────────────

CREATE TYPE campaign_resolution_action AS ENUM ('force_confirm', 'force_cancel_refund');
CREATE TYPE safety_report_status AS ENUM ('open', 'resolved', 'dismissed');

ALTER TABLE public.users
  ADD COLUMN rejection_reason TEXT,
  ADD COLUMN reviewed_by      UUID REFERENCES public.users(id),
  ADD COLUMN reviewed_at      TIMESTAMPTZ;

ALTER TABLE public.campaigns
  ADD COLUMN flagged_at        TIMESTAMPTZ,
  ADD COLUMN flagged_reason    TEXT,
  ADD COLUMN flagged_by        UUID REFERENCES public.users(id),
  ADD COLUMN resolved_at       TIMESTAMPTZ,
  ADD COLUMN resolution_action campaign_resolution_action,
  ADD COLUMN resolved_by       UUID REFERENCES public.users(id);

ALTER TABLE public.campaign_reps
  ADD COLUMN payout_processing_started_at TIMESTAMPTZ,
  ADD COLUMN admin_released               BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN admin_released_by            UUID REFERENCES public.users(id),
  ADD COLUMN admin_released_at            TIMESTAMPTZ;

ALTER TABLE public.parent_records
  ADD COLUMN suspension_reversed_by UUID REFERENCES public.users(id),
  ADD COLUMN suspension_reversed_at TIMESTAMPTZ;

CREATE TABLE public.safety_reports (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  reporter_rep_id  UUID NOT NULL REFERENCES public.rep_profiles(id) ON DELETE CASCADE,
  campaign_id      UUID REFERENCES public.campaigns(id) ON DELETE SET NULL,
  reason           TEXT NOT NULL,
  description      TEXT,
  status           safety_report_status NOT NULL DEFAULT 'open',
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at      TIMESTAMPTZ,
  resolved_by      UUID REFERENCES public.users(id),
  resolution_note  TEXT
);

ALTER TABLE public.safety_reports ENABLE ROW LEVEL SECURITY;

-- A rep can see their own reports (rep portal "my reports" affordance);
-- admin sees everything via the service-role connection (Section 7 note:
-- "Admin sees everything -- enforced via service role key in admin
-- portal"), so no admin-specific policy is needed here, matching the
-- rest of this codebase's RLS convention.
CREATE POLICY "Rep reads own safety reports"
  ON public.safety_reports FOR SELECT
  USING (reporter_rep_id = rls.rep_id_for_user(auth.uid()));

CREATE POLICY "Rep files own safety reports"
  ON public.safety_reports FOR INSERT
  WITH CHECK (reporter_rep_id = rls.rep_id_for_user(auth.uid()));

CREATE INDEX idx_safety_reports_status ON public.safety_reports (status, created_at);
CREATE INDEX idx_campaign_reps_stuck ON public.campaign_reps (payout_status, payout_processing_started_at);
