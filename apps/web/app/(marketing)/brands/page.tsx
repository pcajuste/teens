import Link from "next/link";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { buttonVariants } from "@/components/ui/button";
import { MarketingHero, Section, SectionHeading } from "@/components/marketing/page-shell";

const MOTIVATIONS = [
  {
    title: "Authentic peer voices",
    body: "Reach teens through trusted, verified peers — not paid macro-influencers performing a persona.",
  },
  {
    title: "Trend intelligence, before it's mainstream",
    body: "Aggregated, anonymized signal from real campaign performance — see what's moving before it surfaces anywhere else.",
  },
  {
    title: "Documented completion",
    body: "Every campaign closes with performance evidence you can actually verify, not a screenshot you have to trust.",
  },
  {
    title: "No relationship overhead",
    body: "Skip the cost of managing individual student relationships, contracts, and one-off outreach.",
  },
];

const TIERS = [
  {
    title: "Campaign Access",
    body: "Pay per campaign to activate a curated set of verified reps matched to your target categories and cities.",
  },
  {
    title: "Intelligence Subscription",
    body: "Quarterly trend reports by category, region, and school type — aggregated and anonymized, minimum group size of 10. Never derived from an individual rep's data.",
  },
];

export default function BrandsPage() {
  return (
    <main>
      <MarketingHero
        eyebrow="For brands"
        title="Reach real teens, not creators."
        description="Run authentic peer-influence campaigns with verified reps, backed by documented completion — and access trend intelligence you can't buy anywhere else."
      >
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/brand/signup" className={buttonVariants({ size: "lg" })}>
            Start a campaign
          </Link>
        </div>
      </MarketingHero>

      <Section className="max-w-4xl">
        <SectionHeading>Why brands use Teenure</SectionHeading>
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          {MOTIVATIONS.map((m) => (
            <Card key={m.title} className="p-4">
              <p className="text-sm font-semibold">{m.title}</p>
              <p className="mt-1 text-sm text-muted-foreground">{m.body}</p>
            </Card>
          ))}
        </div>
      </Section>

      <Section className="max-w-4xl">
        <SectionHeading>Two product tiers</SectionHeading>
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          {TIERS.map((t) => (
            <Card key={t.title}>
              <CardHeader>
                <CardTitle>{t.title}</CardTitle>
                <CardDescription>{t.body}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
      </Section>

      <Section className="max-w-4xl">
        <SectionHeading>What you won&apos;t get</SectionHeading>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          Teenure does not sell individual rep behavioral data, and does not support open messaging, discovery, or
          browsing between your brand and reps outside a campaign context. Every submission you receive is scoped
          to the campaign brief, reviewed by you, and the FTC sponsorship disclosure is required before a rep can
          accept any paid campaign.
        </p>
      </Section>

      <section className="border-t border-border bg-muted/30">
        <div className="mx-auto max-w-3xl px-4 py-14 text-center sm:px-6">
          <h2 className="text-xl font-semibold tracking-tight sm:text-2xl">Ready to reach verified teen voices?</h2>
          <div className="mt-6">
            <Link href="/brand/signup" className={buttonVariants({ size: "lg" })}>
              Sign up as a brand
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
