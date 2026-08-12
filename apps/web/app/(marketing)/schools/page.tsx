import Link from "next/link";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { buttonVariants } from "@/components/ui/button";
import { MarketingHero, Section, SectionHeading } from "@/components/marketing/page-shell";

export default function SchoolsPage() {
  return (
    <main>
      <MarketingHero
        eyebrow="For schools & counselors"
        title="A verified record that complements the transcript, not a platform to police."
        description="Teenure exists alongside your school's own policies — it doesn't compete with them, and it doesn't ask students to post anything unrelated to real work."
      />

      <Section className="max-w-3xl">
        <SectionHeading>How Teenure complements a transcript</SectionHeading>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          A transcript shows grades and course rigor. It doesn&apos;t show whether a student can deliver real work
          for a real organization, communicate with a client, or follow through on a commitment over months. A
          Teenure record does — every entry on it is a campaign a brand confirmed the student actually completed,
          not a claim the student wrote in an application essay. It&apos;s evidence, sitting next to the
          transcript, not replacing it.
        </p>
      </Section>

      <Section className="max-w-3xl">
        <SectionHeading>The verified achievement record</SectionHeading>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          Each rep&apos;s profile accumulates campaigns completed and brand-confirmed, categories of demonstrated
          work (athletics, gaming, fashion, music, academics, food, beauty, tech), brand ratings, and skills
          auto-tagged from the work itself — content creation, client communication, event activation, peer
          recruitment. Nothing on it is self-graded: every completed campaign carries the brand&apos;s
          confirmation, which is what makes it useful to a college admissions office or an employer evaluating a
          candidate. The profile a college or employer reviews is exactly this record — never a public post, a
          photo, or anything a student wrote about themselves without third-party confirmation.
        </p>
      </Section>

      <Section className="max-w-3xl">
        <SectionHeading>How to recommend it to students</SectionHeading>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          Teenure fits naturally into the same conversations you&apos;re already having about internships,
          part-time work, and extracurricular differentiation — it gives students a way to document real-world
          experience they can point recruiters to directly, with a built-in age gate and mandatory parental
          consent process for students under 16 (see our{" "}
          <Link href="/parents" className="font-medium text-primary hover:underline">
            parents page
          </Link>{" "}
          for the full model). It requires no school-side setup or integration — students sign up individually and
          share their profile with colleges or employers on their own terms.
        </p>
      </Section>

      <Section className="max-w-3xl">
        <Card>
          <CardHeader>
            <CardTitle>Recruiter access, for admissions and employer partners</CardTitle>
            <CardDescription>
              Colleges and employers can request recruiter access to search and contact students who&apos;ve
              opted in — students choose to be visible, and profiles show documented performance, not self-reported
              claims.
            </CardDescription>
          </CardHeader>
        </Card>
      </Section>

      <Section className="max-w-3xl">
        <Card className="p-5">
          <p className="text-sm font-semibold">See it in action</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Preview what a completed rep record actually looks like — profile, confirmed campaigns, and ratings —
            no account required.
          </p>
        </Card>
      </Section>

      <section className="border-t border-border bg-muted/30">
        <div className="mx-auto max-w-3xl px-4 py-14 text-center sm:px-6">
          <h2 className="text-xl font-semibold tracking-tight sm:text-2xl">
            Want to recommend Teenure to your students or employer partners?
          </h2>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <Link href="/demo/rep" className={buttonVariants({ size: "lg" })}>
              See a rep record
            </Link>
            <Link href="/recruiters" className={buttonVariants({ variant: "outline", size: "lg" })}>
              Learn about recruiter access
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
