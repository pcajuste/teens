"use client";

import { AuthProvider } from "@/lib/auth-context";
import { AuthGate, CenteredMessage } from "@/lib/auth-gate";

// /recruiter/profile and /recruiter/subscription stay reachable while
// account_status='pending' -- a pending recruiter must be able to submit
// their institution profile (what admin review checks) and subscribe
// (the *other* half of the dual activation gate -- see
// apps/api/app/routers/webhooks.py's _handle_subscription_created), since
// both are how a recruiter gets out of 'pending' in the first place.
const ALLOWED_WHILE_PENDING_PATHS = new Set(["/recruiter/profile", "/recruiter/subscription"]);

export default function RecruiterLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <AuthGate
        role="recruiter"
        publicPaths={["/recruiter/signup"]}
        pendingState={(me, pathname) =>
          me.pending_reason === "pending_admin_approval" && !ALLOWED_WHILE_PENDING_PATHS.has(pathname) ? (
            <CenteredMessage title="Your account is under review">
              <p className="max-w-sm text-sm text-muted-foreground">
                Every recruiter on Teenure is verified before searching or contacting reps. This also
                requires an active subscription. We&apos;ll email you as soon as your institution is
                approved -- usually within one business day.
              </p>
              <div className="flex gap-4">
                <a href="/recruiter/profile" className="text-sm font-medium text-primary hover:underline">
                  Finish your institution profile
                </a>
                <a href="/recruiter/subscription" className="text-sm font-medium text-primary hover:underline">
                  Subscribe
                </a>
              </div>
            </CenteredMessage>
          ) : null
        }
      >
        {children}
      </AuthGate>
    </AuthProvider>
  );
}
