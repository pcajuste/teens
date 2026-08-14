"use client";

import { useEffect, useState } from "react";
import { AthleticsGate } from "@/components/talent/athletics-gate";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import type { NilEligibility } from "@/lib/types";

export default function NilPage() {
  return <AthleticsGate title="NIL eligibility" backHref="/talent/athletics" render={() => <NilContent />} />;
}

function NilContent() {
  const [nil, setNil] = useState<NilEligibility | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  function load() {
    api
      .get<NilEligibility>("/talents/athletics/nil")
      .then(setNil)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load your NIL status."));
  }

  useEffect(load, []);

  async function handleAcknowledge() {
    setPending(true);
    setError(null);
    try {
      const updated = await api.post<NilEligibility>("/talents/athletics/nil/acknowledge");
      setNil(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not record your acknowledgment.");
    } finally {
      setPending(false);
    }
  }

  if (error) {
    return <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>;
  }

  if (!nil) {
    return <Skeleton className="h-48 w-full" />;
  }

  return (
    <div className="flex flex-col gap-6">
      {nil.nil_eligible_in_state ? (
        <Card className="flex flex-col gap-3 p-5">
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm font-semibold">{nil.state}</p>
            <Badge variant="done">NIL Eligible</Badge>
          </div>

          {nil.school_association_rules_acknowledged ? (
            <div className="flex flex-col gap-1">
              <p className="flex items-center gap-1.5 text-sm font-medium text-green">
                <span aria-hidden="true">✓</span> Rules acknowledged
              </p>
              {nil.acknowledged_at ? (
                <p className="text-xs text-muted-foreground">
                  Acknowledged {new Date(nil.acknowledged_at).toLocaleDateString()}
                </p>
              ) : null}
              <p className="text-xs text-muted-foreground">
                College brand deals require this acknowledgment.
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              <p className="text-sm text-muted-foreground">
                By acknowledging, you confirm you understand your state&apos;s NIL rules and any
                school-association restrictions before accepting a paid brand deal tied to your
                athletic profile.
              </p>
              <Button disabled={pending} onClick={handleAcknowledge}>
                {pending ? "Saving…" : "Acknowledge NIL Rules"}
              </Button>
            </div>
          )}
        </Card>
      ) : (
        <Card className="flex flex-col gap-3 p-5">
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm font-semibold">{nil.state}</p>
            <Badge variant="pending">NIL Not Currently Permitted</Badge>
          </div>
          <p className="text-sm text-muted-foreground">
            State law governs whether high school athletes can pursue NIL deals, and{" "}
            {nil.state} does not currently permit it.
          </p>
          <p className="text-sm text-muted-foreground">
            Your athletic profile can still be discovered by college coaches for recruiting
            purposes. NIL restrictions only apply to paid brand deals.
          </p>
        </Card>
      )}

      {/* Interpreted gap: the ATHLETICS-6 spec says "Link to
         /public/nil-rules for reference" -- GET /public/nil-rules is an
         unauthenticated API endpoint (apps/api/app/routers/public.py),
         not yet backed by any frontend page in apps/web (out of
         ATHLETICS-6's scope, which only covers the talent-facing
         athletics route group). Linking straight at the API URL rather
         than inventing an unscoped public page or a dead internal
         route. */}
      <a
        href={`${process.env.NEXT_PUBLIC_API_URL ?? ""}/public/nil-rules`}
        target="_blank"
        rel="noreferrer"
        className="text-sm font-medium text-teal hover:underline"
      >
        See the full state-by-state NIL list →
      </a>
    </div>
  );
}
