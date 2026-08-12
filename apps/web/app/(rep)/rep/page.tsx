"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AvailableCampaignCard, ActiveCampaignCard } from "@/components/rep/campaign-cards";
import { ChallengesDiscoveryPanel, SubmittedChallengesPanel } from "@/components/rep/challenges-panel";
import { EarningsPanel } from "@/components/rep/earnings-panel";
import { CompletenessPanel } from "@/components/rep/completeness-panel";
import { RepShell } from "@/components/rep/rep-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import type {
  CampaignParticipation,
  CampaignSummary,
  Earnings,
  RepAvailableChallenge,
  RepProfile,
  RepSubmittedChallenge,
} from "@/lib/types";

export default function RepDashboardPage() {
  const [profile, setProfile] = useState<RepProfile | null>(null);
  const [available, setAvailable] = useState<CampaignSummary[]>([]);
  const [active, setActive] = useState<CampaignParticipation[]>([]);
  const [earnings, setEarnings] = useState<Earnings | null>(null);
  const [availableChallenges, setAvailableChallenges] = useState<RepAvailableChallenge[]>([]);
  const [submittedChallenges, setSubmittedChallenges] = useState<RepSubmittedChallenge[]>([]);
  const [needsOnboarding, setNeedsOnboarding] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const [profileRes, availableRes, activeRes, earningsRes, availableChallengesRes, submittedChallengesRes] =
        await Promise.all([
          api.get<RepProfile>("/reps/me"),
          api.get<CampaignSummary[]>("/reps/campaigns/available"),
          api.get<CampaignParticipation[]>("/reps/campaigns/active"),
          api.get<Earnings>("/reps/earnings"),
          api.get<RepAvailableChallenge[]>("/reps/challenges/available"),
          api.get<RepSubmittedChallenge[]>("/reps/challenges/submitted"),
        ]);
      setProfile(profileRes);
      setAvailable(availableRes);
      setActive(activeRes);
      setEarnings(earningsRes);
      setAvailableChallenges(availableChallengesRes);
      setSubmittedChallenges(submittedChallengesRes);
    } catch (err) {
      if (err instanceof ApiError && err.code === "rep_profile_not_found") {
        setNeedsOnboarding(true);
        return;
      }
      setError(err instanceof ApiError ? err.message : "Could not load your dashboard.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (needsOnboarding) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-secondary/30 p-6 text-center">
        <h1 className="text-xl font-semibold tracking-tight">Finish setting up your profile</h1>
        <p className="max-w-sm text-sm text-muted-foreground">
          A few quick details and you&apos;re ready to see campaigns matched to you.
        </p>
        <Link href="/rep/onboarding">
          <Button size="lg">Start onboarding</Button>
        </Link>
      </main>
    );
  }

  const titleFor = (campaignId: string) =>
    available.find((c) => c.id === campaignId)?.title ?? "Campaign";

  return (
    <RepShell title="Your dashboard">
      <div className="flex flex-col gap-8">
        {error ? (
          <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
        ) : null}

        {loading ? (
          <div className="flex flex-col gap-6">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-2">
              {profile ? (
                <Card className="p-5">
                  <CompletenessPanel profile={profile} />
                </Card>
              ) : null}

              {earnings ? (
                <Card className="p-5">
                  <p className="mb-2 text-sm font-semibold text-muted-foreground">Earnings</p>
                  <EarningsPanel earnings={earnings} />
                </Card>
              ) : null}
            </div>

            <section className="flex flex-col gap-3">
              <h2 className="text-sm font-semibold text-muted-foreground">Active campaigns</h2>
              {active.length === 0 ? (
                <EmptyState
                  title="No active campaigns yet"
                  description="Accepted campaigns will show up here with their current status."
                />
              ) : (
                <div className="flex flex-col gap-3">
                  {active.map((cr) => (
                    <ActiveCampaignCard
                      key={cr.campaign_id}
                      participation={cr}
                      title={titleFor(cr.campaign_id)}
                      onWithdrawn={load}
                    />
                  ))}
                </div>
              )}
            </section>

            <section className="flex flex-col gap-3">
              <h2 className="text-sm font-semibold text-muted-foreground">Available campaigns</h2>
              {available.length === 0 ? (
                <EmptyState
                  title="No campaigns match your profile right now"
                  description="Check back soon, or improve your profile completeness to widen your matches."
                />
              ) : (
                <div className="flex flex-col gap-3">
                  {available.map((c) => (
                    <AvailableCampaignCard key={c.id} campaign={c} />
                  ))}
                </div>
              )}
            </section>

            <SubmittedChallengesPanel submissions={submittedChallenges} />
            <ChallengesDiscoveryPanel challenges={availableChallenges} />
          </>
        )}
      </div>
    </RepShell>
  );
}
