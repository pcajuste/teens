"use client";

import { useEffect, useState } from "react";
import { AdminShell } from "@/components/admin/admin-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import type { AdminStuckPayment } from "@/lib/types";

export default function AdminPaymentsPage() {
  const [rows, setRows] = useState<AdminStuckPayment[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [releasing, setReleasing] = useState<string | null>(null);

  async function load() {
    const data = await api.get<AdminStuckPayment[]>("/admin/payments/stuck");
    setRows(data);
  }

  useEffect(() => {
    load();
  }, []);

  async function release(transferId: string | null) {
    if (!transferId) return;
    setError(null);
    setReleasing(transferId);
    try {
      await api.post(`/admin/payments/${transferId}/release`);
      await load();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not release payout.",
      );
    } finally {
      setReleasing(null);
    }
  }

  return (
    <AdminShell
      title="Stuck payments"
      action={<Badge variant="destructive">processing &gt; 48h</Badge>}
    >
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {rows === null ? (
        <Skeleton className="h-32 w-full" />
      ) : rows.length === 0 ? (
        <EmptyState
          title="Nothing stuck"
          description="Every in-flight payout is under 48 hours old."
        />
      ) : (
        <div className="flex flex-col gap-3">
          {rows.map((r) => (
            <Card key={r.campaign_talent_id}>
              <CardContent className="flex items-center justify-between gap-4 p-4">
                <div>
                  <p className="text-sm font-medium">
                    $
                    {r.payout_cents
                      ? (r.payout_cents / 100).toFixed(2)
                      : "0.00"}{" "}
                    -- {r.payout_status}
                  </p>
                  <p className="text-xs text-text-2">
                    Stuck for {r.hours_stuck.toFixed(1)}h -- transfer{" "}
                    {r.stripe_transfer_id ?? "n/a"}
                  </p>
                </div>
                <Button
                  size="sm"
                  disabled={
                    !r.stripe_transfer_id || releasing === r.stripe_transfer_id
                  }
                  onClick={() => release(r.stripe_transfer_id)}
                >
                  {releasing === r.stripe_transfer_id
                    ? "Releasing..."
                    : "Release payout"}
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </AdminShell>
  );
}
