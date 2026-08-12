"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth-context";

const PUBLIC_PATHS = new Set(["/rep/signup", "/rep/login"]);

export function RepGate({ children }: { children: React.ReactNode }) {
  const { session, me, loading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const isPublic = PUBLIC_PATHS.has(pathname);

  useEffect(() => {
    if (loading) return;
    if (!session && !isPublic) {
      router.replace("/rep/login");
    }
  }, [loading, session, isPublic, router]);

  if (isPublic) {
    return <>{children}</>;
  }

  if (loading) {
    return <CenteredMessage title="Loading..." />;
  }

  if (!session) {
    return <CenteredMessage title="Redirecting to sign in..." />;
  }

  if (me?.pending_reason === "awaiting_parental_consent") {
    return (
      <CenteredMessage title="Waiting on your parent">
        <p className="max-w-sm text-sm text-muted-foreground">
          Because you&apos;re under 16, a parent or guardian needs to approve your account before you can
          use Teenure. Check with them to confirm they received the consent email, or ask them to check
          their spam folder.
        </p>
      </CenteredMessage>
    );
  }

  if (me?.account_status === "suspended" || me?.account_status === "rejected") {
    return (
      <CenteredMessage title="Account unavailable">
        <p className="max-w-sm text-sm text-muted-foreground">
          Your account is currently {me.account_status}. Contact support for more information.
        </p>
      </CenteredMessage>
    );
  }

  return <>{children}</>;
}

function CenteredMessage({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-3 p-6 text-center">
      <h1 className="text-xl font-semibold">{title}</h1>
      {children}
    </main>
  );
}
