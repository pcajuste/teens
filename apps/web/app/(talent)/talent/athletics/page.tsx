"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AthleticCompletenessPanel } from "@/components/talent/athletic-completeness-panel";
import { SeasonStatusChip } from "@/components/talent/season-status-chip";
import { TalentShell } from "@/components/talent/talent-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import { SEASON_TYPE_LABELS, SPORT_LABELS, type SupportedSport } from "@/lib/sports";
import type { AthleticProfileSummary } from "@/lib/types";

/**
 * ATHLETICS-6 dashboard: unlike every other /talent/athletics/* page,
 * this one does NOT redirect when the track is disabled -- the spec is
 * explicit that the disabled state renders inline here (an enable-track
 * card with a CTA), while every *sub*-page redirects to /enable.
 *
 * Uses GET /talents/athletics/summary (single call, no track-gate 403 --
 * returns nil_eligibility: null when athletics isn't enabled yet) rather
 * than assembling the dashboard from /talents/me + sports + seasons +
 * nil separately.
 */
export default function AthleticDashboardPage() {
  const [summary, setSummary] = useState<AthleticProfileSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<AthleticProfileSummary>("/talents/athletics/summary")
      .then(setSummary)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load your athletic profile."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <TalentShell title="Athletics">
        <Skeleton className="h-48 w-full" />
      </TalentShell>
    );
  }

  if (error) {
    return (
      <TalentShell title="Athletics">
        <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
      </TalentShell>
    );
  }

  if (!summary?.enabled_tracks.includes("athletics")) {
    return (
      <TalentShell title="Athletics">
        <Card className="flex flex-col gap-3 border-2 border-teal-border bg-teal-dim/40 p-6 text-center">
          <h2 className="text-lg font-semibold">Build your athletic record</h2>
          <p className="text-sm text-muted-foreground">
            Track your seasons, get your coach to verify your stats, and get discovered by
            college programs -- separate from your brand profile.
          </p>
          <Link href="/talent/athletics/enable">
            <Button size="lg" className="w-full">
              Set up my athletic profile
            </Button>
          </Link>
        </Card>
      </TalentShell>
    );
  }

  const { sport_profiles: sportProfiles, recent_seasons: recentSeasons, nil_eligibility: nil } = summary;

  return (
    <TalentShell title="Athletics">
      <div className="flex flex-col gap-8">
        <Card className="p-5">
          <AthleticCompletenessPanel
            score={summary.athletic_completeness_score}
            sportProfiles={sportProfiles}
            seasons={recentSeasons}
            nil={nil}
          />
        </Card>

        {/* Never show the count as 0 -- omit the field entirely (spec:
           "Industry reference: LinkedIn omits '0 profile views' entirely"). */}
        {summary.athletic_recruiter_interest_count > 0 ? (
          <Card className="border-teal-border bg-teal-dim p-4 text-sm font-medium text-teal">
            {summary.athletic_recruiter_interest_count} college program
            {summary.athletic_recruiter_interest_count === 1 ? " has" : "s have"} expressed interest
          </Card>
        ) : null}

        <section className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-muted-foreground">Recent seasons</h2>
            <Link href="/talent/athletics/seasons" className="text-sm font-medium text-teal hover:underline">
              View all
            </Link>
          </div>
          {recentSeasons.length === 0 ? (
            <EmptyState
              title="No seasons yet"
              description="Add your first season to start building your athletic record."
            />
          ) : (
            <div className="flex flex-col gap-2">
              {recentSeasons.map((s) => (
                <Link key={s.id} href={`/talent/athletics/seasons/${s.id}`}>
                  <Card className="flex flex-row items-center justify-between gap-2 p-4">
                    <div>
                      <p className="text-sm font-semibold">
                        {SPORT_LABELS[s.sport as SupportedSport] ?? s.sport} · {s.season_year}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {s.team_name} · {SEASON_TYPE_LABELS[s.season_type as keyof typeof SEASON_TYPE_LABELS] ?? s.season_type}
                      </p>
                    </div>
                    <SeasonStatusChip season={s} />
                  </Card>
                </Link>
              ))}
            </div>
          )}
          <Link href="/talent/athletics/seasons/new">
            <Button variant="outline" className="w-full">
              Add a season
            </Button>
          </Link>
        </section>

        <section className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-muted-foreground">Sport profiles</h2>
            <Link href="/talent/athletics/sports" className="text-sm font-medium text-teal hover:underline">
              Manage
            </Link>
          </div>
          {sportProfiles.length === 0 ? (
            <EmptyState title="No sports set up yet" description="Add a sport to start tracking your stats." />
          ) : (
            <div className="flex flex-col gap-2">
              {sportProfiles.map((sp) => (
                <Card key={sp.id} className="flex flex-row items-center justify-between gap-2 p-4">
                  <div>
                    <p className="text-sm font-semibold">{SPORT_LABELS[sp.sport as SupportedSport] ?? sp.sport}</p>
                    <p className="text-xs text-muted-foreground">
                      {sp.gpa !== null ? `GPA ${sp.gpa.toFixed(2)}` : "No GPA added"}
                    </p>
                  </div>
                  {sp.hudl_url || sp.maxpreps_url ? (
                    <Badge variant="done">Film linked</Badge>
                  ) : (
                    <Badge variant="pending">No film</Badge>
                  )}
                </Card>
              ))}
            </div>
          )}
        </section>

        <section className="flex flex-col gap-2">
          <h2 className="text-sm font-semibold text-muted-foreground">NIL eligibility</h2>
          <Link href="/talent/athletics/nil">
            <Card className="flex flex-row items-center justify-between gap-2 p-4">
              <div>
                <p className="text-sm font-semibold">{nil?.state}</p>
                <p className="text-xs text-muted-foreground">
                  {nil?.school_association_rules_acknowledged ? "Rules acknowledged" : "Not yet acknowledged"}
                </p>
              </div>
              <Badge variant={nil?.nil_eligible_in_state ? "done" : "pending"}>
                {nil?.nil_eligible_in_state ? "NIL Eligible" : "Not Eligible"}
              </Badge>
            </Card>
          </Link>
        </section>
      </div>
    </TalentShell>
  );
}
