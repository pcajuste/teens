"use client";

import { useEffect, useState } from "react";
import { parentApi } from "@/lib/parent-api";
import { ApiError } from "@/lib/api";
import type { PendingCampaignBrief } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { formatCents, formatDate, countdown } from "@/lib/format";

/**
 * Campaign approval queue (Prompt 4A deliverable 3/7). Full brief per
 * PendingCampaignBrief, approve/block actions, and a 48h countdown to
 * parent_approval_deadline.
 */
export default function ParentCampaignsPage() {
  const [campaigns, setCampaigns] = useState<PendingCampaignBrief[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actingId, setActingId] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setCampaigns(await parentApi.getPendingCampaigns());
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? err.message) : "Could not load pending campaigns.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function approve(campaignId: string) {
    setActingId(campaignId);
    try {
      await parentApi.approveCampaign(campaignId);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? err.message) : "Could not approve this campaign.");
    } finally {
      setActingId(null);
    }
  }

  async function block(campaignId: string) {
    if (!confirm("Block this campaign? Your teen will not be able to accept it, and no reason is shared with the brand.")) {
      return;
    }
    setActingId(campaignId);
    try {
      await parentApi.blockCampaign(campaignId);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? err.message) : "Could not block this campaign.");
    } finally {
      setActingId(null);
    }
  }

  return (
    <main className="container max-w-lg space-y-4 py-6">
      <h1 className="text-xl font-semibold">Campaigns awaiting your approval</h1>

      {loading && <p className="text-muted-foreground">Loading…</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}
      {!loading && campaigns.length === 0 && !error && (
        <p className="text-sm text-muted-foreground">Nothing waiting on you right now.</p>
      )}

      {campaigns.map((c) => (
        <Card key={c.campaign_reps_id}>
          <CardHeader>
            <CardTitle>{c.brand_name}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div>
              <div className="font-medium">Product</div>
              <div className="text-muted-foreground">{c.product_name}</div>
            </div>
            <div>
              <div className="font-medium">Messaging</div>
              <div className="text-muted-foreground">{c.key_messaging}</div>
            </div>
            <div>
              <div className="font-medium">Deliverables</div>
              <div className="text-muted-foreground">{c.deliverables_description}</div>
            </div>
            {c.prohibited_content && (
              <div>
                <div className="font-medium">Prohibited content</div>
                <div className="text-muted-foreground">{c.prohibited_content}</div>
              </div>
            )}
            <div>
              <div className="font-medium">Timeline</div>
              <div className="text-muted-foreground">
                {formatDate(c.start_date)} – {formatDate(c.end_date)}
              </div>
            </div>
            <div>
              <div className="font-medium">Payout</div>
              <div className="text-muted-foreground">{c.payout_cents != null ? formatCents(c.payout_cents) : "TBD"}</div>
            </div>
            {c.requires_in_person && (
              <p className="text-sm font-medium text-amber-700">Requires in-person activation.</p>
            )}
            {c.parent_approval_deadline && (
              <p className="text-sm font-medium text-amber-700">{countdown(c.parent_approval_deadline)}</p>
            )}

            <div className="flex flex-col gap-2 sm:flex-row">
              <Button onClick={() => approve(c.campaign_id)} disabled={actingId === c.campaign_id}>
                Approve
              </Button>
              <Button onClick={() => block(c.campaign_id)} disabled={actingId === c.campaign_id} variant="destructive">
                Block
              </Button>
            </div>
          </CardContent>
        </Card>
      ))}
    </main>
  );
}
