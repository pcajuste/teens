"use client";

import { useEffect, useState } from "react";
import { AdminShell } from "@/components/admin/admin-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import type { AdminCampaign } from "@/lib/types";

export default function AdminCampaignsPage() {
  const [campaigns, setCampaigns] = useState<AdminCampaign[] | null>(null);
  const [flaggedOnly, setFlaggedOnly] = useState(false);
  const [flaggingId, setFlaggingId] = useState<string | null>(null);
  const [flagReason, setFlagReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function load() {
    const rows = await api.get<AdminCampaign[]>(
      `/admin/campaigns${flaggedOnly ? "?flagged_only=true" : ""}`,
    );
    setCampaigns(rows);
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flaggedOnly]);

  async function flag(id: string) {
    if (!flagReason.trim()) return;
    setError(null);
    try {
      await api.post(`/admin/campaigns/${id}/flag`, { reason: flagReason });
      setFlaggingId(null);
      setFlagReason("");
      await load();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not flag campaign.",
      );
    }
  }

  async function resolve(
    id: string,
    action: "force_confirm" | "force_cancel_refund",
  ) {
    setError(null);
    if (
      action === "force_cancel_refund" &&
      !confirm("Force-cancel this campaign and refund the un-paid remainder?")
    )
      return;
    try {
      await api.post(`/admin/campaigns/${id}/resolve`, { action });
      await load();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not resolve campaign.",
      );
    }
  }

  return (
    <AdminShell
      title="Campaign oversight"
      action={
        <Button
          size="sm"
          variant={flaggedOnly ? "default" : "outline"}
          onClick={() => setFlaggedOnly((v) => !v)}
        >
          {flaggedOnly ? "Showing flagged only" : "Show flagged only"}
        </Button>
      }
    >
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {campaigns === null ? (
        <Skeleton className="h-40 w-full" />
      ) : campaigns.length === 0 ? (
        <EmptyState
          title="No campaigns"
          description={
            flaggedOnly ? "No flagged campaigns." : "No campaigns exist yet."
          }
        />
      ) : (
        <div className="flex flex-col gap-3">
          {campaigns.map((c) => (
            <Card key={c.id}>
              <CardContent className="flex flex-col gap-2 p-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium">{c.title}</p>
                    <p className="text-xs text-text-2">
                      {c.brand_name} -- ${(c.budget_cents / 100).toFixed(2)} --{" "}
                      {c.target_categories.join(", ")}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Badge variant="pending">{c.status}</Badge>
                    {c.flagged_at && !c.resolved_at ? (
                      <Badge variant="destructive">flagged</Badge>
                    ) : null}
                    {c.resolved_at ? (
                      <Badge variant="success">
                        resolved: {c.resolution_action}
                      </Badge>
                    ) : null}
                  </div>
                </div>
                {c.flagged_reason ? (
                  <p className="text-xs text-text-2">
                    Flag reason: {c.flagged_reason}
                  </p>
                ) : null}

                {flaggingId === c.id ? (
                  <div className="flex flex-col gap-2">
                    <Input
                      placeholder="Reason for flagging"
                      value={flagReason}
                      onChange={(e) => setFlagReason(e.target.value)}
                    />
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        disabled={!flagReason.trim()}
                        onClick={() => flag(c.id)}
                      >
                        Confirm flag
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setFlaggingId(null);
                          setFlagReason("");
                        }}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {!c.flagged_at || c.resolved_at ? (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setFlaggingId(c.id)}
                      >
                        Flag for review
                      </Button>
                    ) : null}
                    {c.flagged_at && !c.resolved_at ? (
                      <>
                        <Button
                          size="sm"
                          onClick={() => resolve(c.id, "force_confirm")}
                        >
                          Force confirm
                        </Button>
                        <Button
                          size="sm"
                          variant="danger"
                          onClick={() => resolve(c.id, "force_cancel_refund")}
                        >
                          Force cancel + refund
                        </Button>
                      </>
                    ) : null}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </AdminShell>
  );
}
