import Link from "next/link";
import { Card } from "@/components/ui/card";
import { MarketingHero, Section } from "@/components/marketing/page-shell";

export default function TermsOfServicePage() {
  return (
    <main>
      <MarketingHero eyebrow="Legal" title="Terms of service" />
      <Section className="max-w-2xl">
        <Card className="p-6">
          <p className="text-sm font-semibold text-warning-foreground">Pending legal review</p>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            This page is a placeholder. Teenure&apos;s terms of service — separate terms for each user type (talent,
            brand, recruiter, and the parent oversight role), reviewed by a lawyer — have not been published here
            yet. No legal text on this page should be relied on as Teenure&apos;s terms of service.
          </p>
          <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
            In the meantime, see our{" "}
            <Link href="/trust" className="font-medium text-primary hover:underline">
              trust &amp; compliance page
            </Link>{" "}
            for a plain-language summary of the platform&apos;s policies.
          </p>
        </Card>
      </Section>
    </main>
  );
}
