"use client";

import { AuthProvider } from "@/lib/auth-context";
import { AuthGate, CenteredMessage } from "@/lib/auth-gate";

export default function RepLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <AuthGate
        role="rep"
        publicPaths={["/rep/signup"]}
        pendingState={(me) =>
          me.pending_reason === "awaiting_parental_consent" ? (
            <CenteredMessage title="Waiting on your parent">
              <p className="max-w-sm text-sm text-muted-foreground">
                Because you&apos;re under 16, a parent or guardian needs to approve your account before
                you can use Teenure. Check with them to confirm they received the consent email, or ask
                them to check their spam folder.
              </p>
            </CenteredMessage>
          ) : null
        }
      >
        {children}
      </AuthGate>
    </AuthProvider>
  );
}
