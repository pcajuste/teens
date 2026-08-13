"use client";

import { useEffect, useMemo, useState } from "react";
import { AdminShell } from "@/components/admin/admin-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import type {
  AdminExclusivityAgreement,
  AdminExclusivityAnalyticsResponse,
  AdminExclusivityCancelResponse,
  AdminExclusivityListResponse,
  ExclusivityAgreementStatus,
} from "@/lib/types";

function money(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

const STATUS_VARIANT: Record<ExclusivityAgreementStatus, "success" | "outline" | "secondary"> = {
  active: "success",
  expired: "outline",
  cancelled: "secondary",
};

type SortKey = "status" | "revenue" | "expiry";

/** Client-side proration preview mirroring apps/api/app/routers/admin.py's
 * cancel_exclusivity_agreement: full refund before starts_at, otherwise
 * fee_cents * remaining_days / total_days rounded down. This is a
 * preview only -- the server recomputes the authoritative amount (based
 * on its own "now") when the cancel endpoint actually runs. */
function previewRefundCents(a: AdminExclusivityAgreement): number {
  const now = Date.now();
  const startsAt = new Date(a.starts_at).getTime();
  const endsAt = new Date(a.ends_at).getTime();
  const totalDays = Math.max(1, Math.floor((endsAt - startsAt) / 86_400_000));
  if (now <= startsAt) return a.fee_cents;
  const remainingDays = Math.max(0, Math.floor((endsAt - now) / 86_400_000));
  return Math.floor((a.fee_cents * remainingDays) / totalDays);
}

export default function AdminExclusivityPage() {
  const [data, setData] = useState<AdminExclusivityListResponse | null>(null);
  const [analytics, setAnalytics] = useState<AdminExclusivityAnalyticsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("expiry");
  const [cancelTarget, setCancelTarget] = useState<AdminExclusivityAgreement | null>(null);
  const [cancelReason, setCancelReason] = useState("");

  function load() {
    api
      .get<AdminExclusivityListResponse>("/admin/exclusivity?limit=200")
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load exclusivity agreements."));
    api.get<AdminExclusivityAnalyticsResponse>("/admin/analytics/exclusivity").then(setAnalytics);
  }

  useEffect(() => {
    load();
  }, []);

  const sorted = useMemo(() => {
    if (!data) return [];
    const rows = [...data.agreements];
    switch (sortKey) {
      case "status":
        return rows.sort((a, b) => a.status.localeCompare(b.status));
      case "revenue":
        return rows.sort((a, b) => b.fee_cents - a.fee_cents);
      case "expiry":
      default:
        return rows.sort((a, b) => new Date(a.ends_at).getTime() - new Date(b.ends_at).getTime());
    }
  }, [data, sortKey]);

  async function confirmCancel() {
    if (!cancelTarget) return;
    if (!cancelReason.trim()) {
      throw new Error("A cancellation reason is required.");
    }
    await api.post<AdminExclusivityCancelResponse>(`/admin/exclusivity/${cancelTarget.id}/cancel`, {
      cancellation_reason: cancelReason.trim(),
    });
    setCancelTarget(null);
    setCancelReason("");
    load();
  }

  return (
    <AdminShell title="Category exclusivity">
      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      <Card>
        <CardHeader>
          <CardTitle>Analytics</CardTitle>
        </CardHeader>
        <CardContent>
          {analytics === null ? (
            <Skeleton className="h-20 w-full" />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <p className="text-xs text-text-2">Total revenue</p>
                <p className="text-lg font-semibold">{money(analytics.total_revenue_cents)}</p>
              </div>
              <div>
                <p className="text-xs text-text-2">Active agreements</p>
                <p className="text-lg font-semibold">{analytics.active_count}</p>
              </div>
              <div>
                <p className="text-xs text-text-2">Avg. agreement length</p>
                <p className="text-lg font-semibold">{analytics.average_agreement_length_days.toFixed(1)}d</p>
              </div>
              <div>
                <p className="text-xs text-text-2">Top categories by purchase frequency</p>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {analytics.categories_by_purchase_frequency.length === 0 ? (
                    <span className="text-xs text-text-2">No purchases yet</span>
                  ) : (
                    analytics.categories_by_purchase_frequency.map((c) => (
                      <Badge key={c.category} variant="outline">
                        {c.category}: {c.purchase_count}
                      </Badge>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-4">
            <CardTitle>Agreements ({data?.total ?? "..."})</CardTitle>
            <div className="flex items-center gap-2">
              <Label htmlFor="sort" className="text-xs">
                Sort by
              </Label>
              <select
                id="sort"
                className="min-h-9 rounded-md border border-input bg-white/4 px-2 text-sm"
                value={sortKey}
                onChange={(e) => setSortKey(e.target.value as SortKey)}
              >
                <option value="expiry">Expiry date</option>
                <option value="status">Status</option>
                <option value="revenue">Revenue</option>
              </select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {data === null ? (
            <Skeleton className="h-32 w-full" />
          ) : sorted.length === 0 ? (
            <EmptyState title="No agreements" description="No brand has purchased category exclusivity yet." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border-muted text-left text-text-2">
                    <th className="py-2 pr-4">Category</th>
                    <th className="py-2 pr-4">City</th>
                    <th className="py-2 pr-4">Window</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2 pr-4">Payment</th>
                    <th className="py-2 pr-4">Fee</th>
                    <th className="py-2 pr-4">Refund</th>
                    <th className="py-2 pr-4">Brand</th>
                    <th className="py-2 pr-4" />
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((a) => (
                    <tr key={a.id} className="border-b border-border-muted/60">
                      <td className="py-2 pr-4">{a.category}</td>
                      <td className="py-2 pr-4">{a.city ?? "All markets"}</td>
                      <td className="py-2 pr-4 whitespace-nowrap">
                        {new Date(a.starts_at).toLocaleDateString()} &rarr;{" "}
                        {new Date(a.ends_at).toLocaleDateString()}
                      </td>
                      <td className="py-2 pr-4">
                        <Badge variant={STATUS_VARIANT[a.status]}>{a.status}</Badge>
                      </td>
                      <td className="py-2 pr-4">{a.payment_status}</td>
                      <td className="py-2 pr-4">{money(a.fee_cents)}</td>
                      <td className="py-2 pr-4">{a.refund_cents ? money(a.refund_cents) : "—"}</td>
                      <td className="py-2 pr-4 font-mono text-xs">{a.brand_id.slice(0, 8)}</td>
                      <td className="py-2 pr-4">
                        {a.status === "active" ? (
                          <Button size="sm" variant="danger" onClick={() => setCancelTarget(a)}>
                            Cancel
                          </Button>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <ConfirmDialog
        open={cancelTarget !== null}
        title="Cancel exclusivity agreement"
        description={
          cancelTarget
            ? `Cancelling ${cancelTarget.category} (${cancelTarget.city ?? "all markets"}) will issue a Stripe refund and immediately reopen this category-and-city window to other brands.`
            : ""
        }
        confirmLabel="Cancel agreement"
        confirmVariant="destructive"
        confirmDisabled={!cancelReason.trim()}
        onCancel={() => {
          setCancelTarget(null);
          setCancelReason("");
        }}
        onConfirm={confirmCancel}
      >
        {cancelTarget ? (
          <div className="flex flex-col gap-3">
            <div className="rounded-lg bg-secondary/50 p-3 text-sm">
              <p className="font-medium">Proration preview</p>
              <p className="text-text-2">
                Estimated refund: <span className="font-semibold text-foreground">{money(previewRefundCents(cancelTarget))}</span>{" "}
                of {money(cancelTarget.fee_cents)} paid.
              </p>
              <p className="mt-1 text-xs text-text-2">
                Full refund if the window hasn&apos;t started yet; otherwise remaining days are refunded
                proportionally, rounded down. The server computes the authoritative amount at confirmation
                time.
              </p>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cancel-reason">Cancellation reason (required)</Label>
              <Textarea
                id="cancel-reason"
                rows={2}
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                placeholder="e.g. Brand requested cancellation via support ticket #1234"
              />
            </div>
          </div>
        ) : null}
      </ConfirmDialog>
    </AdminShell>
  );
}
