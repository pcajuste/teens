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
            <p className="text-sm text-text-2">
              {dashboard.school_name} &middot; Class of {dashboard.graduation_year}
            </p>
            {dashboard.categories.length > 0 ? (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {dashboard.categories.map((c) => (
                  <Badge key={c} variant="active">
                    {c}
                  </Badge>
                ))}
              </div>
            ) : null}
          </Card>

          <div className="grid gap-4 sm:grid-cols-3">
            <Card className="p-4">
              <p className="text-xs text-text-3">Profile completeness</p>
              <p className="text-xl font-semibold">{dashboard.profile_completeness_score}%</p>
            </Card>
            {/* DS Section 9: total earnings is the most important number
                the parent sees, and it's real earned money -- gold. */}
            <Card variant="earned" className="p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.1em] text-gold">Total earnings</p>
              <p className="text-2xl font-extrabold text-gold">{money(dashboard.total_earnings_cents)}</p>
            </Card>
            <Card variant="earned" className="p-4">
              <p className="text-xs text-text-3">Campaigns completed</p>
              <p className="text-xl font-semibold text-gold">{dashboard.total_campaigns_completed}</p>
            </Card>
          </div>

          <Card variant="featured" className="flex flex-row items-center justify-between p-5">
            <div>
              <p className="text-sm font-medium">Campaign approvals</p>
              <p className="text-sm text-text-2">Review campaigns awaiting your sign-off.</p>
            </div>
            <Link href="/parent/campaigns" className="text-sm font-medium text-primary hover:underline">
              View queue
            </Link>
          </Card>

          <Card className="p-5">
            <p className="text-sm font-semibold">Challenge activity</p>
            <p className="mb-4 text-sm text-text-2">
              Challenges are unpaid brand-discovery submissions -- no financial transaction happens
              unless a brand invites your teen to a paid campaign afterward.
            </p>
            <div className="grid grid-cols-3 gap-3 text-center">
              <div>
                <p className="text-xl font-semibold">{dashboard.challenge_activity.total_submitted}</p>
                <p className="text-xs text-text-3">Submitted</p>
              </div>
              <div>
                <p className="text-xl font-semibold text-gold">{dashboard.challenge_activity.total_converted}</p>
                <p className="text-xs text-text-3">Converted</p>
              </div>
              <div>
                <p className="text-xl font-semibold text-gold">{money(dashboard.challenge_activity.total_bonus_earned_cents)}</p>
                <p className="text-xs text-text-3">Bonus earned</p>
              </div>
            </div>

            {dashboard.challenge_activity.recent_submissions.length > 0 ? (
              <ul className="mt-4 flex flex-col gap-2 border-t border-border-muted pt-4">
                {dashboard.challenge_activity.recent_submissions.map((s, i) => (
                  <li key={i} className="flex items-center justify-between text-sm">
                    <span>{s.challenge_title}</span>
                    {s.status === "converted" ? (
                      <Badge variant="earned">
                        Converted{s.bonus_earned_cents != null ? ` · +${money(s.bonus_earned_cents)}` : ""}
                      </Badge>
                    ) : (
                      <Badge variant="pending">Submitted</Badge>
                    )}
                  </li>
                ))}
              </ul>
            ) : null}
          </Card>

          <Card className="p-5">
            <p className="text-sm font-semibold">Learning modules</p>
            <p className="mb-4 text-sm text-text-2">
              Short, platform-curated modules your teen can complete to earn verified badges. You&apos;ll see
              completion status and badges earned here -- not quiz scores or which questions they missed.
            </p>
            <div className="grid grid-cols-3 gap-3 text-center">
              <div>
                <p className="text-xl font-semibold">{dashboard.module_activity.total_started}</p>
                <p className="text-xs text-text-3">Started</p>
              </div>
              <div>
                <p className="text-xl font-semibold">{dashboard.module_activity.total_passed}</p>
                <p className="text-xs text-text-3">Passed</p>
              </div>
              <div>
                <p className="text-xl font-semibold">{dashboard.module_activity.total_failed}</p>
                <p className="text-xs text-text-3">Retrying</p>
              </div>
            </div>
            <div className="mt-4 flex items-center justify-between border-t border-border-muted pt-4 text-sm">
              <span>FTC Disclosure Essentials</span>
              {/* DS Section 9: passed = green (compliance confirmed);
                  not-yet is neutral, never alarming -- a parent doesn't
                  need to see failure drama for a retake-eligible module. */}
              <Badge variant={dashboard.module_activity.ftc_module_passed ? "done" : "pending"}>
                {dashboard.module_activity.ftc_module_passed ? "Passed" : "Not yet completed"}
              </Badge>
            </div>
            {dashboard.module_activity.badges_earned.length > 0 ? (
              <ul className="mt-3 flex flex-wrap gap-2">
                {dashboard.module_activity.badges_earned.map((b, i) => (
                  <Badge key={i} variant="active">
                    {b.badge_title}
                  </Badge>
                ))}
              </ul>
            ) : null}
          </Card>

          <ExplainerPanel />
        </div>
      ) : null}
    </ParentShell>
  );
}
