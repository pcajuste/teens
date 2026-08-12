# TEENURE — AI Builder Prompt Suite v1.4

> Companion to `Teenure_MVP_Gameplan.md` (the spec of record). That document is the source of truth for schema, routes, business rules, and legal constraints — this document sequences the build into discrete, verbatim prompts an AI coding assistant can execute one at a time, in order.
>
> **How to use this file:** Paste the Master Context Prompt once at the start of a build session (or keep it in the assistant's persistent context). Then paste each numbered prompt in order, one at a time. Do not start prompt N+1 until prompt N's acceptance criteria are met. Do not skip prompts or reorder phases — the dependency chain is explicit in each prompt's "Depends on" line.

---

## Table of Contents

0. [Master Context Prompt](#0-master-context-prompt)
0A. [Design System & UX Standards](#0a-design-system--ux-standards)
1. [Repo & Environment Scaffolding](#1-repo--environment-scaffolding)
2. [Database Schema & Row-Level Security](#2-database-schema--row-level-security)
3. [FastAPI Core: Config, Security, Auth Scaffolding](#3-fastapi-core-config-security-auth-scaffolding)
4. [Auth Flows: Signup, Age Gate, Parental Consent](#4-auth-flows-signup-age-gate-parental-consent)
4A. [Parent Portal](#4a-parent-portal)
5. [Rep Portal — Backend](#5-rep-portal--backend)
6. [Rep Portal — Frontend](#6-rep-portal--frontend)
6A. [Demo Mode — Rep Demo](#6a-demo-mode--rep-demo)
7. [Stripe Foundation: Connect Onboarding & Platform Billing](#7-stripe-foundation-connect-onboarding--platform-billing)
8. [Brand Portal — Backend](#8-brand-portal--backend)
8B. [Performance Milestone Payments](#8b-performance-milestone-payments)
8C. [Category Exclusivity](#8c-category-exclusivity)
8D. [Advance Cohort Reservation](#8d-advance-cohort-reservation)
8E. [Rep Syndicates](#8e-rep-syndicates)
8F. [Relationship Continuity Product (Year Two)](#8f-relationship-continuity-product-year-two)
8G. [Skill Challenges](#8g-skill-challenges)
8H. [Learning Modules and Verified Badges](#8h-learning-modules-and-verified-badges)
9. [Brand Portal — Frontend](#9-brand-portal--frontend)
10. [Campaign Lifecycle & Payout Engine](#10-campaign-lifecycle--payout-engine)
11. [Recruiter Portal — Backend](#11-recruiter-portal--backend)
12. [Recruiter Portal — Frontend](#12-recruiter-portal--frontend)
12A. [Demo Mode — Recruiter Preview & Brand Sales Page](#12a-demo-mode--recruiter-preview--brand-sales-page)
13. [Admin Portal](#13-admin-portal)
14. [Intelligence Layer & Anonymization Pipeline](#14-intelligence-layer--anonymization-pipeline)
15. [Compliance Audit Pass](#15-compliance-audit-pass)
16. [Testing Suite](#16-testing-suite)
17. [Deployment & CI/CD](#17-deployment--cicd)
18. [Marketing Site](#18-marketing-site)
19. [Analytics Integration (PostHog)](#19-analytics-integration-posthog)

---

## 0. Master Context Prompt

> Paste this first, in every new session, before any other prompt in this file.

```
You are building Teenure — a three-sided verified achievement platform for
high school students. There are three external user types (Rep, Brand,
Recruiter) plus an internal Admin role, and a linked Parent role tied to
Rep accounts for minors.

The full specification lives in Teenure_MVP_Gameplan.md in this repository.
Read it in full before writing any code, and re-read the relevant section
before each phase of work. It contains:
  - Section 1 / 1A: product identity and the enforced content-policy
    exclusions (no rep-to-rep messaging, no public feed, no profile photos,
    no discovery/dating mechanics). Treat these as hard technical
    constraints, not just copy guidance — the enforcement mechanism column
    in the 1A table tells you what to actually build (or deliberately not
    build).
  - Section 4: revenue model (informs what fields campaigns/subscriptions
    need, not what UI to build).
  - Section 5: MVP feature set, phased. Build order is mandatory: Rep
    Portal, then Brand Portal, then Recruiter Portal, then Admin Portal.
    Each phase must be fully functional before the next begins.
  - Section 6: technical architecture, stack, and monorepo layout.
  - Section 7: the complete Postgres schema, verbatim. Do not redesign it
    without flagging the change and reason.
  - Section 8: the complete API surface, verbatim. Route names, request
    bodies, and role restrictions are normative.
  - Section 9: legal/compliance constraints. These are non-negotiable —
    age gating, parental consent, FTC disclosure, data minimization,
    server-side-only financial and credit calculations, anonymized
    intelligence pipeline. Every one of these needs a technical enforcement
    mechanism, not just a UI hint or ToS clause.

Safety-by-design rule (applies to every prompt in this suite):
  Every feature decision is evaluated against a safety-by-design framework
  BEFORE it is evaluated against a product or revenue framework. The
  sequence is: safety first, compliance second, product third. Any feature
  that passes product criteria but fails safety criteria does not get built.
  Teenure handles verified data for minors — this rule is non-negotiable.

Stack (do not substitute without discussion):
  - Frontend: Next.js 14, App Router, TypeScript, Tailwind CSS, shadcn/ui
  - Backend: FastAPI, Python 3.11+
  - Database/Auth/Storage: Supabase (Postgres, Supabase Auth, Supabase
    Storage), Row-Level Security enabled on every table from the first
    migration
  - Payments: Stripe (brand billing) + Stripe Connect (rep payouts)
  - Email: Resend
  - Hosting: Vercel (web) + Railway (api)
  - Analytics: PostHog

Monorepo layout (Section 6):
  teenure/
    apps/web/            Next.js — marketing + all portals via route groups:
                          (marketing) (rep) (brand) (recruiter) (admin)
                          (parent)
    apps/api/             FastAPI — routers per domain, models, schemas,
                          services, core config/security
    packages/shared-types/ Shared TypeScript types between web and any
                          TS tooling

Ground rules for every prompt in this suite:
  - Never trust client-submitted financial amounts, credit balances, or
    role claims. Recompute and re-authorize server-side on every
    financially or access-relevant action.
  - Every table gets RLS before it gets application code that touches it.
  - Every prompt that touches a minor's data must consider the age-gate,
    parental-consent state machine, and parent campaign-approval state —
    do not assume an account is active or a campaign is approved.
  - When a prompt's scope conflicts with something already built, stop
    and flag the conflict rather than silently resolving it.
  - After completing a prompt's deliverables, verify against its
    acceptance criteria explicitly before moving to the next prompt.

This prompt suite (Teenure_Build_Prompts.md) and the gameplan are both
kept in sync as of suite version 1.3 / gameplan version 1.3 — every
normative addition the suite has made has been folded back into the
gameplan itself, so the two documents should not disagree. If a future
edit to either document introduces a conflict, this suite takes
precedence — it reflects build-sequencing decisions made after the
gameplan's original text was written, and its changelog is the record of
why.

Confirm you have read Teenure_MVP_Gameplan.md in full before proceeding to
the first build prompt.
```

---

## 0A. Design System & UX Standards

> Added post-Prompt-8, after the built Rep Portal frontend (Prompt 6) was
> assessed as functionally correct but visually indistinguishable from an
> unstyled component library — default shadcn/ui primitives with no color
> system, type scale, spacing discipline, or motion beyond what Tailwind
> ships out of the box. That's a real gap: Teenure's users are a
> compliance-sensitive three-sided market (teenagers, brand marketers,
> college admissions/HR staff) where visual credibility is not cosmetic —
> a recruiter or brand deciding whether to trust a platform with a minor's
> data and a campaign budget is making a trust judgment partly *from the
> UI itself* before they read a word of copy. Paste this section alongside
> Section 0 for every frontend-touching prompt from Prompt 9 onward, and
> treat Prompt 6/6A's existing screens as due for a retrofit pass against
> it (tracked, not yet scheduled as its own numbered prompt — see the
> changelog).

```
Design authority for this section: Andrew Chen's "Simple Is Marketable"
thesis (https://andrewchen.com/simple-is-marketable/) — the same
reductions that make a product feel clean also make it convert:
fewer choices raise completion rates, shorter paths to value raise
activation, and *removing* a low-value feature (not just visually
de-emphasizing it) is what actually increases the prominence of the
action that matters. This is the standard every screen gets measured
against — not "does this look nice" but "does this reduction serve
both trust and the funnel." If a design decision cannot answer "what
metric or trust signal does this serve," it does not ship, regardless
of how it looks — that cuts both ways: it rules out unstyled default
components AND it rules out decoration for its own sake (gradient-heavy
"AI startup" aesthetics, gratuitous animation, illustration for
illustration's sake). The bar is Stripe's dashboard/checkout, Linear's
issue tracker, and Vercel's dashboard — confident through typography
and whitespace, not through ornamentation. Every one of those products
is also aimed at a skeptical, professional audience deciding whether to
trust the product with money or workflow-critical data, which is
exactly Teenure's situation with brands and recruiters, and exactly why
"looks like a hackathon project" is a real business risk, not just an
aesthetic complaint.

1. Design tokens, defined once, before any screen work in a given
   portal:
   - Color: a real palette in apps/web's Tailwind config / globals.css
     — a primary brand hue (not Tailwind's default blue-600), a full
     neutral scale for text/borders/backgrounds, and semantic colors
     (success/warning/destructive/info) used consistently. Never an
     arbitrary Tailwind color picked ad hoc per component.
   - Typography: a deliberate type scale (display, h1-h4, body, label,
     caption) with consistent weight/line-height per level, and a
     typeface pairing chosen on purpose — not the unstyled system-ui
     fallback. Headings and body text should be visually distinct in
     more than just size.
   - Spacing: an 8px-based scale, applied consistently — no
     component-by-component arbitrary padding/margin values.
   - Elevation: a small, consistent set of shadow/border treatments for
     card hierarchy (resting, hover, active) — flat white-on-white with
     only hairline borders is the single biggest tell of an unstyled
     shadcn/ui screen and is exactly what's being corrected here.
   Land these as an explicit apps/web/lib/design-tokens.ts or Tailwind
   theme extension BEFORE building individual screens in whichever
   prompt you're on — retrofitting tokens after screens exist is far
   more expensive than establishing them first.

2. Interaction and motion, used with restraint:
   - Real button states: default, hover, active/pressed, loading
     (spinner or skeleton, never a frozen button), disabled.
   - Skeleton loading states for any data fetch, never a blank white
     flash or unstyled "Loading..." text.
   - Designed empty states (a short message + an action, not a blank
     list) for every list/table view — available campaigns with none
     yet, inbox with no messages, etc.
   - Transitions (page/panel/modal) should be fast (150-250ms) and
     purposeful — confirming state changed, not decorative. If a
     motion doesn't help the user understand what just happened, cut
     it.

3. Content density and choice architecture (the direct application of
   the Chen thesis above):
   - One visually dominant primary action per screen; every other
     action is visually subordinate (secondary button style, smaller,
     or moved into an overflow/settings area).
   - Onboarding and campaign-acceptance flows are audited for step
     count the same way a growth team audits a signup funnel — every
     field/screen must justify its presence at that step, or it moves
     later/becomes optional.
   - When a feature is genuinely low-value for a given screen, remove
     it from that screen rather than shrinking/graying it out. A
     grayed-out or de-prioritized element still costs the user a
     decision; a removed one doesn't.

4. Trust and credibility signals (Fortune-500-bar specific, since the
   buyers here are brand marketers and college/employer staff
   evaluating whether to associate their organization with the
   platform):
   - Real brand identity: a designed logo lockup, favicon, and OG/share
     images — not the default Next.js starter icon set.
   - Consistent, honest status/verification indicators (e.g. a brand's
     "verified" badge, a campaign's status pill) using the semantic
     color system from (1) — never fabricated social proof numbers.
   - Accessible by default: WCAG AA contrast minimums, visible focus
     states, semantic HTML/ARIA where shadcn/ui doesn't already provide
     it. This is both a trust signal and a legal-risk reducer for an
     app that serves minors.
   - Error and 404/empty states written and styled with the same care
     as the primary flows — a broken-looking error state undermines
     trust disproportionately to how rarely it's seen.

5. Explicit anti-goals — this section corrects "looks unfinished," it
   does not authorize over-designing:
   - No decoration without a stated purpose. Every gradient, shadow,
     animation, or illustration must map to a specific UX or trust
     purpose describable in one sentence; if it can't be, cut it.
   - No motion for motion's sake, no stock-illustration filler, no
     "AI startup" visual clichés (heavy gradients, glassmorphism for
     its own sake, oversized rounded corners applied uniformly without
     reason).
   - Simplicity is the deliverable, not an excuse to ship the current
     unstyled state. "Simple" means deliberately reduced, not
     undesigned — the difference between the two is exactly the token
     system in (1).

Acceptance criteria (apply to every frontend prompt from Prompt 9
onward, and to a future Prompt 6/6A retrofit pass):
  - A design-tokens file/theme extension exists and every new screen
    reads from it — no raw hex values or arbitrary Tailwind color/
    spacing classes in component code.
  - Every list/table view has a designed empty state; every async
    action has a loading state; no blank-white-flash states remain.
  - Every screen has exactly one visually dominant primary action.
  - Lighthouse accessibility score ≥ 90 on every built page.
  - A reviewer unfamiliar with the build should be able to look at any
    two screens from different portals and identify them as the same
    product from typography/color/spacing alone, without reading text.
```

---

## 1. Repo & Environment Scaffolding

**Depends on:** nothing (first code prompt).

```
Scaffold the Teenure monorepo per Section 6 of Teenure_MVP_Gameplan.md.

Deliverables:
1. Root-level workspace config (package.json with workspaces, or Turborepo/
   pnpm-workspace.yaml — choose one and state why) wiring apps/web,
   apps/api, and packages/shared-types together.
2. apps/web: Next.js 14 App Router project, TypeScript strict mode,
   Tailwind CSS configured, shadcn/ui initialized with a neutral base
   theme. Create six route groups as empty shells with a placeholder
   page each: (marketing), (rep), (brand), (recruiter), (admin),
   (parent).
3. apps/api: FastAPI project on Python 3.11+, with the directory structure
   from Section 6 (routers/, models/, schemas/, services/, core/, tests/).
   Include a working `/health` endpoint and app factory pattern (not a
   bare module-level FastAPI() instance) so config can be injected for
   tests later.
4. packages/shared-types: empty TypeScript package, wired into apps/web's
   tsconfig paths, ready to receive generated or hand-written types.
5. .env.example at repo root listing every variable from Section 6's
   Environment Variables block, with comments explaining what each is for.
   Do not put real values in this file.
6. .gitignore covering node_modules, .next, __pycache__, .env* (except
   .env.example), and any Python virtualenv directories.
7. Root README.md: how to install dependencies and run both apps locally
   in dev mode. Keep it short — this is a dev bootstrap doc, not the
   product spec.
8. A /demo directory (empty scaffold only) with a README stating its
   purpose: this will hold the seed data and script that power the public
   demo experiences (Prompt 6A, Prompt 12A) and the marketing/investor/
   sales demo. Keep this strictly separate from the dev-fixture seed
   script Prompt 2 creates — that one is for local development/testing,
   this one is for public-facing demos and must never contain anything
   that looks like a real minor's data, and must stay stable
   release-over-release so demo links don't break.

Acceptance criteria:
  - `next dev` in apps/web serves a page for each of the six route groups
    without errors.
  - `uvicorn` (or the chosen runner) serves apps/api with a passing
    GET /health.
  - No secrets committed anywhere in the tree.
```

---

## 2. Database Schema & Row-Level Security

**Depends on:** Prompt 1.

```
Implement the database layer exactly as specified in Section 7 of
Teenure_MVP_Gameplan.md.

Deliverables:
1. A Supabase migration creating, in order: all ENUM types, then
   public.users, rep_profiles, brand_profiles, campaigns, campaign_reps,
   recruiter_profiles, recruiter_contacts, recruiter_saved_profiles,
   parent_records — schema verbatim from Section 7, including every
   column, constraint, default, and CHECK.

   Key schema notes:
   - campaign_status enum includes pending_payment and payment_failed in
     addition to draft, active, paused, completed, cancelled.
   - rep_profiles includes school_type (nullable enum:
     public/private/charter/homeschool) — self-reported, used only in
     anonymized intelligence aggregation, never surfaced individually.
   - parent_records table: parent_id (UUID PK), rep_id (FK to
     rep_profiles, unique — one parent record per rep), parent_email
     (text not null), digest_enabled (boolean default true), values_filters
     (jsonb default '[]' — array of blocked campaign category strings),
     campaign_approval_required (boolean — true for under-16, toggleable
     for 16-17 by parent, false for 18+), portal_expires_at (timestamptz —
     set to rep's 18th birthday, enforced at login). Parent records are
     not auth.users rows — parents authenticate via a separate magic-link
     flow, not a password account.

2. All indexes listed in Section 7's Indexes block, plus:
   - idx_parent_records_rep on parent_records(rep_id)
   - idx_campaigns_status_category on campaigns(status, target_categories)
     (supports parent approval queue filtering)

3. RLS on every table. In addition to the policies in Section 7:
   - parent_records: a parent can read/update only their own row (matched
     via a parent session token, not auth.uid() — document the session
     mechanism you choose); the rep cannot read or write parent_records
     directly (their onboarding wizard writes the parent_email via an API
     endpoint that creates the record server-side).
   - campaigns: add a policy blocking rep access to any campaign where
     parent campaign_approval_required = TRUE and no parent approval
     exists yet for that campaign_reps row — enforce this at the RLS
     layer so it cannot be bypassed by the API.

4. Trigger/scheduled function design note for rep_profiles cached fields
   (total_campaigns_completed, total_earnings_cents, average_rating,
   profile_completeness_score).

5. Seed script for local dev — clearly marked dev-only, never run
   against production, creates fake users across all roles including
   a parent record linked to each under-18 rep.

Acceptance criteria:
  - Migration applies cleanly to a fresh database.
  - RLS: a rep cannot read another rep's row; a recruiter sees only
    recruiter_visible=TRUE reps; a parent can read only their own
    parent_records row.
  - Seed script runs idempotently.
```

---

## 3. FastAPI Core: Config, Security, Auth Scaffolding

**Depends on:** Prompt 2.

```
Build the FastAPI application core: configuration, security primitives,
and Supabase JWT verification.

Deliverables:
1. app/core/config.py: typed pydantic BaseSettings loading every variable
   from .env.example. Fail fast at startup if a required variable is
   missing.
2. app/core/security.py:
     - JWT dependency extracting and verifying Supabase JWT from the
       Authorization: Bearer header.
     - User-loading dependency exposing role + account_status to routes.
     - Role-enforcement dependency factory (require_role("brand")) returning
       403 on mismatch.
     - Account-status enforcement: pending/suspended/rejected accounts get
       403 with a clear reason distinct from role-mismatch 403.
     - Parent session enforcement: a separate dependency for parent-portal
       routes that validates the parent magic-link session token (not a
       Supabase JWT) — document the token mechanism chosen.
3. Service shells: stripe_service.py, email_service.py, payout_service.py,
   parent_service.py — typed empty shells with function signatures and
   docstrings. parent_service functions: send_digest_email,
   send_campaign_approval_request, record_campaign_approval,
   record_campaign_block, apply_values_filter.
4. Global exception handlers returning {"error": {"code": ...,
   "message": ...}} for 4xx/5xx.
5. CORS scoped to web app origin(s) from env vars — not wildcard.
6. pytest scaffolding with fixtures for authenticated users per role
   (including a parent session fixture).
7. Scheduled-job runner scaffold (app/jobs/runner.py) with one no-op job
   registered end-to-end proving the schedule fires. Document which
   mechanism (Railway cron vs Supabase Edge Function) was chosen and why.

Acceptance criteria:
  - No Authorization header → 401.
  - Wrong-role JWT → 403.
  - Missing required env var → clear startup error.
  - Parent session fixture authenticates correctly against parent-portal
    routes in tests.
```

---

## 4. Auth Flows: Signup, Age Gate, Parental Consent

**Depends on:** Prompt 3.

```
Implement auth routes and the age-gate / parental-consent state machine.
This is the single highest-legal-risk piece of the platform — follow the
spec literally, do not simplify.

Deliverables:
1. POST /auth/signup:
     - age < 13 → 400, no account created.
     - age < 16 → parent_email required (400 if missing); account_status
       = 'pending'; generate cryptographically random single-use
       consent_token; send consent email; token expires 72 hours from
       creation (checked at verification, not just at generation).
     - age 16-17 (rep) → account_status = 'active' immediately; create
       parent_record with parent_email if provided, digest_enabled = true,
       campaign_approval_required = true by default (parent can disable via
       parent portal — see Prompt 4A).
     - age 18+ (rep) → account_status = 'active'; no parent_record
       created; parent portal access not available.
     - brand/recruiter → always account_status = 'pending' regardless of
       age, pending admin approval.
2. POST /auth/parent-verify/:token: check expiry, set parent_verified_at,
   flip account_status to 'active', create parent_record. Return distinct
   errors for expired / already-used / invalid tokens.
3. POST /auth/resend-consent: rate-limited (state rate-limit choice and
   reasoning — this sends email to a parent, so abuse matters).
4. GET /auth/me: returns role, account_status, and enough pending-state
   detail for the frontend to render the correct waiting screen.
5. email_service.send_parental_consent_email via Resend — plain language,
   non-legalese, explains what the parent is consenting to.
6. Server-side age calculation only — never trust client-computed age.

Acceptance criteria:
  - age 12 signup → 400, no row created.
  - age 15 signup → pending, consent email sent, cannot authenticate
    active until consent link used.
  - Consent token used twice → "already used" error.
  - Consent token after 72h → "expired" error.
  - Brand/recruiter never reach active via this flow alone.
  - pytest coverage for every branch.
```

---

## 4A. Parent Portal — **implemented**

**Depends on:** Prompt 4. Canonically sits between Prompts 4 and 5 in
the build sequence — the parent campaign-approval gate and values-filter
exclusion in Prompt 5 depend on the parent_service functions this
prompt implements.

```
Build the Parent Portal: a separate authenticated surface for parents of
minor reps. Parents are not auth.users — they authenticate via a
magic-link email flow and have a scoped session distinct from rep/brand/
recruiter JWTs. The portal is intentionally limited in scope: parents see
what their child does on Teenure, can approve or block campaigns, and can
configure values filters — they do not have co-pilot access to the rep's
account.

Deliverables:
1. Parent authentication flow:
     - POST /parent/auth/request-link: accepts parent_email, looks up the
       parent_record, sends a magic-link email via Resend. Rate-limited.
       Do not confirm whether the email exists (prevents enumeration of
       minor rep accounts).
     - GET /parent/auth/verify/:token: validates token, issues a short-lived
       parent session token (not a Supabase JWT — document the token
       format, signing, and expiry chosen; 24-hour expiry is reasonable for
       a "check in on my kid" use case).
     - All /parent/* routes require a valid parent session token enforced by
       the dependency from Prompt 3.

2. GET /parent/dashboard: returns the linked rep's profile summary
   (display name, school, graduation year, categories, profile completeness
   score, total earnings, campaigns completed) — exactly the fields a
   recruiter would see in no-PII card mode, plus earnings since parents
   have a legitimate interest in income their child is earning.

3. Campaign approval queue (for parents with campaign_approval_required
   = TRUE):
     - GET /parent/campaigns/pending: campaigns the rep has been invited to
       that are awaiting parent approval. Returns full campaign brief —
       brand name, product, messaging, deliverables, prohibited content,
       payout, timeline, whether it requires in-person activation.
     - POST /parent/campaigns/:campaign_id/approve: records approval,
       allows the rep's invitation flow to proceed. Idempotent.
     - POST /parent/campaigns/:campaign_id/block: records block, auto-
       declines the rep's invitation with a neutral message to the brand
       ("rep is unavailable") — do not expose the reason to the brand.
     - Parent approval window: 48 hours from campaign match (same window
       as rep accept/decline). If parent does not respond within 48 hours,
       the campaign auto-declines and the slot frees. The scheduled job
       from Prompt 5 handles this timeout — extend it to also check parent
       approval state before processing rep invitations.

4. Values filter configuration:
     - GET /parent/settings: returns current values_filters and
       campaign_approval_required toggle.
     - PUT /parent/settings/values-filters: updates the jsonb array of
       blocked campaign categories. Valid category values are the same
       centrally-defined enum as rep_profiles.categories plus brand/product
       content categories: alcohol_adjacent, political, dating_romantic,
       gambling, dietary_supplements, in_person_travel_required. Blocked
       categories are enforced server-side in Prompt 5's campaign matching
       — a rep never sees a campaign from a blocked category, the brand
       never knows why.
     - PUT /parent/settings/approval-required: toggle campaign_approval_
       required. Only legal for reps aged 16-17 (under-16 always required,
       18+ parent portal expired). Returns 403 with explanation if called
       for an out-of-range rep age.

5. Monthly digest:
     - GET /parent/digest/preview: returns what the next monthly digest
       email will contain — campaign activity, earnings, profile changes
       since last digest.
     - PUT /parent/settings/digest: toggle digest_enabled.
     - The actual digest send is a scheduled job (register on Prompt 3's
       runner): runs monthly, generates per-parent digest from rep activity,
       sends via Resend. Digest contains: campaigns completed this month,
       earnings this month and lifetime, profile completeness change,
       categories active in. Does NOT contain: recruiter message content,
       submission text or files, brand contact details.
     - Added by Prompt 8G: a "Challenge Submissions" line in the digest —
       challenges submitted this month, how many converted, and any
       conversion bonus earned. This exists because a parent who sees
       only "submitted to 4 challenges, 0 converted" without context may
       reasonably read that as unpaid labor rather than the speculative,
       no-obligation activity it is. Showing the conversion bonus when
       earned makes the compensation model visible, not just the effort.

6. Account controls:
     - POST /parent/account/suspend: immediately sets rep account_status
       to 'suspended'. Sends notification to rep. Admin is alerted.
       Reversible only by admin or parent via unsuspend.
     - POST /parent/account/unsuspend: reverses suspension if the original
       suspension was parent-initiated (not admin-initiated).

7. Parent portal frontend under apps/web/app/(parent)/:
     - Magic-link request screen (email entry only).
     - Dashboard showing rep summary.
     - Campaign approval queue with full brief, approve/block actions, and
       48-hour countdown.
     - Values filter configuration screen with plain-language descriptions
       of each filter category.
     - Settings panel: approval toggle (age-gated), digest toggle.
     - Account controls with confirmation dialogs.
     - A "what parents see" explainer panel — parents unfamiliar with the
       platform need context on what each section means, not just data.
     - Added by Prompt 8G: a "Challenge Submissions" section on the
       dashboard — separate from campaign activity — listing which
       challenges the rep submitted to, conversion status, and any
       conversion bonus earned. Parents need to see this before their
       child submits repeatedly to challenges that never convert, not
       only in the monthly digest.

8. Portal expiry at age 18: when a rep turns 18, portal_expires_at
   triggers (enforce at login, not just at account creation — add a check
   to the parent session verification step). Parent receives an email
   explaining the portal has closed because their child is now an adult.
   Existing parent_record is retained for audit but all active sessions
   are invalidated.

Acceptance criteria:
  - A parent cannot authenticate with an email not linked to a
    parent_record — and the endpoint does not confirm whether the email
    exists.
  - A campaign in a blocked category never appears in the rep's available-
    campaigns list — verified by seeding a blocked-category campaign and
    confirming it is absent from GET /reps/campaigns/available.
  - A campaign pending parent approval cannot be accepted by the rep —
    the accept endpoint returns a clear "awaiting parent approval" error,
    not a generic 403.
  - A parent blocking a campaign results in a neutral auto-decline to the
    brand that does not expose the parent's reason.
  - Portal login after the rep's 18th birthday returns a clear "portal
    has closed" message, not a generic auth error.
  - Monthly digest scheduled job runs against seeded data and produces
    a digest with no recruiter message content, no submission text, and
    no brand contact details in the output — verified by inspecting the
    generated email payload.
```

---

## 5. Rep Portal — Backend

**Depends on:** Prompt 4A (parent approval gate and values filter must
exist before campaign matching runs).

```
Implement the Rep backend routes from Section 8 ("Rep Routes") and the
Phase 1 feature set from Section 5 of Teenure_MVP_Gameplan.md.

Deliverables:
1. GET /reps/me, PUT /reps/me — profile read/update. PUT validates:
   categories against the centrally-defined allowed list (athletics,
   gaming, fashion, music, academics, food, beauty, tech), school_type
   against its enum (public/private/charter/homeschool, nullable),
   graduation_year within schema CHECK range. Rejects writes to cached/
   computed fields — those are server-computed only.
2. GET /reps/me/profile-preview — returns exactly what a brand or
   recruiter sees. Share the serializer with brand/recruiter-facing views
   — do not maintain two field lists that can drift.
3. GET /reps/campaigns/available — open campaigns where:
     - target_categories intersects rep's categories, AND
     - target_cities matches rep's city (if campaign specifies cities), AND
     - campaign category is NOT in the rep's parent values_filters (if a
       parent_record exists for this rep), AND
     - rep does not already have a campaign_reps row for this campaign.
   The values-filter exclusion is applied server-side here, not just in
   the parent portal — this is the enforcement point.
4. GET /reps/campaigns/active, GET /reps/campaigns/history.
5. GET /reps/earnings — pending/confirmed/paid breakdown from
   campaign_reps, not just the cached total.
6. Scope decision — rep-facing "recruiters interested" signal: not built
   at MVP. Deliberate cut pending a product decision on count-only vs.
   identity-revealing and whether credit is charged to appear.
7. POST /campaigns/:id/apply, /accept, /decline:
     - Before allowing accept: check parent_approval state if
       campaign_approval_required = TRUE for this rep. If parent has not
       yet approved, return 403 "awaiting parent approval" — not a generic
       error.
     - Enforce 48-hour deadline via scheduled job (extend the job from
       Prompt 3's runner to also auto-decline invitations where parent
       approval window has lapsed).
     - State-machine legality enforced — 409 on illegal transitions.
8. POST /campaigns/:id/submit — requires ftc_disclosure_accepted = TRUE
   on the campaign_reps row before allowing submission. This is the
   technical FTC enforcement — not a UI hint.
9. POST /campaigns/:id/withdraw — one-tap withdrawal from any campaign at
   any time, no penalty, no explanation required from the rep. Payout
   protection for work already submitted and confirmed. Surface this
   prominently in the UI (Prompt 6) — not buried in settings.
10. Profile completeness score: server-side function, recomputed on update.
    Define scoring rule explicitly (which fields, what weights) in code
    comments.
11. File upload via Supabase Storage: validate file type/size server-side,
    scoped so only the rep and relevant brand can read. Only accept uploads
    for campaigns the rep is actually invited to.
12. Living Achievement Link — GET /reps/me/achievement-link:
    Generates or retrieves a persistent, shareable verified profile URL
    for the rep. The URL is stable (does not change on profile updates)
    and resolves to a public-facing verified profile page that reflects
    the rep's current verified data in real time.

    Implementation:
      - Add achievement_link_token (text, unique, nullable) to
        rep_profiles. Generated once on first request, never regenerated
        (the same URL works forever so bookmarks and application
        submissions never break).
      - Token generation: a cryptographically random 32-character URL-
        safe string. Store the token, expose the full URL:
        https://teenure.com/verified/:token
      - The /verified/:token route is public — no authentication required
        to view it. This is intentional: a college admissions officer
        who receives the link must be able to open it without creating
        a Teenure account.
      - The public profile rendered at this URL shows only: display name,
        school, graduation year, city, categories, badges, campaigns
        completed count, average rating, total earnings (optional — rep
        controls whether earnings are shown via a toggle in profile
        settings), and a Teenure verification badge confirming the profile
        is real and verified. It does NOT show: Instagram/TikTok handles,
        submission content, recruiter messages, parent information, or
        any PII beyond what the rep has explicitly made public.
      - Add a verified_profile_public boolean to rep_profiles (default
        true when recruiter_visible = true, default false otherwise).
        The achievement link only resolves if verified_profile_public =
        true. If false, the URL returns a "this profile is not currently
        public" page — not a 404, because the rep may share the link
        before turning on visibility and should be able to explain what
        the recipient will see.
      - Add earnings_visible_on_public_profile boolean to rep_profiles
        (default false — earnings are opt-in for the public profile,
        always visible in the rep's own dashboard).
      - GET /reps/me/achievement-link returns the full URL, the token,
        and the current visibility settings so the rep can preview
        before sharing.

    RLS: the /verified/:token route bypasses RLS — it is a public
    endpoint. All other achievement link management endpoints require
    rep authentication. The public endpoint renders only from the
    verified_profile_public = true path — it cannot be used to access
    private profile data regardless of authentication state.

13. Goal Setting and Progress Tracking:
    Reps set personal achievement goals. The platform tracks progress
    and surfaces it in the dashboard.

    Schema addition (include in this migration or a separate one —
    document which):

    New table: rep_goals
      id (UUID PK)
      rep_id (FK to rep_profiles)
      goal_type (enum: 'campaigns_completed' | 'earnings_total' |
        'categories_active' | 'badges_earned' | 'profile_completeness')
      target_value (integer — the number to reach:
        campaigns_completed: 10 means "complete 10 campaigns"
        earnings_total: in cents, e.g. 50000 = "$500"
        categories_active: 3 means "campaigns in 3 different categories"
        badges_earned: 3 means "earn 3 badges"
        profile_completeness: 100 means "reach 100% completeness")
      target_date (date, nullable — optional deadline; null means
        "before graduation")
      current_value (integer default 0 — cached current progress,
        updated when the underlying metric changes)
      status (enum: 'active' | 'completed' | 'abandoned', default
        'active')
      completed_at (timestamptz, nullable)
      created_at (timestamptz default now())

    Constraints: maximum 3 active goals per rep at any time. A rep
    who wants a fourth goal must abandon one existing goal first.
    This limit is intentional — more than 3 goals dilutes focus and
    reduces the motivational impact of each.

    Endpoints:
    POST /reps/goals — create goal. Validates: goal_type is valid,
      target_value is positive and appropriate for the goal_type
      (earnings_total minimum $10 = 1000 cents, profile_completeness
      maximum 100), active goal count < 3.
    DELETE /reps/goals/:id — abandon goal (sets status → 'abandoned').
      Completed goals cannot be abandoned.
    GET /reps/goals — all active and recently completed goals with
      current_value, target_value, progress percentage, and projected
      completion date based on current pace.

    Progress update mechanism: extend the rep_profiles cached-field
    recompute (Prompt 2's trigger or service-layer mechanism) to also
    update rep_goals.current_value for all active goals belonging to
    the rep whenever the relevant underlying metric changes:
      - Campaign confirmed → update 'campaigns_completed' goals
      - Transfer paid → update 'earnings_total' goals
      - Campaign confirmed in a new category → update 'categories_active'
        goals (count distinct categories across confirmed campaigns)
      - Module passed → update 'badges_earned' goals
      - Profile completeness score changes → update
        'profile_completeness' goals

    Goal completion check: after each current_value update, if
    current_value >= target_value set status → 'completed', set
    completed_at. Notify the rep via email: "You hit your goal." No
    confetti, no points, no leaderboard — just a clean notification
    that real progress happened.

    GET /reps/goals/suggestions — returns suggested goals based on the
    rep's current profile state. Not personalized AI recommendations —
    simple rule-based suggestions:
      - If campaigns_completed < 5: suggest "Complete 5 campaigns"
      - If profile_completeness < 80: suggest "Reach 80% profile
        completeness"
      - If badges_earned = 0: suggest "Earn your first badge"
      - If categories_active < 2: suggest "Work in 2 categories"
    Suggestions exclude goal_types the rep already has an active goal
    for. Returns at most 3 suggestions. This endpoint is simple enough
    to be stateless — computed on request, not stored.

Acceptance criteria:
  - A campaign in a parent-blocked category never appears in available
    campaigns for that rep.
  - A rep cannot accept a campaign without parent approval when approval
    is required — returns distinct "awaiting parent approval" error.
  - Submission rejected if ftc_disclosure_accepted is not TRUE.
  - Rep cannot read/write another rep's campaign_reps rows.
  - Auto-decline job transitions expired invitations correctly, tested
    directly against the job function (not by waiting on a real clock).
  - Withdraw endpoint available and functional at any campaign status
    where withdrawal is meaningful.
  - Full pytest coverage of accept/decline/submit/withdraw state machine
    including illegal transitions.
```

---

## 6. Rep Portal — Frontend

**Depends on:** Prompt 5. Inbox UI (deliverable 6) depends on Prompt 11
backend. Build deliverables 1–5 and 7 first; stub inbox or defer until
Prompt 11 lands — state which you're doing.

**Retrofit: done (partial).** Auth pages (`/rep/login`, `/rep/signup`),
the dashboard, and the campaign detail page were retrofitted against
Section 0A alongside Prompt 9 — real design tokens, `RepShell`/
`AuthShell`/`CampaignBrief` shared components, semantic colors
replacing hardcoded `amber-*`/`emerald-*` classes, real button states.
Not yet retrofitted: the onboarding wizard, profile-preview, and inbox
screens — they inherit the new color/font tokens automatically (same
CSS variables, same `Card`/`Button`/`Badge` primitives) but haven't had
a layout pass with `RepShell`/`EmptyState`/`Skeleton`. Original note
preserved below for context (0A's own acceptance criterion:
"identify them as the same product from typography/color/spacing
alone").

**Known issue — login routes and gates need consolidation (not yet
fixed).** `/rep/login` (this prompt) and `/brand/login` (Prompt 9)
exist as separate pages under their respective route groups. That's a
misapplication of the route-group pattern: route groups organize code,
they shouldn't fragment a single auth surface into per-role URLs.
Signup genuinely differs by role (age gate + parental consent for
reps, business verification for brands, institution verification for
recruiters) and should stay split under `/signup/rep`,
`/signup/brand`, `/signup/recruiter`. Login does not — one set of
credentials, one page, role read from the account after
authentication. `/parent/auth` stays separate by design (magic-link,
not a credentials login) and `/admin` stays separate and should never
be reachable via role-detection fallthrough from the unified login.

The same copy-paste pattern exists one layer up: `(rep)/rep-gate.tsx`
and `(brand)/brand-gate.tsx` implement near-identical
loading/redirect/suspended-account-status logic, differing only in
`PUBLIC_PATHS` and the pending-state copy. This should collapse the
same way the login pages do — it's the same underlying mistake, not a
second one.

Required fix, to land before Recruiter Portal frontend (Prompt 12)
adds a third per-role login page and a third per-role gate,
compounding both:
- Collapse `/rep/login` and `/brand/login` into a single `/login`
  page reused by all roles (and by the recruiter login this prompt
  suite has not yet built).
- Collapse `RepGate` and `BrandGate` into one shared `useRoleGate`
  hook (or `<AuthGate roles={[...]} pendingState={...}>` component)
  parameterized by allowed roles, public paths, and pending-status
  copy — mirroring how the backend already does this correctly via
  `require_role(*roles)` in `app/core/security.py`, rather than one
  gate component per route group.
- Role-based redirect after auth must be resolved **server-side**
  from the authenticated session/DB record, never from a client-
  supplied redirect/role param — consistent with this spec's
  server-side-only rule for recruiter credit deduction and financial
  calculations (Section 9).
- Update `tests-e2e-auth/rep-signup-and-login.spec.ts` and the brand
  auth E2E suite to point at `/login` once consolidated.

Prompts 12 and 13 below each carry a one-line pointer back to this
fix so it isn't independently rediscovered (and re-duplicated) per
portal.

```
Build the Rep Portal under apps/web/app/(rep)/.

Mobile-first throughout — reps use this almost entirely on phones. Every
screen must be designed and verified at 375px before adapting to larger
viewports.

Deliverables:
1. Onboarding wizard: name, school, school_type (optional, with in-context
   explanation that it feeds only anonymized aggregate trend reports, never
   individual profile), graduation year, city, categories (multi-select),
   bio, Instagram/TikTok handles (display-only). Recruiter-visibility
   toggle defaults OFF with a clear explanation of what turning it on
   means.
2. Dashboard: available-campaigns panel, active-campaigns panel, earnings
   panel (pending/confirmed/lifetime), profile-completeness score with
   actionable field-specific prompts.
3. Campaign detail view: full brief, prohibited content, deliverables,
   timeline, payout amount, FTC disclosure checkbox (unchecked by default,
   explicit user action required — no pre-checked boxes), accept/decline
   with 48-hour countdown. If parent approval is pending, show a clear
   "waiting on a parent's approval" state rather than accept/decline
   actions.
4. Submission interface: text + file upload, client-side validation
   mirroring server-side checks, status tracker (submitted → under review
   → confirmed → paid).
5. Profile preview mode — renders from the same endpoint/serializer a
   brand or recruiter sees.
6. Inbox: read-only list of recruiter messages. Renders message text and
   sender institution name only. No reply box, no reply button, no compose
   affordance. Marks message read on open via POST /reps/inbox/:id/read.
7. Prominent one-tap withdraw button on every active campaign — not buried
   in settings. No confirmation dialog required (withdrawal is frictionless
   by design per Section 9's safety requirements).
8. Section 1A enforcement in frontend: no UI for messaging another rep,
   browsing other rep profiles, or posting outside a campaign submission
   context. These are structural absences, not disabled buttons.
9. Achievement Link sharing UI:
   - In the profile preview screen: a "Share your verified profile"
     section showing the achievement link URL with a copy button and
     a QR code (generated client-side from the URL — no server
     dependency). One toggle for earnings visibility. One toggle for
     public profile on/off.
   - A preview of exactly what the public link shows before the rep
     turns it on. "This is what a college admissions officer sees when
     they open your link."
   - The public /verified/:token page: clean, professional, Teenure-
     branded. Not a marketing page — a credential document. Shows the
     rep's verified data with a clear "Verified by Teenure" mark and
     the date last updated. No CTAs to sign up, no navigation to the
     app — this page exists for the person receiving the link, not for
     converting them to a Teenure user. Keep it focused.
10. Goal setting UI:
    - Goals panel on the dashboard: current active goals with progress
      bars, current value versus target value, projected completion at
      current pace.
    - Add goal flow: goal type selector (plain language labels, not
      enum values — "Complete X campaigns" not "campaigns_completed"),
      target value input with sensible defaults and input validation,
      optional target date.
    - Suggestions panel: "Goals to consider" showing the rule-based
      suggestions from GET /reps/goals/suggestions. One-tap to add a
      suggested goal.
    - Goal completion notification: when a goal completes, the dashboard
      shows a completion state for that goal before it moves to the
      completed history. No animation, no points — a clean "Goal
      reached" state with the completed goal details.
    - The 3-goal limit is communicated proactively: when a rep has 3
      active goals, the "add goal" action is replaced with "Manage
      your goals to add a new one" with a link to abandon an existing
      goal. Never a silent rejection.
11. Mobile-first verification for all new surfaces:
    Every screen added in deliverables 9 and 10 must pass the same
    375px viewport check required for the original Prompt 6 deliverables.
    The achievement link QR code must be large enough to scan on a
    phone screen. The goals panel must render without truncation on a
    375px viewport. This is not a new requirement — it is the existing
    mobile-first requirement applied explicitly to the new deliverables
    so it is not overlooked.

**Also depends on (added by Prompts 8G/8H):** Prompt 8G (Skill
Challenges) adds a challenge-discovery panel, pre-submission disclosure,
and challenge-submission UI to this portal; Prompt 8H (Learning Modules
and Verified Badges) adds a learning hub, pre-module disclosure, module
experience, and badge display. Both add a line item to the dashboard
earnings panel — conversion bonus earnings (8G) shown distinctly from
campaign earnings, and module completions are called out as unpaid in
context so the earnings panel is never misread as incomplete. See those
prompts' "Frontend additions" sections — apply them alongside
deliverables 1–11 above.

Acceptance criteria:
  - Under-16 pending parental consent → "waiting on your parent" state,
    not the dashboard.
  - FTC checkbox cannot be bypassed client-side or server-side.
  - Campaign with pending parent approval shows waiting state, not
    accept/decline.
  - Full walkthrough: signup → onboarding → view available campaign →
    accept → submit → status update, against locally seeded campaign.
  - Every screen verified at 375px: no horizontal scroll, no truncated
    interactive elements, no tap targets below touch-friendly minimum.
```

---

## 6A. Demo Mode — Rep Demo

**Depends on:** Prompt 6. Rep-side only — recruiter demo deferred to
Prompt 12A after the real Recruiter Portal exists.

```
Build the interactive rep demo at apps/web/app/(marketing)/demo/rep/.

First, populate /demo with a rep-side seed dataset. Every demo rep must
be unmistakably fictional — invented names, invented schools, no resemblance
to a real person. Use the real profile schema and completeness-scoring
logic from Prompt 5 so profiles actually score as complete. Include one
available campaign from a realistic-sounding fictional brand, and one
submitted/confirmed campaign with mock submission evidence using the real
campaign state machine. No multi-year earnings history yet — that gets
added in Prompt 12A if needed.

Then build the demo screen:
1. Fully interactive, no authenticated session required. Read-only against
   seed data — mutates nothing server-side.
2. Shows complete senior profile, available campaign, confirmed campaign,
   earnings panel.
3. Single CTA on every screen: "Start building yours" → real age-gated
   signup flow from Prompt 4. This demo must not create any shortcut
   around age gating or parental consent.

No signup wall between a visitor and the demo — parents and prospective
reps must explore fully before hitting any prompt.

Acceptance criteria:
  - Works with no authenticated session, mutates nothing.
  - No real user data reachable from demo routes.
  - Every demo record obviously synthetic on inspection.
  - "Start building yours" routes into the real age-gated signup flow —
    cannot reach an active rep account without passing through Prompt 4's
    flow.
```

---

## 7. Stripe Foundation: Connect Onboarding & Platform Billing — **implemented**

**Depends on:** Prompt 4. Can run parallel to Prompts 5–6.

**Build-log note:** All 5 deliverables implemented. `stripe_service.py`
now implements `create_customer`, `create_connect_account`,
`create_connect_onboarding_link`, and `verify_webhook_signature`
(checkout/transfer/refund remain `NotImplementedError` stubs, correctly
scoped to Prompt 10). `rep_profiles` gained `stripe_account_id` +
`stripe_onboarding_complete` columns (migration
`20260814090000_stripe_connect_columns.sql`). New endpoint
`POST /reps/stripe/onboarding` creates-or-resumes Connect onboarding.
New `POST /webhooks/stripe` verifies signatures before any dispatch and
implements `account.updated`; every other Section 8 event is a
registered no-op stub returning 200 so Stripe doesn't retry before its
owning prompt lands. `docs/stripe-minors-policy.md` researched against
Stripe's actual primary sources (not the SEO content-farm sites a plain
search surfaces) and linked from the README, per the acceptance
criteria.

**Flagged for human/legal review before real (non-test-mode) Connect
payouts go live for any rep under 18** — see
`docs/stripe-minors-policy.md`'s last section: Teenure's own age gate
(parental consent under 16) is narrower than Stripe's Representative
requirement (applies to everyone under 18), which is a real product gap
for 16-17-year-old reps with no parent otherwise involved in their
account. The gameplan's own "parent-as-payee fallback" note is the
likely direction but is not implemented in this prompt — it needs a
product decision and legal sign-off, not a guess.

14 new tests in `tests/test_stripe.py` (service-level Stripe SDK call
shape, onboarding create-vs-resume, webhook signature
verification/rejection, `account.updated` handling). All 93 backend
tests pass.

```
Implement the Stripe integration foundation. Covers account creation and
onboarding only — charges and payouts wire up in Prompt 10.

Deliverables:
1. stripe_service.py: implement create_customer (brands, recruiter billing)
   and create_connected_account (reps).
2. Research and document Stripe's current policy on Connected Accounts for
   under-18 individuals. Produce docs/stripe-minors-policy.md covering:
   what Stripe currently allows for minors, whether a parent-as-payee
   fallback is needed, which Connect account type fits. Do not guess —
   cite findings and flag anything requiring human (legal/Stripe support)
   confirmation before launch.
3. Rep Connect onboarding endpoint: creates or resumes onboarding link,
   stores resulting account ID on rep_profiles (add stripe_account_id
   column — flag as schema addition beyond Section 7, justified because
   payouts require it).
4. Brand Stripe Customer creation: service function ready for admin
   approval flow (Prompt 13).
5. Webhook endpoint scaffold: POST /webhooks/stripe, signature verified
   against STRIPE_WEBHOOK_SECRET, dispatch table for all Section 8 events.
   Implement account.updated now; leave payment_intent.* and transfer.*
   as stubs for Prompt 10; leave customer.subscription.* as stubs for
   Prompt 11.

Acceptance criteria:
  - Invalid webhook signature rejected before any business logic runs.
  - Rep can complete test-mode Connect onboarding end-to-end; platform
    records account ID and onboarding-complete status.
  - Minors-policy decision doc exists and is linked from README.
```

---

## 8. Brand Portal — Backend — **implemented**

**Depends on:** Prompt 5, Prompt 7.

**Build-log note:** All 10 deliverables implemented (`app/routers/brands.py`,
`app/repositories/brand_profiles_repository.py`, `app/services/campaign_service.py`
for the fee-split math, `app/core/crypto.py` for Fernet-based EIN
encryption at rest). No schema migration needed -- every column Prompt
8 touches already existed in Section 7's verbatim schema.

Two real, pre-existing bugs were found and fixed while building this,
unrelated to Prompt 8's own deliverables but directly in the code path
this prompt extends:

1. `campaign_reps_repository.py` had every rep-participation function
   (`CampaignRep`, `create_application`, accept/decline/submit/withdraw,
   `list_active_for_rep`, `list_history_for_rep`, `earnings_breakdown`,
   `auto_decline_expired_parent_approvals`) defined **twice** -- the
   entire first block (parent-facing helpers aside) was dead code,
   silently shadowed by a second block with the same names. One
   function's behavior genuinely differed between the two versions:
   the live `auto_decline_expired_parent_approvals` left
   `parent_approval_status` at `'pending'` after auto-declining an
   expired invitation, which kept it surfacing forever in the parent's
   pending-approval queue and would let a parent later "approve" an
   already-terminal, auto-declined invitation. Fixed by deleting the
   dead block and setting `parent_approval_status = 'blocked'` in the
   one that remains, matching `block_campaign`'s existing semantics.
   New regression test added.
2. `parent_service.send_campaign_approval_request` existed, was fully
   implemented, and was documented as "called by Prompt 5 when a rep is
   invited/matched to a campaign" -- but nothing ever called it. A
   parent whose approval was required got no notification that
   anything was waiting on them. Fixed in both `POST /campaigns/:id/apply`
   (rep self-apply) and the new brand-invite endpoint, which now share
   a single `determine_parent_approval` helper rather than each
   re-deriving the same decision independently (the exact shape of
   mistake that caused bug #1). New regression tests added for both
   paths (email sent when required, not sent when not required).

Interpretive decisions made and documented rather than guessed past:
- `GET /brands/campaigns/:id/reps/browse`'s exact no-PII field set
  isn't specified in Section 8 -- documented in
  `rep_profiles_repository.RepBrowseCard`'s docstring (excludes
  display_name, school_name, bio, handles; includes city/state/
  categories/school_type/completeness/rating).
- Campaign cancellation refund policy is explicitly unresolved --
  `docs/campaign-cancellation-refund-policy.md` states the open
  question per the deliverable's own instruction not to assume; the
  endpoint transitions status and reports `refund_pending` without
  calling the still-`NotImplementedError` Stripe refund stub.
- Invite-time capacity enforcement uses a live COUNT of non-declined
  `campaign_reps` rows, not the `reps_accepted_count` cache column,
  which nothing in this codebase currently increments (flagged in
  `brands.py`'s invite endpoint, not silently fixed -- out of this
  prompt's stated deliverables).

44 new tests (`test_brands_portal.py`, `test_campaign_service.py`, plus
2 new regression tests in `test_reps_portal.py` for the bugs above).
All 139 backend tests pass. Verified end-to-end against the real local
Supabase stack: brand signup → profile creation with real EIN
encryption confirmed at the DB layer → campaign creation with correct
server-side fee split.

```
Implement Brand backend routes from Section 8 and Phase 2 of Section 5.

Deliverables:
1. GET/PUT /brands/me — profile including EIN encrypted at rest (implement
   now, not deferred — Section 7 flags this explicitly).
2. Campaign CRUD: GET /brands/campaigns, POST /brands/campaigns,
   GET/PUT /brands/campaigns/:id. PUT legal only in 'draft' status → 409
   otherwise.
3. Server-side fee-split at campaign creation: platform_fee_cents and
   rep_pool_cents from budget_cents using STRIPE_PLATFORM_FEE_PERCENT from
   config (never hardcoded). payout_per_rep_cents = rep_pool_cents /
   max_reps. Never accept these as client input.
4. POST /brands/campaigns/:id/activate — validates brief complete, start
   date in future, max_reps > 0. Transitions 'draft' → 'pending_payment'
   and kicks off PaymentIntent.
5. POST /brands/campaigns/:id/retry-payment — legal only from
   'payment_failed'. Creates a new PaymentIntent (do not reuse failed one),
   stores new ID, transitions 'payment_failed' → 'pending_payment'. Calling
   /activate on a 'payment_failed' campaign returns a clear "use
   retry-payment" error. Calling /retry-payment on any other status
   returns 409.
6. POST /brands/campaigns/:id/pause, /cancel — cancel triggers refund
   logic. State the refund policy explicitly (full refund if no reps have
   submitted? partial for reps mid-campaign?) and flag it as a business
   decision requiring confirmation — do not assume.
7. Rep discovery: GET .../reps/browse (no PII at browse stage),
   POST .../reps/invite.
8. Submission review: GET .../reps/:rep_id/submission,
   POST .../reps/:rep_id/confirm (stubs payout engine, Prompt 10 wires it),
   POST .../reps/:rep_id/revision.
9. POST .../reps/:rep_id/rate — 1–5 stars, write-once, legal only after
   confirmation. No PUT/PATCH route for ratings.
10. Billing history: Stripe-hosted receipt URLs, not reimplemented invoices.

Acceptance criteria:
  - Cannot activate with missing brief fields, invalid dates, max_reps ≤ 0.
  - Cannot edit a campaign that has left 'draft'.
  - Fee-split unit tests cover rounding edge cases; rep_pool_cents +
    platform_fee_cents always equals budget_cents.
  - Browse endpoints never return PII — verified by inspecting response
    payloads.
  - /activate on 'payment_failed' → clear "use retry-payment" error.
  - /retry-payment on non-'payment_failed' → 409.
  - Successful retry produces a new stripe_payment_intent_id distinct from
    the failed one.
```

---

## 8B. Performance Milestone Payments

**Depends on:** Prompt 8, Prompt 10 (the existing flat payout engine
must be fully operational before the milestone layer is added on top of
it — this prompt extends the payout engine, it does not replace it).
Positioned here, immediately after Prompt 8, purely for narrative
grouping with the rest of the campaign-payment-model prompts (8B–8F) —
its actual dependency on Prompt 10 means it cannot be built until Prompt
10 is complete, regardless of numbering. Do not build 8B before 10.

**Replaces:** A previously drafted Prompt 8B (Featured Campaign
Placement). That draft was fully reverted before any of its code was
committed — no schema, endpoints, or feature flag exist for it in this
codebase. If a future session finds featured-placement code already
shipped from some other source, disable it via feature flag rather than
deleting it, but as of this revision there is nothing to disable.

**What this prompt is not:** A replacement for flat campaigns. Milestone
payments are an optional campaign type that coexists with the existing
flat payment model. Every decision in this prompt is made to preserve
full backward compatibility with flat campaigns. A builder who reads
only Prompts 1–10 and ignores this prompt should still have a fully
functional platform — this prompt adds capability, it does not change
what already works.

```
Implement performance milestone payments — a campaign payment type where
brands structure compensation as a series of milestone-triggered releases
rather than a single flat payout at confirmation. This aligns brand spend
with documented outcomes, not just content delivery, and is the most
structurally differentiated feature Teenure can offer relative to any
existing influencer or campus ambassador platform.

The thesis behind this feature: paying for posts is a commodity. Paying
for documented outcomes — a peer referral used, a product purchased by
someone the rep introduced, a survey completed by documented peers — is
something no current platform does for this demographic at verified scale.
Milestone payments are the technical expression of that thesis.

---

SCHEMA ADDITIONS (new migration, separately numbered from Prompt 2):

1. Add to campaigns table:
     payment_type (enum: 'flat' | 'milestone', default 'flat' — existing
       campaigns are unaffected, new campaigns choose at creation)

   Note: payment_type is immutable after campaign activation. A brand
   cannot switch a live campaign from flat to milestone or vice versa.
   Enforce this at the API layer with a clear error: "Payment type cannot
   be changed after campaign activation."

2. New table: campaign_milestones
     id (UUID PK)
     campaign_id (FK to campaigns, not nullable)
     milestone_number (integer — ordering within the campaign, 1-based)
     title (text not null — shown to rep: "Post delivered", "Referral
       code used 10 times", "Survey completed by 5 peers")
     description (text — plain language explanation of what constitutes
       completion of this milestone)
     verification_method (enum: 'brand_confirmation' | 'rep_submission' —
       how completion is verified; see verification mechanics below.
       'code_redemption' is deliberately excluded from this prompt — see
       the note at the end of the verification mechanics section)
     payout_percentage (integer — percentage of rep_pool_cents this
       milestone releases, 1–100; all milestones for a campaign must
       sum to exactly 100, enforced at campaign creation)
     sequence_required (boolean default true — if true, this milestone
       cannot be confirmed until all prior milestones are confirmed)
     created_at (timestamptz default now())

   RLS: brands can read/write milestones only for their own campaigns.
   Reps can read milestones for campaigns they are invited to. No direct
   write access for reps.

3. Add to campaign_reps table:
     milestones_completed_count (integer default 0 — cached count,
       recomputed on each milestone confirmation)
     total_milestone_payout_cents (integer default 0 — cumulative payout
       released across all confirmed milestones for this rep on this
       campaign; must never exceed payout_per_rep_cents)

4. New table: campaign_rep_milestones
     id (UUID PK)
     campaign_rep_id (FK to campaign_reps)
     campaign_milestone_id (FK to campaign_milestones)
     status (enum: 'pending' | 'submitted' | 'confirmed' | 'paid',
       default 'pending')
     rep_submission_text (text, nullable — rep's submission evidence for
       this milestone)
     rep_submission_file_urls (text[], default '{}')
     brand_confirmation_note (text, nullable)
     payout_cents (integer, nullable — calculated at confirmation:
       campaign_milestone.payout_percentage / 100 *
       campaign_reps.payout_per_rep_cents, rounded down, with any
       rounding remainder added to the final milestone)
     stripe_transfer_id (text, nullable)
     payout_status (enum: 'pending' | 'processing' | 'paid' | 'failed',
       default 'pending')
     dispute_flag (boolean default false — see deliverable 7)
     submitted_at (timestamptz, nullable)
     confirmed_at (timestamptz, nullable)
     paid_at (timestamptz, nullable)

   RLS: a rep can read/write only their own campaign_rep_milestones rows.
   A brand can read/write only rows for campaign_reps belonging to their
   campaigns.

   UNIQUE constraint: (campaign_rep_id, campaign_milestone_id) — one row
   per rep per milestone per campaign.

5. Add index:
     idx_campaign_rep_milestones_status on
       campaign_rep_milestones(campaign_rep_id, status)
     idx_campaign_milestones_campaign on campaign_milestones(campaign_id,
       milestone_number)

---

VERIFICATION MECHANICS:

Two verification methods are supported at MVP. The method is set per
milestone at campaign creation and determines what the confirmation flow
looks like for that milestone.

'brand_confirmation': the brand manually reviews rep-submitted evidence
and confirms the milestone. This is the simplest method and works for
any deliverable — a post, an event appearance, a piece of content. The
brand sees the rep's submission and clicks confirm. Identical in flow to
the existing flat campaign confirmation, applied per milestone.

'rep_submission': the milestone is considered submitted when the rep
submits evidence via the milestone submission interface. No separate brand
confirmation step — the submission itself triggers the payout. Use for
milestones where the evidence is self-verifying (a screenshot of a
published post, a link to a video). Requires a brief review window
(24 hours) during which the brand can dispute before payout releases.
If no dispute within the review window, payout releases automatically.
Build the auto-release into the scheduled job runner from Prompt 3.

Note on scope: an earlier draft of this prompt included a third method,
'code_redemption' (paying out when a brand-issued referral/promo code
hit a redemption threshold, confirmed manually since the platform has no
real integration with brand redemption-tracking systems at MVP). It has
been removed from this prompt entirely, for two reasons. First, without
real tracking infrastructure it was brand-manual in exactly the same way
'brand_confirmation' already is — it added a schema/UX distinction with
no functional difference. Second, and more importantly: it was the only
verification method in this prompt where a rep could do everything asked
of them and still not get paid, because the outcome depended on a third
party's behavior (whether a peer redeemed the code), not the rep's own.
Both 'brand_confirmation' and 'rep_submission' only ever pay for
something the rep directly did — every milestone in this prompt's scope
is fully within the rep's control. Outcome-linked, third-party-contingent
verification (via real e-commerce integration or a platform-issued
tracked short link, not brand-manual confirmation) is deferred to a
separate future prompt, to be written once that tracking infrastructure
actually exists. Do not add 'code_redemption' back into this prompt's
scope without that infrastructure and without re-deriving the UX
safeguards a genuinely contingent payout requires (see the rep portal
additions below).

---

BACKEND DELIVERABLES:

1. Campaign creation (extend Prompt 8's POST /brands/campaigns):
   When payment_type = 'milestone', require a milestones array in the
   request body:
     milestones: [
       {
         milestone_number: 1,
         title: "Post delivered",
         description: "Publish one Instagram post featuring the product
           with #ad disclosure and submit the link here.",
         verification_method: "brand_confirmation",
         payout_percentage: 30,
         sequence_required: true
       },
       {
         milestone_number: 2,
         title: "Story follow-up",
         description: "Publish one Instagram Story within 7 days of
           the post.",
         verification_method: "rep_submission",
         payout_percentage: 30,
         sequence_required: true
       },
       {
         milestone_number: 3,
         title: "Bonus content",
         description: "Publish one additional piece of content of your
           choice (Reel, TikTok, or blog post) featuring the product.",
         verification_method: "rep_submission",
         payout_percentage: 40,
         sequence_required: false
       }
     ]

   Server-side validation at campaign creation:
     - milestones array required when payment_type = 'milestone'
     - minimum 2 milestones, maximum 5 milestones per campaign
     - payout_percentage values must sum to exactly 100 (reject if the
       brand submits percentages that sum to 99 or 101 — do not silently
       adjust; return a clear validation error)
     - milestone_number values must be sequential starting from 1
     - at least one milestone must have sequence_required = true
     - milestones with sequence_required = false may only appear after
       all sequence_required milestones (i.e., non-sequential milestones
       are always the final milestone(s) in a campaign — this prevents
       a brand from making a foundational milestone non-sequential)

   When payment_type = 'flat', milestones array must be absent or empty.
   Create campaign_milestone rows atomically with the campaign in a
   single database transaction. If milestone creation fails, roll back
   the campaign creation.

2. campaign_rep_milestones initialization: when a rep accepts a campaign
   invitation (POST /campaigns/:id/accept), create campaign_rep_milestones
   rows for every milestone in the campaign — one row per milestone per
   rep, all initialized to status 'pending'. This creation is atomic with
   the accept action. If any milestone row fails to create, roll back the
   accept.

3. GET /reps/campaigns/active (extend Prompt 5): for milestone campaigns,
   include the milestone list with each active campaign, showing each
   milestone's title, description, payout_percentage, status for this rep,
   and whether it is currently actionable (sequence_required milestone
   where all prior milestones are confirmed, or a non-sequential milestone).
   A rep should never be confused about which milestone they are working on.

4. Milestone submission (new endpoint):
   POST /campaigns/:campaign_id/milestones/:milestone_id/submit
     - Validates the campaign_rep exists and is in 'accepted' status
     - Validates the milestone is actionable for this rep (sequence check)
     - Writes rep_submission_text and rep_submission_file_urls
     - Sets status 'pending' → 'submitted', sets submitted_at
     - For 'rep_submission' milestones: schedules auto-release after 24
       hours via the Prompt 3 runner (see deliverable 6 below)
     - For 'brand_confirmation' milestones: notifies brand via email that
       a milestone submission is awaiting their review

5. Milestone confirmation (new endpoint):
   POST /campaigns/:campaign_id/reps/:rep_id/milestones/:milestone_id/confirm
     - Brand-only route
     - Validates the milestone status is 'submitted'
     - Sets status → 'confirmed', sets confirmed_at
     - Calculates payout_cents: (payout_percentage / 100) *
       payout_per_rep_cents, rounded down. For the final milestone,
       add any rounding remainder so total_milestone_payout_cents across
       all milestones equals exactly payout_per_rep_cents. Never let
       rounding silently reduce or increase total rep earnings.
     - Calls payout_service.release_milestone_payout(campaign_rep_milestone_id)
       — a new function in payout_service that validates the milestone
       row, checks the rep's Stripe Connect account is complete, and
       creates a Transfer for payout_cents. This is the per-milestone
       equivalent of the flat release_payout function from Prompt 10.
     - Updates campaign_rep_milestones.milestones_completed_count and
       total_milestone_payout_cents on the parent campaign_reps row
     - After the final milestone is confirmed: update campaign_reps.status
       to 'confirmed' (matching flat campaign behavior) so the rating flow
       and overall campaign status logic from Prompt 10 still work without
       modification. The campaign_reps row status transitions the same way
       regardless of payment type — the milestone layer sits below it.

6. Auto-release scheduled job (extend Prompt 3 runner):
   New job: milestone_auto_release — runs every 30 minutes. Finds
   campaign_rep_milestones rows where:
     - verification_method = 'rep_submission'
     - status = 'submitted'
     - submitted_at < now() - interval '24 hours'
     - dispute_flag = false
   For each: call payout_service.release_milestone_payout() and set
   status → 'confirmed'. Idempotent — a row that was already confirmed
   is skipped without error. Log every auto-release for admin audit.

7. Milestone dispute (new endpoint):
   POST /campaigns/:campaign_id/reps/:rep_id/milestones/:milestone_id/dispute
     - Brand-only route
     - Legal only within 24 hours of the rep's submission (the auto-
       release window)
     - Sets dispute_flag = true on the campaign_rep_milestone row (see
       the migration's own dispute_flag column in the schema addition
       above — do not add it in a second migration)
     - Pauses the auto-release job for this row
     - Notifies the rep via email that the brand has flagged this
       milestone for review
     - Creates an admin queue entry for manual resolution — milestone
       disputes are a new category in the admin queue from Prompt 13,
       distinct from campaign disputes (which cover the whole campaign)
       and payment disputes (which cover stuck transfers)
   Resolution: admin reviews the dispute, views the rep's submission
   evidence, and either confirms (triggering payout) or declines
   (setting the milestone back to 'submitted' status, notifying both
   parties). Do not build a self-serve dispute resolution between brand
   and rep — all disputes go through admin at MVP.

8. payout_service.py additions:
   release_milestone_payout(campaign_rep_milestone_id):
     - Validates the milestone row is in 'confirmed' status with a
       non-null payout_cents
     - Validates the parent campaign_rep's rep has a completed Stripe
       Connect account
     - Creates a Stripe Transfer for payout_cents with metadata:
       payment_type: 'milestone', milestone_id: ..., campaign_rep_id: ...
     - Sets payout_status → 'processing', stores stripe_transfer_id
     - Idempotent — a milestone row with an existing stripe_transfer_id
       is a no-op, not a duplicate transfer

9. Stripe webhook additions (extend Prompt 10's handler):
   transfer.paid where metadata.payment_type = 'milestone':
     → campaign_rep_milestones.payout_status → 'paid', set paid_at
     → update campaign_reps.total_milestone_payout_cents
     → update rep_profiles cached total_earnings_cents (same mechanism
        as Prompt 10's flat campaign recompute)
   transfer.failed where metadata.payment_type = 'milestone':
     → alert admin, flag milestone row for manual review
     → same admin queue surfacing as flat campaign transfer failures
   Distinguish by metadata.payment_type — do not change the flat
   campaign webhook handlers. If metadata.payment_type is absent,
   treat as flat (backward compatible with all existing transfers).
   Metadata is a stripe.StripeObject on a real signed webhook, not a
   plain dict — use `"payment_type" in metadata` / item access, not
   `.get()` (see the existing `_handle_account_updated` handler's own
   documented note on this).

10. GET /reps/earnings (extend Prompt 5):
    For milestone campaigns, the earnings breakdown must show milestone-
    level detail: which milestones are pending, which are paid, what
    amount each released. The rep must be able to see at a glance what
    they have earned and what remains achievable in each active campaign.
    Aggregate to the campaign level for the summary totals but expose
    milestone-level detail in the campaign earnings breakdown.

11. Brand billing and reporting:
    For milestone campaigns, the brand's campaign spend view (Prompt 8,
    deliverable 10) shows milestone-level payout history: which milestone
    was confirmed, when, which rep, and what amount was transferred. This
    view is the brand's proof that they paid for documented outcomes, not
    just content delivery. It is a significant trust signal for brands
    and a reporting tool for their own marketing attribution.

---

FRONTEND ADDITIONS:

These additions belong in Prompt 9 (Brand Portal Frontend) and Prompt 6
(Rep Portal Frontend). Document them here so the builders of those
prompts know what to add.

Brand portal additions (Prompt 9):
  - Brief builder step addition: if payment_type = 'milestone', show a
    milestone builder with add/remove milestone controls, title/description
    fields, verification method selector, and a live payout percentage
    calculator that shows remaining percentage as milestones are added.
    The calculator must show a clear error state when percentages do not
    sum to 100 before the brand can proceed.
  - Milestone submission review: each active campaign rep shows a milestone
    progress view — which milestones are pending, submitted, or confirmed
    per rep. Each submitted milestone shows the rep's evidence and a
    confirm/dispute action.
  - Dispute window indicator: for 'rep_submission' milestones, show a
    countdown to the 24-hour auto-release so brands know how long they
    have to review before the payout releases automatically.

Rep portal additions (Prompt 6):
  - Campaign detail view for milestone campaigns: show each milestone
    with its title, description, payout amount, current status, and
    whether it is currently actionable. A rep should never have to guess
    what they need to do next.
  - Milestone submission interface: per-milestone submission form (text
    + file upload) that mirrors the flat campaign submission interface
    from deliverable 4, applied per milestone rather than per campaign.
  - Earnings panel: milestone-level breakdown for active milestone
    campaigns. "You have earned $X of $Y available in this campaign.
    2 milestones remaining."
  - Status tracker per milestone: pending → submitted → confirmed → paid,
    same visual pattern as the flat campaign status tracker.

  UX guidance — framing and progress visibility: every milestone in this
  prompt's scope is something the rep directly does (a post, a story, a
  submission), so there is no externally-contingent payout to soften at
  MVP — do not use "guaranteed base + bonus" language here, since nothing
  is actually at risk from a third party's behavior. What still matters:
  a rep should always be able to see, at a glance, exactly what she has
  already earned (confirmed/paid milestones) versus what remains
  achievable through her own further effort (pending/actionable
  milestones) — never a single blended total that obscures which part is
  locked in. Where a milestone involves a count or threshold the rep
  controls directly (e.g. "publish 3 pieces of content"), show real-time
  progress toward it ("2 of 3 published") rather than a flat pending/done
  state, so the milestone reads as trackable effort in progress, not a
  black box. This visibility pattern — earned vs. achievable, real-time
  progress toward thresholds — is a hard requirement to carry forward
  into the future outcome-linked verification prompt referenced above:
  once a milestone's payout genuinely depends on someone else's behavior,
  this same panel must also distinguish "guaranteed for what you already
  did" from "possible bonus outside your control," which is not a
  distinction this prompt's milestones need to make.

---

ACCEPTANCE CRITERIA:

Schema and data integrity:
  - A milestone campaign with percentages summing to 99 or 101 is
    rejected at creation with a clear validation error. Never silently
    adjusted.
  - campaign_rep_milestones rows are created atomically with campaign_reps
    at accept. If any row fails, the accept is rolled back — a rep cannot
    be in an accepted state without a complete milestone record.
  - total_milestone_payout_cents across all confirmed milestones for a
    single campaign_rep never exceeds payout_per_rep_cents — verified by
    unit test covering the rounding calculation across multiple milestone
    percentage combinations including those that do not divide evenly.

State machine:
  - A sequence_required milestone cannot be confirmed before all prior
    milestones are confirmed — API returns 409 with a clear reason.
  - A non-sequential milestone can be confirmed independently of later
    milestones but not before all sequence_required milestones are
    confirmed.
  - A milestone in 'paid' status cannot be re-confirmed — idempotent
    no-op or clean 409, not a duplicate transfer.

Payout safety:
  - release_milestone_payout called twice for the same milestone produces
    exactly one Stripe Transfer — verified with a concurrency test
    matching the pattern from Prompt 11's credit deduction test.
  - transfer.paid webhook for a milestone transfer updates only the
    campaign_rep_milestones row and the rep's cached earnings — does not
    affect flat campaign payout state.
  - transfer.paid webhook for a flat campaign transfer does not affect
    campaign_rep_milestones rows.

Auto-release:
  - A 'rep_submission' milestone submitted 25 hours ago with no dispute
    flag is auto-released by the scheduled job — tested directly against
    the job function with a seeded row.
  - A 'rep_submission' milestone submitted 25 hours ago WITH a dispute
    flag is NOT auto-released — dispute flag correctly blocks auto-release.
  - Running the auto-release job twice against the same eligible row
    produces one transfer and one log entry.

Backward compatibility:
  - All existing flat campaign tests from Prompts 8, 9, and 10 pass
    without modification after this prompt is implemented. This is the
    single most important acceptance criterion: this prompt must not
    break anything that was already working.

Admin:
  - Milestone disputes appear in a distinct admin queue category separate
    from campaign-level disputes and payment disputes.
  - Admin resolution of a milestone dispute (confirm or decline) correctly
    triggers payout or resets status, verified by test.
```

LAUNCH GATE (not a pytest-verifiable acceptance criterion — do not try to
automate this):

Before milestone campaigns are enabled for the full rep network (even
though nothing in this prompt's scope is externally contingent), validate
the milestone framing itself — the language, the progress visibility, the
"earned vs. achievable" split — with a small cohort of real teenagers.
The thing to learn is whether staged, multi-step payout reads to a teen
as motivating and fair or as confusing/unfair relative to a single flat
payout for the same total amount. This matters more once the future
outcome-linked verification prompt ships (where a milestone genuinely can
depend on someone else's behavior), but the base framing patterns this
prompt establishes are what that prompt will build on, so get them right
here first. Findings from this test should shape the rep portal UI before
general release — this is a go/no-go product gate, not a code review
checklist item, and it blocks enabling milestone campaigns broadly even
if every automated acceptance criterion above passes.

---

## 8C. Category Exclusivity

**Depends on:** Prompt 8B (builds on stable campaign schema — not
strictly on the milestone layer itself, but sequenced after it per the
product roadmap this prompt suite follows).

**Status: not yet drafted.** A campaign-level attribute and new payment
surface — a brand can pay a premium for exclusive access to reps in a
target category/city for the campaign's duration, preventing a
competing brand's campaign from reaching the same reps in that
category. Full deliverables, schema, acceptance criteria, and
brand/rep-facing framing need to be specified in the same level of
detail as Prompt 8B before this is buildable. Do not build from this
one-line summary alone — treat it as a placeholder marking where this
prompt belongs in sequence, not as an instruction.

---

## 8D. Advance Cohort Reservation

**Depends on:** Prompt 8C (builds on stable campaign and milestone
foundations).

**Status: not yet drafted.** Introduces a pre-campaign reservation
state — a brand can reserve a cohort of reps (by category/city/size)
ahead of a campaign's actual brief being finalized, converting the
reservation into a real campaign later. Full deliverables, schema,
acceptance criteria, and the reservation-to-campaign conversion flow
need to be specified in the same level of detail as Prompt 8B before
this is buildable. Do not build from this one-line summary alone.

---

## 8E. Rep Syndicates

**Depends on:** Prompt 8D (builds on stable campaign lifecycle).

**Status: not yet drafted.** Introduces a new entity — a syndicate of
reps with its own profile and payout distribution — allowing a group of
reps to be booked and paid as a unit rather than individually. This is
the most structurally involved of the 8B–8F additions (new entity type,
new profile surface, new payout-splitting logic on top of the milestone
and flat payout engines) and needs its own full schema/deliverables/
acceptance-criteria pass, plus an explicit decision on how syndicate
payout splits interact with individual rep Stripe Connect accounts,
before this is buildable. Do not build from this one-line summary alone.

---

## 8F. Relationship Continuity Product (Year Two)

**Depends on:** Prompt 8E, and real longitudinal data from completed
multi-campaign rep histories.

**Status: deferred, placeholder only.** Do not build until sufficient
data exists to make the product credible rather than theoretical — per
the product rationale for this prompt, building it early against
synthetic or thin data would produce a feature nobody has evidence
justifies. Revisit this placeholder once Prompts 8B–8E have shipped and
enough real campaign history has accumulated to design it against actual
usage patterns rather than speculation.

---

## 8G. Skill Challenges

**Depends on:** Prompt 8 (Brand Portal backend — implemented), Prompt 5
(Rep Portal backend — implemented), Prompt 10 (Campaign Lifecycle &
Payout Engine — implemented, specifically Stripe Connect payout path
which this prompt extends for the conversion bonus).

**Also affects:** Prompt 9 (Brand Portal frontend — add challenge
management tab), Prompt 6 (Rep Portal frontend — add challenge discovery
panel and disclosure copy), Prompt 4A (Parent Portal — add challenge
activity to parent dashboard). Execute those additions when you reach
this prompt; do not defer them to a separate cleanup pass.

**Numbering note:** The builder named this 8G. The planning conversation
called it 8C. Both refer to the same feature. The suite document should
be updated to reflect 8G before this prompt is executed.

```
Implement skill challenges — an open, low-commitment submission surface
where brands post creative briefs that any matching rep can respond to
without a formal campaign relationship. Challenges are how brands
discover talent before committing campaign budget. For reps, challenges
are a way to build profile depth and earn potential campaign invitations
even before being directly approached by a brand.

THE FUNDAMENTAL DISTINCTION FROM CAMPAIGNS — enforce this everywhere:

  Campaigns: formal relationship, guaranteed payout, FTC disclosure
    required, parent approval required for under-16, rep is invited
    by the brand.
  Challenges: open audition, NO guaranteed payout, NO FTC disclosure
    (no compensation means no sponsored content), NO parent approval
    required (no financial transaction involving a minor), any matching
    rep can submit, brand discovers talent.

This distinction is the legal and safety architecture. A challenge that
offers compensation is a campaign and must use the full campaign flow.
A challenge that offers only the possibility of a future campaign
invitation is categorically different and subject to different rules.

The pre-challenge disclosure is NOT optional UI copy. It is a server-
enforced contract. A rep submitting via direct API call without seeing
the disclosure UI is still submitting to a system that never promised
payment. The schema and API response must make this explicit.

COMPENSATION DESIGN — read before building:

  Challenges are unpaid by design. However, when a brand converts a
  challenge submission to a campaign invitation, the platform pays a
  small conversion bonus to the rep from platform margin — not from
  the brand. This bonus signals that creative effort has real value
  and that the platform respects the rep's time even when they did
  not know upfront whether their work would convert.

  Conversion bonus amount: defined in config as
  CHALLENGE_CONVERSION_BONUS_CENTS (starting value: 750 cents = $7.50).
  This is a platform cost, not a brand charge. Document it as a rep
  acquisition cost — the platform spends $7.50 to convert a passive
  rep into an active campaign participant, which is a fraction of the
  cost of any other acquisition channel.

  All conversion bonuses flow through the existing Stripe Connect
  payout path from Prompt 10. No new payment infrastructure.

TEEN AND PARENT EXPECTATION MANAGEMENT:

  Some reps and parents will expect payment for challenge submissions.
  The platform handles this through radical transparency, not fine print:
    - The challenge submission flow states clearly before any work is
      done: "Challenges are unpaid. Brands use them to discover reps
      for paid campaigns. If a brand invites you to a campaign based
      on your submission, you receive a $7.50 discovery bonus from
      Teenure — but this is not guaranteed."
    - The parent portal shows all challenge activity and any conversion
      bonuses earned, so parents always know what their child submitted
      to and what they received.
    - Declined submissions are never shown to reps (protects confidence)
      but ARE shown in aggregate in the parent dashboard ("submitted to
      4 challenges, 1 converted, $7.50 earned") so parents have the
      full picture.

---

SCHEMA ADDITIONS (new migration, separately numbered from all prior
migrations — do not alter any existing migration file):

1. New table: challenges
     id (UUID PK default gen_random_uuid())
     brand_id (UUID not null references brand_profiles(id)
       on delete restrict)
     title (text not null)
     brief (text not null)
     category (text not null — must be a value from the centrally-
       defined category list in Prompt 5; enforce at API layer)
     target_cities (text[] not null default '{}' — empty array means
       all cities; non-empty means only reps in those cities)
     submission_format (text not null default 'both'
       check (submission_format in ('text', 'file', 'both')))
     submission_prompt (text not null — specific instruction to the rep:
       what to create, how long, what format)
     status (text not null default 'draft'
       check (status in ('draft', 'active', 'closed')))
     max_submissions (integer nullable — null means unlimited)
     submissions_count (integer not null default 0)
     opens_at (timestamptz nullable — null means immediately on activate)
     closes_at (timestamptz nullable — null means brand closes manually)
     conversion_count (integer not null default 0)
     created_at (timestamptz not null default now())
     updated_at (timestamptz not null default now())

2. New table: challenge_submissions
     id (UUID PK default gen_random_uuid())
     challenge_id (UUID not null references challenges(id)
       on delete restrict)
     rep_id (UUID not null references rep_profiles(id)
       on delete restrict)
     submission_text (text nullable)
     submission_file_urls (text[] not null default '{}')
     status (text not null default 'submitted'
       check (status in ('submitted', 'reviewed', 'converted',
       'declined')))
     brand_note (text nullable — internal only, never returned in any
       rep-facing endpoint response)
     converted_to_campaign_id (UUID nullable references campaigns(id))
     payout_cents (integer nullable — null until conversion; set to
       CHALLENGE_CONVERSION_BONUS_CENTS on convert action)
     payout_status (text nullable default null
       check (payout_status in (null, 'pending', 'processing',
       'paid', 'failed')))
     stripe_transfer_id (text nullable unique)
     submitted_at (timestamptz not null default now())
     reviewed_at (timestamptz nullable)
     converted_at (timestamptz nullable)
     paid_at (timestamptz nullable)
     UNIQUE (challenge_id, rep_id)

3. Add to rep_profiles:
     challenges_submitted_count (integer not null default 0)
     challenges_converted_count (integer not null default 0)
   These are cached counts updated on submission and conversion.
   The conversion rate (challenges_converted_count /
   challenges_submitted_count) is derived at the API layer — never
   stored separately, always computed from these two fields to avoid
   drift.

4. Indexes:
     CREATE INDEX idx_challenges_status_category
       ON challenges(status, category)
       WHERE status = 'active';
     CREATE INDEX idx_challenges_brand
       ON challenges(brand_id, status);
     CREATE INDEX idx_challenge_submissions_rep
       ON challenge_submissions(rep_id, status);
     CREATE INDEX idx_challenge_submissions_challenge
       ON challenge_submissions(challenge_id, status);
     CREATE INDEX idx_challenge_submissions_payout
       ON challenge_submissions(payout_status)
       WHERE payout_status IN ('pending', 'processing');

5. RLS policies:
     Enable RLS on both new tables before any application code touches
     them — this is the ground rule from the Master Context Prompt.

     challenges:
       Brands read and write only their own challenges (brand_id matches
       authenticated brand's brand_profiles.id). Reps read only active
       challenges (status = 'active'). No rep can read draft or closed
       challenges. Recruiters and parents have no direct table access.
       Admin uses service role.

     challenge_submissions:
       Reps read and write only their own rows (rep_id matches
       authenticated rep's rep_profiles.id). Brands read all submissions
       for challenges they own. Reps cannot read other reps' submissions
       under any circumstances — submissions are never public. Recruiters
       and parents have no direct table access. Admin uses service role.

     The brand_note column must never appear in any rep-facing serializer
     regardless of RLS — add this as an explicit serializer exclusion,
     not just an RLS trust.

---

BACKEND DELIVERABLES:

1. Config addition:
   Add CHALLENGE_CONVERSION_BONUS_CENTS to app/core/config.py, loaded
   from environment variables. Starting value: 750. Document in
   .env.example with comment: "Platform-funded bonus paid to a rep
   when their challenge submission converts to a campaign invitation.
   Funded from platform margin, not charged to brand."

2. Brand challenge management (new router: app/routers/challenges.py):

   POST /brands/challenges
     Creates a challenge in 'draft' status. Required fields: title,
     brief, category (validated against centrally-defined list),
     submission_format, submission_prompt. Optional: target_cities,
     max_submissions, opens_at, closes_at. Returns full challenge
     object. Brand must be in 'active' account_status.

   PUT /brands/challenges/:id
     Edit challenge. Legal only in 'draft' status — return 409 if
     status is 'active' or 'closed' with message: "Active challenges
     cannot be edited. Close this challenge and create a new one."
     Brands can update all fields while in draft.

   POST /brands/challenges/:id/activate
     Transitions 'draft' → 'active'. Validates: title, brief, category,
     submission_prompt all present and non-empty. Sets opens_at to
     now() if not specified. Challenges are free for brands at launch
     — no Stripe charge. Document this explicitly: challenges are a
     brand acquisition tool. Charging at launch reduces adoption. Pricing
     is introduced when value is demonstrated, not before.

   POST /brands/challenges/:id/close
     Transitions 'active' → 'closed'. Idempotent — closing an already-
     closed challenge returns the current state with a 200, not a 409.
     No submissions can be made against a closed challenge.

   GET /brands/challenges
     List all brand's challenges. Include per-challenge: submissions_count,
     conversion_count, derived conversion_rate, status, and
     closes_at countdown if applicable.

   GET /brands/challenges/:id/submissions
     All submissions for a brand's challenge. Returns per submission:
       - rep_id (opaque UUID only — brand cannot directly identify the
         rep from this field alone)
       - rep display_name, city, categories, profile_completeness_score,
         campaigns_completed, average_rating, challenges_converted_count,
         derived conversion_rate — this is the no-PII card for challenge
         context
       - submission_text and submission_file_urls
       - submitted_at, status (submitted/reviewed/converted — never
         'declined' in the brand's own view, that would be misleading;
         declined submissions show as 'reviewed' from the brand's list
         perspective — the decline was their action)
     Does NOT include: brand_note (that is internal server state),
     rep Instagram/TikTok handles, school name, date of birth, or any
     other PII not listed above.

     Full profile view: in the challenge submission context, a brand may
     view a rep's full profile (GET /reps/:id/profile — add this brand-
     facing endpoint if it does not already exist from Prompt 8's
     implementation) without spending a recruiter credit. The rep
     submitted voluntarily to the brand's challenge; the brand has
     implicit context to view their full profile. Document this decision
     explicitly so it does not conflict with the recruiter credit model:
     recruiter credit applies to cold discovery. Challenge submission
     is warm discovery — the rep initiated contact by submitting.

3. Brand submission review actions:

   POST /brands/challenges/:id/submissions/:submission_id/review
     Marks submission as reviewed. Accepts optional brand_note (internal
     only — never returned in any rep-facing endpoint). Sets status
     'submitted' → 'reviewed'. No rep notification. Reviewed is a brand-
     internal state for managing their inbox.

   POST /brands/challenges/:id/submissions/:submission_id/convert
     The key action. Converts a challenge submission into a campaign
     invitation. Required: campaign_id (must be an active campaign
     belonging to this brand). Process:
       a. Validate: challenge_submission exists, belongs to this brand's
          challenge, status is 'submitted' or 'reviewed' (not already
          'converted' or 'declined').
       b. Validate: campaign_id is active, belongs to this brand,
          has available rep slots (reps_accepted_count < max_reps).
       c. Create a campaign_reps invitation row for this rep on this
          campaign — status 'invited', invite_expires_at set per the
          standard 48-hour window. This invitation is identical in
          structure to a direct brand invitation from Prompt 8. The
          RLS policies from Prompt 2 must hold for this row — verify
          that a campaign_reps row created through this path is
          indistinguishable from one created through the normal
          invitation flow from the payout engine's perspective.
       d. Set challenge_submissions.status → 'converted'.
       e. Set converted_to_campaign_id, converted_at.
       f. Set payout_cents = CHALLENGE_CONVERSION_BONUS_CENTS from config.
       g. Set payout_status = 'pending'.
       h. Call payout_service.release_challenge_conversion_bonus(
          challenge_submission_id) — a new function in payout_service
          (see deliverable 5).
       i. Update challenges.conversion_count (+1).
       j. Update rep_profiles.challenges_converted_count (+1).
       k. Notify rep via email: "A brand loved your challenge submission
          and has invited you to a paid campaign. You've also earned a
          $7.50 discovery bonus from Teenure." The bonus amount should
          be formatted from CHALLENGE_CONVERSION_BONUS_CENTS, not
          hardcoded in the email template.
     All steps a–k must execute atomically in a database transaction.
     If any step fails, the entire conversion rolls back. A partially-
     converted submission is worse than a failed conversion.
     Idempotent: if called twice with the same submission_id, the second
     call returns the current converted state with 200, not a 500 or
     a duplicate payout.

   POST /brands/challenges/:id/submissions/:submission_id/decline
     Sets status → 'declined'. Idempotent. No rep notification —
     declined submissions are silently archived. Reps see their own
     submission status as 'submitted', 'reviewed', or 'converted' only.
     'declined' is never returned in any rep-facing endpoint. This is a
     deliberate UX decision: protecting rep confidence, especially for
     younger users who may internalize rejection disproportionately.

4. Rep challenge discovery and submission:

   GET /reps/challenges/available
     Active challenges where:
       - challenge.category intersects rep's categories (same logic as
         campaign matching from Prompt 5)
       - challenge.target_cities matches rep's city, OR target_cities
         is empty (all cities)
       - rep does not already have a challenge_submission row for this
         challenge (already submitted)
       - challenge is not closed and max_submissions has not been reached
         (submissions_count < max_submissions, or max_submissions is null)
     Does NOT apply parent values_filter — challenges are unpaid, do not
     involve a brand relationship, and do not require parent approval.
     However: if the rep is under 16 and parent campaign_approval_required
     is TRUE, challenges are still available — the approval gate is
     specific to paid campaigns. Document this decision.

   GET /reps/challenges/submitted
     Rep's own submission history. Returns: challenge title, category,
     submitted_at, status — but status mapping for rep-facing output:
       'submitted' → 'submitted'
       'reviewed' → 'submitted' (rep sees no difference between reviewed
         and unreviewed — this is intentional)
       'converted' → 'converted' (with campaign name and payout_cents)
       'declined' → never returned, row excluded from this endpoint
     If status is 'converted': include the campaign they were invited to
     (campaign title, payout_per_rep_cents) and the conversion bonus
     amount (payout_cents). This is the direct line from effort to
     outcome that makes challenges worth doing.

   POST /reps/challenges/:id/submit
     Creates a challenge_submission row. Process:
       a. Validate challenge is active.
       b. Validate max_submissions not exceeded.
       c. Validate rep has not already submitted (UNIQUE constraint will
          catch this, but return a clear error before hitting the
          constraint: "You have already submitted to this challenge").
       d. Validate submission content matches submission_format: if format
          is 'text', submission_text required and non-empty; if 'file',
          at least one submission_file_url required; if 'both', at least
          one of the two required.
       e. Record disclosure_acknowledged: the request body must include
          disclosure_acknowledged: true (boolean). If absent or false,
          return 400 with message: "Challenge disclosure acknowledgment
          required. Challenges are unpaid brand discovery tools. Your
          submission may result in a paid campaign invitation, but this
          is not guaranteed." This is the server-side enforcement of the
          pre-challenge disclosure — a rep who calls this endpoint via
          direct API without the disclosure UI must still acknowledge the
          terms, or the submission is rejected.
       f. Create challenge_submission row.
       g. Increment challenges.submissions_count (+1, atomic).
       h. Increment rep_profiles.challenges_submitted_count (+1).
       i. Return the created submission with status 'submitted'. Do not
          return an estimated response time or any implication that the
          brand will respond. Neutral confirmation only.

5. payout_service.py addition:

   release_challenge_conversion_bonus(challenge_submission_id: UUID):
     - Fetch the challenge_submission row. Validate:
         status = 'converted'
         payout_cents is not null and > 0
         payout_status = 'pending' (not already processing or paid)
         rep has a completed Stripe Connect account (same check as
           release_payout from Prompt 10)
     - Create a Stripe Transfer from the platform account to the rep's
       Connected Account for payout_cents. Transfer metadata:
         payment_type: 'challenge_conversion_bonus'
         challenge_submission_id: <id>
         rep_id: <rep_id>
     - Set payout_status → 'processing', store stripe_transfer_id.
     - Idempotent: if stripe_transfer_id already exists on this row,
       return without creating a duplicate Transfer. This is the
       primary idempotency guard — the Transfer ID proves the payout
       was already initiated.

6. Stripe webhook additions (extend Prompt 10's handler):

   transfer.paid where metadata.payment_type = 'challenge_conversion_bonus':
     → challenge_submissions.payout_status → 'paid', set paid_at
     → update rep_profiles.total_earnings_cents (same cached-field
       recompute mechanism from Prompt 10 — challenge conversion bonuses
       count toward the rep's total lifetime earnings)
   transfer.failed where metadata.payment_type = 'challenge_conversion_bonus':
     → alert admin queue, set payout_status → 'failed', flag for manual
       review
     → same admin surfacing pattern as flat campaign transfer failures

   Distinguish by metadata.payment_type. If metadata.payment_type is
   absent or has a different value, do not handle in this branch —
   fall through to the existing handlers. Never let a challenge bonus
   webhook handler touch campaign payout rows or vice versa.

7. Challenge auto-close scheduled job (extend Prompt 3 runner):
   New job: challenge_auto_close — runs every hour.
   Finds challenges where:
     closes_at < now()
     status = 'active'
   Transitions status → 'closed'. Idempotent — a challenge already
   'closed' is skipped without error. Logs every auto-close with
   challenge_id, closes_at, and the timestamp of closure.

8. Profile serializer additions:
   Add to the rep profile serializer used by:
     - GET /reps/me
     - GET /reps/me/profile-preview
     - Brand-facing rep browse (GET /brands/campaigns/:id/reps/browse)
     - Recruiter search results (GET /recruiters/reps/search)
   Fields to add:
     challenges_submitted_count (integer)
     challenges_converted_count (integer)
     challenge_conversion_rate (derived: challenges_converted_count /
       challenges_submitted_count, rounded to 2 decimal places; null
       if challenges_submitted_count = 0 to avoid division by zero)
   For recruiter search results (no-PII cards): include
   challenges_converted_count and challenge_conversion_rate — these
   are achievement signals, not PII, and do not require a credit spend
   to see. A rep's conversion rate is as relevant to a recruiter as
   their campaign count.

9. Admin analytics addition (extend Prompt 13):
   GET /admin/analytics/challenges
   Returns:
     - Total challenges created, active, closed
     - Total submissions platform-wide
     - Platform-wide conversion rate
     - Conversion bonus total paid (in cents) — this is a platform cost
       that leadership needs to track
     - Top categories by submission volume
     - Brands with highest conversion rates (a quality signal — a brand
       that converts 40% of submissions is a better platform partner
       than one that converts 5% and wastes rep effort)
     - Brands with zero conversions after 30+ submissions (a warning
       signal — these brands may be using challenges to harvest creative
       work without paying for campaigns)

10. Parent portal addition (extend Prompt 4A):
    Add to GET /parent/dashboard:
      challenge_activity: {
        total_submitted: integer
        total_converted: integer
        total_bonus_earned_cents: integer
        recent_submissions: [last 5, with challenge title, submitted_at,
          status visible to parent ('submitted'|'converted'), and
          bonus_earned_cents if converted]
      }
    Parents see aggregate challenge activity and bonuses earned.
    Parents do NOT see declined submissions (same protection as reps —
    no reason to expose rejection to a parent who may pressure their
    child about it). Parents DO see 'converted' submissions including
    the campaign the rep was invited to, because a campaign invitation
    is a financial event the parent has a legitimate interest in knowing
    about before their child accepts.

---

FRONTEND ADDITIONS:

Brand portal (add to Prompt 9's challenge management tab):
  - Challenges tab in the brand dashboard navigation alongside Campaigns.
  - Challenge creation form: title, brief field, category selector
    (same options as campaign targeting), submission format selector,
    submission prompt field, optional max submissions and close date.
    A preview panel showing exactly what a rep will see before the
    brand activates.
  - Challenge list: all challenges with status, submissions_count,
    conversion_count, conversion_rate per challenge.
  - Submissions inbox per challenge: rep no-PII card, submission
    content, submitted_at. Review, Convert, and Decline actions.
    Convert action requires selecting an active campaign from a
    dropdown. A clear note on the Convert action: "Converting sends
    the rep a campaign invitation and a $7.50 Teenure discovery bonus.
    This does not create a billing event — the campaign budget was
    set at campaign activation."
  - Zero-conversions warning state: if a brand has closed a challenge
    with 30+ submissions and zero conversions, surface a prompt:
    "Consider using challenges to discover reps for active campaigns.
    Reps invest time in submissions — converting the best ones builds
    your brand reputation on Teenure."

Rep portal (add to Prompt 6's challenge panel):
  - Challenge discovery panel on the dashboard. Visually distinct from
    the Campaigns panel. Header: "Brand Challenges — Unpaid Discovery"
    with a one-line explanation: "Submit your creative work. Brands may
    invite you to a paid campaign based on what you submit."
  - Challenge detail view: full brief, submission prompt, format,
    close date if applicable. Before the submission form, a mandatory
    disclosure box (cannot be hidden or scrolled past):
      "This challenge is unpaid. You are sharing your creative work
      to help a brand discover talent. If the brand loves your
      submission, they may invite you to a paid campaign and Teenure
      will pay you a $7.50 discovery bonus. This is not guaranteed."
    A checkbox: "I understand this challenge is unpaid." The checkbox
    must be checked before the submission form is accessible. The
    checkbox sends disclosure_acknowledged: true to the server — this
    is the UI implementation of the server-side enforcement in
    deliverable 4e above.
  - Submission interface: text field and/or file upload per format.
    Character count for text submissions. File type and size validation
    mirroring server-side checks. A submit button with the label
    "Submit My Work" — not "Apply" (implies job application framing)
    and not "Earn" (implies payment). Submit confirmation: "Submitted.
    You'll hear from us if a brand wants to work with you."
  - Submitted challenges panel: challenge title, submitted_at, and
    status. Status display:
      In review → "Submitted — brand is reviewing"
      Converted → "Brand invited you to [campaign name]. +$7.50 bonus
        added to your earnings."
    No declined state visible — simply absent from the list once declined.
  - Mobile-first: all challenge surfaces must pass the 375px viewport
    check per the mobile-first requirement from Prompt 6.

---

ACCEPTANCE CRITERIA:

Schema and RLS:
  - brand_note is never present in any rep-facing API response payload —
    verified by inspecting GET /reps/challenges/submitted and the
    challenge detail response.
  - A rep cannot read another rep's challenge_submissions rows — RLS
    verified by attempting cross-rep access with two seeded reps.
  - A rep cannot see declined submissions in any rep-facing endpoint —
    verified by seeding a declined submission and confirming it is
    absent from GET /reps/challenges/submitted.

Disclosure enforcement:
  - POST /reps/challenges/:id/submit with disclosure_acknowledged absent
    or false returns 400 with the correct disclosure message. Verified
    by calling the endpoint directly without a UI session.
  - A rep who submits via direct API with disclosure_acknowledged: true
    but no UI interaction creates a valid submission — the server
    does not require UI interaction, only the acknowledgment flag.

Submission validation:
  - Submitting to a closed challenge returns a clear "challenge is
    closed" error, not a generic 4xx.
  - Submitting to a challenge already submitted returns "already
    submitted," not a UNIQUE constraint violation error.
  - Submitting to a challenge at max_submissions returns a clear
    "challenge is full" error.

Conversion:
  - Converting a submission creates a campaign_reps invitation row
    that is indistinguishable from a direct brand invitation — verified
    by running Prompt 10's existing campaign lifecycle integration test
    against a campaign_reps row created via conversion.
  - Converting the same submission twice does not create a duplicate
    Transfer — verified by calling the convert endpoint twice and
    asserting stripe_transfer_id is identical on both responses and
    only one Stripe Transfer exists.
  - Converting a submission to a campaign with no available rep slots
    returns 409 "campaign is full" and does not create a
    campaign_reps row or initiate a payout.
  - The conversion transaction is atomic — if the campaign_reps
    creation fails, the challenge_submission status does not change
    to 'converted' and no payout is initiated.

Payout safety:
  - release_challenge_conversion_bonus called twice for the same
    submission_id produces exactly one Stripe Transfer — verified
    with a concurrency test matching the pattern from Prompt 11's
    credit deduction test.
  - transfer.paid for a challenge bonus Transfer updates only
    challenge_submissions and rep_profiles.total_earnings_cents —
    does not touch any campaign_reps or campaign payout rows.
  - transfer.paid for a campaign Transfer does not affect
    challenge_submissions rows.

Auto-close job:
  - A challenge with closes_at in the past is transitioned to 'closed'
    when the job runs — tested directly against the job function.
  - Running the job twice against the same expired challenge produces
    one log entry and no duplicate state transition.

Profile serializer:
  - challenge_conversion_rate is null when challenges_submitted_count
    is 0 — unit test the division-by-zero guard explicitly.
  - challenge_conversion_rate appears in recruiter search results
    without a credit spend — verified by calling the search endpoint
    as an authenticated recruiter and asserting the field is present.

Parent portal:
  - Converted submissions appear in the parent dashboard challenge
    activity with the campaign name and bonus amount.
  - Declined submissions are absent from the parent dashboard.
```

---

## 8H. Learning Modules and Verified Badges

**Depends on:** Prompt 5 (Rep Portal backend — implemented), Prompt 8G
(establishes the non-campaign rep activity pattern this prompt follows;
specifically the disclosure architecture, the profile serializer
additions, and the admin analytics pattern).

**Also affects:** Prompt 6 (Rep Portal frontend — learning hub, module
player, badge display), Prompt 13 (Admin Portal — module management
interface and analytics), Prompt 4A (Parent Portal — module activity
in parent dashboard). Execute those additions when you reach this prompt.

**FTC module dependency:** This prompt introduces the FTC Disclosure
module as a prerequisite for campaign acceptance. This changes the
behavior of POST /campaigns/:id/accept from Prompt 5. Update that
endpoint in this prompt — do not leave it for a separate pass. The
compliance audit in Prompt 15 will check for this; it should find it
already implemented, not open.

```
Implement learning modules and verified badges — short, platform-curated
educational content that reps complete to earn verified profile badges.
Badges are issued by Teenure, not self-reported by reps. They appear on
the rep's profile and are visible to brands and recruiters as verified
credentials.

PURPOSE (three distinct goals — design against all three):

  1. Give new reps with zero campaigns a reason to stay active and
     build profile depth. A rep who just signed up should land in
     the learning hub if no campaigns are available, not a blank screen.

  2. Give districts and schools a curriculum hook. When district licensing
     activates, modules become the curriculum that districts pay for.
     The module infrastructure must support a future district-funded
     completion stipend without a rebuild (see payout_cents field below).

  3. Give brands a quality signal beyond campaign count. A rep with
     verified FTC knowledge and client communication credentials is more
     credible than one without.

COMPENSATION DESIGN — read before building:

  Modules are unpaid at MVP. However the schema includes a payout_cents
  field on rep_module_completions that is null at MVP. This field exists
  to enable district-funded module completion stipends when district
  licensing activates: a district pays Teenure, Teenure pays reps a
  stipend for completing curriculum, stipend flows through Stripe Connect.
  Do not implement the payment logic now. Do implement the field so the
  payment logic can be added via a new prompt without a schema migration.

  The pre-module disclosure states the current compensation model
  honestly: "This module is unpaid. Completing it earns a verified badge
  that appears on your profile and is visible to brands and colleges. If
  your school district has a Teenure curriculum agreement, you may be
  eligible for a completion stipend — check with your school counselor."
  This disclosure future-proofs the model without overpromising.

TEEN AND PARENT EXPECTATION MANAGEMENT:

  Same principle as challenges: radical transparency before any work
  is done. The disclosure is mandatory and server-enforced. A rep who
  completes a module without passing the disclosure acknowledgment has
  not completed the module in the platform's view.

CONTENT GOVERNANCE:

  Modules are platform-created, admin-curated. Brands do not create
  modules. Reps do not create modules. This is intentional — the badge's
  value depends on consistent quality standards. A community-generated
  badge is not a verified credential. An admin-curated badge is.

  Module content must never be editable after activation. Archive and
  recreate is the only path to content changes. This protects reps who
  earned a badge on a specific version of the content — the badge they
  earned remains accurate even if the content is later updated.

FTC DISCLOSURE MODULE — MANDATORY:

  One specific module — title: "FTC Disclosure Essentials", defined in
  a config constant FTC_MODULE_ID — is mandatory for all reps before
  their first campaign acceptance. This replaces the current checkbox-
  only mechanism with a verified understanding check. The checkbox at
  campaign acceptance remains as an acknowledgment that the rep already
  understands the requirement — it is now backed by a verified module
  completion, not just a click.

  The gate logic in POST /campaigns/:id/accept must be updated in this
  prompt: before allowing accept, check that the rep has a 'passed'
  rep_module_completions row for FTC_MODULE_ID. If not, return 403 with
  message: "Complete the FTC Disclosure Essentials module before
  accepting campaigns. It takes about 5 minutes and is required to
  work with brands on Teenure."

---

SCHEMA ADDITIONS (new migration, separately numbered):

1. New table: learning_modules
     id (UUID PK default gen_random_uuid())
     title (text not null)
     description (text not null)
     category (text nullable — if set, this module is especially
       relevant to reps in this category; null means relevant to all)
     content_blocks (jsonb not null — ordered array. Each element:
       {
         "type": "text" | "video_url" | "image_url" | "quiz",
         "content": <string for text/video_url/image_url> |
           <array of question objects for quiz>
       }
       Quiz question object:
       {
         "question": "string",
         "options": ["string", "string", "string", "string"],
         "correct_index": integer  ← NEVER sent to client
       }
       The correct_index field in quiz blocks is stored server-side and
       evaluated server-side. It must never appear in any client-facing
       API response regardless of authentication role — including admin
       preview mode. Admin previews the module as a rep sees it, with
       correct answers hidden. This is enforced by a dedicated module
       serializer that strips correct_index from all outbound responses.)
     passing_score (integer nullable — minimum percentage correct to
       pass. null means no quiz; completion on content view alone)
     badge_title (text not null)
     badge_description (text not null — one sentence explaining what
       the rep demonstrated)
     badge_color (text not null — hex color e.g. '#6C3FC5')
     badge_icon (text nullable — icon name from the shared icon set)
     estimated_minutes (integer not null)
     status (text not null default 'draft'
       check (status in ('draft', 'active', 'archived')))
     created_at (timestamptz not null default now())
     updated_at (timestamptz not null default now())

2. New table: rep_module_completions
     id (UUID PK default gen_random_uuid())
     rep_id (UUID not null references rep_profiles(id) on delete restrict)
     module_id (UUID not null references learning_modules(id)
       on delete restrict)
     status (text not null default 'in_progress'
       check (status in ('in_progress', 'passed', 'failed')))
     quiz_score (integer nullable — percentage correct 0–100; null if
       no quiz in module)
     attempts (integer not null default 1)
     last_attempt_at (timestamptz nullable)
     passed_at (timestamptz nullable)
     badge_issued_at (timestamptz nullable — same as passed_at at MVP;
       separate field anticipates future where badge issuance could be
       decoupled from completion)
     disclosure_acknowledged_at (timestamptz nullable — set when the
       rep acknowledges the pre-module disclosure; required before
       start is recorded)
     payout_cents (integer nullable default null — null at MVP; set
       to the district stipend amount when district licensing activates;
       do not implement payment logic now, implement the field)
     payout_status (text nullable default null
       check (payout_status in (null, 'pending', 'processing',
       'paid', 'failed')))
     stripe_transfer_id (text nullable unique)
     UNIQUE (rep_id, module_id) — one completion record per rep per
       module; retakes update the existing row, never create a new one

3. Add to rep_profiles:
     badges (jsonb not null default '[]' — denormalized array of
       earned badge data for fast profile rendering:
       [{"module_id": "uuid", "badge_title": "string",
         "badge_description": "string", "badge_color": "#hex",
         "badge_icon": "string|null", "earned_at": "iso8601"}]
       Updated atomically with rep_module_completions when a module
       is passed. The badges jsonb is for display; rep_module_completions
       is the source of truth for audit.)
     badges_earned_count (integer not null default 0 — cached count,
       updated when badges jsonb is appended to)

4. Add to profile_completeness_score calculation (from Prompt 5
   deliverable 10): each badge up to a maximum of 3 contributes to
   the score. Define exact weights in the centrally-defined scoring
   function — document the weights in code comments. Suggested: each
   badge adds 5 points to the completeness score (max 15 points from
   badges). Update only the scoring function, not the schema — the
   score is computed, not stored separately.

5. Config addition:
   Add FTC_MODULE_ID to app/core/config.py. Value: the UUID of the
   FTC Disclosure Essentials module once created by admin. Use an empty
   string as the default — if FTC_MODULE_ID is empty, the gate check
   in campaign accept is skipped with a warning log. This allows the
   platform to activate before the module is created, but any deploy
   where FTC_MODULE_ID is not set should generate a visible warning.

6. Indexes:
     CREATE INDEX idx_learning_modules_status
       ON learning_modules(status) WHERE status = 'active';
     CREATE INDEX idx_rep_module_completions_rep
       ON rep_module_completions(rep_id, status);
     CREATE INDEX idx_rep_module_completions_ftc
       ON rep_module_completions(module_id, rep_id, status)
       WHERE status = 'passed';
       (This index specifically optimizes the FTC gate check on
       campaign accept, which runs on every accept action.)

7. RLS policies:
     Enable RLS on both tables before any application code touches them.

     learning_modules:
       All authenticated users can SELECT active modules
       (status = 'active'). Only admin (service role) can read draft
       or archived modules, and can insert, update, or delete.

     rep_module_completions:
       Reps can SELECT and UPDATE only their own rows (rep_id matches).
       Reps can INSERT only their own rows. Admin uses service role.
       No other role has direct table access.

     The correct_index fields within content_blocks (jsonb) are not
     row-level security concerns — they are serializer-level concerns.
     RLS does not protect jsonb sub-fields. The serializer must strip
     correct_index on every outbound response. This is enforced via a
     dedicated ModulePublicSerializer that never includes correct_index,
     used for every client-facing response regardless of role.

---

BACKEND DELIVERABLES:

1. Admin module management (new admin routes, extend Prompt 13's router):

   POST /admin/modules
     Create module in 'draft' status. Required: title, description,
     estimated_minutes, badge_title, badge_description, badge_color,
     content_blocks (validated: at least one block, quiz questions have
     exactly 4 options each, correct_index is 0–3, passing_score is
     null if no quiz blocks or 1–100 if quiz blocks are present).
     Returns module with correct_index STRIPPED from content_blocks
     even in admin response — admin creates with correct answers but
     never retrieves them via this API; they are write-only after creation.
     If admin needs to verify correct answers, they do so in the database
     directly, not via the API.

   PUT /admin/modules/:id
     Edit module. Draft status only — 409 if active or archived with
     message: "Active modules cannot be edited. Archive this module
     and create a new one to preserve the integrity of existing badges."

   POST /admin/modules/:id/activate
     Validates: all required fields present, content_blocks is valid,
     passing_score is consistent with quiz presence. Transitions
     'draft' → 'active'. Once active, the module is visible to reps
     and completions can be recorded.

   POST /admin/modules/:id/archive
     Transitions 'active' → 'archived'. Reps who already earned the
     badge keep it permanently — archiving does not revoke badges.
     No new completions can be started against an archived module.
     In-progress completions (status = 'in_progress') are orphaned —
     document how to handle: return them as 'in_progress' in rep-facing
     endpoints with a message "This module is no longer available" if
     the rep tries to complete it.

   GET /admin/modules
     All modules (all statuses) with: completion_count (total passed),
     pass_rate (passed / (passed + failed), null if no completions),
     average_attempts (mean attempts across all completions),
     in_progress_count. Pass rate and average_attempts are content
     quality signals — surface them prominently in the admin UI.

2. FTC gate update (modify Prompt 5's POST /campaigns/:id/accept):
   Add at the start of the accept handler, before any other business
   logic:

   If FTC_MODULE_ID is set (non-empty string in config):
     Check for a rep_module_completions row where:
       rep_id = current rep
       module_id = FTC_MODULE_ID
       status = 'passed'
     If no such row exists:
       Return 403 with body:
         {"error": {"code": "ftc_module_required",
           "message": "Complete the FTC Disclosure Essentials module
           before accepting campaigns. It takes about 5 minutes and
           is required to ensure you understand sponsored content
           disclosure rules.",
           "module_id": FTC_MODULE_ID}}
       The module_id in the error response allows the frontend to deep-
       link directly to the module without a separate lookup.
   If FTC_MODULE_ID is not set (empty string):
     Log warning: "FTC_MODULE_ID not configured. FTC gate skipped."
     Continue with accept flow normally.

   This change must have its own test in this prompt's acceptance
   criteria and must be added to the Prompt 15 compliance audit
   checklist as item 10.

3. Rep module discovery and progress:

   GET /reps/modules/available
     Active modules the rep has NOT passed (no 'passed' row in
     rep_module_completions). Include modules with 'in_progress' or
     'failed' rows — those are available to continue or retake.
     Sorted: FTC module first (always), then category-matched modules,
     then general modules. For each module: id, title, description,
     category, badge_title, badge_description, badge_color, badge_icon,
     estimated_minutes, passing_score (as a percentage, e.g. 80),
     rep_progress (object: status, attempts, quiz_score, last_attempt_at
     — or null if no completion row exists yet).

   GET /reps/modules/completed
     Modules the rep has passed. Returns full badge details and
     passed_at. This is the source of truth for badge history — the
     badges jsonb on rep_profiles is for display; this endpoint is for
     the complete audit trail.

   GET /reps/modules/:id
     Full module content using ModulePublicSerializer — content_blocks
     with correct_index STRIPPED from all quiz questions. Every field
     present except correct_index. The frontend renders content blocks
     in order; the quiz question format includes options but no answer.

4. Module start:
   POST /reps/modules/:id/start
     Body must include: disclosure_acknowledged: true
     If absent or false: return 400 with message:
       "Module disclosure acknowledgment required. This module is
       unpaid. Completing it earns a verified badge on your profile.
       Your school district may offer a completion stipend — check
       with your school counselor."
     Validate module is active (not draft or archived).
     Validate no 'passed' row exists (cannot restart a passed module —
       return 409 "already completed").
     Validate retake cooldown: if status = 'failed' and last_attempt_at
       > now() - interval '24 hours', return 429 with:
         {"error": {"code": "retake_cooldown",
           "message": "You can retake this module in X hours and Y
           minutes.",
           "available_at": "<iso8601 timestamp>"}}
       The available_at field allows the frontend to show a precise
       countdown without a separate server call.
     Upsert the rep_module_completions row:
       If no row exists: INSERT with status 'in_progress', attempts 1
       If row exists with status 'failed': UPDATE status →
         'in_progress', increment attempts, set last_attempt_at = now()
       Set disclosure_acknowledged_at = now() in both cases.
     Returns the module content (same as GET /reps/modules/:id) plus
     the rep's current completion record.

5. Module completion:
   POST /reps/modules/:id/complete
     Body: {"answers": [integer, integer, ...]} — one answer index per
     quiz question in content_block order. For modules with no quiz:
     empty array is valid and the module passes immediately.
     Process:
       a. Validate rep has an 'in_progress' completion row (cannot
          complete without starting — 409 if no in_progress row).
       b. Validate module is still active (not archived mid-session —
          rare but possible; return 410 Gone with explanation).
       c. Fetch content_blocks including correct_index values (use
          service role or a server-side query that bypasses the public
          serializer — never rely on client-submitted correct answers).
       d. For each quiz block in content_blocks (in order), compare the
          rep's submitted answer against correct_index. Count correct.
       e. Calculate quiz_score = (correct / total_questions) * 100,
          rounded to nearest integer. If no quiz questions: quiz_score
          = null.
       f. Determine pass/fail:
            If passing_score is null (no quiz): passed.
            If quiz_score >= passing_score: passed.
            Else: failed.
       g. On pass:
            Update rep_module_completions: status → 'passed',
              quiz_score, passed_at = now(), badge_issued_at = now()
            Append to rep_profiles.badges atomically:
              {module_id, badge_title, badge_description, badge_color,
               badge_icon, earned_at: now()}
            Increment rep_profiles.badges_earned_count (+1)
            Recompute rep_profiles.profile_completeness_score using the
              centrally-defined scoring function (which now includes
              badge contribution)
            Return: {passed: true, quiz_score, badge: {badge_title,
              badge_description, badge_color, badge_icon},
              profile_completeness_score: <new score>}
       h. On fail:
            Update rep_module_completions: status → 'failed', quiz_score,
              last_attempt_at = now()
            Return: {passed: false, quiz_score, passing_score,
              correct_answers: [{question_index, correct_index,
              rep_answer_index}] — return which questions the rep got
              wrong with the correct answers. This is a learning tool.
              Showing correct answers after failure is intentional.
              Do NOT return correct answers for questions the rep got
              right.}
       Steps g must execute atomically: if the badges jsonb append fails,
       the completion status must not be set to 'passed'. A rep whose
       module passed but whose badge was not issued is in an inconsistent
       state that requires manual admin resolution.

6. Badge display in profile serializers:
   Add badges (full array from rep_profiles.badges) and
   badges_earned_count to:
     - GET /reps/me (full array)
     - GET /reps/me/profile-preview (full array)
     - Brand-facing rep browse: badge_count and badge_titles array only
       (enough for brand to see credentials without full badge detail)
     - Recruiter search results (no-PII cards): badge_count and
       badge_titles — no credit required to see badge count and titles.
       Badges are verified credentials, not PII.

7. Leaderboard: explicitly NOT built. No rep-to-rep badge count
   comparison, module completion ranking, or any other comparative
   metric. A rep's badge record is their own achievement. Leaderboards
   create social dynamics that violate Section 1A's no-discovery
   mechanics. If this is requested later, it requires an explicit
   product decision and safety review before the prompt is written.

8. Parent portal addition (extend Prompt 4A):
   Add to GET /parent/dashboard:
     module_activity: {
       total_started: integer
       total_passed: integer
       total_failed: integer (so parents understand if their child is
         struggling — not to pressure them, but to offer support)
       badges_earned: [badge_title, earned_at] — the parent can
         celebrate these with their child
       ftc_module_passed: boolean — explicitly surfaced because the
         FTC module is a prerequisite for campaign acceptance; parents
         should know their child has demonstrated understanding of
         disclosure rules
     }
   Note: parents do not see quiz scores or incorrect answers. The
   detailed performance data is the rep's own. Parents see completion
   status and badges earned — the outcome, not the struggle.

9. Admin analytics addition (extend Prompt 13):
   GET /admin/analytics/modules
   Returns:
     - Total modules (by status)
     - Total completions (by status: in_progress, passed, failed)
     - Per-module: pass_rate, average_attempts, completion_count
     - FTC module specifically: what percentage of reps who have
       tried to accept a campaign have the FTC module passed? This
       is a launch readiness metric — if it is low, reps are hitting
       the gate and bouncing.
     - Badge distribution: which badges are most earned, by category
     - Modules with pass_rate < 50%: flag these for content review
       (too hard or poorly written)
     - Modules with average_attempts > 2: flag for content review
       (confusing questions)

---

FRONTEND ADDITIONS:

Rep portal (add to Prompt 6 as the learning hub):
  - Learning Hub: a dedicated section accessible from the main
    navigation (not buried in settings or profile). After onboarding,
    if no campaigns are available, the rep lands here by default rather
    than an empty dashboard.
  - Module list: available modules (not yet passed). FTC module pinned
    to the top with a badge: "Required before campaigns." Category-
    matched modules next. General modules last. Each card shows:
    badge preview (color and title), estimated_minutes, and a progress
    state if in_progress or failed.
  - Completed modules: a separate section showing earned badges with
    passed_at dates.
  - Pre-module disclosure modal: shown before content begins.
    Cannot be dismissed without acknowledging. Text:
      "This module is unpaid. Completing it earns a verified [badge_title]
      badge that appears on your profile and is visible to brands and
      colleges. If your school has a Teenure curriculum agreement, you
      may be eligible for a completion stipend — check with your
      counselor."
    Checkbox: "I understand this module is unpaid and I am completing
    it to earn a verified credential." Start button enabled only when
    checked. Sends disclosure_acknowledged: true to the server.
  - Module player: content blocks rendered in sequence.
      text blocks: readable prose with appropriate line length
      video_url blocks: embedded video player
      image_url blocks: full-width image with alt text
      quiz blocks: one question at a time, four answer options as radio
        buttons, "Next Question" after selecting (cannot go back),
        "Submit Quiz" on the final question — one-shot submission, no
        per-question feedback during the quiz
    Progress bar showing position through all content blocks. The
    submit button is visible only after all non-quiz content blocks
    have been scrolled past (client-side scroll tracking — not a timer,
    not a checkbox, actual content engagement).
  - Pass screen: badge reveal. Badge color, title, description. "This
    badge has been added to your profile." Two CTAs: "View My Profile"
    and "Continue Learning." No confetti, no points, no score display
    on the pass screen — the badge is the reward, not the score.
  - Fail screen: "Not quite — review and try again in 24 hours."
    Show the questions the rep got wrong and the correct answers (not
    the ones they got right). Countdown timer to retake availability.
    Warm, encouraging tone. Not "You failed" — "Almost there."
  - FTC module gate modal: if a rep tries to accept a campaign before
    passing the FTC module, show a modal (not a redirect):
      "Before accepting campaigns, complete the FTC Disclosure
      Essentials module. It takes about 5 minutes and ensures you
      understand the sponsored content disclosure rules that protect
      you and your followers."
    CTA: "Go to Learning Hub" — deep-links to the FTC module.
    Do not reject silently. Do not redirect without explanation.
  - Badge display on profile preview: badges rendered as colored chips
    with badge_title. Tap/hover shows badge_description and earned_at.
    Same rendering in profile preview mode so reps see exactly what
    brands and recruiters see before opting into visibility.
  - Mobile-first: all learning hub surfaces must pass the 375px
    viewport check. Quiz options must be large enough to tap without
    mis-selection. Badge chips must wrap cleanly on narrow screens.

Admin portal (add to Prompt 13's admin frontend):
  - Module management section: module list with status, pass_rate,
    average_attempts. Create, preview, activate, archive actions.
  - Module builder:
      content block builder: add blocks (text/video/image/quiz),
        drag to reorder, remove blocks
      text block: rich text editor or plain textarea
      video block: URL input with preview
      image block: URL input or upload to Supabase Storage
      quiz block: question text input, four option inputs, correct
        answer selector (radio button selecting which option is correct)
    Passing score input (shown only when quiz blocks are present).
    Badge configuration: title, description, color picker, icon selector.
    Estimated minutes input.
  - Preview mode: renders the module exactly as a rep sees it, with
    correct answers hidden. Admin cannot see correct answers in preview.
    This enforces the security model at the UI level — the API already
    enforces it server-side, the UI should too.
  - Module analytics panel per module: pass_rate, average_attempts,
    completion timeline chart. Flags for low pass_rate and high
    average_attempts.

---

ACCEPTANCE CRITERIA:

Security — correct answers never exposed:
  - GET /reps/modules/:id response payload contains no correct_index
    field anywhere in the content_blocks structure — verified by
    recursively searching the JSON response for the key "correct_index".
  - GET /admin/modules/:id response payload contains no correct_index
    field — same verification. Admin sees the module structure but
    not the answer key via the API.
  - POST /reps/modules/:id/complete rejects if the request body
    contains correct answer indices submitted by the client — the
    server fetches correct answers independently and ignores any
    correct-answer-adjacent fields in the request body.

Disclosure enforcement:
  - POST /reps/modules/:id/start with disclosure_acknowledged absent
    or false returns 400 with the correct message — verified by direct
    API call without UI session.

FTC gate:
  - POST /campaigns/:id/accept with a rep who has no FTC module
    completion returns 403 with code "ftc_module_required" and
    module_id in the error body.
  - POST /campaigns/:id/accept with a rep who has a 'failed' FTC
    module completion returns 403 (failed is not passed).
  - POST /campaigns/:id/accept with a rep who has a 'passed' FTC
    module completion proceeds normally.
  - If FTC_MODULE_ID is not configured (empty string), the gate is
    skipped and a warning is logged — acceptance proceeds normally.
  - These four cases must each have a named pytest test.

Retake cooldown:
  - POST /reps/modules/:id/start for a rep with a 'failed' row and
    last_attempt_at within 24 hours returns 429 with available_at.
  - POST /reps/modules/:id/start for a rep with a 'failed' row and
    last_attempt_at more than 24 hours ago succeeds.
  - POST /reps/modules/:id/start for a rep with a 'passed' row
    returns 409 "already completed."

Completion atomicity:
  - Passing a module updates rep_module_completions, rep_profiles.badges,
    and rep_profiles.badges_earned_count atomically — if the badges
    append fails, the completion status is not set to 'passed'. Verified
    by mocking a database failure mid-transaction and asserting the
    rolled-back state.
  - Failing a module does not modify rep_profiles.badges.

Badge in serializers:
  - badges_earned_count appears in recruiter no-PII search result cards
    without a credit spend — verified by calling the search endpoint
    and asserting the field is present.
  - badge_titles array appears in brand-facing rep browse — verified
    by seeding a rep with badges and calling the browse endpoint.

Module content protection:
  - An archived module cannot be started (400 with explanation).
  - An in_progress completion on an archived module returns a clear
    message when the rep attempts to complete it.

Prompt 15 compliance update:
  - Add item 10 to the compliance checklist: "FTC module gate on
    campaign accept — verified by named pytest tests for all four
    cases (no completion, failed completion, passed completion, no
    FTC_MODULE_ID configured)."
  - Add item 11: "Module correct answers never present in any API
    response — verified by recursive key search on representative
    responses from GET /reps/modules/:id and GET /admin/modules."

Prompt 19 PostHog update:
  Add these events to the instrumentation list:
    - module_started (module_id, category — no rep identity)
    - module_passed (module_id, quiz_score, attempts — no rep identity)
    - module_failed (module_id, quiz_score, attempts — no rep identity)
    - ftc_gate_triggered (when a rep hits the FTC gate — critical
      funnel metric; high volume here means reps are ready to accept
      campaigns but haven't completed the module)
    - badge_earned (badge_title, module category — no rep identity)
    - challenge_submitted (category — no rep identity)
    - challenge_converted (category, bonus_amount — no rep identity)
```

---

## 9. Brand Portal — Frontend — **implemented (core flow)**

**Depends on:** Prompt 8, [Section 0A](#0a-design-system--ux-standards)
(design tokens must exist — ideally shared with a Prompt 6 retrofit
pass — before screens in this prompt are built).

**Build-log note:** Section 0A's token system landed first (real
color/type/spacing tokens in `app/globals.css` + `lib/design-tokens.ts`,
Inter via `next/font/google`, `Skeleton`/`EmptyState` primitives), then
Prompt 6's already-built Rep Portal screens (auth pages, dashboard,
campaign detail) were retrofitted against it — shared `RepShell`/
`AuthShell`/`CampaignBrief` components extracted so both portals read
as one product, per 0A's own acceptance criterion. Then the Brand
Portal core flow: signup, company-profile onboarding (EIN, categories),
campaign dashboard, brief builder with a live preview (reusing
`CampaignBrief`, satisfying deliverable 2's "reuse the rep-facing
renderer" instruction literally), campaign detail with activate/retry-
payment/pause/cancel, and rep browse + invite.

**Not built in this pass** (scoped out, not silently skipped): actual
Stripe Elements/Checkout card collection UI (deliverable 3 explicitly
leaves "Elements or Checkout — pick one" as an open choice; a real
`PaymentIntent` is created server-side and its `client_secret` returned,
but no client-side card form consumes it yet — meaningful testing needs
a real Stripe test-mode key, not the local placeholder), submission
review UI (viewing/confirming/requesting revision on a rep's
submission — the data and backend routes exist from Prompt 8, only the
UI is missing), and the billing/receipt page.

**A real, load-bearing bug was found and fixed while building this**,
not a hypothetical: every brand signup lands `account_status='pending'`
(no admin-approval flow exists yet — Prompt 13 builds it), and
`require_role("brand")` gated *every* brand route, including
`GET/PUT /brands/me`, behind `account_status='active'`. That meant a
real brand could never reach the API call that submits their profile
for review in the first place — Prompt 8's own tests never caught this
because they seed brand users as `'active'` directly via SQL, bypassing
the real signup flow entirely. Only surfaced because this prompt drove
a real signup through the real UI. Fixed with a new
`require_role_any_status` dependency (`app/core/security.py`), used
only for `GET/PUT /brands/me`; every money-moving/campaign route still
requires `'active'`. A matching frontend fix lets `/brand/onboarding`
stay reachable while `pending_reason === "pending_admin_approval"`
(`app/(brand)/brand-gate.tsx`), with every other authenticated route
still gated behind the "under review" state. New regression tests at
both layers (`test_brands_portal.py`, and the new
`tests-e2e-auth/brand-portal.spec.ts`, which also demonstrates the
current, real boundary: a real signup can complete onboarding but
genuinely cannot create a campaign without an admin approving it first
— that suite simulates the missing approval step directly, the same
way pytest's own fixtures do, rather than pretending the gap isn't
there).

All existing Playwright suites (demo portal, rep auth pages, rep
authenticated E2E) and all 140 backend tests still pass.

```
Build the Brand Portal under apps/web/app/(brand)/.

Apply Section 0A in full: land/reuse the shared design-token theme
before building screens, not after. This portal's audience (brand
marketers deciding whether to trust the platform with a campaign
budget) is exactly the "Fortune-500-bar" case 0A describes — treat its
acceptance criteria as part of this prompt's own acceptance criteria,
not a separate later pass.

Deliverables:
1. Signup/verification: business email, company name, website, EIN field,
   "pending admin approval" state after signup.
2. Brief builder: every field from Prompt 8's schema, preview step showing
   exactly what reps see (reuse the rep-facing campaign detail component
   from Prompt 6 — do not build a second renderer).
3. Stripe payment capture at activation (Elements or Checkout — pick one
   and justify). Campaign in 'payment_failed' shows a clear "payment
   failed, retry" state using this same UI — not a dead end.
4. Rep discovery: filter panel, no-PII cards, full profile on click,
   invite action, platform-auto-match alternative.
5. Campaign management dashboard: all campaigns with status, per-campaign
   rep list, submission review (approve/revision with note), rating UI
   enforcing write-once/post-confirmation rule.
6. Billing view: spend history, Stripe receipt links.

Acceptance criteria:
  - Full walkthrough: signup → simulated admin approval → create campaign
    → activate (Stripe test card) → browse/invite reps → review submission
    → confirm → rate. Each step matches backend state.
  - Pending brand cannot reach campaign creation UI.
```

---

## 10. Campaign Lifecycle & Payout Engine — **implemented**

**Depends on:** Prompt 7, Prompt 8.

**Note for Prompt 8B:** `release_payout` below is the flat-campaign-
specific payout function. Prompt 8B (Performance Milestone Payments)
adds `release_milestone_payout` as its per-milestone equivalent — the
two coexist, neither replaces the other. The `transfer.paid`/
`transfer.failed` webhook handlers built in this prompt gain a
`metadata.payment_type` branch in Prompt 8B; this prompt's own flat-
campaign handling stays the default when that key is absent, so nothing
below needs to change for Prompt 8B to build on top of it.

**Build-log note:** All 7 deliverables implemented.
`app/services/payout_service.py`'s three stubs are now real
(`calculate_platform_fee_split`, `release_payout`,
`handle_transfer_paid`/`handle_transfer_failed`);
`app/services/stripe_service.py`'s `create_payout_transfer` and
`refund_campaign` stubs are now real Transfer/Refund calls;
`app/routers/webhooks.py` implements `payment_intent.succeeded`,
`payment_intent.payment_failed`, `transfer.paid`, `transfer.failed`
(only `customer.subscription.*` remains a Prompt-11 stub) with a new
`stripe_events` table (migration
`20260815090000_stripe_events_table.sql` — a schema addition beyond
Section 7, flagged per the same "documented, not assumed" convention as
Prompt 7's `stripe_account_id` addition) giving every webhook
insert-or-skip idempotency on Stripe's event id, checked before any
handler runs. `POST /brands/campaigns/:id/confirm` now calls
`release_payout` in the same request right after the state-machine
transition to `'confirmed'`; `POST /activate`/`/retry-payment` now
lazily create-or-reuse the brand's Stripe Customer
(`campaign_service.get_or_create_stripe_customer_id`, same
create-or-resume shape as the rep Connect onboarding flow) before
creating the PaymentIntent against it, resolving Prompt 8's own
build-log note that this was "ready for admin approval flow, Prompt
13" — it turned out not to need Prompt 13 at all, since a brand's
Stripe Customer identity doesn't depend on admin verification.

**Refund policy resolved, not left open**: Prompt 8 explicitly declined
to pick a cancellation refund amount and flagged it as a business
decision. Rather than leave `refund_campaign` unimplemented
indefinitely, this prompt adopts its own proposed fallback verbatim
("partial refund for un-paid remainder when some reps already paid")
as the documented interim policy — see the rewritten
`docs/campaign-cancellation-refund-policy.md` for the exact formula and
what's still open (e.g. platform-fee refundability, which this prompt
did decide: refunded proportionally to the unpaid remainder).

**rep_profiles cached-field recompute (deliverable 7)**: Prompt 2 only
ever produced a design note for this ("updated via trigger or
background job") — no trigger exists in any migration. Rather than
inventing one now, `rep_profiles_repository.recompute_cached_totals`
recomputes `total_campaigns_completed`/`total_earnings_cents`/
`average_rating` in application code from `campaign_reps`, called from
`payout_service.handle_transfer_paid` right after a payout completes —
matching this codebase's existing style (`update_profile_completeness_score`)
of computing cached fields at the call site rather than in SQL.

**Interpretive decisions documented rather than guessed past:**
- `payout_service.calculate_platform_fee_split` mirrors
  `campaign_service.compute_campaign_fee_split`'s exact rounding rule
  but is not on `release_payout`'s call path — the per-rep amount is
  already fixed at campaign-creation time on `campaign_reps.payout_cents`,
  so there's no second split to compute at payout time. Kept as its own
  function purely for this prompt's own rounding-invariant unit-test
  coverage, per the acceptance criteria's wording.
- A `transfer.failed` row has no admin queue to land in yet (Prompt 13
  isn't built) — `payout_status = 'failed'` on `campaign_reps` *is* the
  interim queue, flagged rather than inventing a table this prompt
  doesn't own.
- A rep confirmed for payout but not yet Connect-onboarded
  (`release_payout`'s `"rep_not_onboarded"` outcome) does not fail the
  confirm call — the row stays `payout_status='pending'` until the rep
  finishes onboarding. Nothing currently retries the transfer
  automatically once they do; flagged, not a stated deliverable here.

30 new/updated tests: `tests/test_payout.py` (fee-split rounding
invariant, PaymentIntent/Customer wiring, `payment_intent.*` webhook
transitions + brand notification email, `release_payout`'s three
outcomes including idempotency against a retried confirm, `transfer.*`
webhook transitions + cached-total recompute), plus updated coverage in
`tests/test_stripe.py` (webhook idempotency against a replayed event
id) and `tests/test_brands_portal.py` (activate/cancel tests updated
for the real Customer/Refund calls now in their code path). All 155
backend tests pass.

```
Implement the money-movement core. Treat every amount as untrusted until

```
Implement the money-movement core. Treat every amount as untrusted until
recomputed server-side; every state transition must be idempotent against
webhook retries.

Deliverables:
1. payout_service.py: calculate_platform_fee (pure, unit-testable) and
   release_payout(campaign_rep_id) — validates 'confirmed' status, non-null
   payout_cents, completed Connect account before creating Transfer.
2. Wire /activate to create Stripe PaymentIntent for budget_cents against
   brand's stripe_customer_id.
3. Complete webhook handlers (idempotent — dedup on Stripe event ID):
     - payment_intent.succeeded → 'pending_payment' → 'active'
     - payment_intent.payment_failed → notify brand, → 'payment_failed'
     - transfer.paid → campaign_reps payout_status → 'paid', set paid_at
     - transfer.failed → alert admin, flag for manual review
4. Wire /confirm to call release_payout. Idempotent — confirming an
   already-confirmed row is a no-op or clean 409, not a duplicate transfer.
5. Refund logic for /cancel per policy defined in Prompt 8 — partial refund
   for un-paid remainder when some reps already paid.
6. Rating sequence: brand confirms → Stripe transfer → rating optional
   afterward. Confirm this sequence is what's implemented.
7. rep_profiles cached-field recompute on relevant transitions — whatever
   mechanism was documented in Prompt 2.

Acceptance criteria:
  - Full integration test (Stripe test mode): activation → payment webhook
    → rep submits → brand confirms → transfer webhook → rep earnings update.
  - Same webhook payload twice → no duplicate side effects.
  - transfer.failed → surfaces in admin queue (Prompt 13).
  - calculate_platform_fee unit tests: rounding covered,
    rep_pool + fee == budget always holds.
```

---

## 11. Recruiter Portal — Backend

**Depends on:** Prompt 8, Prompt 10.

```
Implement Recruiter backend routes from Section 8 and Phase 3 of Section 5.

Deliverables:
1. GET/PUT /recruiters/me, GET /recruiters/credits.
2. GET /recruiters/reps/search — all query params from Section 8
   (graduation_year, city, state, categories, min_campaigns, min_rating,
   limit, offset) against recruiter_visible=TRUE reps. No credit cost. No
   PII in results.
3. GET /recruiters/reps/:id — full profile, costs 1 credit, deducted
   server-side in same transaction as read. 402 on zero balance.
4. POST /recruiters/reps/:id/contact — costs 1 credit (same transactional
   deduction). One-directional by design — recruiter_contacts has no
   reply column, no reply endpoint exists or will be added here. MVP
   behavior on second contact to same rep: reject with "you've already
   contacted this rep" (UNIQUE constraint enforcement).
   Notification: (a) GET /reps/inbox returns the message row, (b)
   transactional email to rep's account email ("you have a new message
   on Teenure" — not the message content). No push/websocket at MVP.
   Add POST /reps/inbox/:contact_id/read (mark-read) here.
5. POST/DELETE /recruiters/reps/:id/save, GET /recruiters/saved —
   list_name field supported.
6. GET /recruiters/credits returns server-computed low-credit warning flag
   at 20% remaining.
7. Credit top-up: Stripe one-time charge, increments credits on webhook,
   idempotent.
8. Subscription lifecycle webhooks (complete the stubs from Prompt 7):
     - customer.subscription.created → recruiter 'active' (both admin
       approval AND subscription creation required — dual gate) + set
       contact_credits_remaining to plan allotment + set credits_reset_date
     - customer.subscription.renewed → reset credits to plan allotment
       (credits do NOT roll over — unused credits are lost, this is the
       explicit MVP decision) + advance credits_reset_date. Idempotent —
       duplicated event grants reset exactly once.
     - customer.subscription.deleted → account out of 'active'; existing
       saved profiles and message history retained; credit-spending
       endpoints return "subscription inactive" error.

Acceptance criteria:
  - 0 credits → clear distinct error on profile view or contact.
  - Concurrent requests with exactly 1 credit → exactly one success, one
    "insufficient credits" — verified with a concurrency test.
  - Search never returns identifying fields before credit spent.
  - Simulated subscription.created → recruiter active with correct starting
    credits. Duplicated subscription.renewed → credits reset exactly once.
```

---

## 12. Recruiter Portal — Frontend

**Depends on:** Prompt 11, [Section 0A](#0a-design-system--ux-standards).

**Before building auth for this portal:** do not add `/recruiter/login`
or a `RecruiterGate` component. Prompt 6 documents an unresolved
login/gate fragmentation issue (`/rep/login` vs `/brand/login`,
`RepGate` vs `BrandGate`) that this portal must not repeat as a third
copy — land the shared `/login` page and `useRoleGate`/`<AuthGate>`
fix first (or as part of this prompt if still outstanding), then point
recruiter auth at it.

```
Build the Recruiter Portal under apps/web/app/(recruiter)/.

Apply Section 0A in full — reuse the shared design tokens from Prompts
6/9, do not establish a third divergent visual style. This portal's
audience (college admissions/employer staff) is the other half of 0A's
"Fortune-500-bar" case.

Desktop-primary but fully responsive. Phone-width sanity pass required
in acceptance criteria.

Deliverables:
1. Signup/verification: institution email (.edu preferred), institution
   name, type (college|employer), website, pending-admin-approval state.
2. Search/filter UI matching every Prompt 11 filter. No-PII cards. Full
   profile view gated behind explicit "this will use 1 credit" confirmation.
3. Saved-profiles list management (create/rename lists, add/remove).
4. Messaging UI: compose (1-credit confirmation), read-receipt display.
5. Subscription & credits panel: Stripe checkout (monthly/annual), balance
   display, low-credit warning at 20%, top-up flow.

Acceptance criteria:
  - Every credit-spending action shows explicit cost confirmation before
    firing — no silent credit spend.
  - Full walkthrough: signup → simulated admin approval → subscribe (test
    mode) → search → view profile (credit decrements) → contact rep
    (credit decrements) → confirm rep receives message in inbox and alert
    email.
  - Core flows usable at phone viewport — no layout breakage.
```

---

## 12A. Demo Mode — Recruiter Preview & Brand Sales Page

**Depends on:** Prompt 11 (real recruiter search), Prompt 6A (rep seed
data), Prompt 10 (for earnings history if needed), [Section 0A](#0a-design-system--ux-standards).
Placed after the real Recruiter Portal — reuses Prompt 11's actual
search endpoint against seed data rather than building a parallel fake
version.

```
This is the single highest-stakes surface for Section 0A: it's a sales
page a brand or institution sees before ever creating an account. Apply
0A in full, and hold this specific prompt to a higher bar than the
"reviewer can tell it's the same product" acceptance criterion — this
page needs to look like it belongs to an organization already trusted
with money and minors' data, on first impression, with no other context.
Build two things: recruiter search preview and brand sales page.

Part 1 — Recruiter preview at apps/web/app/(marketing)/demo/recruiter/:
1. Live search using Prompt 11's real search endpoint scoped to seed
   dataset from Prompt 6A. Add category/city variety to seed data now if
   Prompt 6A's set is too narrow for search filters to look meaningful.
2. Results as real no-PII cards. Every full-profile attempt → "start your
   free trial" → real recruiter signup.
3. No authenticated session or credits consumed browsing preview.

Part 2 — Brand page at apps/web/app/(marketing)/demo/brand/ (or in the
brand audience section from Prompt 18 — state which):
1. Explains rep network and campaign model.
2. Single CTA: "Schedule a demo" → Calendly or contact form. Not a signup
   flow. No self-serve campaign builder.

Optional: extend Prompt 6A seed dataset with enough confirmed campaign
history to show a multi-year compounding earnings story on the rep demo
profile, now that Prompt 10's payout engine can generate it from real
state transitions.

Acceptance criteria:
  - Recruiter preview works with no session, spends no credits.
  - Search results in preview are the exact same shape (no-PII cards) as
    a signed-in recruiter would see — verified by comparing against Prompt
    12's real search UI for the same query.
  - Brand page's only CTA is "Schedule a demo" — no signup form, no
    self-serve campaign creation reachable.
  - No real user data exposed anywhere.
```

---

## 13. Admin Portal

**Depends on:** Prompts 4, 4A, 8, 10, 11, [Section 0A](#0a-design-system--ux-standards)
(lighter application than the external-facing portals — internal-only,
so density/efficiency for staff working queues all day matters more
than first-impression polish, but still uses the same design tokens,
not a fourth divergent style).

**Auth note:** admin stays a genuinely separate, heavily-protected
surface (per Prompt 6's login-consolidation note) and must not be
reachable via role-detection fallthrough from the unified `/login`
page — but its own gate should still reuse the `useRoleGate`/
`<AuthGate>` primitive from that fix rather than a bespoke
`AdminGate`, since the loading/redirect mechanics are the same shape.

```
Implement Admin Portal — Phase 4 from Section 5, admin routes from
Section 8. Internal-only; service-role/admin auth required on every route.

Deliverables:
1. Approval queues: GET /admin/queue/{reps,brands,recruiters},
   POST /admin/approve/:type/:id, POST /admin/reject/:type/:id (required
   reason on reject, sent to applicant via email). Queue distinguishes
   'pending: awaiting parent consent' from 'pending: awaiting admin
   approval'. Confirm against Section 5 Phase 1 whether reps require admin
   approval at all — implement accordingly.
2. Campaign oversight: GET /admin/campaigns, flag, resolve. Resolve has
   enumerated action set (force-confirm, force-cancel with refund) — not
   a free-text action.
3. Payment management: GET /admin/payments/stuck (real query on
   payout_status and timestamps — not a placeholder),
   POST /admin/payments/:transfer_id/release (uses payout_service with
   admin-initiated audit flag).
4. Analytics: revenue by stream and period (Section 4's three streams),
   reps by city/category, campaigns by status/category, parental consent
   status breakdown (GET /admin/analytics/consent-status — flag as
   addition beyond Section 8).
5. Outlier-rating detection: define a concrete rule (e.g., brand rated
   >2 SD from platform mean, or 100% five-star ratings), surface flagged
   brands.
6. Parent suspension queue: admin can see rep accounts suspended by parents
   and reverse suspension if warranted (separate from admin-initiated
   suspension).
7. Safety report queue (highest-priority lane in admin): reports submitted
   via the rep portal's one-tap report mechanism. Safety reports sit above
   campaign disputes and payment issues in queue priority.
8. Admin frontend under apps/web/app/(admin)/: queues, oversight table,
   stuck-payments list, analytics dashboards, safety report lane.

**Also depends on (added by Prompts 8G/8H):** Prompt 8G (Skill Challenges)
adds GET /admin/analytics/challenges to deliverable 4's analytics routes.
Prompt 8H (Learning Modules and Verified Badges) adds a module management
interface (create/preview/activate/archive, content block builder, quiz
builder) and module analytics (completion rates, pass rates, average
attempts, badge distribution) to deliverable 8's admin frontend.

Acceptance criteria:
  - Non-admin JWT cannot reach /admin/* routes.
  - Approving a pending brand flips account_status to 'active' and unblocks
    campaign creation.
  - Rejection sends reason via email.
  - Stuck-payments query correctly identifies 49-hour row and excludes
    40-hour row.
  - Safety report queue is visually distinct and clearly highest-priority
    in the admin UI.
```

---

## 14. Intelligence Layer & Anonymization Pipeline

**Depends on:** Prompt 10, Prompt 3 (runner). Requires a new migration —
intelligence_events_anonymized is not in Section 7. Write as a new,
separately-numbered migration — do not alter already-applied migrations.

```
Implement the intelligence/data layer per Section 3.5 and Section 9.
The anonymization boundary must be enforced structurally, not by
convention — this is the second-highest legal-risk piece after auth/consent.

Deliverables:
1. New migration creating intelligence_events_anonymized with no FK to
   rep_profiles or users. Columns: category, city, school_type (sourced
   from rep_profiles.school_type — nullable; null values bucketed into an
   explicit "unspecified" group, not silently dropped, still subject to the
   minimum-group-size-of-10 gate), time_period_bucket, and campaign-
   performance metrics needed for trend reports. RLS: read access for
   admin/service role only.
2. Background job (Prompt 3 runner): on campaign_reps reaching 'confirmed'
   or 'paid', strips all PII (enumerate explicitly: rep_id, rep
   display_name, school_name, instagram_handle, tiktok_handle, city at
   individual level — not the aggregate city field — any other
   identifying field) and writes to intelligence_events_anonymized with no
   FK back to source tables.
3. Aggregation logic: any query returning a group smaller than 10 reps
   returns an explicit "insufficient sample size" — not a real number,
   not an empty result.
4. Trend-report generation by category, region, school_type — only against
   the anonymized table.
5. docs/intelligence-pipeline.md: full pipeline documented with codebase
   locations for each stage so a future auditor can verify the boundary
   without reading every file.

Acceptance criteria:
  - Anonymized table cannot be joined back to any identifying table —
    structurally impossible (no shared key), not just discouraged.
    Verified by attempting the join in a test.
  - Group of 8 → "insufficient sample size," not a number, not empty.
  - PII-stripping unit test: sample campaign_reps row → assert every
    PII field absent from output.
  - null school_type → "unspecified" bucket in aggregation output, still
    subject to minimum group size gate.
```

---

## 15. Compliance Audit Pass — **implemented**

**Depends on:** Prompts 4, 4A, 5, 8, 11, 13, 14.

```
Dedicated audit pass against Section 9. Does not add features — verifies
and hardens enforcement, produces a written audit trail.

For each Section 9 requirement: locate implementing code, write or extend
a test that fails if enforcement is removed, record in
docs/compliance-checklist.md.

1. Age gate — enforced server-side in signup handler only. No other code
   path can create a user row bypassing it.
2. Parental consent — 72-hour expiry and single-use token both enforced.
   Add test for reuse after account activation.
3. FTC disclosure — no submission endpoint or admin override can create a
   'submitted' campaign_reps row without ftc_disclosure_accepted = TRUE,
   including admin force-resolve from Prompt 13.
4. Parent campaign approval gate — no rep can accept a campaign requiring
   parent approval without a recorded parent approval. Verify the RLS
   policy from Prompt 2 and the API check from Prompt 5 are both
   enforcing this independently.
5. Data minimization — grep full schema and API response models for any
   field not in Section 7 or explicitly justified in an earlier prompt.
   Remove or justify unlisted fields.
6. Stripe Connect minors — confirm decision doc from Prompt 7 has been
   acted on or explicitly flagged as a launch blocker.
7. Anonymization — re-run Prompt 14's acceptance tests. Do not assume
   they still pass.
8. Parent portal data scope — confirm monthly digest job never includes
   recruiter message content, submission text, or brand contact details
   in its output. Verify by inspecting the generated payload in a test.
9. Privacy policy / ToS / California CPPA — produce a list of every
   technical fact the eventual lawyer-reviewed policy must accurately
   describe (what's collected, why, retention, who sees it, minor-specific
   rights, parent rights, portal expiry at 18). Source from what's
   actually implemented, not the aspirational spec.
10. FTC module gate (added by Prompt 8H) — confirm POST /campaigns/:id/accept
    returns 403 unless the rep has a 'passed' row on the FTC Disclosure
    learning module, distinct from and in addition to the
    ftc_disclosure_accepted checkbox acknowledgment already covered above.
11. Module correct answers never present in any API response (added by
    Prompt 8H) — verified by recursive key search for "correct_index" on
    representative responses from GET /reps/modules/:id and
    GET /admin/modules, including admin preview mode.
12. Public achievement link (added by Prompt 5 deliverable 12) — confirm the
    public /verified/:token page renders no PII beyond what the rep has
    explicitly enabled, verified by inspecting the public endpoint response
    under each combination of verified_profile_public and
    earnings_visible_on_public_profile toggle states.

Deliverable: docs/compliance-checklist.md mapping every Section 9
requirement to (a) implementing code location, (b) covering test(s),
(c) status (implemented / partial / open) with reasoning for anything
not fully closed.

Acceptance criteria:
  - Every Section 9 row has a checklist entry.
  - Every "implemented" row has a named passing test run as part of
    producing this checklist.
  - Every "open" or "partial" row has a specific reason and what's needed
    to close it — not "needs more work."
```

---

## 16. Testing Suite — **implemented**

**Depends on:** all functional prompts (5–14). Build incrementally
alongside them; this prompt is the consolidation pass.

```
Consolidate and fill gaps in automated test coverage.

Deliverables:
1. Backend (pytest): every Section 8 route has at least one happy-path
   test, one role-enforcement rejection test, one primary business-rule
   rejection test. Coverage report — flag any route with zero tests.
   Every Prompt 8B milestone endpoint (submit, confirm, dispute, and the
   auto-release job) needs this same three-test coverage pattern, plus
   the concurrency/idempotency and backward-compatibility coverage
   Prompt 8B's own acceptance criteria call out (two concurrent confirms
   producing exactly one Transfer; flat-campaign tests from Prompts 8/9/10
   passing unmodified after 8B lands).
2. Integration tests for: (a) full campaign lifecycle from creation to
   paid-out rep (extend Prompt 10's test to true end-to-end), and (b)
   parental-consent signup-to-active flow.
3. Integration test for parent portal campaign approval flow: rep invited
   → parent receives approval request → parent approves → rep can accept
   → parent blocks a different campaign → rep cannot see it in available
   campaigns.
4. Frontend tests (Vitest/RTL or Next.js equivalent): FTC checkbox gate,
   credit-spend confirmation prompts, age-gate/pending-consent screen
   states, parent-approval-pending state in rep campaign view,
   parent portal approve/block actions, and the rep dashboard's
   available-campaigns panel excluding a parent-blocked-category
   campaign for a rep whose parent has that category in values_filters
   (mock the API response with a category the seeded rep's parent has
   blocked and assert it never renders — this is a safety-enforcement
   surface, not just a display concern, so it needs the same test-backed
   guarantee as the FTC checkbox rather than resting on manual
   verification alone). Add: a rep cannot submit a sequence-required
   milestone before prior milestones are confirmed — the submission
   control for a non-actionable milestone must be disabled/absent in the
   rendered UI, not just rejected server-side, since this is a safety-
   adjacent feature protecting reps from confusion about what they've
   agreed to deliver next. Add (from Prompt 8H): the FTC module gate
   modal that appears when a rep tries to accept a campaign before
   passing the FTC Disclosure module. Add (from Prompt 5 deliverable 13):
   the goal completion state on the dashboard. Add (from Prompt 5
   deliverable 12): the achievement link visibility toggles (public
   profile on/off, earnings visible on/off) and that the previewed public
   page reflects each toggle state correctly.
5. CI-runnable command running backend and frontend suites together,
   failing build on any failure.

Acceptance criteria:
  - No Section 8 route with zero tests, or explicit documented exception.
  - Integration flows pass end-to-end against local Supabase and Stripe
    test mode.
  - Parent portal approval flow integration test passes.
  - Frontend test proves (not just visually confirms) that a
    parent-blocked-category campaign is absent from the rendered
    available-campaigns panel.
  - CI command returns non-zero on any failure.
```

---

## 17. Deployment & CI/CD

**Depends on:** Prompt 16.

```
Set up deployment and CI per Section 6 (Vercel, Railway, Supabase).

Deliverables:
1. CI pipeline (GitHub Actions): install deps, run backend + frontend
   test suites, lint, type-check on every PR. Block merge on failure.
2. Vercel config for apps/web: build command, output dir, env var mapping
   (document NEXT_PUBLIC_* vs server-only).
3. Railway config for apps/api: secret injection (never committed).
4. Supabase migration-deploy step: documented order relative to API/web
   deploys (migrations land before the API version that depends on them).
5. Staging environment: separate Supabase project, Stripe test mode.
6. Deploy order documented: schema migration → API → web. Rollback
   procedure documented.

Acceptance criteria:
  - Deliberately broken test prevents PR merge (verified in scratch branch,
    then reverted).
  - Full staging deploy succeeds; Prompt 16 integration flows pass against
    staging.
  - No secret value in any committed file, CI log, or deployment config.
```

---

## 18. Marketing Site

**Depends on:** Prompt 1, [Section 0A](#0a-design-system--ux-standards).
Can build any time in parallel. Link to Prompt 6A/12A demo experiences
if already built; otherwise build CTAs to signup and add demo links
once 6A/12A exist.

```
Build the public marketing site under apps/web/app/(marketing)/.

Same "highest-stakes first impression" bar as Prompt 12A applies here —
apply Section 0A in full. If this is built before the token system
exists elsewhere (per the "can build any time in parallel" note above),
this is where the tokens get established first, and Prompts 6/9/12
retrofit/build against what's landed here rather than each inventing
their own.

Deliverables:
1. Landing page: core insight, one-sentence platform rule, differentiation
   from social platforms per Section 1's "What It Is Not" list. No copy
   implying Section 1A-prohibited features.
2. Three audience pages/sections (Rep / Brand / Recruiter) with core
   motivations from Section 2 and clear signup CTAs routing to correct
   portal flows.
3. Parents page — not a footer mention, a real page:
     - What Teenure is and is not
     - How the parent portal works (campaign approval queue, values filters,
       monthly digest, account controls)
     - Age-based autonomy model (under-16 required approval, 16-17 opt-in,
       18 portal closes)
     - What data is collected and who sees it
     - How to suspend the account
     - Why the constraints are protective (Section 1A's "Why These
       Constraints Are Competitive Advantages" — adapted for parents)
4. Schools/counselors page: how Teenure complements transcript, the
   verified achievement record, how to recommend it to students, the
   Teenure Achievement Record export (from Prompt 5 deliverable 9).
5. Trust/compliance messaging: plain language, real page space.
6. Footer: Privacy Policy and Terms of Service placeholders clearly marked
   "pending legal review" — no actual legal text.

Acceptance criteria:
  - No copy implies Section 1A-prohibited features.
  - Each audience CTA routes to correct signup flow.
  - No signup wall on any marketing page or linked demo.
  - A parent reading this site without an account can answer all five:
    what is Teenure, how does my child earn money, who sees their profile,
    what data is collected, how is my child protected — AND can answer:
    what do I see in the parent portal, and how do I stop my child's
    account if I need to. Seven questions, all answerable without signup.
```

---

## 19. Analytics Integration (PostHog)

**Depends on:** Prompts 6, 9, 12, 13, 6A. Add Prompt 12A events as a
follow-up once 12A is built.

```
Integrate PostHog per Section 6. Self-hosted or EU cloud — state which
and why given minor data handling. Document the choice.

Deliverables:
1. PostHog client initialization: never loads before a user is
   authenticated with an assigned role. Marketing-site analytics (if any)
   are a clearly separate, minimal event set.
2. Data minimization: PostHog never receives PII beyond opaque user ID —
   no email, name, date of birth, school name in event properties.
   Conservative autocapture configuration (explicit event calls preferred
   over blanket DOM autocapture). Document reasoning.
3. Instrument key funnel events:
     - signup started/completed per role
     - parental-consent link clicked
     - parent portal: campaign approved, campaign blocked, values filter
       updated
     - campaign viewed/accepted/declined/submitted/withdrawn (rep side)
     - campaign created/activated (brand side)
     - profile viewed/contacted (recruiter side — aggregate-safe properties
       only, no specific rep identity)
     - demo surfaces: demo page viewed (tagged by which demo), demo CTA
       clicked, demo-to-signup conversion (anonymous ID carried across
       redirect, no PII used for join)
     - (from Prompts 8G/8H/5) module_started, module_passed, module_failed
       (module_id, quiz_score, attempts — no rep identity), badge_earned
       (badge_title, module category — no rep identity), ftc_gate_triggered
       (fires when a rep hits the FTC module gate on campaign accept — a
       critical funnel metric; high volume means reps are ready to accept
       campaigns but haven't completed the module), challenge_submitted
       and challenge_converted (category, bonus_amount — no rep identity),
       goal created, goal completed, achievement link generated,
       achievement link page viewed (this last one fires on the public
       /verified/:token page — it is the only analytics event that fires
       without an authenticated session, and it is aggregate-safe since
       it carries no user identity, only a timestamp and a referrer if
       available)
4. PostHog dashboard for Section 13's six milestones. Wire events for
   milestones 1–4 (milestone 4 — intelligence report sale — is a manual
   sales event, not automatable; note this explicitly rather than
   pretending it is).

Acceptance criteria:
  - Each instrumented event produces a visible PostHog event with no PII
    in properties — verified by inspecting actual payload.
  - Unauthenticated user generates no portal-level events.
```

---

## Changelog

**v1.4** — added Prompt 8G (Skill Challenges): open, unpaid brand-
discovery submissions with a server-enforced pre-submission disclosure
(disclosure_acknowledged required at the API layer, not just UI copy)
and a small platform-funded conversion bonus (CHALLENGE_CONVERSION_BONUS_CENTS,
starting $7.50) paid through the existing Stripe Connect payout path
when a submission converts to a campaign invitation. Added Prompt 8H
(Learning Modules and Verified Badges): admin-curated modules with
server-only quiz answer evaluation (correct_index never sent to any
client, including admin preview), a mandatory FTC Disclosure Essentials
module gating campaign acceptance (POST /campaigns/:id/accept, replacing
the checkbox-only enforcement), a 24-hour retake cooldown, atomic badge
issuance, and a payout_cents/payout_status field on rep_module_completions
left null at MVP to support a future district-funded completion stipend
without a schema migration. Both prompts add parent-dashboard visibility
into challenge and module activity, admin analytics, and PostHog events.
Updated Prompt 15's compliance checklist to items 10–12 (FTC module gate,
module answer security, public achievement link scope). Numbered 8G/8H
to preserve 8C–8F as placeholders for Category Exclusivity, Advance
Cohort Reservation, Rep Syndicates, and the Relationship Continuity
Product, none of which are built yet.

**Build-log note (post-8, design system added)** — Added
[Section 0A: Design System & UX Standards](#0a-design-system--ux-standards),
prompted by a direct assessment that the built Rep Portal frontend
(Prompt 6) was functionally correct but visually indistinguishable from
unstyled shadcn/ui defaults — no color system, type scale, spacing
discipline, or motion beyond framework defaults. For a three-sided
platform whose brand and recruiter sides are professional buyers making
a trust judgment (money, a minor's data) partly from the UI itself
before reading any copy, that's a real product risk, not a cosmetic
one.

0A's authority is Andrew Chen's "Simple Is Marketable" thesis: the same
reductions that make a product feel clean also make it convert (fewer
choices raise completion, shorter paths raise activation, removing a
low-value feature beats merely de-emphasizing it) — design decisions
are evaluated against "what metric or trust signal does this serve,"
which rules out both unstyled defaults and decoration-for-its-own-sake.
The visual bar cited is Stripe/Linear/Vercel-style restraint (confident
typography and whitespace, not ornamentation), since those products
target the same kind of skeptical professional audience Teenure's brand
and recruiter sides represent.

Wired into every remaining frontend-touching prompt (9, 12, 12A, 13,
18) as an explicit dependency, and flagged as an unscheduled retrofit
against Prompt 6/6A's already-built screens — not yet its own numbered
prompt; do the retrofit before or alongside Prompt 9 so the Rep and
Brand portals share one design-token system rather than diverging.

**Build-log note (post-6A, pre-7)** — CI (Prompt 17) and part of the
Testing Suite (Prompt 16) were pulled forward out of order, ahead of
their documented dependencies (16 depends on Prompts 5–14 being
complete; 17 depends on 16). Rationale: Prompts 5 and 6 had only ever
been verified via `pytest` and `next build`/type-check — no route had
been rendered in a real browser, and a stale-cache runtime error on
`/rep` surfaced that gap. Rather than wait until Prompt 16/17's
scheduled slot, a minimal early CI pipeline
(`.github/workflows/ci.yml`) and a Playwright E2E suite
(`apps/web/tests-e2e/`) were added immediately, scoped to what's
buildable without a live Supabase project: the backend suite against a
real ephemeral Postgres service (migrations applied fresh, matching
Prompt 2's schema), a frontend build/type-check job, and browser-driven
smoke coverage of the Prompt 6A demo portal (full click-through, zero
backend network calls) plus the two public `/rep/*` auth pages.

This is explicitly a partial stand-in, not a fulfillment of Prompt 16
or 17 — still outstanding when those prompts are reached in sequence:
lint step, frontend unit tests (Vitest/RTL), the full integration
suites listed in Prompt 16 items 2–4 (campaign lifecycle, parental
consent, parent-portal approval flow, parent-blocked-category
exclusion), Vercel/Railway deploy config, staging environment, and
documented rollback procedure. A local Supabase CLI stack
(`supabase start`, replacing the bare-Postgres
`scripts/local-dev/docker-compose.yml` container for auth-dependent
work) is being wired up next specifically so authenticated E2E flows
(real signup → parental consent → onboarding → accept → submit) can be
exercised before Prompt 16 formally requires it — Prompt 16's own
acceptance criteria already assume "local Supabase" as the integration
target, so this isn't a deviation from that prompt's intent, just
earlier setup of infrastructure it already calls for.

**Build-log note (Supabase CLI follow-up)** — `supabase start` is now
wired up and confirmed working: real signup (`POST /auth/signup`) →
real GoTrue login (`POST /auth/v1/token?grant_type=password`) → an
authenticated `GET /auth/me` call all succeed against the local stack.
Two fixes were needed along the way, both now applied:

1. `supabase/migrations/20260811210000_extensions_and_auth_shim.sql`
   and the `auth.parent_record_id()` function in
   `20260811210400_rls.sql` originally assumed they owned the `auth`
   schema (true only for the bare-Postgres container). Against real
   Supabase-managed Postgres, `auth` is owned by `supabase_auth_admin`
   and these statements failed with `insufficient_privilege`. Fixed by
   wrapping the shim objects in `DO` blocks that treat that error as
   "already provided by the platform," and by moving the
   parent-session helper function (which isn't a real Supabase
   built-in) to `public.parent_record_id()`, a schema we actually own.
2. `apps/api`'s JWT verification (`app/core/security.py`) assumed
   Supabase always signs session JWTs with a single shared HS256
   secret. The local Supabase CLI (and increasingly hosted Supabase
   projects) defaults to per-project asymmetric signing keys (ES256),
   verified via GoTrue's JWKS endpoint instead. `get_current_user` now
   branches on whether the token header carries a `kid`: no `kid` is
   treated as a legacy HS256 token (still how `tests/conftest.py`
   signs its test fixtures, and how the bare-Postgres
   `LocalDevSupabaseAuthClient` path would work if used), and a `kid`
   present fetches and verifies against the matching JWKS key. `cryptography`
   was added to `apps/api/requirements.txt` (PyJWT's ES256 support
   requires it).

Correction to the note above: the bare-Postgres
`scripts/local-dev/docker-compose.yml` stack is not being replaced —
`apps/api/tests/conftest.py` deliberately targets it (port 5434, no
GoTrue) to give `pytest` a fast, isolated database that mirrors CI's
ephemeral Postgres service. The two stacks now coexist for distinct
purposes: bare Postgres for `pytest`/CI, the Supabase CLI stack for
interactive local dev with real signup/login. See the README's "Local
database + auth" section for setup steps.

**Build-log note (authenticated E2E)** — a new `apps/web/tests-e2e-auth/`
Playwright suite (its own config, `playwright.auth.config.ts`) now
drives real signup and login through the browser against a live
`apps/api` + local Supabase Auth stack — not just the backend-free demo
portal. Writing it surfaced a real, previously-undetected bug: every
4xx/5xx response from `apps/api` is shaped `{"error": {"code",
"message"}}` (`apps/api/app/core/errors.py`), but
`apps/web/lib/api.ts`'s `parseError` was reading `body.detail.code` —
a shape that never matched, so every API error in the running app
(age-gate messages, "email already registered", the parent-email-required
branch on signup, resend-consent rate-limiting, etc.) silently fell
back to a generic "Request failed with status NNN" and `err.code` was
always `"unknown_error"`. This had been true since Prompt 4 and was
invisible to `pytest` (which only asserts on the backend's own response
shape) and to `next build`/type-check (both sides type-check fine
independently; the mismatch is a runtime contract bug, not a type
error) — it took an actual browser click-through to catch. Fixed in
`apps/web/lib/api.ts`.

CI gained a new `web-e2e-auth` job (`.github/workflows/ci.yml`) that
installs the Supabase CLI (`supabase/setup-cli@v1`), runs
`supabase start` (applying `supabase/migrations/` fresh, same as local
dev), boots `apps/api` against it, and runs this suite — the existing
`web-e2e` job is unchanged and still covers the demo portal with zero
backend dependency, for fast, always-green baseline coverage even if
the authenticated stack has trouble in CI.

**Build-log note (post-15, Prompt 4A frontend gap)** — Prompt 15's
compliance audit pass confirmed all Section 9 backend enforcement is in
place and produced `docs/compliance-checklist.md` (217 backend tests
passing at time of audit; two named open items: the Stripe Connect
minors onboarding gap self-flagged in `docs/stripe-minors-policy.md`,
and an undefined data-retention policy — plus a test-coverage gap on
independently exercising the parent-approval RLS policy rather than
only the API-layer check).

While scoping Prompt 16's frontend test deliverable (item 4, "parent
portal approve/block actions"), discovered that Prompt 4A deliverable 7
— the parent portal frontend under `apps/web/app/(parent)/` — was never
actually built. Only a placeholder stub existed
(`app/(parent)/parent/page.tsx`); every other Prompt 4A deliverable
(backend routes, RLS, values-filter enforcement, monthly digest,
account controls) shipped and is tested, but the frontend item on that
prompt's own list was missed. This had gone undetected because nothing
in Prompt 15 or 16 up to that point exercised the parent-facing UI —
only the API. Built now as a prerequisite for Prompt 16's frontend tests, out of
sequence, the same way CI/Testing-Suite work was pulled forward after
Prompt 6A (see the build-log note above): magic-link request/verify
screens, dashboard, campaign approval queue (approve/block with a
48-hour countdown), values-filter configuration with plain-language
category descriptions, settings (approval-required toggle with the
under-16-locked state surfaced, digest toggle + preview), account
controls (suspend/unsuspend behind a shared `ConfirmDialog`
generalized out of the recruiter portal's credit-confirm dialog), and
a "what parents see" explainer panel. Parents have no Supabase session
— the portal uses its own token-issuing flow, so it gets a parallel,
non-Supabase API client and session gate (`lib/parent-api.ts`,
`lib/parent-session.ts`, `app/(parent)/layout.tsx`) rather than reusing
`lib/api.ts`/`lib/auth-gate.tsx`. `pnpm tsc --noEmit` and `pnpm build`
both pass.

**Build-log note (post-16, Testing Suite)** — Prompt 16 delivered:
backend coverage audit (`docs/test-coverage-report.md`) closing 12
zero-coverage routes with 20 new tests, all reusing existing fixtures;
3 backend integration tests (`apps/api/tests/test_integration.py`) for
the full campaign lifecycle, parental-consent signup-to-active, and
parent-portal approval/block flows; a new Vitest + React Testing
Library frontend suite (`apps/web/__tests__/`, 5 files, 13 tests)
covering the FTC checkbox gate, credit-spend confirmation, the
age-gate/pending-consent screen, the parent-approval-pending state,
parent portal approve/block, and the available-campaigns
blocked-category exclusion; and a combined `pnpm test:ci`
(`scripts/test-ci.sh`) plus a new `web-unit-tests` CI job running
backend pytest, frontend Vitest, and frontend typecheck together,
verified to exit non-zero on a real failure. Full backend suite: 239
passed. Two real findings surfaced along the way, both already
recorded above: Prompt 4A's parent-portal frontend gap (now closed)
and Prompt 8B's milestone-payments code never having shipped (spec-only
— its own concurrency/idempotency/frontend acceptance criteria have no
code to test against; the flat-campaign confirm path's idempotency
test is used as the closest existing analog, and the milestone-UI
frontend requirement is documented as not-yet-applicable in
`apps/web/__tests__/README.md` rather than silently skipped). Also
fixed, unrelated to test-writing itself: a long-running `next dev`
process had a stale build manifest (every static chunk 404ing, so no
page ever hydrated) after many files were added underneath it —
restarted, verified clean with Playwright.

**v1.3** — companion to Teenure_MVP_Gameplan.md v1.3.
Added Prompt 4A (Parent Portal) as a new build phase between Prompts 4
and 5, establishing the parent campaign-approval gate, values filters,
monthly digest, account controls, and portal expiry at 18. Updated
Prompt 5 to enforce parent approval and values filters in campaign
matching server-side. Updated Prompt 6 to include the prominent
one-tap withdraw button and the parent-approval-pending state in
campaign detail view. Updated Prompt 13 to add parent suspension queue
and safety report queue as first-class admin surfaces. Updated Prompt 15
to audit parent portal data scope. Updated Prompt 16 to include a
parent portal approval flow integration test. Updated Prompt 19 to
instrument parent portal events. Updated Master Context Prompt to
reflect parent role and safety-by-design rule. Updated Prompt 18 to
include a real parents page and a schools/counselors page.

v1.3 note: Prompts 5 and 6 are written as if 4A always came first —
their parent-approval gate, values-filter exclusion, withdraw
endpoint, and pending-approval UI state are native deliverables of
those prompts, not a later patch. Build in order (4A before 5, 5
before 6) and no retrofit step is needed.

**v1.2** — added retry-payment endpoint (Prompt 8), subscription
lifecycle webhooks (Prompt 11), school_type to schema and onboarding
(Prompts 2, 6), null school_type bucketing (Prompt 14), precedence
statement in Master Context Prompt.

**v1.1** — added rep inbox (Prompt 6), backend inbox endpoints (Prompt
11), scheduled-job runner (Prompt 3), 48-hour auto-decline job (Prompt
5), intelligence_events_anonymized migration (Prompt 14), Prompt 13 as
dependency of Prompt 15, mobile-first requirements (Prompts 6, 12),
Prompt 19 (PostHog).

**v1.0** — initial release.
