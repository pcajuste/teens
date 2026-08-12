"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { BrandShell } from "@/components/brand/brand-shell";
import { api, ApiError } from "@/lib/api";
import type { Campaign, CampaignStatus } from "@/lib/types";

const STATUS_VARIANT: Record<CampaignStatus, "default" | "secondary" | "warning" | "success" | "destructive" | "outline"> = {
  draft: "outline",
  pending_payment: "secondary",
  payment_failed: "destructive",
  active: "success",
  paused: "warning",
  completed: "secondary",
  cancelled: "outline",
};

const STATUS_LABEL: Record<CampaignStatus, string> = {
  draft: "Draft",
  pending_payment: "Payment pending",
  payment_failed: "Payment failed",
  active: "Active",
  paused: "Paused",
  completed: "Completed",
  cancelled: "Cancelled",
};

function money(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

export default function BrandDashboardPage() {
  const [campaigns, setCampaigns] = useState<Campaign[] | null>(null);
  const [needsOnboarding, setNeedsOnboarding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<Campaign[]>("/brands/campaigns")
      .then(setCampaigns)
      .catch((err) => {
        if (err instanceof ApiError && err.code === "brand_profile_not_found") {
          setNeedsOnboarding(true);
          return;
        }
        setError(err instanceof ApiError ? err.message : "Could not load your campaigns.");
      });
  }, []);

  if (needsOnboarding) {
    return (
      <BrandShell>
        <div className="flex flex-col items-center gap-4 py-16 text-center">
          <h1 className="text-xl font-semibold tracking-tight">Finish setting up your company profile</h1>
          <p className="max-w-sm text-sm text-muted-foreground">
            A few details about your company, then you&apos;re ready to create your first campaign.
          </p>
          <Link href="/brand/onboarding">
            <Button size="lg">Complete company profile</Button>
          </Link>
        </div>
      </BrandShell>
    );
  }

  return (
    <BrandShell
      title="Campaigns"
      action={
        <Link href="/brand/campaigns/new">
          <Button size="lg">New campaign</Button>
        </Link>
      }
    >
      {error ? <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p> : null}

      {campaigns === null ? (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-28 w-full" />
        </div>
      ) : campaigns.length === 0 ? (
        <EmptyState
          title="No campaigns yet"
          description="Create your first campaign brief to start matching with reps."
          action={
            <Link href="/brand/campaigns/new">
              <Button>Create a campaign</Button>
            </Link>
          }
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {campaigns.map((c) => (
            <Link key={c.id} href={`/brand/campaigns/${c.id}`}>
              <Card className="hover:border-primary/30 hover:shadow-md">
                <CardHeader>
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle>{c.title}</CardTitle>
                    <Badge variant={STATUS_VARIANT[c.status]}>{STATUS_LABEL[c.status]}</Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">{c.product_name}</p>
                  <div className="flex items-center justify-between pt-2 text-sm">
                    <span className="text-muted-foreground">
                      {c.reps_accepted_count}/{c.max_reps} reps
                    </span>
                    <span className="font-semibold text-foreground">{money(c.budget_cents)}</span>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </BrandShell>
  );
}
