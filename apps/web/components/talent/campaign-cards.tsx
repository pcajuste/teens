import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Countdown } from "@/components/talent/countdown";
import { WithdrawButton } from "@/components/talent/withdraw-button";
import type { CampaignParticipation, CampaignSummary } from "@/lib/types";

function money(cents: number | null): string {
  if (cents === null) return "—";
  return `$${(cents / 100).toFixed(2)}`;
}

export function AvailableCampaignCard({
  campaign,
}: {
  campaign: CampaignSummary;
}) {
  return (
    <Link href={`/talent/campaigns/${campaign.id}`} className="block">
      <Card className="min-h-11">
        <CardHeader>
          <CardTitle>{campaign.title}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-text-2">
            {campaign.product_name}
          </p>
          <div className="flex items-center justify-between pt-1">
            <span className="text-sm font-semibold">
              {money(campaign.payout_per_talent_cents)}
            </span>
            <div className="flex flex-wrap gap-1">
              {campaign.target_categories.slice(0, 3).map((c) => (
                <Badge key={c} variant="pending">
                  {c}
                </Badge>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

const STATUS_LABEL: Record<string, string> = {
  invited: "Invited",
  applied: "Applied",
  accepted: "Accepted",
  submitted: "Submitted",
  under_review: "Under review",
  revision_requested: "Revision requested",
  confirmed: "Confirmed",
  paid: "Paid",
};

// DS Section 6: invited/accepted/applied are in-progress (teal, "active"
// chip); submitted/under_review/revision_requested haven't been decided
// yet (neutral, "pending" chip); confirmed is the earned moment (gold,
// "earned" chip + earned card top edge); paid is complete (green,
// "done" chip).
const STATUS_CHIP_VARIANT: Record<string, "active" | "earned" | "done" | "pending"> = {
  invited: "active",
  applied: "active",
  accepted: "active",
  submitted: "pending",
  under_review: "pending",
  revision_requested: "pending",
  confirmed: "earned",
  paid: "done",
};

const STATUS_CARD_VARIANT: Record<string, "standard" | "earned"> = {
  confirmed: "earned",
  paid: "earned",
};

export function ActiveCampaignCard({
  participation,
  title,
  onWithdrawn,
}: {
  participation: CampaignParticipation;
  title: string;
  onWithdrawn: () => void;
}) {
  return (
    <Card variant={STATUS_CARD_VARIANT[participation.status] ?? "standard"}>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <CardTitle>{title}</CardTitle>
          <Badge variant={STATUS_CHIP_VARIANT[participation.status] ?? "pending"}>
            {STATUS_LABEL[participation.status] ?? participation.status}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        {participation.parent_approval_status === "pending" &&
        participation.parent_approval_deadline ? (
          <p className="rounded-md border border-teal-border bg-teal-dim px-2.5 py-1.5 text-sm text-teal">
            Waiting on a parent&apos;s approval ·{" "}
            <Countdown deadline={participation.parent_approval_deadline} />
          </p>
        ) : null}
        <div className="flex items-center justify-between gap-2 pt-2">
          <Link
            href={`/talent/campaigns/${participation.campaign_id}`}
            className="text-sm font-medium underline"
          >
            View details
          </Link>
          <WithdrawButton
            campaignId={participation.campaign_id}
            onWithdrawn={onWithdrawn}
            className="w-32"
          />
        </div>
      </CardContent>
    </Card>
  );
}
