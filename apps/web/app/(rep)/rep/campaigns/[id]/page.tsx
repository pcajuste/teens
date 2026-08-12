"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { CampaignSummary } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { formatCents, formatDate, countdown, statusLabel } from "@/lib/format";

// There's no GET /campaigns/{id} single-resource endpoint from Prompt 5 —
// only the three list endpoints (available/active/history). We fetch all
// three and find the matching campaign, which also gives us the rep's
// current relationship (status) to it.
export default function CampaignDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [campaign, setCampaign] = useState<CampaignSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ftcChecked, setFtcChecked] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [acting, setActing] = useState(false);

  const load = useMemo(
    () => async () => {
      setLoading(true);
      setError(null);
      try {
        const [avail, act, hist] = await Promise.all([
          api.getAvailableCampaigns(),
          api.getActiveCampaigns(),
          api.getCampaignHistory(),
        ]);
        const found = [...avail, ...act, ...hist].find((c) => c.campaign_id === params.id);
        setCampaign(found ?? null);
        if (!found) setError("Campaign not found.");
      } catch (err) {
        setError(err instanceof ApiError ? String(err.detail ?? err.message) : "Could not load this campaign.");
      } finally {
        setLoading(false);
      }
    },
    [params.id],
  );

  useEffect(() => {
    load();
  }, [load]);

  async function doApply() {
    if (!campaign) return;
    setActing(true);
    setActionError(null);
    try {
      await api.applyToCampaign(campaign.campaign_id);
      await load();
    } catch (err) {
      setActionError(err instanceof ApiError ? String(err.detail ?? err.message) : "Could not apply.");
    } finally {
      setActing(false);
    }
  }

  async function doAccept() {
    if (!campaign) return;
    if (!ftcChecked) {
      setActionError("You must acknowledge the FTC sponsorship disclosure before accepting.");
      return;
    }
    setActing(true);
    setActionError(null);
    try {
      await api.acceptCampaign(campaign.campaign_id, { ftc_disclosure_accepted: true });
      await load();
    } catch (err) {
      setActionError(err instanceof ApiError ? String(err.detail ?? err.message) : "Could not accept this campaign.");
    } finally {
      setActing(false);
    }
  }

  async function doDecline() {
    if (!campaign) return;
    setActing(true);
    setActionError(null);
    try {
      await api.declineCampaign(campaign.campaign_id);
      await load();
    } catch (err) {
      setActionError(err instanceof ApiError ? String(err.detail ?? err.message) : "Could not decline this campaign.");
    } finally {
      setActing(false);
    }
  }

  async function doWithdraw() {
    if (!campaign) return;
    if (!confirm("Withdraw from this campaign? This can't be undone.")) return;
    setActing(true);
    setActionError(null);
    try {
      await api.withdrawCampaign(campaign.campaign_id);
      await load();
    } catch (err) {
      setActionError(err instanceof ApiError ? String(err.detail ?? err.message) : "Could not withdraw from this campaign.");
    } finally {
      setActing(false);
    }
  }

  if (loading) {
    return (
      <main className="container py-6">
        <p className="text-muted-foreground">Loading…</p>
      </main>
    );
  }

  if (error || !campaign) {
    return (
      <main className="container py-6">
        <p className="text-sm text-red-600">{error ?? "Campaign not found."}</p>
      </main>
    );
  }

  const canApply = campaign.status === "available" || campaign.status === "not_applied";
  const awaitingParentApproval = campaign.status === "invited" && campaign.parent_approval_status === "pending";
  const canAcceptDecline = campaign.status === "invited" && !awaitingParentApproval;
  const canSubmit = campaign.status === "accepted" || campaign.status === "revision_requested";
  const canWithdraw = ["invited", "accepted", "submitted", "revision_requested"].includes(campaign.status);
  const expiry = countdown(campaign.invite_expires_at);

  return (
    <main className="container max-w-lg space-y-4 py-6">
      <div className="flex items-start justify-between gap-2">
        <h1 className="text-xl font-semibold">{campaign.title}</h1>
        <Badge variant="outline">{statusLabel(campaign.status)}</Badge>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Brief</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div>
            <div className="font-medium">Product</div>
            <div className="text-muted-foreground">{campaign.product_name}</div>
          </div>
          <div>
            <div className="font-medium">Deliverables</div>
            <div className="text-muted-foreground">{campaign.deliverables_description}</div>
          </div>
          <div>
            <div className="font-medium">Timeline</div>
            <div className="text-muted-foreground">
              {formatDate(campaign.start_date)} – {formatDate(campaign.end_date)}
            </div>
          </div>
          <div>
            <div className="font-medium">Payout</div>
            <div className="text-muted-foreground">
              {campaign.payout_cents != null ? formatCents(campaign.payout_cents) : "TBD"}
            </div>
          </div>
          <div>
            <div className="font-medium">Prohibited content</div>
            <div className="text-muted-foreground">
              No sponsored content on platforms outside what&apos;s agreed, no misleading claims about the
              product, and disclosure is required on every post per FTC guidelines below.
            </div>
          </div>
        </CardContent>
      </Card>

      {expiry && canAcceptDecline && (
        <p className="text-sm font-medium text-amber-700">{expiry}</p>
      )}

      {actionError && <p className="text-sm text-red-600">{actionError}</p>}

      {canApply && (
        <Button onClick={doApply} disabled={acting} size="lg" className="w-full">
          {acting ? "Applying…" : "Apply"}
        </Button>
      )}

      {awaitingParentApproval && (
        <Card>
          <CardHeader>
            <CardTitle>Waiting on your parent</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            This campaign needs your parent or guardian&apos;s approval before you can accept or
            decline it. We&apos;ve sent them a notification — check back once they&apos;ve responded,
            or it will automatically expire if they don&apos;t respond within 48 hours.
          </CardContent>
        </Card>
      )}

      {canAcceptDecline && (
        <Card>
          <CardHeader>
            <CardTitle>FTC sponsorship disclosure</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <label className="flex min-h-11 cursor-pointer items-start gap-3">
              <Checkbox checked={ftcChecked} onChange={(e) => setFtcChecked(e.target.checked)} />
              <span className="text-sm text-muted-foreground">
                I understand I must clearly disclose this as sponsored content (e.g. #ad) on every post, per FTC
                guidelines, and that failing to do so can result in removal from the campaign.
              </span>
            </label>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button onClick={doAccept} disabled={acting || !ftcChecked}>
                {acting ? "Accepting…" : "Accept"}
              </Button>
              <Button onClick={doDecline} disabled={acting} variant="outline">
                Decline
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {canSubmit && (
        <Link href={`/rep/campaigns/${campaign.campaign_id}/submit`}>
          <Button size="lg" className="w-full">
            Go to submission
          </Button>
        </Link>
      )}

      <StatusTracker status={campaign.status} />

      {canWithdraw && (
        <Button onClick={doWithdraw} disabled={acting} variant="destructive" size="sm">
          Withdraw from campaign
        </Button>
      )}
    </main>
  );
}

const TRACKER_STEPS = ["submitted", "under_review", "confirmed", "paid"];

function StatusTracker({ status }: { status: string }) {
  if (!TRACKER_STEPS.includes(status)) return null;
  const currentIndex = TRACKER_STEPS.indexOf(status);
  return (
    <Card>
      <CardHeader>
        <CardTitle>Status</CardTitle>
      </CardHeader>
      <CardContent>
        <ol className="flex flex-wrap gap-2">
          {TRACKER_STEPS.map((step, i) => (
            <li key={step}>
              <Badge variant={i <= currentIndex ? "default" : "muted"}>{statusLabel(step)}</Badge>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  );
}
