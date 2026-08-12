-- Prompt 2: Database Schema & Row-Level Security
-- Section 7 of Teenure_MVP_Gameplan.md, applied verbatim, migration 1 of 4.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE user_role AS ENUM ('rep', 'brand', 'recruiter', 'admin');
CREATE TYPE account_status AS ENUM ('pending', 'active', 'suspended', 'rejected');
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
