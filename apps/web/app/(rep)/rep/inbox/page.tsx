import Link from "next/link";

// Backend deferred to Prompt 11 (no GET /reps/inbox or POST
// /reps/inbox/:id/read exist yet). Per Prompt 6's own instructions,
// this is a minimal placeholder rather than a full inbox UI -- there
// is nothing here to wire up yet. Deliberately still has no reply
// box/button/compose affordance so nothing needs to be re-audited for
// Section 1A compliance once the backend lands.
export default function InboxPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center gap-3 p-6 text-center">
      <h1 className="text-xl font-semibold">Inbox</h1>
      <p className="text-sm text-muted-foreground">
        Coming soon. Recruiter messages will appear here as a read-only list -- there is no reply feature by
        design.
      </p>
      <Link href="/rep" className="text-sm font-medium underline">
        Back to dashboard
      </Link>
    </main>
  );
}
