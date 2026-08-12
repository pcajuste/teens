import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Countdown } from "@/components/rep/countdown";
import { WithdrawButton } from "@/components/rep/withdraw-button";
import type { CampaignParticipation, CampaignSummary } from "@/lib/types";

function money(cents: number | null): string {
  if (cents === null) return "—";
  return `$${(cents / 100).toFixed(2)}`;
}

export function AvailableCampaignCard({ campaign }: { campaign: CampaignSummary }) {
  return (
    <Link href={`/rep/campaigns/${campaign.id}`} className="block">
      <Card className="min-h-11">
        <CardHeader>
          <CardTitle>{campaign.title}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">{campaign.product_name}</p>
          <div className="flex items-center justify-between pt-1">
            <span className="text-sm font-semibold">{money(campaign.payout_per_rep_cents)}</span>
            <div className="flex flex-wrap gap-1">
              {campaign.target_categories.slice(0, 3).map((c) => (
                <Badge key={c} variant="outline">
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
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <CardTitle>{title}</CardTitle>
          <Badge variant="secondary">{STATUS_LABEL[participation.status] ?? participation.status}</Badge>
        </div>
      </CardHeader>
      <CardContent>
        {participation.parent_approval_status === "pending" && participation.parent_approval_deadline ? (
          <p className="text-sm text-amber-700 dark:text-amber-400">
            Waiting on a parent&apos;s approval ·{" "}
            <Countdown deadline={participation.parent_approval_deadline} />
          </p>
        ) : null}
        <div className="flex items-center justify-between gap-2 pt-2">
          <Link href={`/rep/campaigns/${participation.campaign_id}`} className="text-sm font-medium underline">
            View details
          </Link>
          <WithdrawButton campaignId={participation.campaign_id} onWithdrawn={onWithdrawn} className="w-32" />
        </div>
      </CardContent>
    </Card>
  );
}
