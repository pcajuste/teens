-- ──────────────────────────────────────────────────────────────────
-- ENUMS — verbatim from Teenure_MVP_Gameplan.md Section 7
-- ──────────────────────────────────────────────────────────────────

CREATE TYPE user_role AS ENUM ('rep', 'brand', 'recruiter', 'admin');
CREATE TYPE account_status AS ENUM ('pending', 'active', 'suspended', 'rejected');

-- campaign_status: per Build Prompt 2's schema note, includes
-- pending_payment and payment_failed in addition to the base set.
CREATE TYPE campaign_status AS ENUM (
  'draft', 'pending_payment', 'payment_failed',
  'active', 'paused', 'completed', 'cancelled'
);
-- pending_payment: brand has activated the campaign and a Stripe
--   PaymentIntent has been created, awaiting payment_intent.succeeded.
-- payment_failed: payment_intent.payment_failed was received; brand is
--   notified and must retry payment before the campaign can go active.
--   Distinct from 'draft' so the brand isn't shown a blank draft state
--   after having already attempted activation.

CREATE TYPE rep_campaign_status AS ENUM (
  'invited', 'accepted', 'declined',
  'submitted', 'revision_requested',
  'confirmed', 'paid'
);
CREATE TYPE institution_type AS ENUM ('college', 'employer');
CREATE TYPE payout_status AS ENUM ('pending', 'processing', 'paid', 'failed');
CREATE TYPE parent_approval_status AS ENUM ('not_required', 'pending', 'approved', 'blocked');
-- not_required: rep is 18+, or rep is 16-17 with campaign_approval_required = FALSE.
-- pending: campaign_approval_required = TRUE for this rep and the linked parent
--   has not yet approved or blocked this specific invitation.
-- Values-filter category exclusion (Section 9A) happens upstream of this enum
--   entirely -- a blocked-category campaign never reaches
--   GET /reps/campaigns/available in the first place, so it never gets a
--   campaign_reps row and never enters this state machine.

-- rep_profiles.school_type: Build Prompt 2's schema note calls this a
-- "nullable enum (public/private/charter/homeschool)" while Section 7's
-- literal DDL declares it TEXT with the same four values documented in
-- a comment. We reconcile the two by keeping it a nullable TEXT column
-- constrained by CHECK to exactly those four values (see rep_profiles
-- table below) rather than a Postgres ENUM type. Rationale: it is
-- self-reported at onboarding and only ever read in aggregate by the
-- intelligence layer (Section 9) — a CHECK gives the same integrity
-- guarantee as an enum without the schema-migration cost of adding a
-- 5th value later (ALTER TYPE ... ADD VALUE has transactional
-- restrictions that a CHECK constraint does not). This is a deliberate
-- deviation, called out in the Prompt 2 report as required.
