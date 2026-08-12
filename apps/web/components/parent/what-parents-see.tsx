import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

/**
 * "What parents see" explainer (Prompt 4A deliverable 7) -- parents
 * unfamiliar with the platform need context on what each section means,
 * not just data.
 */
export function WhatParentsSeeExplainer() {
  return (
    <Card className="border-dashed">
      <CardHeader>
        <CardTitle>What you can see and do here</CardTitle>
        <CardDescription>Teenure&apos;s parent portal is intentionally limited in scope.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2 text-sm text-muted-foreground">
        <p>
          <strong>Profile:</strong> the same summary a college recruiter or brand would see, plus your
          teen&apos;s earnings, which we show you because it&apos;s their income.
        </p>
        <p>
          <strong>Approvals:</strong> if approval is required for your teen&apos;s age, you&apos;ll review
          and approve or block each campaign brief before they can accept it.
        </p>
        <p>
          <strong>Filters:</strong> you can block entire categories of campaigns (e.g. gambling, dating
          apps) so your teen never even sees them as an option.
        </p>
        <p>
          <strong>What we don&apos;t show you:</strong> private messages, submission files/text, or brand
          contact details. This portal is oversight, not a copy of their account.
        </p>
      </CardContent>
    </Card>
  );
}
