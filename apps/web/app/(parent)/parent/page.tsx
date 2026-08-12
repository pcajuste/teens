"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { parentApi } from "@/lib/parent-api";
import { clearParentSession } from "@/lib/parent-session";
import { ApiError } from "@/lib/api";
import type { RepSummary } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatCents } from "@/lib/format";
import { WhatParentsSeeExplainer } from "@/components/parent/what-parents-see";

/**
 * Parent Portal dashboard (Prompt 4A deliverable 2/7). Shows exactly the
 * fields GET /parent/dashboard returns -- a recruiter no-PII card plus
 * earnings, nothing more (see app.services.parent_service.get_dashboard).
 */
export default function ParentDashboardPage() {
  const router = useRouter();
  const [summary, setSummary] = useState<RepSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    parentApi
      .getDashboard()
      .then(setSummary)
      .catch((err) => {
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          clearParentSession();
          router.replace("/parent/login");
          return;
        }
        setError(err instanceof ApiError ? String(err.detail ?? err.message) : "Could not load the dashboard.");
      })
      .finally(() => setLoading(false));
  }, [router]);

  return (
    <main className="container space-y-6 py-6">
      <h1 className="text-xl font-semibold">
        {summary ? `${summary.display_name}'s Teenure account` : "Your teen's Teenure account"}
      </h1>

      {loading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {summary && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Profile</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
              <Stat label="School" value={summary.school_name} />
              <Stat label="Graduates" value={String(summary.graduation_year)} />
              <Stat label="Profile complete" value={`${summary.profile_completeness_score}%`} />
              <Stat label="Categories" value={summary.categories.join(", ") || "None yet"} />
              <Stat label="Campaigns completed" value={String(summary.total_campaigns_completed)} />
              <Stat label="Total earnings" value={formatCents(summary.total_earnings_cents)} />
            </CardContent>
          </Card>

          <WhatParentsSeeExplainer />
        </>
      )}
    </main>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="font-medium">{value}</div>
    </div>
  );
}
