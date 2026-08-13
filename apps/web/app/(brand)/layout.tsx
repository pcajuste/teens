"use client";

import { AuthProvider } from "@/lib/auth-context";
import { AuthGate, CenteredMessage } from "@/lib/auth-gate";

// /brand/onboarding stays reachable even while account_status='pending' -- a
// pending brand must be able to submit their company profile, since submitting
// it is what admin review (Prompt 13) actually reviews. Every other
// authenticated route stays blocked behind the "under review" state.
const ALLOWED_WHILE_PENDING_PATHS = new Set(["/brand/onboarding"]);

export default function BrandLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <AuthGate
        role="brand"
        publicPaths={["/brand/signup"]}
        pendingState={(me, pathname) =>
          me.pending_reason === "pending_admin_approval" && !ALLOWED_WHILE_PENDING_PATHS.has(pathname) ? (
            <CenteredMessage title="Your account is under review">
              <p className="max-w-sm text-sm text-text-2">
                Every brand on Teenure is verified before they can run campaigns. We&apos;ll email you
                as soon as your account is approved -- usually within one business day.
              </p>
              <a href="/brand/onboarding" className="text-sm font-medium text-primary hover:underline">
                Finish your company profile
              </a>
            </CenteredMessage>
          ) : null
        }
      >
        {children}
      </AuthGate>
    </AuthProvider>
  );
}
