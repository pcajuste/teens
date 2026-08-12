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
  AdminOutlierBrand,
  AdminRevenuePeriod,
} from "@/lib/types";

function Breakdown({ title, rows, keyName }: { title: string; rows: Record<string, string | number>[]; keyName: string }) {
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
                <span className="text-muted-foreground">
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
  const [reps, setReps] = useState<AdminCountBreakdown | null>(null);
  const [campaigns, setCampaigns] = useState<AdminCountBreakdown | null>(null);
  const [consent, setConsent] = useState<AdminConsentStatusEntry[] | null>(null);
  const [outliers, setOutliers] = useState<AdminOutlierBrand[] | null>(null);

  useEffect(() => {
    api.get<AdminRevenuePeriod[]>("/admin/analytics/revenue").then(setRevenue);
    api.get<AdminCountBreakdown>("/admin/analytics/reps").then(setReps);
    api.get<AdminCountBreakdown>("/admin/analytics/campaigns").then(setCampaigns);
    api.get<AdminConsentStatusEntry[]>("/admin/analytics/consent-status").then(setConsent);
    api.get<AdminOutlierBrand[]>("/admin/analytics/outlier-brands").then(setOutliers);
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
                  <tr className="border-b border-border text-left text-muted-foreground">
                    <th className="py-2 pr-4">Period</th>
                    <th className="py-2 pr-4">Brand campaign fees</th>
                    <th className="py-2 pr-4">Intelligence subscriptions</th>
                    <th className="py-2 pr-4">Active recruiter subscriptions</th>
                  </tr>
                </thead>
                <tbody>
                  {revenue.map((r) => (
                    <tr key={r.period} className="border-b border-border/60">
                      <td className="py-2 pr-4">{r.period}</td>
                      <td className="py-2 pr-4">${(r.brand_campaign_fees_cents / 100).toFixed(2)}</td>
                      <td className="py-2 pr-4 text-muted-foreground">
                        ${(r.intelligence_subscription_cents / 100).toFixed(2)}
                      </td>
                      <td className="py-2 pr-4">{r.recruiter_active_subscriptions}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-2 text-xs text-muted-foreground">
                Intelligence Subscription billing lands with the anonymization pipeline (Build Prompt 14) --
                reported as $0 until that table exists, not fabricated.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Breakdown title="Reps by city" rows={reps?.by_city ?? []} keyName="city" />
        <Breakdown title="Reps by category" rows={reps?.by_category ?? []} keyName="category" />
        <Breakdown title="Campaigns by status" rows={campaigns?.by_status ?? []} keyName="status" />
        <Breakdown title="Campaigns by category" rows={campaigns?.by_category ?? []} keyName="category" />
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
                <Badge key={c.consent_state} variant="outline">
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
            <EmptyState title="No outliers detected" description="No brand's rating pattern crosses the threshold." />
          ) : (
            <ul className="flex flex-col gap-2">
              {outliers.map((o) => (
                <li key={o.brand_id} className="rounded-lg border border-border p-3 text-sm">
                  <p className="font-medium">{o.company_name}</p>
                  <p className="text-xs text-muted-foreground">
                    {o.rating_count} ratings, avg {o.average_rating.toFixed(2)} -- {o.reason}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </AdminShell>
  );
}
