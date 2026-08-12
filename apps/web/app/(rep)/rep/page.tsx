"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AvailableCampaignCard, ActiveCampaignCard } from "@/components/rep/campaign-cards";
import { EarningsPanel } from "@/components/rep/earnings-panel";
import { CompletenessPanel } from "@/components/rep/completeness-panel";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import type { CampaignParticipation, CampaignSummary, Earnings, RepProfile } from "@/lib/types";

export default function RepDashboardPage() {
  const { signOut } = useAuth();
  const [profile, setProfile] = useState<RepProfile | null>(null);
  const [available, setAvailable] = useState<CampaignSummary[]>([]);
  const [active, setActive] = useState<CampaignParticipation[]>([]);
  const [earnings, setEarnings] = useState<Earnings | null>(null);
  const [needsOnboarding, setNeedsOnboarding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const [profileRes, availableRes, activeRes, earningsRes] = await Promise.all([
        api.get<RepProfile>("/reps/me"),
        api.get<CampaignSummary[]>("/reps/campaigns/available"),
        api.get<CampaignParticipation[]>("/reps/campaigns/active"),
        api.get<Earnings>("/reps/earnings"),
      ]);
      setProfile(profileRes);
      setAvailable(availableRes);
      setActive(activeRes);
      setEarnings(earningsRes);
    } catch (err) {
      if (err instanceof ApiError && err.code === "rep_profile_not_found") {
        setNeedsOnboarding(true);
        return;
      }
      setError(err instanceof ApiError ? err.message : "Could not load your dashboard.");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (needsOnboarding) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-6 text-center">
        <h1 className="text-xl font-semibold">Finish setting up your profile</h1>
        <Link href="/rep/onboarding">
          <Button className="h-11">Start onboarding</Button>
        </Link>
      </main>
    );
  }

  const titleFor = (campaignId: string) =>
    available.find((c) => c.id === campaignId)?.title ?? "Campaign";

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col gap-6 p-4 pb-16">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Your dashboard</h1>
        <div className="flex gap-2">
          <Link href="/rep/profile-preview" className="text-sm font-medium underline">
            Preview
          </Link>
          <button onClick={() => signOut()} className="text-sm text-muted-foreground underline">
            Sign out
          </button>
        </div>
      </header>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      {profile ? (
        <section>
          <CompletenessPanel profile={profile} />
        </section>
      ) : null}

      {earnings ? (
        <section className="flex flex-col gap-2">
          <h2 className="text-sm font-semibold text-muted-foreground">Earnings</h2>
          <EarningsPanel earnings={earnings} />
        </section>
      ) : null}

      <section className="flex flex-col gap-2">
        <h2 className="text-sm font-semibold text-muted-foreground">Active campaigns</h2>
        {active.length === 0 ? (
          <p className="text-sm text-muted-foreground">No active campaigns yet.</p>
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

      <section className="flex flex-col gap-2">
        <h2 className="text-sm font-semibold text-muted-foreground">Available campaigns</h2>
        {available.length === 0 ? (
          <p className="text-sm text-muted-foreground">No campaigns match your profile right now.</p>
        ) : (
          <div className="flex flex-col gap-3">
            {available.map((c) => (
              <AvailableCampaignCard key={c.id} campaign={c} />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
