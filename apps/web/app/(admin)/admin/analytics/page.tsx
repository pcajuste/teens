"use client";

import { useEffect, useState } from "react";
import { AdminShell } from "@/components/admin/admin-shell";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import type {
  AdminConsentStatusEntry,
  AdminCountBreakdown,
  AdminModuleAnalytics,
  AdminOutlierBrand,
  AdminRevenuePeriod,
} from "@/lib/types";

function Breakdown({
  title,
  rows,
  keyName,
}: {
  title: string;
  rows: Record<string, string | number>[];
  keyName: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <EmptyState title="No data yet" />
        ) : (
          <ul className="flex flex-col gap-1.5">
            {rows.map((row, i) => (
              <li key={i} className="flex items-center justify-between text-sm">
                <span className="text-text-2">
                  {String(row[keyName])}
                  {row.state ? `, ${row.state}` : ""}
                </span>
                <span className="font-medium">{row.count}</span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

export default function AdminAnalyticsPage() {
  const [revenue, setRevenue] = useState<AdminRevenuePeriod[] | null>(null);
  const [talents, setTalents] = useState<AdminCountBreakdown | null>(null);
  const [campaigns, setCampaigns] = useState<AdminCountBreakdown | null>(null);
  const [consent, setConsent] = useState<AdminConsentStatusEntry[] | null>(
    null,
  );
  const [outliers, setOutliers] = useState<AdminOutlierBrand[] | null>(null);
  const [modules, setModules] = useState<AdminModuleAnalytics | null>(null);

  useEffect(() => {
    api.get<AdminRevenuePeriod[]>("/admin/analytics/revenue").then(setRevenue);
    api.get<AdminCountBreakdown>("/admin/analytics/talents").then(setTalents);
    api
      .get<AdminCountBreakdown>("/admin/analytics/campaigns")
      .then(setCampaigns);
    api
      .get<AdminConsentStatusEntry[]>("/admin/analytics/consent-status")
      .then(setConsent);
    api
      .get<AdminOutlierBrand[]>("/admin/analytics/outlier-brands")
      .then(setOutliers);
    api.get<AdminModuleAnalytics>("/admin/analytics/modules").then(setModules);
  }, []);

  return (
    <AdminShell title="Analytics">
      <Card>
        <CardHeader>
          <CardTitle>Revenue by stream and period</CardTitle>
        </CardHeader>
        <CardContent>
          {revenue === null ? (
            <Skeleton className="h-24 w-full" />
          ) : revenue.length === 0 ? (
            <EmptyState title="No revenue yet" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border-muted text-left text-text-2">
                    <th className="py-2 pr-4">Period</th>
                    <th className="py-2 pr-4">Brand campaign fees</th>
                    <th className="py-2 pr-4">Intelligence subscriptions</th>
                    <th className="py-2 pr-4">
                      Active recruiter subscriptions
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {revenue.map((r) => (
                    // DS Section 10: earned/completed metrics (revenue
                    // actually collected) are gold; activity/pipeline
                    // metrics (an ongoing count) stay teal.
                    <tr key={r.period} className="border-b border-border-muted/60">
                      <td className="py-2 pr-4">{r.period}</td>
                      <td className="py-2 pr-4 font-medium text-gold">
                        ${(r.brand_campaign_fees_cents / 100).toFixed(2)}
                      </td>
                      <td className="py-2 pr-4 font-medium text-gold">
                        ${(r.intelligence_subscription_cents / 100).toFixed(2)}
                      </td>
                      <td className="py-2 pr-4 font-medium text-teal">
                        {r.recruiter_active_subscriptions}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-2 text-xs text-text-2">
                Intelligence Subscription billing lands with the anonymization
                pipeline (Build Prompt 14) -- reported as $0 until that table
                exists, not fabricated.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Breakdown
          title="Talents by city"
          rows={talents?.by_city ?? []}
          keyName="city"
        />
        <Breakdown
          title="Talents by category"
          rows={talents?.by_category ?? []}
          keyName="category"
        />
        <Breakdown
          title="Campaigns by status"
          rows={campaigns?.by_status ?? []}
          keyName="status"
        />
        <Breakdown
          title="Campaigns by category"
          rows={campaigns?.by_category ?? []}
          keyName="category"
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Parental consent status</CardTitle>
        </CardHeader>
        <CardContent>
          {consent === null ? (
            <Skeleton className="h-16 w-full" />
          ) : (
            <div className="flex flex-wrap gap-3">
              {consent.map((c) => (
                <Badge key={c.consent_state} variant="pending">
                  {c.consent_state.replace(/_/g, " ")}: {c.count}
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Flagged brands (outlier ratings)</CardTitle>
        </CardHeader>
        <CardContent>
          {outliers === null ? (
            <Skeleton className="h-16 w-full" />
          ) : outliers.length === 0 ? (
            <EmptyState
              title="No outliers detected"
              description="No brand's rating pattern crosses the threshold."
            />
          ) : (
            <ul className="flex flex-col gap-2">
              {outliers.map((o) => (
                <li
                  key={o.brand_id}
                  className="rounded-lg border border-border-muted p-3 text-sm"
                >
                  <p className="font-medium">{o.company_name}</p>
                  <p className="text-xs text-text-2">
                    {o.rating_count} ratings, avg {o.average_rating.toFixed(2)}{" "}
                    -- {o.reason}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Learning modules</CardTitle>
        </CardHeader>
        <CardContent>
          {modules === null ? (
            <Skeleton className="h-24 w-full" />
          ) : (
            <div className="flex flex-col gap-4">
              {/* DS Section 10: active modules teal; draft/archived/failed
                  neutral; passed completions gold (earned); in-progress
                  teal (pipeline). */}
              <div className="flex flex-wrap gap-3 text-sm">
                <Badge variant="active">{modules.active_modules} active</Badge>
                <Badge variant="pending">{modules.draft_modules} draft</Badge>
                <Badge variant="pending">
                  {modules.archived_modules} archived
                </Badge>
                <Badge variant="earned">
                  {modules.completions_passed} passed
                </Badge>
                <Badge variant="pending">
                  {modules.completions_failed} failed
                </Badge>
                <Badge variant="active">
                  {modules.completions_in_progress} in progress
                </Badge>
              </div>
              {modules.ftc_module_readiness ? (
                <p className="text-sm text-text-2">
                  FTC launch readiness:{" "}
                  {modules.ftc_module_readiness.pass_percentage ?? 0}% of
                  talents who have touched a campaign have passed the FTC module
                  ({modules.ftc_module_readiness.passed_reps}/
                  {modules.ftc_module_readiness.attempted_reps}).
                </p>
              ) : (
                <p className="text-sm text-text-2">
                  FTC_MODULE_ID not configured yet.
                </p>
              )}
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border-muted text-left text-text-2">
                      <th className="py-2 pr-4">Module</th>
                      <th className="py-2 pr-4">Completions</th>
                      <th className="py-2 pr-4">Pass rate</th>
                      <th className="py-2 pr-4">Avg attempts</th>
                    </tr>
                  </thead>
                  <tbody>
                    {modules.per_module.map((m) => {
                      const lowPassRate =
                        modules.modules_flagged_low_pass_rate.includes(
                          m.module_id,
                        );
                      const highAttempts =
                        modules.modules_flagged_high_attempts.includes(
                          m.module_id,
                        );
                      return (
                        <tr
                          key={m.module_id}
                          className="border-b border-border-muted/60"
                        >
                          <td className="py-2 pr-4">{m.title}</td>
                          <td className="py-2 pr-4">{m.completion_count}</td>
                          <td className="py-2 pr-4">
                            {m.pass_rate !== null
                              ? `${Math.round(m.pass_rate * 100)}%`
                              : "—"}
                            {lowPassRate ? (
                              <Badge variant="destructive" className="ml-2">
                                Review content
                              </Badge>
                            ) : null}
                          </td>
                          <td className="py-2 pr-4">
                            {m.average_attempts ?? "—"}
                            {highAttempts ? (
                              <Badge variant="destructive" className="ml-2">
                                Confusing?
                              </Badge>
                            ) : null}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <div>
                <p className="mb-1 text-sm font-medium">Badge distribution</p>
                <div className="flex flex-wrap gap-2">
                  {modules.badge_distribution.map((b) => (
                    <Badge key={b.badge_title} variant="active">
                      {b.badge_title}: {b.earned_count}
                    </Badge>
                  ))}
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </AdminShell>
  );
}
