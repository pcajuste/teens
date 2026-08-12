"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Countdown } from "@/components/rep/countdown";
import { api, ApiError } from "@/lib/api";
import type { MilestoneProgress } from "@/lib/types";

const STATUS_LABEL: Record<string, string> = {
  pending: "Pending",
  submitted: "Submitted",
  confirmed: "Confirmed",
  paid: "Paid",
};

function money(cents: number | null): string {
  if (cents === null) return "—";
  return `$${(cents / 100).toFixed(2)}`;
}

/** Brand-facing milestone progress view for a single active rep on a
 * milestone campaign (Build Prompt 8B frontend note: "which milestones
 * are pending, submitted, or confirmed per rep. Each submitted
 * milestone shows the rep's evidence and a confirm/dispute action" plus
 * the dispute-window countdown note). Wired directly to the real
 * confirm/dispute endpoints -- apps/api/app/routers/brands.py's
 * confirm_milestone and dispute_milestone. */
export function RepMilestoneProgress({ campaignId, repId }: { campaignId: string; repId: string }) {
  const [milestones, setMilestones] = useState<MilestoneProgress[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [disputeTarget, setDisputeTarget] = useState<MilestoneProgress | null>(null);

  async function load() {
    try {
      const result = await api.get<MilestoneProgress[]>(
        `/brands/campaigns/${campaignId}/reps/${repId}/milestones`
      );
      setMilestones(result.sort((a, b) => a.milestone_number - b.milestone_number));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load milestone progress.");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaignId, repId]);

  async function handleConfirm(m: MilestoneProgress) {
    setPending(true);
    setError(null);
    try {
      await api.post(
        `/brands/campaigns/${campaignId}/reps/${repId}/milestones/${m.campaign_milestone_id}/confirm`
      );
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not confirm this milestone.");
    } finally {
      setPending(false);
    }
  }

  async function handleDispute() {
    if (!disputeTarget) return;
    await api.post(
      `/brands/campaigns/${campaignId}/reps/${repId}/milestones/${disputeTarget.campaign_milestone_id}/dispute`,
      { reason: null }
    );
    setDisputeTarget(null);
    await load();
  }

  if (error) return <p className="text-xs text-destructive">{error}</p>;
  if (!milestones) return <p className="text-xs text-muted-foreground">Loading milestone progress…</p>;

  return (
    <div className="flex flex-col gap-2">
      {milestones.map((m) => {
        const autoReleaseDeadline =
          m.verification_method === "rep_submission" && m.status === "submitted" && m.submitted_at
            ? new Date(new Date(m.submitted_at).getTime() + 24 * 60 * 60 * 1000).toISOString()
            : null;

        return (
          <Card key={m.id} className="p-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-medium">
                {m.milestone_number}. {m.title}
              </p>
              <Badge variant={m.status === "paid" || m.status === "confirmed" ? "success" : "secondary"}>
                {STATUS_LABEL[m.status] ?? m.status}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              {m.payout_percentage}% · {money(m.payout_cents)}
            </p>

            {m.rep_submission_text ? <p className="mt-1 text-sm">{m.rep_submission_text}</p> : null}
            {m.rep_submission_file_urls.length > 0 ? (
              <div className="mt-1 flex flex-col gap-0.5">
                {m.rep_submission_file_urls.map((url) => (
                  <a key={url} href={url} target="_blank" rel="noreferrer" className="text-xs underline">
                    {url}
                  </a>
                ))}
              </div>
            ) : null}

            {m.dispute_flag ? (
              <p className="mt-1 text-xs text-warning-foreground">Disputed — awaiting admin review</p>
            ) : null}

            {autoReleaseDeadline ? (
              <p className="mt-1 text-xs text-muted-foreground">
                Auto-releases in <Countdown deadline={autoReleaseDeadline} /> unless disputed
              </p>
            ) : null}

            {m.status === "submitted" ? (
              <div className="mt-2 flex gap-2">
                <Button size="sm" disabled={pending} onClick={() => handleConfirm(m)}>
                  Confirm
                </Button>
                {!m.dispute_flag ? (
                  <Button size="sm" variant="outline" disabled={pending} onClick={() => setDisputeTarget(m)}>
                    Dispute
                  </Button>
                ) : null}
              </div>
            ) : null}
          </Card>
        );
      })}

      <ConfirmDialog
        open={disputeTarget !== null}
        title="Dispute this milestone?"
        description="This flags the submission for admin review and pauses the 24-hour auto-release. The rep will be notified."
        confirmLabel="Dispute"
        confirmVariant="destructive"
        onCancel={() => setDisputeTarget(null)}
        onConfirm={handleDispute}
      />
    </div>
  );
}
