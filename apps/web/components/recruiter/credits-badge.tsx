"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { api, ApiError } from "@/lib/api";
import type { RecruiterCredits } from "@/lib/types";

/** Small persistent credit-balance readout, reused wherever a recruiter
 * needs to see (or be reminded of) their remaining contact credits --
 * search results, saved lists, messaging. Pass `refreshKey` to force a
 * re-fetch after a credit-spending action completes (view profile /
 * contact) so the number on screen never lags the server-side truth
 * (Section 9: never a locally-decremented counter). */
export function CreditsBadge({ refreshKey }: { refreshKey?: number }) {
  const [credits, setCredits] = useState<RecruiterCredits | null>(null);

  useEffect(() => {
    api
      .get<RecruiterCredits>("/recruiters/credits")
      .then(setCredits)
      .catch((err) => {
        // recruiter_profile_not_found (pre-onboarding) is expected here;
        // anything else just leaves the badge blank rather than erroring
        // out a page whose main content doesn't depend on this widget.
        if (!(err instanceof ApiError)) {
          // no-op
        }
      });
  }, [refreshKey]);

  if (credits === null) return null;

  return (
    <Badge
      variant={credits.low_credit_warning ? "warning" : "outline"}
      className="px-3 py-1.5"
    >
      {credits.contact_credits_remaining} credit
      {credits.contact_credits_remaining === 1 ? "" : "s"} remaining
      {credits.low_credit_warning ? " · low" : ""}
    </Badge>
  );
}
