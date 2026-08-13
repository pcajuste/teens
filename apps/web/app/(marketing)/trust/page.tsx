import Link from "next/link";
import { Card } from "@/components/ui/card";
import {
  MarketingHero,
  Section,
  SectionHeading,
} from "@/components/marketing/page-shell";

const REQUIREMENTS = [
  {
    title: "Hard age gate",
    body: "Signup is blocked entirely for anyone under 13. Birthdate is collected and validated on the server, not just checked in the browser.",
  },
  {
    title: "Parental consent under 16",
    body: "A teen signing up under 16 cannot activate their account until a parent clicks a one-time consent link sent to their email. That link expires after 72 hours.",
  },
  {
    title: "FTC sponsorship disclosure",
    body: "Before accepting any paid campaign, a talent must accept a required disclosure acknowledgment, timestamped and stored, so sponsored work is always labeled sponsored.",
  },
  {
    title: "Data minimization",
    body: "We collect only the fields needed to run the platform. No passive behavioral tracking. No third-party data enrichment. Every field we collect has a stated purpose.",
  },
  {
    title: "Server-side money math",
    body: "Every payout, fee split, and recruiter contact-credit deduction is calculated on our servers. Nothing a device submits is trusted as the final number.",
  },
  {
    title: "Row-level security",
    body: "Our database enforces access control at the row level on every table, from the very first migration — not as a bolt-on after launch.",
  },
];

export default function TrustPage() {
  return (
    <main>
      <MarketingHero
        eyebrow="Trust & compliance"
        title="Built for a platform that handles minors' data and income."
        description="This page explains, in plain language, the technical and policy commitments behind Teenure — not legal boilerplate, but what's actually enforced in the product."
      />

      <Section className="max-w-4xl">
        <SectionHeading>Non-negotiable requirements</SectionHeading>
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          {REQUIREMENTS.map((r) => (
            <Card key={r.title} className="p-4">
              <p className="text-sm font-semibold">{r.title}</p>
              <p className="mt-1 text-sm text-muted-foreground">{r.body}</p>
            </Card>
          ))}
        </div>
      </Section>

      <Section className="max-w-3xl">
        <SectionHeading>
          How the intelligence layer stays anonymous
        </SectionHeading>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          Brands can subscribe to trend reports built from campaign performance
          data. That data is never used at the individual level. Before any
          report is generated, personally identifying information (talent ID, name,
          school name) is stripped, and results are aggregated to a category,
          city, and time-period level. A trend is never reported for a group
          smaller than 10 talents — this floor exists specifically so a brand
          can never reverse-engineer an individual teen&apos;s behavior from a
          report.
        </p>
      </Section>

      <Section className="max-w-3xl">
        <SectionHeading>
          Content boundaries, technically enforced
        </SectionHeading>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          These aren&apos;t policy promises we ask people to follow —
          they&apos;re structural. There is no messaging interface or endpoint
          between talents, so talent-to-talent contact isn&apos;t hidden, it&apos;s
          nonexistent. Talents cannot search or browse other Talent profiles; that
          search interface only exists for authenticated brand and recruiter
          accounts. Talents can only reply to a recruiter who messaged them first —
          there is no field or endpoint for a Talent to initiate contact. No
          public feed exists anywhere on the platform, and no profile photos are
          collected or displayed.
        </p>
      </Section>

      <Section className="max-w-3xl">
        <Card className="p-5">
          <p className="text-sm font-semibold">Read more</p>
          <p className="mt-2 text-sm text-muted-foreground">
            <Link
              href="/parents"
              className="font-medium text-primary hover:underline"
            >
              How the parent portal works
            </Link>{" "}
            &middot;{" "}
            <Link
              href="/privacy"
              className="font-medium text-primary hover:underline"
            >
              Privacy policy
            </Link>{" "}
            &middot;{" "}
            <Link
              href="/terms"
              className="font-medium text-primary hover:underline"
            >
              Terms of service
            </Link>
          </p>
        </Card>
      </Section>
    </main>
  );
}
