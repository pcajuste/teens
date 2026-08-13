import Link from "next/link";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { buttonVariants } from "@/components/ui/button";
import { Section, SectionHeading } from "@/components/marketing/page-shell";

const NOT_LIST = [
  "Not a social network — no feed, no likes, no followers, no trending content.",
  "Not a dating platform — no matching between users, no talent-to-talent contact of any kind.",
  "Not Instagram or TikTok — talents submit private campaign evidence to brands, never public posts.",
  "Not a general content platform — no status updates, no photos, no personal expression outside a bio.",
  "Not an influencer marketplace — talents are verified peer voices with documented track records, not influencers for hire.",
  "Not a gig app — the profile that compounds over years is the product, not any single transaction.",
];

const AUDIENCES = [
  {
    href: "/talents",
    label: "Talents",
    title: "Build a record no one can fake",
    description:
      "Earn real money through brand campaigns and walk away with a verified achievement record colleges and employers actually trust.",
  },
  {
    href: "/brands",
    label: "Brands",
    title: "Reach real teens, not creators",
    description:
      "Run authentic peer-influence campaigns with verified talents and get trend intelligence you can't buy anywhere else.",
  },
  {
    href: "/recruiters",
    label: "Recruiters",
    title: "See proof, not essays",
    description:
      "Search and contact students with documented, brand-confirmed performance — before they're on anyone else's radar.",
  },
];

export default function MarketingHomePage() {
  return (
    <>
      <section className="border-b border-border bg-secondary/30">
        <div className="mx-auto max-w-4xl px-4 py-20 text-center sm:py-28">
          <p className="text-xs font-semibold uppercase tracking-wide text-primary">
            Earn yours early
          </p>
          <h1 className="mt-4 text-3xl font-semibold tracking-tight sm:text-5xl">
            A verified professional achievement record for teenagers.
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-base leading-relaxed text-muted-foreground sm:text-lg">
            Every other teen platform captures attention. Teenure captures
            verified performance. Teens complete real brand campaigns, earn real
            money, and build a documented record that colleges and employers can
            trust — because a brand confirmed it, not because a teen claimed it.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link
              href="/talent/signup"
              className={buttonVariants({ size: "lg" })}
            >
              Get started as a talent
            </Link>
            <Link
              href="/demo/talent"
              className={buttonVariants({ variant: "outline", size: "lg" })}
            >
              See a live demo
            </Link>
          </div>
        </div>
      </section>

      <Section className="max-w-3xl text-center">
        <p className="text-xs font-semibold uppercase tracking-wide text-primary">
          The platform rule
        </p>
        <blockquote className="mt-4 text-xl font-semibold leading-snug tracking-tight sm:text-2xl">
          &ldquo;Teenure is a verified professional achievement record for
          teenagers. Every feature either adds to that record or it does not
          belong on the platform.&rdquo;
        </blockquote>
        <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
          If a proposed feature doesn&apos;t directly build, verify, or surface
          a talent&apos;s achievement record, it doesn&apos;t get built — full
          stop. That single rule is why Teenure looks nothing like a teen social
          app.
        </p>
      </Section>

      <Section className="max-w-5xl">
        <SectionHeading>
          Built for three people who need proof, not a profile
        </SectionHeading>
        <div className="mt-8 grid gap-4 sm:grid-cols-3">
          {AUDIENCES.map((a) => (
            <Card key={a.href} className="justify-between">
              <CardHeader>
                <p className="text-xs font-semibold uppercase tracking-wide text-primary">
                  {a.label}
                </p>
                <CardTitle className="text-lg">{a.title}</CardTitle>
                <CardDescription>{a.description}</CardDescription>
              </CardHeader>
              <CardContent>
                <Link
                  href={a.href}
                  className={buttonVariants({ variant: "outline", size: "sm" })}
                >
                  Learn more
                </Link>
              </CardContent>
            </Card>
          ))}
        </div>
      </Section>

      <Section className="max-w-3xl">
        <SectionHeading>What Teenure is not</SectionHeading>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          Teenure is deliberately narrow. That restraint is a feature, not a
          limitation.
        </p>
        <ul className="mt-6 flex flex-col gap-4">
          {NOT_LIST.map((item) => (
            <li
              key={item}
              className="flex gap-3 text-sm leading-relaxed text-foreground"
            >
              <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-destructive/10 text-xs font-semibold text-destructive">
                &times;
              </span>
              {item}
            </li>
          ))}
        </ul>
        <p className="mt-6 text-sm leading-relaxed text-muted-foreground">
          Parents, schools, brands, and colleges all get the same promise:
          nothing here isn&apos;t serious. Read more on our{" "}
          <Link
            href="/trust"
            className="font-medium text-primary hover:underline"
          >
            trust &amp; compliance page
          </Link>
          , or see how it works for{" "}
          <Link
            href="/parents"
            className="font-medium text-primary hover:underline"
          >
            parents
          </Link>{" "}
          and{" "}
          <Link
            href="/schools"
            className="font-medium text-primary hover:underline"
          >
            schools
          </Link>
          .
        </p>
      </Section>

      <section className="border-t border-border bg-secondary/30">
        <div className="mx-auto max-w-3xl px-4 py-16 text-center">
          <h2 className="text-2xl font-semibold tracking-tight">
            See it before you sign up for it
          </h2>
          <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">
            Walk through a real Talent dashboard — profile, campaigns, and
            earnings — with no account required.
          </p>
          <div className="mt-6">
            <Link href="/demo/talent" className={buttonVariants({ size: "lg" })}>
              Try the Talent demo
            </Link>
          </div>
        </div>
      </section>
    </>
  );
}
