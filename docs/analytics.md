# Analytics (PostHog)

Implements Build Prompt 19 ("Analytics Integration (PostHog)"). Client-side
only, per Section 6's "Analytics: PostHog" and the deliverable-1 wording
("PostHog client initialization") -- `apps/api` does not use `posthog-node`.

## Self-hosted vs. cloud: PostHog EU Cloud

**Decision: PostHog EU Cloud**, not self-hosted.

Reasoning:
- Teenure has no dedicated infra team at MVP stage (Section 6's stack is
  Vercel + Railway + Supabase -- all managed services). Self-hosting
  PostHog would add a service to operate, patch, and scale for no
  benefit at this scale.
- Teenure's user base includes minors. EU Cloud keeps event data
  in-region under GDPR-aligned handling without Teenure having to build
  or maintain that infrastructure itself.
- Event volume and query needs at MVP (a handful of funnel events per
  user session, Section 13 milestone tracking) do not require anything
  self-hosting would offer over the managed product.

## Data minimization

- **Explicit events only.** `posthog.init()` (in `apps/web/lib/analytics.ts`)
  sets `autocapture: false` and `capture_pageview: false`. Every event sent
  to PostHog is a hand-written `trackEvent(name, properties)` call at a
  specific, reviewed call site -- never a blanket DOM-click or page-view
  capture that could sweep up incidental PII (form contents, URLs,
  click targets). This matches CLAUDE.md's "no passive behavioral
  tracking" constraint.
- **Opaque identity only.** `identifyPortalUser(userId, role)` identifies
  the PostHog person by the internal Teenure user id (`me.id`) and role
  only. Email, name, date of birth, and school name are never sent to
  PostHog, in `identify()` calls or in any event property.
- **Gated init.** The PostHog client is only initialized/identified from
  inside `AuthGate` (`apps/web/lib/auth-gate.tsx`), and only once a real
  session exists AND `me.role` has resolved to match the portal being
  rendered. An unauthenticated visitor to any portal route never
  triggers `identify` or any portal-level event.
- **Separate, minimal public-surface path.** Signup pages and the public
  `/demo/rep` surfaces use `initPublicAnalytics()` instead -- a small,
  clearly separate event set (`signup_started`, `signup_completed`,
  `parental_consent_requested`, `demo_page_viewed`, `demo_cta_clicked`)
  that stays on PostHog's anonymous `distinct_id` and never calls
  `identify`. PostHog persists that anonymous id in `localStorage`, so a
  demo -> signup redirect carries it forward with no query params or PII
  needed to link the two.
- **No-op fallback.** `trackEvent()` no-ops (never throws) when PostHog
  hasn't been initialized -- e.g. `NEXT_PUBLIC_POSTHOG_KEY` unset in an
  environment, or a page rendered before any init call has run.

## Instrumented events

| Event | Where | Notes |
|---|---|---|
| `signup_started` / `signup_completed` | rep/brand/recruiter signup pages | tagged `role` |
| `parental_consent_requested` | rep signup, `account_status === "pending"` | proxy for the parent's email-link click -- there is no separate consent-landing frontend route in this repo to instrument the click itself |
| `parent_campaign_approved` / `parent_campaign_blocked` | parent campaign approvals page | `campaign_id` only |
| `parent_values_filter_updated` | parent filters page | `filter_count` only |
| `campaign_viewed` | rep campaign detail, on mount | `campaign_id` |
| `campaign_accepted` / `campaign_declined` / `campaign_submitted` / `campaign_withdrawn` | rep campaign detail + withdraw button | `campaign_id`, `categories` |
| `campaign_created` / `campaign_activated` | brand new-campaign / campaign detail | `campaign_id`, `categories` |
| `recruiter_profile_viewed` / `recruiter_profile_contacted` | recruiter search page | aggregate-safe only -- `categories`, no rep id or name |
| `demo_page_viewed` | `/demo/rep`, `/demo/rep/campaigns/[id]` | tagged by `demo` surface |
| `demo_cta_clicked` | "Start building yours" button | anonymous id carries into `/rep/signup` |

## Section 13 milestones (dashboard note)

PostHog dashboards/insights should be built from the events above for
milestones 1-4:

1. **10 reps, complete profiles, one city** -- not a PostHog funnel event;
   query Supabase `rep_profiles` directly (completeness + city), PostHog
   isn't the source of truth for profile state.
2. **First brand pays $300+, campaign confirmed** -- `campaign_activated`
   (payment initiated) funneled against campaign-completion state from
   the backend; PostHog can show the funnel from `signup_started` (brand)
   through `campaign_created` -> `campaign_activated`.
3. **First admissions officer asks for more profiles** -- not
   automatable from product events; qualitative/sales signal.
4. **First brand pays for intelligence data independent of a campaign**
   -- **explicitly a manual, non-automatable sales event.** There is no
   frontend flow for this in the current build (no self-serve
   intelligence-report purchase surface exists), so no event is faked
   for it. Track it manually (e.g. a note in the sales pipeline) rather
   than pretending a product event represents it.

Milestones 5 (`$10k in a month across revenue streams`) and 6 (`a 14-year-old
rep uses their profile in a college application`) are out of scope for this
event set -- 5 is a revenue rollup better computed from Stripe/billing data,
and 6 has no frontend-observable signal at all.
