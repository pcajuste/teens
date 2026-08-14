"use client";

import { useEffect, useState } from "react";
import { ParentShell } from "@/components/parent/parent-shell";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { parentApi, ParentApiError } from "@/lib/parent-api";
import { SPORT_LABELS, seasonStatusDisplay, type SupportedSport } from "@/lib/sports";
import type { ParentAthleticSummary } from "@/lib/types";

// ATHLETICS-8 deliverable 4: read-only. The parent has no route to
// approve/block a season or affect coach attestation -- athletic
// records aren't a commercial transaction like a brand campaign, so
// there's nothing here to act on, only to see.
export default function ParentAthleticsPage() {
  const [summary, setSummary] = useState<ParentAthleticSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    parentApi
      .get<ParentAthleticSummary>("/parent/athletics")
      .then(setSummary)
      .catch((err) => setError(err instanceof ParentApiError ? err.message : "Could not load athletics."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <ParentShell title="Athletics">
        <Skeleton className="h-40 w-full" />
      </ParentShell>
    );
  }

  if (error) {
    return (
      <ParentShell title="Athletics">
        <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
      </ParentShell>
    );
  }

  if (!summary || !summary.athletics_enabled) {
    return (
      <ParentShell title="Athletics">
        <Card>
          <CardContent>
            <p className="text-base font-medium">The athletic track isn&rsquo;t enabled yet.</p>
            <p className="mt-2 text-sm text-text-2">
              Teenure&rsquo;s athletic track lets your teen build a coach-verified record of sport seasons,
              stats, and achievements alongside their brand work. Your teen can enable it from their own
              portal — there&rsquo;s nothing for you to set up.
            </p>
          </CardContent>
        </Card>
      </ParentShell>
    );
  }

  return (
    <ParentShell title="Athletics">
      {summary.nil_eligibility ? (
        <Card>
          <CardContent>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-text-2">NIL eligibility</h2>
            <div className="mt-2 flex items-center gap-2">
              <Badge variant={summary.nil_eligibility.nil_eligible_in_state ? "done" : "pending"}>
                {summary.nil_eligibility.nil_eligible_in_state ? "Eligible" : "Not eligible"} in{" "}
                {summary.nil_eligibility.state}
              </Badge>
              <Badge variant={summary.nil_eligibility.school_association_rules_acknowledged ? "done" : "pending"}>
                {summary.nil_eligibility.school_association_rules_acknowledged
                  ? "Rules acknowledged"
                  : "Rules not yet acknowledged"}
              </Badge>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardContent>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-text-2">Sport profiles</h2>
          {summary.sport_profiles.length === 0 ? (
            <p className="mt-2 text-sm text-text-2">No sport profiles yet.</p>
          ) : (
            <div className="mt-3 flex flex-col gap-3">
              {summary.sport_profiles.map((sp) => (
                <div key={sp.id} className="rounded-lg border border-border-muted p-3">
                  <p className="font-medium">{SPORT_LABELS[sp.sport as SupportedSport] ?? sp.sport}</p>
                  {sp.positions.length > 0 ? (
                    <p className="mt-1 text-sm text-text-2">{sp.positions.join(", ")}</p>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-text-2">Recent seasons</h2>
          {summary.recent_seasons.length === 0 ? (
            <p className="mt-2 text-sm text-text-2">No seasons recorded yet.</p>
          ) : (
            <div className="mt-3 flex flex-col gap-3">
              {summary.recent_seasons.map((s) => {
                const chip = seasonStatusDisplay(s);
                return (
                  <div key={s.id} className="rounded-lg border border-border-muted p-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-medium">
                        {SPORT_LABELS[s.sport as SupportedSport] ?? s.sport} · {s.season_year}
                      </p>
                      <Badge variant={chip.variant}>{chip.label}</Badge>
                    </div>
                    <p className="mt-1 text-sm text-text-2">
                      {s.team_name} · {s.level}
                    </p>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </ParentShell>
  );
}
