-- ──────────────────────────────────────────────────────────────────
-- USERS (extends Supabase auth.users) — verbatim, Section 7
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
-- talent PROFILES — verbatim, Section 7 (see enums.sql for the
-- school_type CHECK-vs-enum reconciliation note)
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE public.talent_profiles (
  id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                     UUID NOT NULL UNIQUE REFERENCES public.users(id) ON DELETE CASCADE,
  display_name                TEXT NOT NULL,
  school_name                 TEXT NOT NULL,
  school_type                 TEXT
                                 CHECK (school_type IS NULL OR school_type IN ('public','private','charter','homeschool')),
                               -- self-reported, optional at onboarding; used only in
                               -- aggregate by the intelligence layer — never joined
                               -- back to an individual talent in any report
  city                        TEXT NOT NULL,
  state                       TEXT NOT NULL,
  graduation_year             INTEGER NOT NULL CHECK (graduation_year BETWEEN 2024 AND 2035),
  bio                         TEXT,
  categories                  TEXT[] NOT NULL DEFAULT '{}',    -- e.g. ['athletics','gaming']
  instagram_handle            TEXT,
  tiktok_handle               TEXT,
  recruiter_visible           BOOLEAN NOT NULL DEFAULT FALSE,

  -- computed/cached fields (updated via trigger or background job —
  -- see docs/talent_profiles_cache_recompute.md for the design note)
  total_campaigns_completed   INTEGER NOT NULL DEFAULT 0,
  total_earnings_cents        INTEGER NOT NULL DEFAULT 0,
  average_rating              NUMERIC(3,2),                   -- e.g. 4.75
  profile_completeness_score  INTEGER NOT NULL DEFAULT 0,     -- 0-100

  created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ──────────────────────────────────────────────────────────────────
-- BRAND PROFILES — verbatim, Section 7
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
-- CAMPAIGNS — verbatim, Section 7
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
  max_talents                  INTEGER NOT NULL DEFAULT 10,
  talents_accepted_count       INTEGER NOT NULL DEFAULT 0,

  -- Financials (all in cents)
  budget_cents              INTEGER NOT NULL,
  platform_fee_cents        INTEGER NOT NULL,         -- calculated at brief creation
  talent_pool_cents            INTEGER NOT NULL,         -- budget_cents - platform_fee_cents
  payout_per_talent_cents      INTEGER,                  -- talent_pool_cents / max_talents

  -- Dates
  start_date                DATE NOT NULL,
  end_date                  DATE NOT NULL,

  -- Stripe
  stripe_payment_intent_id  TEXT UNIQUE,

  created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ──────────────────────────────────────────────────────────────────
-- CAMPAIGN REPS (join table — one row per talent per campaign) — verbatim
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE public.campaign_talents (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id             UUID NOT NULL REFERENCES public.campaigns(id) ON DELETE RESTRICT,
  talent_id                  UUID NOT NULL REFERENCES public.talent_profiles(id) ON DELETE RESTRICT,
  status                  talent_campaign_status NOT NULL DEFAULT 'invited',

  -- FTC compliance
  ftc_disclosure_accepted BOOLEAN NOT NULL DEFAULT FALSE,
  ftc_accepted_at         TIMESTAMPTZ,

  -- Parent approval gate (Section 9A) -- only meaningful when the talent has
  -- a parent_records row with campaign_approval_required = TRUE
  parent_approval_status   parent_approval_status NOT NULL DEFAULT 'not_required',
  parent_approval_deadline TIMESTAMPTZ,           -- 48h from invite, mirrors invite_expires_at
  parent_decided_at        TIMESTAMPTZ,

  -- Submission
  submission_text         TEXT,
  submission_file_urls    TEXT[] DEFAULT '{}',
  revision_note            TEXT,                       -- brand's revision request

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

  UNIQUE (campaign_id, talent_id)
);

-- ──────────────────────────────────────────────────────────────────
-- RECRUITER PROFILES — verbatim, Section 7
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
-- RECRUITER CONTACTS (join table) — verbatim, Section 7
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE public.recruiter_contacts (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  recruiter_id    UUID NOT NULL REFERENCES public.recruiter_profiles(id) ON DELETE RESTRICT,
  talent_id          UUID NOT NULL REFERENCES public.talent_profiles(id) ON DELETE RESTRICT,
  message_text    TEXT NOT NULL,
  read_at         TIMESTAMPTZ,
  messaged_at     TIMESTAMPTZ NOT NULL DEFAULT now(),

  UNIQUE (recruiter_id, talent_id)       -- one contact per talent per recruiter
);

-- ──────────────────────────────────────────────────────────────────
-- RECRUITER SAVED PROFILES — verbatim, Section 7
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE public.recruiter_saved_profiles (
  recruiter_id    UUID NOT NULL REFERENCES public.recruiter_profiles(id) ON DELETE CASCADE,
  talent_id          UUID NOT NULL REFERENCES public.talent_profiles(id) ON DELETE CASCADE,
  saved_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  list_name       TEXT DEFAULT 'Default',
  PRIMARY KEY (recruiter_id, talent_id)
);

-- ──────────────────────────────────────────────────────────────────
-- PARENT RECORDS (Section 9A) -- one row per parent-of-a-minor-talent
-- link. Parents are NOT public.users -- they authenticate via a
-- separate magic-link flow (parent_auth_tokens below), not Supabase
-- Auth, since they have no auth.users identity of their own.
--
-- Column shape follows Build Prompt 2's explicit schema note (which
-- takes precedence over Section 7's DDL for this table per the task
-- brief): parent_id as the PK name, values_filters as JSONB rather
-- than TEXT[]. Section 7's suspended_by_parent_at, created_at and
-- updated_at columns are additionally kept since Prompt 4A's parent
-- suspend/unsuspend routes and audit needs depend on them and Prompt 2
-- doesn't say to drop them -- see Prompt 2 deviation note in the
-- final report.
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE public.parent_records (
  parent_id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  talent_id                        UUID NOT NULL UNIQUE REFERENCES public.talent_profiles(id) ON DELETE CASCADE,
  parent_email                  TEXT NOT NULL,
  -- Seeded from users.parent_email at signup (Section 8's /auth/signup
  -- behavior for under-16 talents); a row is only created for talents who
  -- required parental consent at signup. A 16-17 talent has no
  -- parent_records row unless a parent separately claims one -- out of
  -- scope for MVP, so 16-17 talents without a consent-flow parent simply
  -- have campaign_approval_required permanently FALSE with no row here.
  campaign_approval_required    BOOLEAN NOT NULL DEFAULT TRUE,
  -- Always TRUE and not parent-editable while the talent is under 16
  -- (enforced in application code, not just a default -- see Section 9A).
  values_filters                 JSONB NOT NULL DEFAULT '[]'::jsonb,
  -- Blocked campaign categories, as a JSON array of strings. Valid
  -- values: the same category enum used by talent_profiles.categories /
  -- campaigns.target_categories, plus the brand/product-content-only
  -- categories: alcohol_adjacent, political, dating_romantic, gambling,
  -- dietary_supplements, in_person_travel_required.
  digest_enabled                 BOOLEAN NOT NULL DEFAULT TRUE,
  portal_expires_at              TIMESTAMPTZ NOT NULL,
  -- Set at row creation from the talent's date_of_birth (18th birthday).
  -- Recomputed if date_of_birth is ever corrected.
  suspended_by_parent_at         TIMESTAMPTZ,
  created_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ──────────────────────────────────────────────────────────────────
-- PARENT AUTH TOKENS (Section 9A) -- magic-link login, single-use.
-- Not explicitly listed in Prompt 2's table-creation order, but is
-- part of "the database layer exactly as specified in Section 7" and
-- is a hard FK dependency for the parent_records RLS/session model
-- Prompt 2 asks for, so it is included here.
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE public.parent_auth_tokens (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  parent_record_id  UUID NOT NULL REFERENCES public.parent_records(parent_id) ON DELETE CASCADE,
  token_hash        TEXT NOT NULL UNIQUE,     -- store a hash, never the raw token
  expires_at        TIMESTAMPTZ NOT NULL,     -- 15 minutes from issuance (login link, not session)
  used_at           TIMESTAMPTZ,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- The 24-hour parent *session* issued after a successful magic-link
-- verification is a stateless signed token (HS256, PARENT_SESSION_SECRET
-- -- a new env var, distinct from SUPABASE_JWT_SECRET, since parent
-- sessions are not Supabase-issued) carrying {parent_record_id, talent_id,
-- exp}. Nothing further is stored server-side for the session itself;
-- only the one-time login link above needs a DB row (so it can be
-- marked used / rate-limited).
