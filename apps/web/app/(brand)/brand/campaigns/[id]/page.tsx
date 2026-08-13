"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { BrandShell } from "@/components/brand/brand-shell";
import { TalentMilestoneProgress } from "@/components/brand/talent-milestone-progress";
import { CampaignBrief } from "@/components/campaigns/campaign-brief";
import { api, ApiError } from "@/lib/api";
import { trackEvent } from "@/lib/analytics";
import type {
  Campaign,
  campaignTalent,
  CampaignStatus,
  InviteResult,
  TalentBrowseCard,
} from "@/lib/types";

const STATUS_VARIANT: Record<
  CampaignStatus,
  "default" | "secondary" | "warning" | "success" | "destructive" | "outline"
> = {
  draft: "outline",
  pending_payment: "secondary",
  payment_failed: "destructive",
  active: "success",
  paused: "warning",
  completed: "secondary",
  cancelled: "outline",
};

const STATUS_LABEL: Record<CampaignStatus, string> = {
  draft: "Draft",
  pending_payment: "Payment pending",
  payment_failed: "Payment failed",
  active: "Active",
  paused: "Paused",
  completed: "Completed",
  cancelled: "Cancelled",
};

const talent_STATUS_LABEL: Record<string, string> = {
  invited: "Invited",
  accepted: "Accepted",
  declined: "Declined",
  submitted: "Submitted",
  revision_requested: "Revision requested",
  confirmed: "Confirmed",
  paid: "Paid",
};

export default function BrandCampaignDetailPage() {
  const params = useParams<{ id: string }>();
  const campaignId = params.id;

  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [campaignTalents, setCampaignReps] = useState<campaignTalent[]>([]);
  const [browseCards, setBrowseCards] = useState<TalentBrowseCard[] | null>(
    null,
  );
  const [showBrowse, setShowBrowse] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function load() {
    try {
      const [campaignRes, repsRes] = await Promise.all([
        api.get<Campaign>(`/brands/campaigns/${campaignId}`),
        api.get<campaignTalent[]>(`/brands/campaigns/${campaignId}/talents`),
      ]);
      setCampaign(campaignRes);
      setCampaignReps(repsRes);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not load this campaign.",
      );
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaignId]);

  async function runAction(action: () => Promise<void>) {
    setPending(true);
    setError(null);
    setNotice(null);
    try {
      await action();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setPending(false);
    }
  }

  async function handleActivate() {
    await runAction(async () => {
      const result = await api.post<{
        id: string;
        status: string;
        stripe_payment_intent_client_secret: string;
      }>(`/brands/campaigns/${campaignId}/activate`);
      trackEvent("campaign_activated", { campaign_id: campaignId });
      setNotice(
        `Payment initiated (status: ${result.status}). Card collection isn't wired up in this build yet -- ` +
          `see Prompt 9's deliverable 3 note; the PaymentIntent itself is real and server-created.`,
      );
      await load();
    });
  }

  async function handleRetryPayment() {
    await runAction(async () => {
      await api.post(`/brands/campaigns/${campaignId}/retry-payment`);
      await load();
    });
  }

  async function handlePause() {
    await runAction(async () => {
      await api.post(`/brands/campaigns/${campaignId}/pause`);
      await load();
    });
  }

  async function handleCancel() {
    await runAction(async () => {
      const result = await api.post<{ refund_pending: boolean }>(
        `/brands/campaigns/${campaignId}/cancel`,
      );
      if (result.refund_pending) {
        setNotice(
          "Campaign cancelled. A refund is owed and will be handled manually -- see docs/campaign-cancellation-refund-policy.md.",
        );
      }
      await load();
    });
  }

  async function loadBrowse() {
    setShowBrowse(true);
    if (browseCards !== null) return;
    try {
      const cards = await api.get<TalentBrowseCard[]>(
        `/brands/campaigns/${campaignId}/talents/browse`,
      );
      setBrowseCards(cards);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not load talents to browse.",
      );
    }
  }

  async function handleInvite(repId: string) {
    await runAction(async () => {
      const results = await api.post<InviteResult[]>(
        `/brands/campaigns/${campaignId}/talents/invite`,
        {
          talent_ids: [repId],
        },
      );
      const result = results[0];
      if (result.status === "invited") {
        setNotice("Talent invited.");
      } else if (result.status === "already_invited") {
        setNotice("This talent is already invited to this campaign.");
      } else if (result.status === "campaign_full") {
        setNotice("This campaign has already reached its max talents.");
      }
      await load();
    });
  }

  if (!campaign) {
    return (
      <BrandShell backHref="/brand">
        <div className="flex flex-col gap-4">
          <Skeleton className="h-8 w-1/2" />
          <Skeleton className="h-48 w-full" />
        </div>
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
      </BrandShell>
    );
  }

  const invitedRepIds = new Set(campaignTalents.map((cr) => cr.talent_id));

  return (
    <BrandShell backHref="/brand">
      <div className="flex flex-col gap-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              {campaign.title}
            </h1>
            <p className="text-sm text-muted-foreground">
              {campaign.product_name}
            </p>
          </div>
          <Badge
            variant={STATUS_VARIANT[campaign.status]}
            className="px-3 py-1 text-sm"
          >
            {STATUS_LABEL[campaign.status]}
          </Badge>
        </div>

        {error ? (
          <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        ) : null}
        {notice ? (
          <p className="rounded-lg bg-info/10 px-3 py-2 text-sm text-info">
            {notice}
          </p>
        ) : null}

        <div className="flex flex-wrap gap-2">
          {campaign.status === "draft" ? (
            <Button onClick={handleActivate} disabled={pending} size="lg">
              Activate campaign
            </Button>
          ) : null}
          {campaign.status === "payment_failed" ? (
            <Button onClick={handleRetryPayment} disabled={pending} size="lg">
              Retry payment
            </Button>
          ) : null}
          {campaign.status === "active" ? (
            <Button
              onClick={handlePause}
              disabled={pending}
              variant="outline"
              size="lg"
            >
              Pause
            </Button>
          ) : null}
          {[
            "draft",
            "pending_payment",
            "payment_failed",
            "active",
            "paused",
          ].includes(campaign.status) ? (
            <Button
              onClick={handleCancel}
              disabled={pending}
              variant="destructive"
              size="lg"
            >
              Cancel campaign
            </Button>
          ) : null}
        </div>

        <CampaignBrief campaign={campaign} />

        <section className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-muted-foreground">
              Talents ({campaignTalents.length}/{campaign.max_talents})
            </h2>
            <Button
              variant="outline"
              onClick={loadBrowse}
              disabled={showBrowse}
            >
              Browse talents
            </Button>
          </div>

          {campaignTalents.length === 0 ? (
            <EmptyState
              title="No talents invited yet"
              description="Browse matched talents below and invite the ones you want."
            />
          ) : (
            <div className="flex flex-col gap-2">
              {campaignTalents.map((cr) => (
                <Card key={cr.id} className="flex flex-col gap-3 p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium">
                       talent {cr.talent_id.slice(0, 8)}
                      </p>
                      {cr.parent_approval_status === "pending" ? (
                        <p className="text-xs text-warning-foreground">
                          Awaiting parent approval
                        </p>
                      ) : null}
                    </div>
                    <Badge variant="secondary">
                      {talent_STATUS_LABEL[cr.status] ?? cr.status}
                    </Badge>
                  </div>

                  {campaign.payment_type === "milestone" &&
                  cr.status !== "invited" &&
                  cr.status !== "declined" ? (
                    <div className="border-t border-border pt-3">
                      <TalentMilestoneProgress
                        campaignId={campaignId}
                        repId={cr.talent_id}
                      />
                    </div>
                  ) : null}
                </Card>
              ))}
            </div>
          )}
        </section>

        {showBrowse ? (
          <section className="flex flex-col gap-3">
            <h2 className="text-sm font-semibold text-muted-foreground">
              Browse matched talents
            </h2>
            {browseCards === null ? (
              <Skeleton className="h-24 w-full" />
            ) : browseCards.length === 0 ? (
              <EmptyState
                title="No matching talents found"
                description="Talents must opt into recruiter/brand visibility and match this campaign's categories to appear here."
              />
            ) : (
              <div className="grid gap-3 sm:grid-cols-2">
                {browseCards.map((card) => (
                  <Card key={card.talent_id}>
                    <CardHeader>
                      <CardTitle className="text-sm">
                        {card.city}, {card.state} · Class of{" "}
                        {card.graduation_year}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="flex flex-wrap gap-1">
                        {card.categories.slice(0, 4).map((cat) => (
                          <Badge key={cat} variant="outline">
                            {cat}
                          </Badge>
                        ))}
                      </div>
                      <div className="flex items-center justify-between pt-2">
                        <p className="text-xs text-muted-foreground">
                          {card.profile_completeness_score}% complete
                          {card.average_rating
                            ? ` · ${card.average_rating.toFixed(1)}★`
                            : ""}
                        </p>
                        <Button
                          size="sm"
                          disabled={
                            pending || invitedRepIds.has(card.talent_id)
                          }
                          onClick={() => handleInvite(card.talent_id)}
                        >
                          {invitedRepIds.has(card.talent_id)
                            ? "Invited"
                            : "Invite"}
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </section>
        ) : null}
      </div>
    </BrandShell>
  );
}
