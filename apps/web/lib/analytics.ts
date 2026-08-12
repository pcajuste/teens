"use client";

import posthog from "posthog-js";

// Explicit-event analytics only (Build Prompt 19, deliverable 2).
// autocapture and capture_pageview are disabled by design: every event
// this app ever sends to PostHog is a deliberate, named `trackEvent(...)`
// call with a hand-picked property payload below, never a blanket
// DOM/pageview capture that could sweep up incidental PII (form field
// contents, URLs, click targets). That posture is deliberately
// conservative given the teen user base and CLAUDE.md's "no passive
// behavioral tracking" constraint.
const POSTHOG_KEY = process.env.NEXT_PUBLIC_POSTHOG_KEY;
const POSTHOG_HOST = process.env.NEXT_PUBLIC_POSTHOG_HOST ?? "https://eu.i.posthog.com";

let initialized = false;

function ensureInit() {
  if (initialized || typeof window === "undefined" || !POSTHOG_KEY) return;
  posthog.init(POSTHOG_KEY, {
    api_host: POSTHOG_HOST,
    autocapture: false,
    capture_pageview: false,
    persistence: "localStorage",
  });
  initialized = true;
}

/**
 * Called once from AuthGate, and only after a session exists AND
 * `me.role` has resolved -- never before, and never for an
 * unauthenticated visitor. Identifies the PostHog person by the
 * internal user id only; no email, name, date of birth, or school ever
 * reaches PostHog.
 */
export function identifyPortalUser(userId: string, role: string) {
  ensureInit();
  if (!initialized) return;
  posthog.identify(userId, { role });
}

/**
 * Separate, minimal init path for the small set of pre-auth surfaces that
 * the spec explicitly calls out for instrumentation (signup funnel start,
 * public demo pages). Deliberately does NOT call `identify` -- these stay
 * on PostHog's anonymous distinct_id, which PostHog persists in
 * localStorage so the same anonymous id is carried across a demo -> signup
 * redirect without any PII or query-param plumbing (deliverable 3).
 */
export function initPublicAnalytics() {
  ensureInit();
}

/**
 * Thin capture wrapper. No-ops (rather than throwing) when PostHog hasn't
 * been initialized yet -- e.g. any page that hasn't called
 * `identifyPortalUser`/`initPublicAnalytics`, or when
 * NEXT_PUBLIC_POSTHOG_KEY isn't configured in this environment -- so no
 * page ever breaks because analytics is inactive.
 */
export function trackEvent(name: string, properties?: Record<string, unknown>) {
  if (!initialized || typeof window === "undefined") return;
  posthog.capture(name, properties);
}
