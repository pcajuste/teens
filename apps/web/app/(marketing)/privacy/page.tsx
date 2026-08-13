import Link from "next/link";
import { Card } from "@/components/ui/card";
import { MarketingHero, Section } from "@/components/marketing/page-shell";

export default function PrivacyPolicyPage() {
  return (
    <main>
      <MarketingHero eyebrow="Legal" title="Privacy policy" />
      <Section className="max-w-2xl">
        <Card className="p-6">
          <p className="text-sm font-semibold text-warning-foreground">
            Pending legal review
          </p>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            This page is a placeholder. Teenure&apos;s actual privacy policy —
            written specifically for a platform that handles minors&apos; data,
            and reviewed by a privacy lawyer for COPPA and state-law compliance
            (including California) — has not been published here yet. No legal
            text on this page should be relied on as Teenure&apos;s privacy
            policy.
          </p>
          <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
            In the meantime, see our{" "}
            <Link
              href="/trust"
              className="font-medium text-primary hover:underline"
            >
              trust &amp; compliance page
            </Link>{" "}
            for a plain-language summary of our data practices, or our{" "}
            <Link
              href="/parents"
              className="font-medium text-primary hover:underline"
            >
              parents page
            </Link>{" "}
            for what data is collected about a minor Talent and who can see it.
          </p>
        </Card>
      </Section>
    </main>
  );
}
