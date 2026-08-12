import Link from "next/link";
import { Card } from "@/components/ui/card";
import { buttonVariants } from "@/components/ui/button";
import { MarketingHero, Section, SectionHeading } from "@/components/marketing/page-shell";

const MOTIVATIONS = [
  {
    title: "Verified initiative",
    body: "Find students who've actually done real-world work, confirmed by a third party — not who wrote the best essay about it.",
  },
  {
    title: "Recruit early",
    body: "See students before they're on every other platform's radar.",
  },
  {
    title: "Documented performance",
    body: "Campaign history, brand ratings, and skills — not self-reported claims you have to take on faith.",
  },
  {
    title: "A signal nobody else has",
    body: "Access to a talent pool defined by real completed work, not GPA or test scores alone.",
  },
];

export default function RecruitersPage() {
  return (
    <main>
      <MarketingHero
        eyebrow="For recruiters"
        title="See proof, not essays."
        description="Search and contact verified teen profiles built from real, brand-confirmed work. A subscription replaces guesswork with documented performance data."
      >
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/recruiter/signup" className={buttonVariants({ size: "lg" })}>
            Get recruiter access
          </Link>
        </div>
      </MarketingHero>

      <Section className="max-w-4xl">
        <SectionHeading>Why recruiters use Teenure</SectionHeading>
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
        <SectionHeading>How access works</SectionHeading>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          Reps only appear in recruiter search when they&apos;ve opted in — visibility is never on by default.
          Contacting a rep deducts a credit from your subscription, calculated and enforced entirely server-side,
          so there is never a way to see a profile without it being accounted for. Reps can only reply to a
          recruiter who has already messaged them; they cannot browse or contact recruiters, and recruiters cannot
          browse rep-to-rep activity because none exists.
        </p>
      </Section>

      <section className="border-t border-border bg-muted/30">
        <div className="mx-auto max-w-3xl px-4 py-14 text-center sm:px-6">
          <h2 className="text-xl font-semibold tracking-tight sm:text-2xl">Ready to see documented performance?</h2>
          <div className="mt-6">
            <Link href="/recruiter/signup" className={buttonVariants({ size: "lg" })}>
              Sign up as a recruiter
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
