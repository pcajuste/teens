# TEENURE — Comprehensive MVP Game Plan
### *Earn Yours Early.*

> **For AI builders:** Jump to [Section 10](#10-ai-builder-prompt) for the verbatim build prompt. Everything else is the context that makes that prompt work.

---

## Table of Contents

1. [What Is Teenure](#1-what-is-teenure)
2. [The Three Users](#2-the-three-users)
3. [Core Platform Mechanics](#3-core-platform-mechanics)
4. [Revenue Model](#4-revenue-model)
5. [MVP Feature Set](#5-mvp-feature-set)
6. [Technical Architecture](#6-technical-architecture)
7. [Database Schema](#7-database-schema)
8. [API Specification](#8-api-specification)
9. [Legal and Compliance](#9-legal-and-compliance)
9A. [Parent Portal](#9a-parent-portal)
10. [AI Builder Prompt](#10-ai-builder-prompt)
11. [Go-To-Market Sequence](#11-go-to-market-sequence)
12. [Risk Register](#12-risk-register)
13. [Milestones That Matter](#13-milestones-that-matter)

---

## 1. What Is Teenure

Teenure is a **three-sided verified achievement platform** for high school students.

Teens build documented, third-party-confirmed performance profiles through real brand campaigns. Those profiles are used by colleges to recruit, by employers to hire, and by brands to run authentic peer-influence campaigns. The platform generates three compounding revenue streams: campaign fees from brands, intelligence subscriptions from brands, and recruitment subscriptions from colleges and employers.

### The Core Insight

Every other teen platform captures **attention**. Teenure captures **verified performance**.

A four-year Teenure profile is an asset a student cannot replicate anywhere else and cannot afford to abandon. That switching cost is the entire moat.

### What It Is Not

- **Not a social network.** No feed. No likes. No followers. No trending content. No discovery by interest.
- **Not a dating platform.** No matching between users. No "who viewed my profile" signals between reps. No rep-to-rep contact of any kind.
- **Not Instagram or TikTok.** Reps do not post content on Teenure. They submit campaign evidence to brands. Those submissions are private — visible only to the brand and the rep, never to other reps or the public.
- **Not a general content platform.** There is no place on Teenure to post anything unrelated to a campaign. No status updates. No photos. No personal expression outside profile bio.
- **Not an influencer marketplace.** Reps are not influencers. They are verified peer voices with documented real-world track records.
- **Not a gig app.** The profile that compounds over time is the product, not the individual transaction.

### Platform Identity — The One-Sentence Rule

> **Teenure is a verified professional achievement record for teenagers. Every feature either adds to that record or it does not belong on the platform.**

If a proposed feature does not directly contribute to building, verifying, or surfacing a rep's achievement record — it does not get built. This rule is non-negotiable and applies to every product decision.

---

## 1A. Content Policy

> This section must be implemented at the application layer, not just communicated in terms of service. Every restriction below requires a technical enforcement mechanism.

### What Is Permitted on the Platform

| Content Type | Where | Who Sees It |
|---|---|---|
| Profile bio | Rep profile | Brands + opted-in recruiters only |
| Category selections | Rep profile | Brands + opted-in recruiters only |
| Campaign submission text | Campaign record | Brand + rep only |
| Campaign submission file uploads | Campaign record | Brand + rep only |
| Brand rating and rating note | Rep profile (aggregated) | Brands + opted-in recruiters only |
| Recruiter message to rep | Rep inbox | Rep only |
| Rep reply to recruiter | Recruiter thread | Recruiter only |

### What Is Prohibited — With Technical Enforcement

| Prohibited | Enforcement Mechanism |
|---|---|
| Rep-to-rep messaging | No messaging UI exists between reps. No endpoint exists. Not a missing feature — a deliberate absence. |
| Rep-to-brand unsolicited contact | Reps cannot initiate contact with brands. Reps only respond to campaign invitations. |
| Rep-to-recruiter contact (unsolicited or reply) | Reps can only read messages a recruiter sends. No reply field, endpoint, or UI exists on the rep side. `recruiter_contacts` has no rep-authored column — the schema itself makes a reply structurally unstorable, not just hidden by the UI. |
| Public content posting | No public feed exists anywhere on the platform. No submission is visible outside the campaign context. |
| Profile photos | Not collected. Not displayed. Profiles show category badges, campaign counts, and earnings — not images of the person. |
| Personal social content | Submission fields accept campaign evidence only. File upload accepts screenshots and links. Moderator review flags submissions with no campaign relevance. |
| Profile browsing between reps | Reps cannot search, view, or discover other rep profiles. The rep search interface is available only to authenticated brand and recruiter accounts. |
| Dating or romantic interaction | No mechanism exists. No shared spaces. No discovery layer. Structurally impossible, not just prohibited. |
| Content unrelated to campaigns | Campaign briefs define what constitutes valid submission content. Submissions outside scope trigger revision request from brand. Repeat off-scope submissions flagged for admin review. |

### Why These Constraints Are Competitive Advantages

Every platform that starts clean and adds a social layer destroys its original value proposition. The professional record becomes noise. Parents distrust it. Schools distance from it. Brands see it as another influencer platform.

Teenure's strictness is its brand promise to every stakeholder:

- **To parents:** Your child's activity here is professional, documented, and supervised.
- **To schools:** We do not compete with your policies. We extend professional development.
- **To brands:** You are reaching verified peer voices, not a teen social network.
- **To colleges:** Every profile you see is a professional record, not a curated personal brand.
- **To reps:** Your profile here is taken seriously because nothing here isn't serious.

The constraint is the moat. Do not erode it.

---

## 2. The Three Users

### 2.1 The Rep (Teen, Ages 14–18)

The primary user. Joins to earn money and build a verified achievement record. Participates in brand campaigns, completes deliverables, earns ratings, and accumulates a profile that grows in value over time.

**Core motivations:**
- Earn real income with no fixed schedule and no uniform
- Build a college application differentiator that is verified, not self-reported
- Gain documented real-world experience before entering the workforce
- Be discovered by colleges and employers before peers are on their radar

**Profile fields accumulated over time:**
- Campaigns completed and confirmed by brand
- Categories of influence: athletics, gaming, fashion, music, academics, food, beauty, tech
- Total earnings (a proxy for market-validated worth)
- Engagement performance per campaign (submitted by rep, confirmed by brand)
- Skills auto-tagged from campaign types completed: content creation, client communication, event activation, peer recruitment
- Brand ratings (1–5 stars averaged over all campaigns)
- School, grade, graduation year, city
- School type (public / private / charter / homeschool) — optional, self-reported; exists solely to power the Intelligence Layer's "by school type" trend cut (Section 3.5, Section 4)
- Recruiter visibility status (opt-in only)

> **⚠ Data constraint:** All profile data is self-reported and consent-driven. No passive behavioral tracking. No inferred data. No third-party data enrichment. See [Section 9](#9-legal-and-compliance).

---

### 2.2 The Brand

Pays to access the rep network for authentic teen peer-influence campaigns. Also pays for aggregated, anonymized trend intelligence derived from campaign performance data.

**Core motivations:**
- Reach teens authentically through trusted peer voices, not paid macro-influencers
- Access trend intelligence before it surfaces on mainstream platforms
- Verified campaign completion with documented performance evidence
- Avoid the cost and overhead of managing individual student relationships

**Two product tiers:**
1. **Campaign Access** — pay per campaign to activate a curated set of reps
2. **Intelligence Subscription** — quarterly trend reports by category, region, and school type

---

### 2.3 The Recruiter (College / Employer)

Pays a subscription to search and contact verified teen profiles. Replaces self-reported essays and test scores with documented real-world performance data.

**Core motivations:**
- Find students with verified initiative and real-world experience
- Recruit before students are on every other platform
- See documented performance, not self-reported claims
- Access a talent signal nobody else has

---

### 2.4 The Parent (Guardian of a Minor Rep — Oversight Role, Not a Platform Side)

Teenure remains a three-sided platform (Rep, Brand, Recruiter) — the parent is not a fourth revenue-generating side, and does not have an `auth.users` account or a `user_role` value. It is a scoped, non-paying oversight role that exists because Teenure handles minors' data and income: a `parent_records` row links a parent to their (under-18) rep and grants a deliberately narrow set of permissions. See [Section 9A](#9a-parent-portal) for the full spec.

**Core motivations:**
- See what their child is doing on the platform without needing the rep's own login
- Approve or block specific campaigns before their child can accept one
- Filter out categories of campaign content they don't want their child exposed to (e.g. alcohol-adjacent, political, dating/romantic framing)
- Get a low-friction monthly summary instead of having to check in constantly

**What this role explicitly does not have:** co-pilot access to the rep's account (cannot message recruiters, cannot edit the rep's profile, cannot submit campaign work), access to recruiter message content or campaign submission files, or any role beyond age 18 (the portal expires automatically at the rep's 18th birthday).

---

## 3. Core Platform Mechanics

### 3.1 The Teenure Profile

The profile is the product. Everything else exists to make it more valuable. It is a living, third-party-verified record of real-world performance that compounds over time and cannot be rebuilt elsewhere.

The profile answers one question that colleges, brands, and employers all have: **Show me proof.**

### 3.2 The Campaign Flow

```
Brand submits brief
        ↓
Platform surfaces matching reps (by category, city, history)
        ↓
Brand selects reps OR platform auto-assigns by fit score
        ↓
Rep receives brief → accepts or declines within 48 hours
        ↓
Rep completes deliverables (posts, events, word-of-mouth, reviews)
        ↓
Rep submits evidence (screenshots, links, written notes)
        ↓
Brand reviews evidence → confirms completion OR requests revision
        ↓
Brand submits rating (1–5 stars + optional note)
        ↓
Stripe Transfer releases payout to rep's Connected Account
        ↓
Campaign data feeds anonymized into trend intelligence layer
```

### 3.3 The LinkedIn Mechanic (Switching Cost)

A rep with a two-year verified profile **cannot rebuild it on a competitor platform**. Every campaign makes the profile more valuable. Moving means starting from zero.

Three compounding network effects:

| Effect | Mechanism |
|---|---|
| **Geographic density** | 20 reps in one city is sellable. Thin national spread is not. Brands pay for concentrated local reach. |
| **Category clustering** | 50 verified athletes is worth more than 500 random teens. Clusters drive brand willingness to pay. |
| **Data flywheel** | More campaigns → richer intelligence → higher brand willingness to pay → more budget → more reps attracted → more campaigns. |

### 3.4 The College Recruitment Mechanic

Reps opt in to recruiter visibility. Every campaign they complete is simultaneously **income and college application material**. This inverts the incentive entirely:

- Without college recruitment: "Earn $20 to post." (weak pitch)
- With college recruitment: "Build the verified record that gets you into better schools while earning money." (existential pitch)

Colleges pay for search access. Reps want to be found. Every additional recruiter makes every rep profile more worth completing. Every additional rep makes the recruiter product more useful.

### 3.5 The Intelligence Layer

Every campaign generates behavioral data no company on earth currently sells at scale: **verified, longitudinal, peer-influence data from inside high schools**.

- Not survey responses
- Not focus groups
- Not social media scraping

Actual documented peer influence, tracked over time, across real schools, by category.

This data is what turns a services business into a data business. The campaigns fund the data collection. The data subscription is where margin lives.

---

## 4. Revenue Model

### Stream One — Brand Campaign Fees

| Item | Detail |
|---|---|
| Pricing | $500–$5,000 per campaign depending on rep count and category specificity |
| Platform take | 30–40% of campaign value. Remainder distributed to reps. |
| Month 1 viable | 3 local brands at $500 = $1,500 gross. Platform keeps $525. |
| Scale target | 100 campaigns/month at $1,500 avg = $150,000 gross. Platform keeps ~$52,500/month. |

### Stream Two — Intelligence Subscription

| Item | Detail |
|---|---|
| Product | Quarterly trend reports by category, region, school type |
| Pricing | $25,000–$75,000 per brand per year |
| Comparable | Morning Consult ($50K/year), Nielsen teen panels ($40K+/year) |
| Differentiation | Verified behavioral data from actual peer influence, not surveys |
| Minimum viable | 3 brands at $25,000/year = $75,000 ARR from intelligence alone |

### Stream Three — Recruiter Subscriptions

| Item | Detail |
|---|---|
| Pricing | $2,400–$12,000/year per institution |
| Contact credit model | Each profile contact costs one credit. Credits refresh monthly. |
| Comparable | Naviance ($5K–$25K/year), Handshake ($8K–$30K/year) |
| Differentiation | Verified real-world performance, not grades and test scores |
| Minimum viable | 10 colleges at $3,600/year = $36,000 ARR |

### Combined Revenue Trajectory

| Period | Target |
|---|---|
| Month 1–3 | $0 revenue. Build rep network manually. Prove the model. |
| Month 4–6 | First 3 local brand campaigns. $3,000–$5,000 gross. |
| Month 6–12 | 20 campaigns/month + first recruiter subscriptions. $25,000–$35,000/month gross. |
| Year 2 | Intelligence subscription layer active. $500,000 ARR. |
| Year 3 | All three streams at scale. $2M–$5M ARR without institutional funding. |

---

## 5. MVP Feature Set

> **Build sequence is mandatory.** Phase 1 must be fully functional before Phase 2 begins. Phase 2 before Phase 3. Do not skip ahead.

### Phase 1 — Rep Portal (Build First)

#### Authentication & Onboarding
- Email signup with date-of-birth collection
- Hard age gate: under 13 blocked entirely
- Under 16: parental consent email flow (see [Section 9](#9-legal-and-compliance))
- Profile creation wizard on first login: name, school, graduation year, city, categories (multi-select), bio
- Social handle fields: Instagram, TikTok (display only — no API integration at MVP)
- Recruiter visibility toggle: default OFF

#### Rep Dashboard
- Available campaigns panel: open campaigns matching rep's categories
- Active campaigns panel: current brief, deliverables, deadline, submission interface
- Earnings panel: pending (campaign confirmed, payout processing), confirmed (transferred), lifetime total
- Profile completeness score with actionable prompts to improve it

#### Campaign Participation
- Campaign detail view: full brief, prohibited content, deliverables, timeline, payout amount
- FTC disclosure acknowledgment: required checkbox before accepting any campaign
- Accept / decline action with 48-hour deadline
- Submission interface: text field + file upload (screenshots, links)
- Submission status tracker: submitted → under review → confirmed → paid

#### Profile View (Own)
- Preview mode: exactly what a recruiter or brand sees
- Campaign history with brand confirmations and ratings displayed
- Category badges with campaign count behind each
- Earnings total displayed as a credibility signal

#### Parent Portal (see [Section 9A](#9a-parent-portal))
- Part of Phase 1, not a later phase: minors' campaign participation is gated on it (parent approval, values filters), so it must exist before Phase 1 is considered "fully functional" for under-18 reps.
- Magic-link parent authentication, campaign approval queue, values-filter configuration, monthly digest, account suspend/unsuspend, portal expiry at 18.
- One-tap campaign withdrawal (no penalty, no reason required) is a Rep Portal feature in the same spirit — surfaced prominently, not buried in settings.

---

### Phase 2 — Brand Portal (Build Second)

#### Authentication & Verification
- Business email required
- Company name, website, EIN field (stored for verification)
- Manual admin approval at MVP — no self-serve brand activation

#### Campaign Creation
- Brief builder with fields:
  - Campaign title
  - Product / service name
  - Campaign goal (free text)
  - Key messaging (what to say)
  - Prohibited content (what never to say)
  - Deliverables required (e.g., "2 Instagram posts, 1 TikTok, attend one event")
  - Timeline: start date, end date
  - Budget (platform auto-calculates fee split)
  - Target rep categories (multi-select)
  - Target cities (multi-select)
  - Max number of reps
- Preview before submission
- Stripe payment capture at campaign activation

#### Rep Discovery
- Browse opted-in rep profiles filtered by category, city, graduation year, campaign history
- Rep card: categories, campaigns completed, average rating, city — no PII at browse stage
- Full profile view on click (no contact credit required for brands)
- Invite specific reps to campaign
- OR: request platform auto-match based on category and city targeting

#### Campaign Management
- Campaign dashboard: all campaigns with status
- Per-campaign view: rep list with individual statuses
- Submission review: view rep evidence, approve or request revision with note
- Completion confirmation: single action triggers Stripe payout
- Rating submission: 1–5 stars + optional written note per rep

#### Billing
- Stripe integration: payment at campaign activation
- Invoice and receipt generation
- Campaign history with spend per campaign

---

### Phase 3 — Recruiter Portal (Build Third)

#### Authentication & Verification
- Institution email preferred (.edu)
- Institution name, type (college | employer), website
- Manual admin approval at MVP

#### Search & Discovery
- Filter panel:
  - Graduation year (single or range)
  - City / state
  - Category (one or more)
  - Minimum campaigns completed
  - Minimum average rating
- Rep result cards: category badges, campaign count, graduation year, city — no PII until contact credit spent
- Full profile view costs one contact credit
- Saved profiles list: build and manage prospect lists

#### Messaging
- Direct message to rep costs one contact credit
- Message delivered to rep's Teenure inbox (not their personal email at MVP)
- Rep receives in-app notification
- Recruiter sees read receipts

#### Subscription & Credits
- Stripe subscription billing: monthly or annual
- Credit balance displayed in dashboard
- Credits deducted server-side at point of profile view and contact — never client-side
- Low credit warning at 20% remaining
- Credit top-up available without plan change

---

### Phase 4 — Admin Portal (Internal Only)

- Rep approval queue: review new signups, approve or reject
- Brand approval queue: review new brand accounts, verify EIN if needed
- Campaign oversight: view all campaigns, flag disputes, force-resolve
- Payment management: view all transfers, manual release override for stuck payouts
- Basic analytics:
  - Reps by city and category
  - Campaigns by status and category
  - Revenue by stream and period
  - Parental consent status breakdown

---

## 6. Technical Architecture

### Recommended Stack

| Layer | Technology | Reason |
|---|---|---|
| Frontend | Next.js 14 with App Router | Industry standard, SSR/SSG flexibility, file-based routing |
| Styling | Tailwind CSS + shadcn/ui | Fastest path to polished UI without custom design system |
| Backend | FastAPI (Python) | Extensible for data science/intelligence layer later |
| Database | PostgreSQL via Supabase | Auth, storage, RLS, and real-time subscriptions included |
| Auth | Supabase Auth | Role-aware, extensible, handles JWT out of the box |
| Payments | Stripe + Stripe Connect | Campaign billing + rep payouts in one integration |
| File storage | Supabase Storage | Campaign submission uploads |
| Email | Resend | Transactional email including parental consent flow |
| Background jobs | Supabase Edge Functions or Railway cron | Credit refresh, payment reconciliation, reminders |
| Hosting | Vercel (frontend) + Railway (FastAPI) | Both have generous free tiers to start |
| Analytics | PostHog | Open source, self-hostable, privacy-friendly |

### Application Structure

```
teenure/
├── apps/
│   ├── web/                        # Next.js — all three portals + marketing
│   │   ├── app/
│   │   │   ├── (marketing)/        # Public landing pages
│   │   │   ├── (rep)/              # Rep portal routes
│   │   │   ├── (brand)/            # Brand portal routes
│   │   │   ├── (recruiter)/        # Recruiter portal routes
│   │   │   └── (admin)/            # Admin portal routes
│   │   ├── components/
│   │   │   ├── rep/
│   │   │   ├── brand/
│   │   │   ├── recruiter/
│   │   │   └── shared/
│   │   └── lib/
│   │       ├── supabase.ts
│   │       ├── stripe.ts
│   │       └── api.ts
│   └── api/                        # FastAPI backend
│       ├── app/
│       │   ├── routers/
│       │   │   ├── auth.py
│       │   │   ├── reps.py
│       │   │   ├── brands.py
│       │   │   ├── campaigns.py
│       │   │   ├── recruiters.py
│       │   │   ├── payments.py
│       │   │   └── admin.py
│       │   ├── models/
│       │   ├── schemas/
│       │   ├── services/
│       │   │   ├── stripe_service.py
│       │   │   ├── email_service.py
│       │   │   └── payout_service.py
│       │   └── core/
│       │       ├── config.py
│       │       └── security.py
│       └── tests/
└── packages/
    └── shared-types/               # Shared TypeScript types
```

### Environment Variables

```bash
# Supabase
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=

# Stripe
STRIPE_SECRET_KEY=
STRIPE_PUBLISHABLE_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PLATFORM_FEE_PERCENT=35

# Resend
RESEND_API_KEY=
RESEND_FROM_EMAIL=noreply@teenure.com
RESEND_PARENT_CONSENT_TEMPLATE_ID=

# App
NEXT_PUBLIC_APP_URL=
API_URL=
ADMIN_SECRET_KEY=

# Feature flags
MIN_REP_AGE=14
PARENTAL_CONSENT_REQUIRED_UNDER=16

# Parent Portal (Section 9A)
PARENT_SESSION_SECRET=
RESEND_PARENT_MAGIC_LINK_TEMPLATE_ID=
RESEND_PARENT_DIGEST_TEMPLATE_ID=
```

---

## 7. Database Schema

### Full PostgreSQL Schema

```sql
-- ──────────────────────────────────────────────────────────────────
-- ENUMS
-- ──────────────────────────────────────────────────────────────────

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
CREATE TYPE parent_approval_status AS ENUM ('not_required', 'pending', 'approved', 'blocked');
-- not_required: rep is 18+, or rep is 16-17 with campaign_approval_required = FALSE.
-- pending: campaign_approval_required = TRUE for this rep and the linked parent
--   has not yet approved or blocked this specific invitation.
-- Values-filter category exclusion (Section 9A) happens upstream of this enum
--   entirely -- a blocked-category campaign never reaches
--   GET /reps/campaigns/available in the first place, so it never gets a
--   campaign_reps row and never enters this state machine.

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
  profile_completeness_score  INTEGER NOT NULL DEFAULT 0,     -- 0–100

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
  campaign_goal             TEXT NOT NULL,
  key_messaging             TEXT NOT NULL,
  prohibited_content        TEXT,
  deliverables_description  TEXT NOT NULL,

  -- Targeting
  target_categories         TEXT[] NOT NULL DEFAULT '{}',
  target_cities             TEXT[] NOT NULL DEFAULT '{}',
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
-- CAMPAIGN REPS (join table — one row per rep per campaign)
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE public.campaign_reps (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id             UUID NOT NULL REFERENCES public.campaigns(id) ON DELETE RESTRICT,
  rep_id                  UUID NOT NULL REFERENCES public.rep_profiles(id) ON DELETE RESTRICT,
  status                  rep_campaign_status NOT NULL DEFAULT 'invited',

  -- FTC compliance
  ftc_disclosure_accepted BOOLEAN NOT NULL DEFAULT FALSE,
  ftc_accepted_at         TIMESTAMPTZ,

  -- Parent approval gate (Section 9A) -- only meaningful when the rep has
  -- a parent_records row with campaign_approval_required = TRUE
  parent_approval_status  parent_approval_status NOT NULL DEFAULT 'not_required',
  parent_approval_deadline TIMESTAMPTZ,           -- 48h from invite, mirrors invite_expires_at
  parent_decided_at        TIMESTAMPTZ,

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
-- PARENT RECORDS (Section 9A) -- one row per parent-of-a-minor-rep
-- link. Parents are NOT public.users -- they authenticate via a
-- separate magic-link flow (parent_auth_tokens below), not Supabase
-- Auth, since they have no auth.users identity of their own.
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE public.parent_records (
  id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rep_id                      UUID NOT NULL UNIQUE REFERENCES public.rep_profiles(id) ON DELETE CASCADE,
  parent_email                TEXT NOT NULL,
  -- Seeded from users.parent_email at signup (Section 8's /auth/signup
  -- behavior for under-16 reps); a row is only created for reps who
  -- required parental consent at signup. A 16-17 rep has no
  -- parent_records row unless a parent separately claims one -- out of
  -- scope for MVP, so 16-17 reps without a consent-flow parent simply
  -- have campaign_approval_required permanently FALSE with no row here.
  campaign_approval_required  BOOLEAN NOT NULL DEFAULT TRUE,
  -- Always TRUE and not parent-editable while the rep is under 16
  -- (enforced in application code, not just a default -- see Section 9A).
  values_filters               TEXT[] NOT NULL DEFAULT '{}',
  -- Blocked campaign categories. Valid values: the same category enum
  -- used by rep_profiles.categories / campaigns.target_categories, plus
  -- the brand/product-content-only categories: alcohol_adjacent,
  -- political, dating_romantic, gambling, dietary_supplements,
  -- in_person_travel_required.
  digest_enabled                BOOLEAN NOT NULL DEFAULT TRUE,
  portal_expires_at             TIMESTAMPTZ NOT NULL,
  -- Set at row creation from the rep's date_of_birth (18th birthday).
  -- Recomputed if date_of_birth is ever corrected.
  suspended_by_parent_at        TIMESTAMPTZ,
  created_at                    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ──────────────────────────────────────────────────────────────────
-- PARENT AUTH TOKENS (Section 9A) -- magic-link login, single-use
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE public.parent_auth_tokens (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  parent_record_id  UUID NOT NULL REFERENCES public.parent_records(id) ON DELETE CASCADE,
  token_hash        TEXT NOT NULL UNIQUE,     -- store a hash, never the raw token
  expires_at        TIMESTAMPTZ NOT NULL,     -- 15 minutes from issuance (login link, not session)
  used_at           TIMESTAMPTZ,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- The 24-hour parent *session* issued after a successful magic-link
-- verification is a stateless signed token (HS256, PARENT_SESSION_SECRET
-- -- a new env var, distinct from SUPABASE_JWT_SECRET, since parent
-- sessions are not Supabase-issued) carrying {parent_record_id, rep_id,
-- exp}. Nothing further is stored server-side for the session itself;
-- only the one-time login link above needs a DB row (so it can be
-- marked used / rate-limited).

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

-- ──────────────────────────────────────────────────────────────────
-- INDEXES
-- ──────────────────────────────────────────────────────────────────

CREATE INDEX idx_rep_profiles_categories ON public.rep_profiles USING GIN (categories);
CREATE INDEX idx_rep_profiles_city ON public.rep_profiles (city);
CREATE INDEX idx_rep_profiles_graduation_year ON public.rep_profiles (graduation_year);
CREATE INDEX idx_rep_profiles_recruiter_visible ON public.rep_profiles (recruiter_visible) WHERE recruiter_visible = TRUE;
CREATE INDEX idx_campaigns_brand ON public.campaigns (brand_id);
CREATE INDEX idx_campaigns_status ON public.campaigns (status);
CREATE INDEX idx_campaigns_categories ON public.campaigns USING GIN (target_categories);
CREATE INDEX idx_campaign_reps_rep ON public.campaign_reps (rep_id);
CREATE INDEX idx_campaign_reps_status ON public.campaign_reps (status);
CREATE INDEX idx_campaign_reps_parent_approval
  ON public.campaign_reps (parent_approval_status, parent_approval_deadline)
  WHERE parent_approval_status = 'pending';
CREATE INDEX idx_parent_records_rep ON public.parent_records (rep_id);
CREATE INDEX idx_parent_auth_tokens_expiry ON public.parent_auth_tokens (expires_at) WHERE used_at IS NULL;

-- ──────────────────────────────────────────────────────────────────
-- ROW LEVEL SECURITY
-- ──────────────────────────────────────────────────────────────────

ALTER TABLE public.rep_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.brand_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.campaign_reps ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.recruiter_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.recruiter_contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.parent_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.parent_auth_tokens ENABLE ROW LEVEL SECURITY;
-- Parents have no Supabase auth.uid() of their own (see Section 9A), so
-- there is no meaningful auth.uid()-based RLS policy to write for these
-- two tables -- access is enforced entirely at the application layer via
-- the parent session token (Prompt 3's dependency, Prompt 4A's routes).
-- RLS is still enabled with no policies, so the default-deny applies to
-- any connection that isn't the service-role key the API uses.

-- Reps see only their own profile in edit mode
CREATE POLICY "Rep owns their profile"
  ON public.rep_profiles FOR ALL
  USING (user_id = auth.uid());

-- Recruiters see only opted-in rep profiles
CREATE POLICY "Recruiters see opted-in reps"
  ON public.rep_profiles FOR SELECT
  USING (
    recruiter_visible = TRUE
    AND EXISTS (
      SELECT 1 FROM public.users
      WHERE id = auth.uid() AND role = 'recruiter'
    )
  );

-- Brands see reps only in campaign context (via campaign_reps)
-- Admin sees everything — enforced via service role key in admin portal
```

---

## 8. API Specification

### Base URL

```
https://api.teenure.com/v1
```

### Authentication

All endpoints require `Authorization: Bearer <supabase_jwt>` except public endpoints marked `[PUBLIC]`.

Role enforcement is applied at the route level. A rep hitting a brand endpoint returns `403 Forbidden`.

---

### Auth Routes

```
POST   /auth/signup                    Register new user (role-aware)
POST   /auth/parent-verify/:token      Parent clicks consent link — activates rep account
POST   /auth/resend-consent            Resend parental consent email
GET    /auth/me                        Current user + role + account status
```

**POST /auth/signup — Request body:**
```json
{
  "email": "string",
  "password": "string",
  "role": "rep | brand | recruiter",
  "date_of_birth": "YYYY-MM-DD",
  "parent_email": "string | null"
}
```

**POST /auth/signup — Behavior:**
- If `date_of_birth` indicates age < 13: return `400 Age not permitted`
- If `date_of_birth` indicates age < 16: `parent_email` required; send consent email; set `account_status = 'pending'`
- If `date_of_birth` indicates age 16+: set `account_status = 'active'` immediately for reps
- Brands and recruiters: always `account_status = 'pending'` pending admin approval

---

### Rep Routes

```
GET    /reps/me                        Own full profile
PUT    /reps/me                        Update profile fields
GET    /reps/me/profile-preview        Exactly what a recruiter/brand sees
GET    /reps/campaigns/available       Open campaigns matching rep's categories
GET    /reps/campaigns/active          Campaigns rep has accepted
GET    /reps/campaigns/history         Completed campaigns
GET    /reps/earnings                  Earnings breakdown: pending / confirmed / paid
```

**Campaign participation:**
```
POST   /campaigns/:id/apply            Apply to a campaign
POST   /campaigns/:id/accept           Accept a campaign invitation
POST   /campaigns/:id/decline          Decline a campaign invitation
POST   /campaigns/:id/submit           Submit completion evidence
POST   /campaigns/:id/withdraw         Withdraw from a campaign at any time, no penalty, no reason required
```

**Parent approval gate:** if the rep has a `parent_records` row with `campaign_approval_required = TRUE`, `/accept` returns `403 "awaiting parent approval"` (a distinct message, not a generic 403) until the linked parent calls `POST /parent/campaigns/:campaign_id/approve` (see [Section 9A](#9a-parent-portal)). `GET /reps/campaigns/available` also excludes any campaign whose category is in that parent's `values_filters` — the rep never sees it as an option in the first place, so there's nothing to decline on that basis.

**POST /campaigns/:id/submit — Request body:**
```json
{
  "submission_text": "string",
  "submission_file_urls": ["string"]
}
```

---

### Brand Routes

```
GET    /brands/me                      Own brand profile
PUT    /brands/me                      Update brand profile

GET    /brands/campaigns               All campaigns for this brand
POST   /brands/campaigns               Create new campaign
GET    /brands/campaigns/:id           Campaign detail
PUT    /brands/campaigns/:id           Update draft campaign
POST   /brands/campaigns/:id/activate  Activate campaign (triggers Stripe charge)
POST   /brands/campaigns/:id/pause     Pause active campaign
POST   /brands/campaigns/:id/cancel    Cancel campaign (triggers refund logic)
```

**Rep management within campaigns:**
```
GET    /brands/campaigns/:id/reps           List all reps on campaign with status
GET    /brands/campaigns/:id/reps/browse    Browse matched rep profiles
POST   /brands/campaigns/:id/reps/invite    Invite specific rep(s)
GET    /brands/campaigns/:id/reps/:rep_id/submission    View rep's submission
POST   /brands/campaigns/:id/reps/:rep_id/confirm       Confirm + trigger payout
POST   /brands/campaigns/:id/reps/:rep_id/revision      Request revision with note
POST   /brands/campaigns/:id/reps/:rep_id/rate          Submit rating
```

**POST /brands/campaigns — Request body:**
```json
{
  "title": "string",
  "product_name": "string",
  "campaign_goal": "string",
  "key_messaging": "string",
  "prohibited_content": "string | null",
  "deliverables_description": "string",
  "target_categories": ["string"],
  "target_cities": ["string"],
  "max_reps": "integer",
  "budget_cents": "integer",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD"
}
```

---

### Recruiter Routes

```
GET    /recruiters/me                  Own recruiter profile
PUT    /recruiters/me                  Update recruiter profile
GET    /recruiters/credits             Current credit balance and reset date

GET    /recruiters/reps/search         Search opted-in rep profiles (costs no credit)
GET    /recruiters/reps/:id            View full rep profile (costs 1 credit)
POST   /recruiters/reps/:id/contact    Send message to rep (costs 1 credit)
POST   /recruiters/reps/:id/save       Save rep to list
DELETE /recruiters/reps/:id/save       Remove from saved list
GET    /recruiters/saved               All saved rep profiles
```

**GET /recruiters/reps/search — Query params:**
```
graduation_year=2026
city=Chicago
state=IL
categories=athletics,gaming
min_campaigns=5
min_rating=4.0
limit=20
offset=0
```

---

### Admin Routes (service role key required)

```
GET    /admin/queue/reps               Pending rep approvals
GET    /admin/queue/brands             Pending brand approvals
GET    /admin/queue/recruiters         Pending recruiter approvals
POST   /admin/approve/:type/:id        Approve account (type: rep|brand|recruiter)
POST   /admin/reject/:type/:id         Reject account with reason

GET    /admin/campaigns                All campaigns with status
POST   /admin/campaigns/:id/flag       Flag campaign for review
POST   /admin/campaigns/:id/resolve    Force resolve disputed campaign

GET    /admin/payments/stuck           Transfers in processing > 48 hours
POST   /admin/payments/:transfer_id/release   Manual payout release

GET    /admin/analytics/revenue        Revenue by stream and period
GET    /admin/analytics/reps           Rep counts by city and category
GET    /admin/analytics/campaigns      Campaign counts by status and category
```

---

### Stripe Webhook Handler

```
POST   /webhooks/stripe                Handles all Stripe events
```

**Events handled:**
```
payment_intent.succeeded          → activate campaign
payment_intent.payment_failed     → notify brand, revert campaign to draft
transfer.paid                     → update campaign_rep payout_status to 'paid'
transfer.failed                   → alert admin, flag for manual review
customer.subscription.created     → activate recruiter account + set credits
customer.subscription.renewed     → reset contact credits on new billing cycle
customer.subscription.deleted     → downgrade recruiter account
```

---

## 9. Legal and Compliance

> ⚠ **None of the following are optional.** Each represents existential legal risk if skipped. Engage a privacy lawyer before public launch.

### Non-Negotiable Requirements

| Requirement | Implementation |
|---|---|
| **Age gate** | Hard block at under-13 in signup flow. Date of birth collected and validated server-side, not client-side. |
| **Parental consent (under-16)** | Double opt-in email flow. Teen signs up → parent receives email with one-time consent link → profile not activated until link clicked. Token expires in 72 hours. |
| **FTC disclosure** | Required checkbox and acknowledgment at campaign acceptance step. Text: "I agree to disclose that this post is sponsored using #ad or #sponsored as required by FTC guidelines." Stored as `ftc_disclosure_accepted` with timestamp. |
| **Data minimization** | Collect only fields listed in the schema. No passive behavioral tracking. No third-party enrichment. Document the purpose of every field collected. |
| **Stripe Connect minors** | Research Stripe's current policy on Connected Accounts for under-18 before launch. May require parent as account holder depending on state. |
| **Privacy policy** | Must be written specifically for minors. Plain language. Reviewed by a lawyer. Must explain parental rights under COPPA and state laws. |
| **Terms of service** | Separate terms for each user type. Reviewed by a lawyer. |
| **California CPPA** | Build for California compliance (strictest state) and you cover most others. No selling of minor data. No targeted advertising using minor data. |

### Data Architecture Constraint

The intelligence layer must operate on **anonymized, aggregated** data only. No individual rep profile data — even internal data — may be used to generate intelligence reports. The pipeline is:

```
Campaign completion event
        ↓
Strip all PII (rep ID, name, school name)
        ↓
Aggregate to category + city + time period level
        ↓
Intelligence layer (minimum group size: 10 reps — never report on groups smaller than 10)
        ↓
Trend report output
```

This architecture protects against the scenario where a brand could reverse-engineer individual teen behavior from intelligence data.

---

## 9A. Parent Portal

A separate, deliberately narrow authenticated surface for parents/guardians of minor reps (see [Section 2.4](#24-the-parent-guardian-of-a-minor-rep--oversight-role-not-a-platform-side) for the role's scope and motivations, and [Section 7](#7-database-schema) for the `parent_records` / `parent_auth_tokens` / `campaign_reps.parent_approval_status` schema). Parents do not have `auth.users` accounts and are not a fourth platform side — this section exists because Teenure handles minors' data and income, not because it adds a new revenue stream.

### Authentication

Parents authenticate via magic link, not a password:

```
POST   /parent/auth/request-link       [PUBLIC] Request a login link by email
GET    /parent/auth/verify/:token      [PUBLIC] Verify a login link, issue a parent session
```

- `request-link` looks up `parent_records` by `parent_email`. **Always returns the same response regardless of whether the email matches a record** — do not reveal whether a given email is linked to a minor rep's account (enumeration risk). Rate-limited per email, same pattern as `/auth/resend-consent`.
- If the email matches, a single-use token is created in `parent_auth_tokens` (15-minute expiry) and emailed via Resend.
- `verify/:token` validates the token (invalid/expired/already-used get distinct responses, same pattern as `/auth/parent-verify/:token`), marks it used, and issues a signed parent session token (24-hour expiry; see Section 7's schema note on `PARENT_SESSION_SECRET`).
- Every `/parent/*` route below (except the two above) requires `Authorization: Bearer <parent_session_token>`, verified against `PARENT_SESSION_SECRET` — not the Supabase JWT verification path used everywhere else, since parents have no Supabase identity.
- **Portal expiry:** verified at login time (not just checked once at record creation) — if `now() > parent_records.portal_expires_at`, `verify/:token` and any still-live session both return a distinct "portal has closed, your child is now an adult" response rather than a generic auth failure.

### Routes

```
GET    /parent/dashboard                        Linked rep's profile summary + earnings
GET    /parent/campaigns/pending                 Campaigns awaiting this parent's approval
POST   /parent/campaigns/:campaign_id/approve    Approve a pending campaign invitation
POST   /parent/campaigns/:campaign_id/block      Block it (neutral auto-decline to the brand)
GET    /parent/settings                          Current values_filters + approval-required + digest toggle
PUT    /parent/settings/values-filters            Update blocked categories
PUT    /parent/settings/approval-required          Toggle approval gate (16-17 only, see below)
GET    /parent/digest/preview                     Preview of the next monthly digest email
PUT    /parent/settings/digest                     Toggle monthly digest
POST   /parent/account/suspend                     Immediately suspend the rep account
POST   /parent/account/unsuspend                   Reverse a parent-initiated suspension
```

- `GET /parent/dashboard` returns exactly the no-PII fields a recruiter's card view would show (display name, school, graduation year, categories, completeness score), **plus** total earnings and campaigns completed — a parent has a legitimate interest in income their own minor child is earning, unlike a recruiter.
- `campaign_approval_required` is **always `TRUE` and not parent-editable while the rep is under 16** — `PUT /parent/settings/approval-required` returns `403` with an explanation if called for an out-of-range rep age (under 16, or 18+ where the portal itself has already expired). It's only actually togglable for a 16-17-year-old rep.
- `POST .../block` never exposes the parent's reason to the brand — the campaign auto-declines with a neutral message ("rep is unavailable"), matching the existing decline flow's shape from the brand's point of view.
- The monthly digest (a scheduled job, registered on the Prompt 3 job runner, alongside the existing invite-expiry job) contains: campaigns completed this month, earnings this month and lifetime, profile-completeness change, active categories. It must **never** contain recruiter message content, submission text/files, or brand contact details — this is a hard content boundary, not a formatting choice.
- `POST /parent/account/suspend` sets the rep's `account_status` to `suspended` immediately, notifies the rep, and alerts admin. `unsuspend` only works if the original suspension was parent-initiated — an admin-initiated suspension can only be reversed by admin.

### Compliance notes (extends Section 9's Non-Negotiable Requirements)

| Requirement | Implementation |
|---|---|
| **No enumeration via parent login** | `/parent/auth/request-link` gives an identical response whether or not the email is linked to a rep — same principle as not confirming account existence elsewhere in the auth flow. |
| **Parent portal data minimization** | The parent dashboard and digest are both allow-listed to specific fields (see above) — never a raw dump of the rep's activity. Recruiter message content and submission files are explicitly excluded from every parent-facing surface. |
| **Values-filter enforcement point** | Enforced server-side in `GET /reps/campaigns/available` (Section 8) — the rep never sees a blocked-category campaign as an option. The parent portal's filter *configuration* screen and the *enforcement* point are different layers; configuring a filter with no enforcement would be a compliance gap, not just a UX one. |
| **Portal expiry at 18** | Checked at every parent login/session-verify, not only at `parent_records` row creation, so a stale valid-looking session token can't outlive the rep's 18th birthday. |

---

## 10. AI Builder Prompt

> Copy and paste this verbatim to any AI coding assistant along with this document.

---

**SYSTEM CONTEXT:**

You are building Teenure — a three-sided verified achievement platform for high school students. The full product specification, data models, API endpoints, technical stack, and business logic are in the accompanying Teenure MVP Game Plan document. Read the entire document before writing any code.

**BUILD INSTRUCTIONS:**

Stack:
- Frontend: Next.js 14 with App Router, TypeScript, Tailwind CSS, shadcn/ui
- Backend: FastAPI (Python 3.11+)
- Database: PostgreSQL via Supabase (use the schema in Section 7 exactly as written)
- Auth: Supabase Auth with role-aware signup and parental consent flow
- Payments: Stripe for brand billing, Stripe Connect for rep payouts
- Email: Resend for transactional email
- File uploads: Supabase Storage

Build sequence — do not deviate:
1. Database schema first (Section 7) with row-level security enabled
2. FastAPI backend with all routes in Section 8
3. Phase 1: Rep Portal (Section 5, Phase 1) — fully functional before Phase 2
4. Phase 2: Brand Portal (Section 5, Phase 2) — fully functional before Phase 3
5. Phase 3: Recruiter Portal (Section 5, Phase 3)
6. Phase 4: Admin Portal (Section 5, Phase 4)

Non-negotiable constraints:
- Parental consent email flow for under-16 reps (double opt-in, token-based, 72-hour expiry)
- FTC disclosure checkbox required before any rep accepts any campaign
- Credit deduction for recruiter profile views and contacts enforced server-side only
- No passive behavioral tracking. No data collection beyond the schema fields.
- All financial calculations server-side. Never trust client-submitted amounts.
- Row-level security on all tables from day one.

Start with the database schema and the FastAPI project scaffolding. Confirm the schema is applied before moving to application code.

---

## 11. Go-To-Market Sequence

### Week 1–2: Build the Rep Side Manually

The cold start problem kills every platform. Solve the rep side manually before the brand side exists.

- Identify 10 socially connected teens personally. Not through marketing.
- Sign them up by hand. Fill their profiles with them in person.
- These are founding reps, not users. Treat them as co-founders of the network.
- Get commitment from each: two campaigns completed in first 60 days.
- Target: 10 reps in one city before approaching any brand.

### Week 3–4: First Brand Conversations

- Target local businesses, not national brands.
- The gym everyone goes to. The new sneaker boutique. The restaurant near school.
- Pitch is one sentence: *"I have 10 verified student brand ambassadors at [school] ready to promote you this month for $300."*
- Three yeses from local brands funds first rep payouts and proves the model.
- Run first campaigns manually. Google Form for brief, group chat for coordination, Venmo for payment.
- Build the platform while the first campaigns run. Not before.

### Month 2–3: Expand the Rep Network

- Each founding rep recruits 3 friends. 10 becomes 30–40.
- Expand to a second school in the same city before touching a second city.
- Category clustering: deliberately recruit athletes, gamers, fashion-forward students separately.
- Rep portal launches internally.

### Month 3–6: First College Conversation

- Target admissions officers at local colleges, not national universities.
- Pitch: *"We have 40 verified student profiles with documented real-world performance in [city]. Would your admissions team want early access?"*
- Offer first 3 months free in exchange for feedback and a testimonial.
- One college on record changes every subsequent brand conversation.

### Month 6–12: Intelligence Layer Activates

- By month 6 there is enough campaign data to produce a first trend report.
- Produce it manually. Present it to 3 brands who ran campaigns.
- If they would pay for it, the intelligence product exists.
- This is the moment the business model shifts from services to data.

---

## 12. Risk Register

| Risk | Mitigation |
|---|---|
| **Teen data regulation tightens** | Data minimization architecture from day one. Anonymize and aggregate before any intelligence use. Privacy-first design is harder to attack even if laws change. |
| **Rep churn at graduation** | Graduation is also your distribution channel. Every rep who goes to college is a Teenure advocate on campus. Build an alumni rep tier for 18–22 year olds explicitly. |
| **Brands run campaigns directly** | They already do and it costs them more. Your value is curation, verification, and data — not access alone. |
| **Competitor copies the model** | Profiles and data are the moat, not the idea. A copycat starts with zero profiles. A two-year head start on verified profile depth is not quickly replicable. |
| **FTC enforcement on disclosure** | Build FTC acknowledgment into the platform at campaign acceptance. Make it impossible to complete without it. Document every disclosure acceptance with timestamp. |
| **School access restrictions** | Never recruit on school property without permission. Work through students, not administration. The rep recruits peers — you never go near the school directly. |
| **Stripe Connect minors** | Research Stripe's minor policy before launch. May require parent as account holder. Build parent-as-payee option into the payout flow as a fallback. |
| **Brand gaming the rating system** | Brands cannot submit ratings until they confirm completion. Completion releases payment. Ratings cannot be edited after submission. Flag outlier rating patterns in admin panel. |

---

## 13. Milestones That Matter

Ignore vanity metrics. These are the only six milestones worth tracking.

| # | Milestone | What It Proves |
|---|---|---|
| 1 | 10 reps with complete profiles in one city | The network has a nucleus |
| 2 | First brand pays $300+ and confirms campaign completion | The campaign model works |
| 3 | First college admissions officer asks for more profiles | The recruitment product has real demand |
| 4 | First brand pays for intelligence data independent of a campaign | The data business exists |
| 5 | $10,000 in a single month across all revenue streams | The model is real |
| 6 | A rep who joined at 14 uses their Teenure profile in a college application | The switching cost is real |

---

> *The first time a college admissions officer asks for a Teenure profile is when you have a business. Everything before that is infrastructure.*

---

**Document version:** 1.3
**Status:** MVP specification — ready for build
**Domain:** teenure.com
