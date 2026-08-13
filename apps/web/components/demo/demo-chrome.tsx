"use client";

import Link from "next/link";
import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { initPublicAnalytics, trackEvent } from "@/lib/analytics";

/**
 * Fires the "demo page viewed" event on mount, tagged by which demo. A
 * standalone client component so the server-component demo pages (some
 * of which export `generateStaticParams`) don't have to become client
 * components themselves just to instrument a page-view.
 */
export function DemoPageViewTracker({ demo }: { demo: string }) {
  useEffect(() => {
    initPublicAnalytics();
    trackEvent("demo_page_viewed", { demo });
  }, [demo]);
  return null;
}

// Shared chrome for every screen under /demo/talent. Fully static, no
// client-side state, no network calls -- this whole route group must
// render with zero authenticated session and zero dependency on the
// FastAPI backend.
export function DemoBanner() {
  return (
    <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-center text-sm font-medium text-amber-800 dark:text-amber-300">
      Demo — this is example data. &quot;Maya Chen,&quot; her school, and every
      campaign shown here are fictional.
    </div>
  );
}

export function StartBuildingYoursButton({
  className,
}: {
  className?: string;
}) {
  return (
    <Link
      href="/talent/signup"
      className={className}
      onClick={() => trackEvent("demo_cta_clicked", { demo: "talent" })}
    >
      {/* Links straight into the real age-gated signup flow (Build
          Prompt 4) -- no query params, no alternate entry point, no way
          to skip the age gate or parental consent from here. PostHog's
          anonymous distinct_id is persisted in localStorage, so this
          click is the demo-to-signup conversion link -- no PII or query
          param is needed to carry it across the redirect. */}
      <Button className="h-11 w-full">Start building yours</Button>
    </Link>
  );
}

export function DemoBackLink({ href, label }: { href: string; label: string }) {
  return (
    <Link href={href} className="text-sm font-medium underline">
      {label}
    </Link>
  );
}
