import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { MarketingHero, Section, SectionHeading } from "@/components/marketing/page-shell";

const AGE_MODEL = [
  {
    range: "Under 16",
    body: "Every campaign requires your explicit approval before your teen can accept it. This is not optional and cannot be turned off while they're under 16.",
  },
  {
    range: "16–17",
    body: "Approval becomes opt-in: you can choose to keep requiring sign-off on every campaign, or let your teen accept campaigns on their own. You can turn this back on at any time.",
  },
  {
    range: "18",
    body: "The parent portal closes automatically on their 18th birthday. Your access ends; your teen's account becomes fully theirs.",
  },
];

const PARENT_PORTAL_FEATURES = [
  {
    title: "Campaign approval queue",
    body: "See every campaign your teen has been invited to and approve or block it before they can accept. A block never reveals your reason to the brand — it's shown as a neutral decline.",
  },
  {
    title: "Values filters",
    body: "Block entire categories of campaigns (e.g. alcohol-adjacent, political, dating/romantic framing) so your teen never even sees them as an option. This is enforced on the server, not just hidden in the app.",
  },
  {
    title: "Monthly digest",
    body: "A low-friction summary emailed monthly: campaigns completed, earnings, profile-completeness change, active categories. It never includes recruiter message content or submission files.",
  },
  {
    title: "Account controls",
    body: "Suspend your teen's account immediately if you need to. You can reverse a suspension you initiated yourself at any time.",
  },
];

const DATA_SEEN_BY: { audience: string; sees: string }[] = [
  { audience: "Brands", sees: "Profile bio, categories, campaign submissions for their own campaign, aggregated ratings." },
  { audience: "Opted-in recruiters", sees: "Profile bio, categories, campaign history, ratings — never contact info until your teen replies." },
  { audience: "You (parent)", sees: "Everything a recruiter's card view shows, plus total earnings and campaigns completed — never recruiter messages or submission files." },
  { audience: "Other reps", sees: "Nothing. Reps cannot search, view, or discover other reps at all." },
  { audience: "The public", sees: "Nothing. There is no public profile page, no feed, and nothing indexed publicly." },
];

export default function ParentsPage() {
  return (
    <>
      <MarketingHero
        eyebrow="For Parents"
        title="Supervised by design, not by promise."
        description="Teenure is a verified professional achievement record for teenagers — not a social platform. Here's exactly what your teen does here, what you can see, and how you stay in control."
      >
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/trust" className={buttonVariants({ variant: "outline", size: "lg" })}>
            Read our trust &amp; compliance page
          </Link>
        </div>
      </MarketingHero>

      <Section className="max-w-3xl">
        <SectionHeading>What Teenure is — and isn&apos;t</SectionHeading>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          Teenure is where teens 14–18 complete real, paid campaigns for real brands, and build a documented
          record of that work — confirmed by the brand, not self-reported. It is <strong>not</strong> a social
          network: there is no feed, no likes, no followers, no discovery-by-interest, and no way for your teen
          to post personal content. It is <strong>not</strong> a dating or messaging app: there is no matching
          between users, and reps cannot message each other or contact anyone unsolicited. There are no profile
          photos anywhere on the platform — profiles show category badges, campaign counts, and earnings, never
          an image of your child.
        </p>
      </Section>

      <Section className="max-w-4xl">
        <SectionHeading>How your child earns money</SectionHeading>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          Brands post campaigns targeted at categories (like gaming, fashion, or academics) and cities. Your
          teen accepts a matched campaign (subject to your approval if required — see below), completes the
          deliverable, and submits evidence to the brand for confirmation. Once confirmed, payment is calculated
          and processed entirely server-side — never by anything your teen or the brand submits directly — and
          appears in their earnings.
        </p>
      </Section>

      <Section className="max-w-4xl">
        <SectionHeading>Who sees their profile</SectionHeading>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          Nobody sees anything by default outside a campaign your teen accepted. Here&apos;s exactly who can see
          what:
        </p>
        <div className="mt-6 overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-left text-sm">
            <thead className="bg-secondary/50 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">Who</th>
                <th className="px-4 py-3 font-medium">What they see</th>
              </tr>
            </thead>
            <tbody>
              {DATA_SEEN_BY.map((row, i) => (
                <tr key={row.audience} className={i > 0 ? "border-t border-border" : undefined}>
                  <td className="px-4 py-3 font-medium">{row.audience}</td>
                  <td className="px-4 py-3 text-muted-foreground">{row.sees}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section className="max-w-4xl">
        <SectionHeading>What data is collected</SectionHeading>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          Only what your teen enters directly: profile bio, categories, school, grade, graduation year, city,
          and campaign submissions. There is no passive behavioral tracking, no inferred data, and no
          third-party data enrichment of any kind — every field is self-reported and consent-driven.
        </p>
      </Section>

      <Section className="max-w-4xl">
        <SectionHeading>The age-based autonomy model</SectionHeading>
        <div className="mt-6 flex flex-col gap-4">
          {AGE_MODEL.map((a) => (
            <Card key={a.range}>
              <CardHeader>
                <p className="text-xs font-semibold uppercase tracking-wide text-primary">{a.range}</p>
                <CardDescription className="text-sm text-foreground">{a.body}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
      </Section>

      <Section className="max-w-4xl">
        <SectionHeading>What you see in the parent portal</SectionHeading>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          You get your own login (no password — a secure email link) and a dashboard scoped narrowly to what
          you need:
        </p>
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          {PARENT_PORTAL_FEATURES.map((f) => (
            <Card key={f.title}>
              <CardHeader>
                <CardTitle className="text-base">{f.title}</CardTitle>
                <CardDescription>{f.body}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
        <p className="mt-4 text-xs text-muted-foreground">
          What you don&apos;t get: co-pilot access to your teen&apos;s account. You cannot message recruiters,
          edit their profile, or submit campaign work on their behalf.
        </p>
      </Section>

      <Section className="max-w-4xl">
        <SectionHeading>How to suspend the account</SectionHeading>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          From the parent portal, one action immediately suspends your teen&apos;s account — they&apos;re
          notified and our admin team is alerted. If you initiated the suspension, you can reverse it yourself
          at any time. (A suspension initiated by our admin team for a policy violation can only be reversed by
          admin.)
        </p>
      </Section>

      <Section className="max-w-3xl">
        <SectionHeading>Why the constraints are protective</SectionHeading>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          Every platform that starts clean and adds a social layer eventually turns the record into noise. We
          deliberately don&apos;t: no feed for your teen to perform for, no rep-to-rep contact for anyone to
          exploit, no photos to be judged on. What&apos;s here is documented, supervised, professional work —
          nothing your teen does on Teenure is designed to capture their attention. It&apos;s designed to build
          something they can point to for the next ten years.
        </p>
      </Section>

      <section className="border-t border-border bg-secondary/30">
        <div className="mx-auto max-w-3xl px-4 py-16 text-center">
          <h2 className="text-2xl font-semibold tracking-tight">Questions before your teen signs up?</h2>
          <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">
            Read our full trust and compliance breakdown, or preview a rep dashboard yourself — no account
            needed.
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <Link href="/trust" className={buttonVariants({ size: "lg" })}>
              Trust &amp; compliance
            </Link>
            <Link href="/demo/rep" className={buttonVariants({ variant: "outline", size: "lg" })}>
              See the rep demo
            </Link>
          </div>
        </div>
      </section>
    </>
  );
}
