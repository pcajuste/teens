import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { MarketingHero, Section, SectionHeading } from "@/components/marketing/page-shell";
import { DemoPageViewTracker } from "@/components/demo/demo-chrome";
import { ScheduleDemoButton } from "@/components/demo/schedule-demo-button";

// Build Prompt 12A part 2. This is the single highest-stakes surface
// for Section 0A -- a sales page seen before a brand ever creates an
// account. Deliberately not a signup flow: the only CTA is "Schedule a
// demo," never a self-serve campaign builder.
const HOW_IT_WORKS = [
  {
    title: "Verified Talent network",
    body: "Every teen on Teenure builds a verified professional record -- completed campaigns, ratings, and skill badges, not follower counts.",
  },
  {
    title: "Campaign model",
    body: "You define a campaign brief, budget, and target categories/cities. We match it against opted-in Talent profiles and handle the entire payout lifecycle, including parental consent for minors.",
  },
  {
    title: "Documented completion",
    body: "Every campaign closes with performance evidence you can verify -- not a screenshot you have to trust.",
  },
  {
    title: "Compliance built in",
    body: "FTC sponsorship disclosure, parental consent, and age-gating are enforced server-side on every campaign, automatically.",
  },
];

export default function DemoBrandPage() {
  return (
    <main className="flex flex-col">
      <DemoPageViewTracker demo="brand_sales" />
      <MarketingHero
        eyebrow="For brands"
        title="A verified teen Talent network, without the relationship overhead"
        description="See how campaigns work on Teenure before you talk to us. This page is a walkthrough, not a sign-up -- there's nothing to configure here."
      >
        <div className="mt-6">
          <ScheduleDemoButton />
        </div>
      </MarketingHero>

      <Section>
        <SectionHeading>How it works</SectionHeading>
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
          {HOW_IT_WORKS.map((item) => (
            <Card key={item.title}>
              <CardHeader>
                <CardTitle>{item.title}</CardTitle>
                <CardDescription>{item.body}</CardDescription>
              </CardHeader>
              <CardContent />
            </Card>
          ))}
        </div>
      </Section>

      <Section>
        <div className="flex flex-col items-center gap-4 text-center">
          <h2 className="text-xl font-semibold">Ready to see it with your own campaign brief?</h2>
          <p className="max-w-md text-sm text-text-2">
            Talk to us first -- campaigns on Teenure aren&apos;t self-serve. We&apos;ll
            walk through targeting, budget, and payout mechanics together.
          </p>
          <ScheduleDemoButton />
        </div>
      </Section>
    </main>
  );
}
