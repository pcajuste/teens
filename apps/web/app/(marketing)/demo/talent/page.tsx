import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CompletenessPanel } from "@/components/talent/completeness-panel";
import { EarningsPanel } from "@/components/talent/earnings-panel";
import { ProfileView } from "@/components/talent/profile-view";
import {
  DemoBanner,
  DemoPageViewTracker,
  StartBuildingYoursButton,
} from "@/components/demo/demo-chrome";
import {
  DEMO_AVAILABLE_CAMPAIGN,
  DEMO_CONFIRMED_CAMPAIGN,
  DEMO_CONFIRMED_PARTICIPATION,
  DEMO_EARNINGS,
  DEMO_TALENT_PROFILE,
} from "@/lib/demo-data";

// Read-only demo dashboard. No auth, no session, no API calls -- every
// value on this page comes from the local seed module in lib/demo-data.ts.
// Nothing here can mutate server-side state because nothing here talks
// to a server at all.
function money(cents: number | null): string {
  if (cents === null) return "—";
  return `$${(cents / 100).toFixed(2)}`;
}

const STATUS_LABEL: Record<string, string> = {
  submitted: "Submitted",
  under_review: "Under review",
  confirmed: "Confirmed",
  paid: "Paid",
};

export default function DemoTalentDashboardPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col gap-6 p-4 pb-16">
      <DemoPageViewTracker demo="talent_dashboard" />
      <DemoBanner />

      <header>
        <h1 className="text-xl font-semibold">Maya&apos;s dashboard</h1>
        <p className="text-sm text-text-2">
          A preview of what a Teenure Talent dashboard looks like once your
          profile is fully built out.
        </p>
      </header>

      <section>
        <ProfileView profile={DEMO_TALENT_PROFILE} />
      </section>

      <section>
        <CompletenessPanel profile={DEMO_TALENT_PROFILE} />
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-sm font-semibold text-text-3">
          Earnings
        </h2>
        <EarningsPanel earnings={DEMO_EARNINGS} />
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-sm font-semibold text-text-3">
          Active campaign
        </h2>
        <Card variant="earned">
          <CardHeader>
            <div className="flex items-center justify-between gap-2">
              <CardTitle>{DEMO_CONFIRMED_CAMPAIGN.title}</CardTitle>
              <Badge variant="earned">
                {STATUS_LABEL[DEMO_CONFIRMED_PARTICIPATION.status] ??
                  DEMO_CONFIRMED_PARTICIPATION.status}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-text-2">
              {DEMO_CONFIRMED_CAMPAIGN.product_name}
            </p>
            <div className="flex items-center justify-between pt-2">
              <Link
                href={`/demo/talent/campaigns/${DEMO_CONFIRMED_CAMPAIGN.id}`}
                className="text-sm font-medium underline"
              >
                View details
              </Link>
              <span className="text-sm font-semibold text-gold">
                {money(DEMO_CONFIRMED_PARTICIPATION.payout_cents)}
              </span>
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-sm font-semibold text-text-3">
          Available campaign
        </h2>
        <Link
          href={`/demo/talent/campaigns/${DEMO_AVAILABLE_CAMPAIGN.id}`}
          className="block"
        >
          <Card className="min-h-11">
            <CardHeader>
              <CardTitle>{DEMO_AVAILABLE_CAMPAIGN.title}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-text-2">
                {DEMO_AVAILABLE_CAMPAIGN.product_name}
              </p>
              <div className="flex items-center justify-between pt-1">
                <span className="text-sm font-semibold">
                  {money(DEMO_AVAILABLE_CAMPAIGN.payout_per_talent_cents)}
                </span>
                <div className="flex flex-wrap gap-1">
                  {DEMO_AVAILABLE_CAMPAIGN.target_categories
                    .slice(0, 3)
                    .map((c) => (
                      <Badge key={c} variant="outline">
                        {c}
                      </Badge>
                    ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </Link>
      </section>

      <StartBuildingYoursButton />
    </main>
  );
}
