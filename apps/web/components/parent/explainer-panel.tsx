import { Card } from "@/components/ui/card";

/** Static "what parents see" copy -- deliverable 8. Parents arriving here
 * are often unfamiliar with the platform, so each dashboard section gets
 * a one-line plain-language explanation, not just raw data. */
export function ExplainerPanel() {
  return (
    <Card className="p-5">
      <p className="mb-3 text-sm font-semibold text-muted-foreground">What you&apos;re seeing</p>
      <dl className="flex flex-col gap-3 text-sm">
        <div>
          <dt className="font-medium">Dashboard</dt>
          <dd className="text-muted-foreground">
            A snapshot of your teen&apos;s public Teenure profile and how much they&apos;ve earned so far.
            This is the same summary a recruiter would see, plus their earnings.
          </dd>
        </div>
        <div>
          <dt className="font-medium">Campaign approvals</dt>
          <dd className="text-muted-foreground">
            Brand campaigns your teen has been matched to that need your sign-off before they can accept.
            You have 48 hours from the match to approve or block each one, or it auto-declines.
          </dd>
        </div>
        <div>
          <dt className="font-medium">Values filters</dt>
          <dd className="text-muted-foreground">
            Categories of campaigns you never want your teen offered at all. Blocked categories are
            filtered out before your teen ever sees them, and brands are never told why.
          </dd>
        </div>
        <div>
          <dt className="font-medium">Settings</dt>
          <dd className="text-muted-foreground">
            Whether every campaign needs your approval (always on for reps under 16), and whether you
            get a monthly email summary of activity.
          </dd>
        </div>
        <div>
          <dt className="font-medium">Account controls</dt>
          <dd className="text-muted-foreground">
            Suspending pauses your teen&apos;s account immediately -- they can&apos;t use Teenure until you
            (or an admin) unsuspend it.
          </dd>
        </div>
      </dl>
    </Card>
  );
}
