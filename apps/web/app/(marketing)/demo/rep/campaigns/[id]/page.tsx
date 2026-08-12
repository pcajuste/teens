import { notFound } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DemoBackLink, DemoBanner, DemoPageViewTracker, StartBuildingYoursButton } from "@/components/demo/demo-chrome";
import {
  DEMO_AVAILABLE_CAMPAIGN,
  DEMO_AVAILABLE_CAMPAIGN_ID,
  DEMO_CONFIRMED_CAMPAIGN,
  DEMO_CONFIRMED_CAMPAIGN_ID,
  DEMO_CONFIRMED_PARTICIPATION,
} from "@/lib/demo-data";

// Static demo campaign detail. Both possible ids are hardcoded seed
// records -- there is no dynamic fetch, so no route param here ever
// reaches a network call. Purely read-only rendering.

function money(cents: number | null): string {
  if (cents === null) return "—";
  return `$${(cents / 100).toFixed(2)}`;
}

const STATUS_STEPS = ["submitted", "under_review", "confirmed", "paid"];

export function generateStaticParams() {
  return [{ id: DEMO_AVAILABLE_CAMPAIGN_ID }, { id: DEMO_CONFIRMED_CAMPAIGN_ID }];
}

export default function DemoCampaignDetailPage({ params }: { params: { id: string } }) {
  const { id } = params;

  if (id === DEMO_AVAILABLE_CAMPAIGN_ID) {
    return (
      <main className="mx-auto flex min-h-screen max-w-md flex-col gap-5 p-4 pb-16">
        <DemoPageViewTracker demo="rep_campaign_detail" />
        <DemoBanner />
        <DemoBackLink href="/demo/rep" label="Back to dashboard" />

        <div>
          <h1 className="text-xl font-semibold">{DEMO_AVAILABLE_CAMPAIGN.title}</h1>
          <p className="text-sm text-muted-foreground">{DEMO_AVAILABLE_CAMPAIGN.product_name}</p>
        </div>

        <section className="flex flex-col gap-2 rounded-lg border border-border p-3">
          <div>
            <p className="text-xs font-medium text-muted-foreground">Goal</p>
            <p className="text-sm">{DEMO_AVAILABLE_CAMPAIGN.campaign_goal}</p>
          </div>
          <div>
            <p className="text-xs font-medium text-muted-foreground">Deliverables</p>
            <p className="text-sm">{DEMO_AVAILABLE_CAMPAIGN.deliverables_description}</p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {DEMO_AVAILABLE_CAMPAIGN.target_categories.map((c) => (
              <Badge key={c} variant="outline">
                {c}
              </Badge>
            ))}
          </div>
          <div className="flex items-center justify-between pt-1">
            <p className="text-xs font-medium text-muted-foreground">Payout</p>
            <p className="text-base font-semibold">{money(DEMO_AVAILABLE_CAMPAIGN.payout_per_rep_cents)}</p>
          </div>
        </section>

        <section className="rounded-lg border border-border bg-muted/40 p-3 text-sm text-muted-foreground">
          In the real app, you&apos;d apply here, accept the FTC sponsorship disclosure, and submit your work once
          approved. This demo is read-only, so applying is disabled.
        </section>

        <StartBuildingYoursButton />
      </main>
    );
  }

  if (id === DEMO_CONFIRMED_CAMPAIGN_ID) {
    const currentIndex = STATUS_STEPS.indexOf(DEMO_CONFIRMED_PARTICIPATION.status);
    return (
      <main className="mx-auto flex min-h-screen max-w-md flex-col gap-5 p-4 pb-16">
        <DemoPageViewTracker demo="rep_campaign_detail" />
        <DemoBanner />
        <DemoBackLink href="/demo/rep" label="Back to dashboard" />

        <div>
          <h1 className="text-xl font-semibold">{DEMO_CONFIRMED_CAMPAIGN.title}</h1>
          <p className="text-sm text-muted-foreground">{DEMO_CONFIRMED_CAMPAIGN.product_name}</p>
        </div>

        <section className="flex flex-col gap-2 rounded-lg border border-border p-3">
          <div>
            <p className="text-xs font-medium text-muted-foreground">Goal</p>
            <p className="text-sm">{DEMO_CONFIRMED_CAMPAIGN.campaign_goal}</p>
          </div>
          <div>
            <p className="text-xs font-medium text-muted-foreground">Deliverables</p>
            <p className="text-sm">{DEMO_CONFIRMED_CAMPAIGN.deliverables_description}</p>
          </div>
          <div className="flex items-center justify-between pt-1">
            <p className="text-xs font-medium text-muted-foreground">Payout</p>
            <p className="text-base font-semibold">{money(DEMO_CONFIRMED_PARTICIPATION.payout_cents)}</p>
          </div>
        </section>

        <Card>
          <CardHeader>
            <CardTitle>Submitted work (example)</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            <p className="text-sm">{DEMO_CONFIRMED_PARTICIPATION.submission_text}</p>
            <div className="flex flex-col gap-1">
              {DEMO_CONFIRMED_PARTICIPATION.submission_file_urls.map((f) => (
                <p key={f} className="text-xs text-muted-foreground">
                  📎 {f} (mock file, not a real upload)
                </p>
              ))}
            </div>
          </CardContent>
        </Card>

        <section className="flex flex-col gap-2 rounded-lg border border-border p-3">
          <h2 className="text-sm font-semibold">Status</h2>
          <div className="flex items-center justify-between">
            {STATUS_STEPS.map((step, i) => (
              <div key={step} className="flex flex-1 flex-col items-center gap-1">
                <div className={`size-3 rounded-full ${i <= currentIndex ? "bg-primary" : "bg-muted"}`} />
                <span className="text-center text-[0.65rem] text-muted-foreground">{step.replace("_", " ")}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-lg border border-border bg-muted/40 p-3 text-sm text-muted-foreground">
          This campaign is shown as confirmed and awaiting payout. This demo is read-only, so there&apos;s no
          withdraw action here.
        </section>

        <StartBuildingYoursButton />
      </main>
    );
  }

  notFound();
}
