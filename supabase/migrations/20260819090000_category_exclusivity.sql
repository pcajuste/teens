-- ──────────────────────────────────────────────────────────────────
-- Category Exclusivity (Build Prompt 8C) -- a premium, platform-revenue
-- feature: a brand can purchase sole rights to a category+city
-- combination for a bounded time window. Entirely additive -- no
-- existing table/column is touched. The purchasing brand's own
-- exclusivity does not get stored on campaigns (Section 8C's own
-- text: "the campaign itself does not store a reference to an
-- exclusivity agreement; the agreement stands independently") -- all
-- conflict detection is a live query against this table at campaign
-- creation/activation time (app/services/exclusivity_service.py).
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE public.category_exclusivity_agreements (
  id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  brand_id                  UUID NOT NULL REFERENCES public.brand_profiles(id) ON DELETE RESTRICT,
  category                  TEXT NOT NULL,
  city                      TEXT,
  starts_at                 TIMESTAMPTZ NOT NULL,
  ends_at                   TIMESTAMPTZ NOT NULL,
  status                    TEXT NOT NULL DEFAULT 'active'
                              CHECK (status IN ('active', 'expired', 'cancelled')),
  fee_cents                 INTEGER NOT NULL,
  stripe_payment_intent_id  TEXT NOT NULL UNIQUE,
  payment_status            TEXT NOT NULL DEFAULT 'pending'
                              CHECK (payment_status IN ('pending', 'paid', 'refunded', 'partially_refunded', 'failed')),
  cancelled_at              TIMESTAMPTZ,
  cancellation_reason       TEXT,
  refund_cents              INTEGER,
  created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT category_exclusivity_agreements_ends_after_starts CHECK (ends_at > starts_at),
  CONSTRAINT category_exclusivity_agreements_max_90_days CHECK (ends_at - starts_at <= interval '90 days')
);

-- Critical path: every campaign creation/activation and every
-- GET /brands/exclusivity/check call hits this. Partial on
-- status = 'active' keeps it small as agreements expire/cancel over
-- time -- expired/cancelled rows are dead weight for conflict
-- detection and never need to be in this index.
CREATE INDEX idx_exclusivity_active_category_city
  ON public.category_exclusivity_agreements (category, city, starts_at, ends_at)
  WHERE status = 'active';

CREATE INDEX idx_exclusivity_brand
  ON public.category_exclusivity_agreements (brand_id, status);

-- Used by the exclusivity_auto_expire job (finds ends_at < now() AND
-- status = 'active').
CREATE INDEX idx_exclusivity_expiry
  ON public.category_exclusivity_agreements (ends_at, status)
  WHERE status = 'active';

-- ──────────────────────────────────────────────────────────────────
-- RLS
-- ──────────────────────────────────────────────────────────────────

ALTER TABLE public.category_exclusivity_agreements ENABLE ROW LEVEL SECURITY;

-- Reuses the rls schema's SECURITY DEFINER pattern established in
-- 20260811210400_rls.sql rather than inlining a subquery -- see that
-- migration's "Cross-table RLS helper functions" note for why.
CREATE OR REPLACE FUNCTION rls.brand_owns_exclusivity_agreement(p_agreement_id UUID, p_user_id UUID) RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.category_exclusivity_agreements a
    JOIN public.brand_profiles bp ON bp.id = a.brand_id
    WHERE a.id = p_agreement_id AND bp.user_id = p_user_id
  );
$$;

-- Brands may only SELECT their own agreements. No brand INSERT/UPDATE/
-- DELETE policy exists at all -- agreements are created and managed
-- exclusively through the API (which runs on the service-role/direct
-- DATABASE_URL connection that bypasses RLS per app/db/pool.py's own
-- module docstring), enforcing the purchase/cancellation business
-- rules (conflict check, proration, Stripe PaymentIntent/Refund) before
-- ever writing a row. Talents, recruiters, and parents get no policy at
-- all, so default-deny applies to them, matching this codebase's
-- parent_auth_tokens / milestone_disputes convention.
CREATE POLICY "Brand reads own exclusivity agreements"
  ON public.category_exclusivity_agreements FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.brand_profiles bp
      WHERE bp.id = category_exclusivity_agreements.brand_id
        AND bp.user_id = auth.uid()
    )
  );
