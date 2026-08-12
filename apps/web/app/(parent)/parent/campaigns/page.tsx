"use client";

import { useEffect, useState } from "react";
import { ParentShell } from "@/components/parent/parent-shell";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Countdown } from "@/components/rep/countdown";
import { parentApi, ParentApiError } from "@/lib/parent-api";
import type { ParentPendingCampaign } from "@/lib/parent-types";

function money(cents: number | null): string {
  if (cents === null) return "Not specified";
  return `$${(cents / 100).toFixed(2)}`;
}

export default function ParentCampaignsPage() {
  const [campaigns, setCampaigns] = useState<ParentPendingCampaign[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionTarget, setActionTarget] = useState<{ campaign: ParentPendingCampaign; kind: "approve" | "block" } | null>(
    null
  );

  async function load() {
    setLoading(true);
    try {
      const res = await parentApi.get<ParentPendingCampaign[]>("/parent/campaigns/pending");
      setCampaigns(res);
    } catch (err) {
      setError(err instanceof ParentApiError ? err.message : "Could not load pending campaigns.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleConfirm() {
    if (!actionTarget) return;
    const { campaign, kind } = actionTarget;
    await parentApi.post(`/parent/campaigns/${campaign.campaign_id}/${kind}`);
    setActionTarget(null);
    await load();
  }

  return (
    <ParentShell title="Campaign approvals">
      {error ? <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p> : null}

      {loading ? (
        <div className="flex flex-col gap-4">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      ) : campaigns && campaigns.length > 0 ? (
        <div className="flex flex-col gap-4">
          {campaigns.map((c) => (
            <Card key={c.campaign_id} className="p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-base font-semibold">{c.title}</p>
                  <p className="text-sm text-muted-foreground">
                    {c.brand_name} &middot; {c.product_name}
                  </p>
                </div>
                {c.parent_approval_deadline ? <Countdown deadline={c.parent_approval_deadline} /> : null}
              </div>

              <div className="mt-3 flex flex-col gap-2 text-sm">
                <p>
                  <span className="font-medium">Goal: </span>
                  {c.campaign_goal}
                </p>
                <p>
                  <span className="font-medium">Messaging: </span>
                  {c.key_messaging}
                </p>
                <p>
                  <span className="font-medium">Deliverables: </span>
                  {c.deliverables_description}
                </p>
                {c.prohibited_content ? (
                  <p>
                    <span className="font-medium">Prohibited content: </span>
                    {c.prohibited_content}
                  </p>
                ) : null}
                <p>
                  <span className="font-medium">Payout: </span>
                  {money(c.payout_per_rep_cents)}
                </p>
                <p>
                  <span className="font-medium">Timeline: </span>
                  {c.start_date} to {c.end_date}
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {c.requires_in_person_activation ? <Badge variant="warning">In-person activation required</Badge> : null}
                </div>
              </div>

              <div className="mt-4 flex gap-2">
                <Button onClick={() => setActionTarget({ campaign: c, kind: "approve" })}>Approve</Button>
                <Button variant="destructive" onClick={() => setActionTarget({ campaign: c, kind: "block" })}>
                  Block
                </Button>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState
          title="Nothing awaiting your approval"
          description="Campaigns your teen is matched to that need your sign-off will show up here."
        />
      )}

      {actionTarget ? (
        <ConfirmDialog
          open={true}
          title={actionTarget.kind === "approve" ? "Approve this campaign?" : "Block this campaign?"}
          description={
            actionTarget.kind === "approve"
              ? `Your teen will be able to accept "${actionTarget.campaign.title}" from ${actionTarget.campaign.brand_name}.`
              : `"${actionTarget.campaign.title}" will be declined on your teen's behalf. The brand is only told your teen is unavailable -- your reason is never shared.`
          }
          confirmLabel={actionTarget.kind === "approve" ? "Approve" : "Block"}
          confirmVariant={actionTarget.kind === "block" ? "destructive" : "default"}
          onCancel={() => setActionTarget(null)}
          onConfirm={handleConfirm}
        />
      ) : null}
    </ParentShell>
  );
}
