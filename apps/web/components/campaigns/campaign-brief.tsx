import { Badge } from "@/components/ui/badge";
import type { CampaignBriefLike } from "@/lib/types";

function money(cents: number | null): string {
  if (cents === null) return "—";
  return `$${(cents / 100).toFixed(2)}`;
}

/** Renders a campaign brief -- goal, deliverables, categories, payout.
 * Shared by the talent-facing campaign detail page and the brand-facing
 * brief-builder preview step (Build Prompt 9 deliverable 2: reuse the
 * talent-facing renderer rather than building a second one). Both portals
 * see exactly the same layout for exactly the same data, which is the
 * point -- a brand previewing their own campaign should see precisely
 * what a talent will see, not an approximation of it. */
export function CampaignBrief({ campaign }: { campaign: CampaignBriefLike }) {
  return (
    <section className="flex flex-col gap-4 rounded-xl border border-border bg-card p-5">
      <div>
        <p className="text-xs font-medium text-muted-foreground">Product</p>
        <p className="text-sm">{campaign.product_name}</p>
      </div>
      <div>
        <p className="text-xs font-medium text-muted-foreground">Goal</p>
        <p className="text-sm">{campaign.campaign_goal}</p>
      </div>
      <div>
        <p className="text-xs font-medium text-muted-foreground">
          Deliverables
        </p>
        <p className="text-sm">{campaign.deliverables_description}</p>
      </div>
      {campaign.prohibited_content ? (
        <div>
          <p className="text-xs font-medium text-muted-foreground">
            Prohibited content
          </p>
          <p className="text-sm">{campaign.prohibited_content}</p>
        </div>
      ) : null}
      <div className="flex flex-wrap gap-1.5">
        {campaign.target_categories.map((c) => (
          <Badge key={c} variant="outline">
            {c}
          </Badge>
        ))}
      </div>
      <div className="flex items-center justify-between border-t border-border pt-3">
        <p className="text-xs font-medium text-muted-foreground">
          Payout per talent
        </p>
        <p className="text-lg font-semibold text-foreground">
          {money(campaign.payout_per_talent_cents)}
        </p>
      </div>
    </section>
  );
}
