"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { CampaignSummary, EarningsBreakdown, RepProfile } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatCents, statusLabel } from "@/lib/format";
import { missingFields } from "@/lib/profile-completeness";

export default function RepDashboardPage() {
  const [profile, setProfile] = useState<RepProfile | null>(null);
  const [available, setAvailable] = useState<CampaignSummary[] | null>(null);
  const [active, setActive] = useState<CampaignSummary[] | null>(null);
  const [earnings, setEarnings] = useState<EarningsBreakdown | null>(null);
  const [errors, setErrors] = useState<string[]>([]);

  useEffect(() => {
    const errs: string[] = [];
    Promise.allSettled([
      api.getRepProfile().then(setProfile),
      api.getAvailableCampaigns().then(setAvailable),
      api.getActiveCampaigns().then(setActive),
      api.getEarnings().then(setEarnings),
    ]).then((results) => {
      results.forEach((r) => {
        if (r.status === "rejected") {
          const err = r.reason;
          errs.push(err instanceof ApiError ? String(err.detail ?? err.message) : "Something failed to load.");
        }
      });
      setErrors(errs);
    });
  }, []);

  return (
    <main className="container space-y-6 py-6">
      <h1 className="text-xl font-semibold">Welcome back{profile ? `, ${profile.display_name.split(" ")[0]}` : ""}</h1>

      {errors.length > 0 && (
        <Card className="border-amber-300 bg-amber-50">
          <CardContent className="py-3 text-sm text-amber-800">
            Some data couldn&apos;t load right now: {errors.join(" ")}
          </CardContent>
        </Card>
      )}

      {profile && (
        <Card>
          <CardHeader>
            <CardTitle>Profile completeness: {profile.profile_completeness_score}%</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="mb-3 h-2 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full bg-primary"
                style={{ width: `${Math.min(100, Math.max(0, profile.profile_completeness_score))}%` }}
              />
            </div>
            {missingFields(profile).length === 0 ? (
              <p className="text-sm text-muted-foreground">Your profile is complete.</p>
            ) : (
              <ul className="space-y-1">
                {missingFields(profile).map((f) => (
                  <li key={f.href}>
                    <Link href={f.href} className="text-sm text-primary underline">
                      {f.label}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}

      {earnings && (
        <Card>
          <CardHeader>
            <CardTitle>Earnings</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-3 gap-2 text-center">
            <Stat label="Pending" value={formatCents(earnings.pending_cents)} />
            <Stat label="Confirmed" value={formatCents(earnings.confirmed_cents)} />
            <Stat label="Lifetime" value={formatCents(earnings.lifetime_total_cents)} />
          </CardContent>
        </Card>
      )}

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Active campaigns</h2>
        {active === null && <p className="text-sm text-muted-foreground">Loading…</p>}
        {active?.length === 0 && <p className="text-sm text-muted-foreground">No active campaigns yet.</p>}
        <div className="space-y-3">
          {active?.map((c) => (
            <CampaignCard key={c.campaign_reps_id} campaign={c} />
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Available campaigns</h2>
        {available === null && <p className="text-sm text-muted-foreground">Loading…</p>}
        {available?.length === 0 && <p className="text-sm text-muted-foreground">No available campaigns right now.</p>}
        <div className="space-y-3">
          {available?.map((c) => (
            <CampaignCard key={c.campaign_reps_id} campaign={c} />
          ))}
        </div>
      </section>
    </main>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-lg font-semibold">{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}

function CampaignCard({ campaign }: { campaign: CampaignSummary }) {
  return (
    <Link href={`/rep/campaigns/${campaign.campaign_id}`}>
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-2">
            <CardTitle>{campaign.title}</CardTitle>
            <Badge variant="outline">{statusLabel(campaign.status)}</Badge>
          </div>
          <CardDescription>{campaign.product_name}</CardDescription>
        </CardHeader>
        <CardContent className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">{campaign.deliverables_description}</span>
          {campaign.payout_cents != null && <span className="font-medium">{formatCents(campaign.payout_cents)}</span>}
        </CardContent>
      </Card>
    </Link>
  );
}
