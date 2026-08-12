"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ParentShell } from "@/components/parent/parent-shell";
import { ExplainerPanel } from "@/components/parent/explainer-panel";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { parentApi, ParentApiError } from "@/lib/parent-api";
import type { ParentDashboard } from "@/lib/parent-types";

function money(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

export default function ParentDashboardPage() {
  const [dashboard, setDashboard] = useState<ParentDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    parentApi
      .get<ParentDashboard>("/parent/dashboard")
      .then(setDashboard)
      .catch((err) => setError(err instanceof ParentApiError ? err.message : "Could not load the dashboard."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <ParentShell title="Dashboard">
      {error ? <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p> : null}

      {loading ? (
        <div className="flex flex-col gap-4">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      ) : dashboard ? (
        <div className="flex flex-col gap-6">
          <Card className="p-5">
            <p className="text-lg font-semibold">{dashboard.display_name}</p>
            <p className="text-sm text-muted-foreground">
              {dashboard.school_name} &middot; Class of {dashboard.graduation_year}
            </p>
            {dashboard.categories.length > 0 ? (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {dashboard.categories.map((c) => (
                  <Badge key={c} variant="secondary">
                    {c}
                  </Badge>
                ))}
              </div>
            ) : null}
          </Card>

          <div className="grid gap-4 sm:grid-cols-3">
            <Card className="p-4">
              <p className="text-xs text-muted-foreground">Profile completeness</p>
              <p className="text-xl font-semibold">{dashboard.profile_completeness_score}%</p>
            </Card>
            <Card className="p-4">
              <p className="text-xs text-muted-foreground">Total earnings</p>
              <p className="text-xl font-semibold">{money(dashboard.total_earnings_cents)}</p>
            </Card>
            <Card className="p-4">
              <p className="text-xs text-muted-foreground">Campaigns completed</p>
              <p className="text-xl font-semibold">{dashboard.total_campaigns_completed}</p>
            </Card>
          </div>

          <Card className="flex flex-row items-center justify-between p-5">
            <div>
              <p className="text-sm font-medium">Campaign approvals</p>
              <p className="text-sm text-muted-foreground">Review campaigns awaiting your sign-off.</p>
            </div>
            <Link href="/parent/campaigns" className="text-sm font-medium text-primary hover:underline">
              View queue
            </Link>
          </Card>

          <ExplainerPanel />
        </div>
      ) : null}
    </ParentShell>
  );
}
