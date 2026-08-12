# TEENURE — AI Builder Prompt Suite v1.3

> Companion to `Teenure_MVP_Gameplan.md` (the spec of record). That document is the source of truth for schema, routes, business rules, and legal constraints — this document sequences the build into discrete, verbatim prompts an AI coding assistant can execute one at a time, in order.
>
> **How to use this file:** Paste the Master Context Prompt once at the start of a build session (or keep it in the assistant's persistent context). Then paste each numbered prompt in order, one at a time. Do not start prompt N+1 until prompt N's acceptance criteria are met. Do not skip prompts or reorder phases — the dependency chain is explicit in each prompt's "Depends on" line.

---

## Table of Contents

0. [Master Context Prompt](#0-master-context-prompt)
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

## 4A. Parent Portal

**Depends on:** Prompt 4. Canonically sits between Prompts 4 and 5 in
the build sequence — the parent campaign-approval gate and values-filter
exclusion in Prompt 5 depend on the parent_service functions this
prompt implements. Because this prompt is built before Prompt 5 in this
repo, Prompt 5's parent-approval gate, values-filter exclusion, and
withdraw endpoint (its own deliverables 3, 7, and 9) are native parts of
its original implementation — there is no retrofit step here or in
Prompt 5/6; build each prompt once, in order, using the parent_service
functions this prompt creates.

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

## 7. Stripe Foundation: Connect Onboarding & Platform Billing

**Depends on:** Prompt 4. Can run parallel to Prompts 5–6.

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

## 8. Brand Portal — Backend

**Depends on:** Prompt 5, Prompt 7.

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

## 9. Brand Portal — Frontend

**Depends on:** Prompt 8.

```
Build the Brand Portal under apps/web/app/(brand)/.

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

## 10. Campaign Lifecycle & Payout Engine

**Depends on:** Prompt 7, Prompt 8.

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

**Depends on:** Prompt 11.

```
Build the Recruiter Portal under apps/web/app/(recruiter)/.

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
data), Prompt 10 (for earnings history if needed). Placed after the real
Recruiter Portal — reuses Prompt 11's actual search endpoint against seed
data rather than building a parallel fake version.

```
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

**Depends on:** Prompts 4, 4A, 8, 10, 11.

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

## 15. Compliance Audit Pass

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

## 16. Testing Suite

**Depends on:** all functional prompts (5–14). Build incrementally
alongside them; this prompt is the consolidation pass.

```
Consolidate and fill gaps in automated test coverage.

Deliverables:
1. Backend (pytest): every Section 8 route has at least one happy-path
   test, one role-enforcement rejection test, one primary business-rule
   rejection test. Coverage report — flag any route with zero tests.
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
   verification alone).
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

**Depends on:** Prompt 1. Can build any time in parallel. Link to Prompt
6A/12A demo experiences if already built; otherwise build CTAs to signup
and add demo links once 6A/12A exist.

```
Build the public marketing site under apps/web/app/(marketing)/.

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
