"use client";

import { Button } from "@/components/ui/button";
import { trackEvent } from "@/lib/analytics";

const SCHEDULING_URL = process.env.NEXT_PUBLIC_DEMO_SCHEDULING_URL || "mailto:brands@teenure.dev";

// Build Prompt 12A part 2: the brand sales page's only CTA. Deliberately
// not a Link into any signup/campaign-builder route -- opens Calendly (or
// whatever scheduling tool is configured) in a new tab, or falls back to
// a plain mailto if no scheduling link is set.
export function ScheduleDemoButton() {
  return (
    <a
      href={SCHEDULING_URL}
      target="_blank"
      rel="noopener noreferrer"
      onClick={() => trackEvent("demo_cta_clicked", { demo: "brand" })}
    >
      <Button size="lg">Schedule a demo</Button>
    </a>
  );
}
