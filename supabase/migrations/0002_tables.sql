-- Prompt 2: Database Schema & Row-Level Security
-- Section 7 of Teenure_MVP_Gameplan.md, applied verbatim, migration 2 of 4.

-- ──────────────────────────────────────────────────────────────────
-- USERS (extends Supabase auth.users)
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE public.users (
  id                  UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email               TEXT NOT NULL UNIQUE,
  role                user_role NOT NULL,
  account_status      account_status NOT NULL DEFAULT 'pending',
  date_of_birth       DATE NOT NULL,
  parent_email        TEXT,                         -- required if age < 16
  parent_verified_at  TIMESTAMPTZ,                  -- NULL until parent clicks consent link
  consent_token       TEXT UNIQUE,                  -- one-time token emailed to parent
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ──────────────────────────────────────────────────────────────────
-- REP PROFILES
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE public.rep_profiles (
  id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                     UUID NOT NULL UNIQUE REFERENCES public.users(id) ON DELETE CASCADE,
  display_name                TEXT NOT NULL,
  school_name                 TEXT NOT NULL,
  school_type                 TEXT,                            -- 'public' | 'private' | 'charter' | 'homeschool'; nullable at MVP (self-reported, optional at onboarding), used only in aggregate by the intelligence layer — never joined back to an individual rep in any report
  city                        TEXT NOT NULL,
  state                       TEXT NOT NULL,
  graduation_year             INTEGER NOT NULL CHECK (graduation_year BETWEEN 2024 AND 2035),
  bio                         TEXT,
  categories                  TEXT[] NOT NULL DEFAULT '{}',    -- e.g. ['athletics','gaming']
  instagram_handle            TEXT,
  tiktok_handle               TEXT,
  recruiter_visible           BOOLEAN NOT NULL DEFAULT FALSE,

  -- computed/cached fields (updated via trigger or background job)
  total_campaigns_completed   INTEGER NOT NULL DEFAULT 0,
  total_earnings_cents        INTEGER NOT NULL DEFAULT 0,
  average_rating              NUMERIC(3,2),                   -- e.g. 4.75
  profile_completeness_score  INTEGER NOT NULL DEFAULT 0,     -- 0-100

  created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ──────────────────────────────────────────────────────────────────
-- BRAND PROFILES
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE public.brand_profiles (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID NOT NULL UNIQUE REFERENCES public.users(id) ON DELETE CASCADE,
  company_name        TEXT NOT NULL,
  website             TEXT,
  ein                 TEXT,                         -- stored encrypted in production
  industry            TEXT,
  target_categories   TEXT[] DEFAULT '{}',
  verified            BOOLEAN NOT NULL DEFAULT FALSE,
  verified_at         TIMESTAMPTZ,
  verified_by         UUID REFERENCES public.users(id),
  stripe_customer_id  TEXT UNIQUE,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ──────────────────────────────────────────────────────────────────
-- CAMPAIGNS
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE public.campaigns (
  id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  brand_id                  UUID NOT NULL REFERENCES public.brand_profiles(id) ON DELETE RESTRICT,
  title                     TEXT NOT NULL,
  status                    campaign_status NOT NULL DEFAULT 'draft',

  -- Brief
  product_name              TEXT NOT NULL,
  campaign_goal              TEXT NOT NULL,
  key_messaging             TEXT NOT NULL,
  prohibited_content        TEXT,
  deliverables_description  TEXT NOT NULL,

  -- Targeting
  target_categories         TEXT[] NOT NULL DEFAULT '{}',
  target_cities              TEXT[] NOT NULL DEFAULT '{}',
  max_reps                  INTEGER NOT NULL DEFAULT 10,
  reps_accepted_count       INTEGER NOT NULL DEFAULT 0,

  -- Financials (all in cents)
  budget_cents              INTEGER NOT NULL,
  platform_fee_cents        INTEGER NOT NULL,         -- calculated at brief creation
  rep_pool_cents            INTEGER NOT NULL,         -- budget_cents - platform_fee_cents
  payout_per_rep_cents      INTEGER,                  -- rep_pool_cents / max_reps

  -- Dates
  start_date                DATE NOT NULL,
  end_date                  DATE NOT NULL,

  -- Stripe
  stripe_payment_intent_id  TEXT UNIQUE,

  created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ──────────────────────────────────────────────────────────────────
-- CAMPAIGN REPS (join table -- one row per rep per campaign)
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE public.campaign_reps (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id             UUID NOT NULL REFERENCES public.campaigns(id) ON DELETE RESTRICT,
  rep_id                  UUID NOT NULL REFERENCES public.rep_profiles(id) ON DELETE RESTRICT,
  status                  rep_campaign_status NOT NULL DEFAULT 'invited',

  -- FTC compliance
  ftc_disclosure_accepted BOOLEAN NOT NULL DEFAULT FALSE,
  ftc_accepted_at         TIMESTAMPTZ,

  -- Submission
  submission_text         TEXT,
  submission_file_urls    TEXT[] DEFAULT '{}',
  revision_note           TEXT,                       -- brand's revision request

  -- Completion
  brand_rating            INTEGER CHECK (brand_rating BETWEEN 1 AND 5),
  brand_rating_note       TEXT,

  -- Financials
  payout_cents            INTEGER,
  payout_status           payout_status DEFAULT 'pending',
  stripe_transfer_id      TEXT UNIQUE,

  -- Timestamps
  invited_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  accepted_at             TIMESTAMPTZ,
  submitted_at            TIMESTAMPTZ,
  confirmed_at            TIMESTAMPTZ,
  paid_at                 TIMESTAMPTZ,

  UNIQUE (campaign_id, rep_id)
);

-- ──────────────────────────────────────────────────────────────────
-- RECRUITER PROFILES
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE public.recruiter_profiles (
  id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                     UUID NOT NULL UNIQUE REFERENCES public.users(id) ON DELETE CASCADE,
  institution_name            TEXT NOT NULL,
  institution_type            institution_type NOT NULL,
  website                     TEXT,
  verified                    BOOLEAN NOT NULL DEFAULT FALSE,

  -- Contact credits
  contact_credits_remaining   INTEGER NOT NULL DEFAULT 0,
  credits_reset_date          DATE,

  -- Stripe
  stripe_customer_id          TEXT UNIQUE,
  stripe_subscription_id      TEXT UNIQUE,

  created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ──────────────────────────────────────────────────────────────────
-- RECRUITER CONTACTS (join table)
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE public.recruiter_contacts (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  recruiter_id    UUID NOT NULL REFERENCES public.recruiter_profiles(id) ON DELETE RESTRICT,
  rep_id          UUID NOT NULL REFERENCES public.rep_profiles(id) ON DELETE RESTRICT,
  message_text    TEXT NOT NULL,
  read_at         TIMESTAMPTZ,
  messaged_at     TIMESTAMPTZ NOT NULL DEFAULT now(),

  UNIQUE (recruiter_id, rep_id)       -- one contact per rep per recruiter
);

-- ──────────────────────────────────────────────────────────────────
-- RECRUITER SAVED PROFILES
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE public.recruiter_saved_profiles (
  recruiter_id    UUID NOT NULL REFERENCES public.recruiter_profiles(id) ON DELETE CASCADE,
  rep_id          UUID NOT NULL REFERENCES public.rep_profiles(id) ON DELETE CASCADE,
  saved_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  list_name       TEXT DEFAULT 'Default',
  PRIMARY KEY (recruiter_id, rep_id)
);
