import Link from "next/link";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { buttonVariants } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { MarketingHero, Section, SectionHeading } from "@/components/marketing/page-shell";

const MOTIVATIONS = [
  {
    title: "Earn real income",
    body: "No fixed schedule, no uniform. Get paid for completed, brand-confirmed campaign work.",
  },
  {
    title: "Build a differentiator",
    body: "A college application line that's verified by a third party, not a claim you wrote yourself.",
  },
  {
    title: "Get real-world experience",
    body: "Documented client communication, content, and event work before you ever apply for a job.",
  },
  {
    title: "Get discovered early",
    body: "Colleges and employers can find you before your peers are even on their radar — opt-in only.",
  },
];

const CATEGORIES = ["Athletics", "Gaming", "Fashion", "Music", "Academics", "Food", "Beauty", "Tech"];

const PROFILE_FIELDS = [
  "Campaigns completed and confirmed by the brand",
  "Total earnings",
  "Brand ratings, averaged across every campaign",
  "Skills auto-tagged from the campaign types you complete",
  "School, grade, graduation year, and city",
];

export default function RepsPage() {
  return (
    <main>
      <MarketingHero
        eyebrow="For reps"
        title="Earn yours early."
        description="Complete real brand campaigns, get paid, and build a verified achievement record that compounds every year of high school — an asset you can't get anywhere else and won't want to walk away from."
      >
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/rep/signup" className={buttonVariants({ size: "lg" })}>
            Create your profile
          </Link>
          <Link href="/demo/rep" className={buttonVariants({ variant: "outline", size: "lg" })}>
            See a rep profile
          </Link>
        </div>
      </MarketingHero>

      <Section className="max-w-4xl">
        <SectionHeading>Why reps join</SectionHeading>
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
        <SectionHeading>Categories</SectionHeading>
        <p className="mt-2 text-sm text-muted-foreground">
          Pick the categories that fit you. Campaigns are matched to your categories and city — you never see
          campaigns outside your interests.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          {CATEGORIES.map((c) => (
            <Badge key={c} variant="secondary">
              {c}
            </Badge>
          ))}
        </div>
      </Section>

      <Section className="max-w-4xl">
        <SectionHeading>What your profile builds over time</SectionHeading>
        <Card className="mt-6 p-5">
          <ul className="flex flex-col gap-3">
            {PROFILE_FIELDS.map((f) => (
              <li key={f} className="flex items-start gap-2 text-sm">
                <span className="mt-1 size-1.5 shrink-0 rounded-full bg-primary" />
                {f}
              </li>
            ))}
          </ul>
        </Card>
        <p className="mt-4 text-sm text-muted-foreground">
          Everything on your profile is self-reported by you and confirmed by the brand you worked with — no
          passive tracking, no data pulled in from anywhere else. Your profile is visible to brands and to
          recruiters you opt in to — never to other reps, and never in a public feed.
        </p>
      </Section>

      <Section className="max-w-4xl">
        <Card>
          <CardHeader>
            <CardTitle>Under 16?</CardTitle>
            <CardDescription>
              A parent or guardian will need to approve your account before it activates, and can require
              approval on each campaign. Read how that works on the{" "}
              <Link href="/parents" className="font-medium text-primary hover:underline">
                parents page
              </Link>
              .
            </CardDescription>
          </CardHeader>
        </Card>
      </Section>

      <section className="border-t border-border bg-muted/30">
        <div className="mx-auto max-w-3xl px-4 py-14 text-center sm:px-6">
          <h2 className="text-xl font-semibold tracking-tight sm:text-2xl">Ready to start your record?</h2>
          <div className="mt-6">
            <Link href="/rep/signup" className={buttonVariants({ size: "lg" })}>
              Sign up as a rep
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
