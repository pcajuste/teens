import Link from "next/link";
import { Button } from "@/components/ui/button";

// Shared chrome for every screen under /demo/rep. Fully static, no
// client-side state, no network calls -- this whole route group must
// render with zero authenticated session and zero dependency on the
// FastAPI backend.
export function DemoBanner() {
  return (
    <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-center text-sm font-medium text-amber-800 dark:text-amber-300">
      Demo — this is example data. &quot;Maya Chen,&quot; her school, and every campaign shown here are fictional.
    </div>
  );
}

export function StartBuildingYoursButton({ className }: { className?: string }) {
  return (
    <Link href="/rep/signup" className={className}>
      {/* Links straight into the real age-gated signup flow (Build
          Prompt 4) -- no query params, no alternate entry point, no way
          to skip the age gate or parental consent from here. */}
      <Button className="h-11 w-full">Start building yours</Button>
    </Link>
  );
}

export function DemoBackLink({ href, label }: { href: string; label: string }) {
  return (
    <Link href={href} className="text-sm font-medium underline">
      {label}
    </Link>
  );
}
