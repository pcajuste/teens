"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth-context";
import type { MeResponse } from "@/lib/types";

export interface AuthGateProps {
  children: React.ReactNode;
  /** Role this route group is for. A session belonging to a different role is bounced back to /login. */
  role: string;
  /** Paths within this route group reachable without a session (e.g. signup). */
  publicPaths: string[];
  /** Render a blocking screen for a given `me`/pathname (e.g. "waiting on parent", "under review"). Return null to fall through to `children`. */
  pendingState?: (me: MeResponse, pathname: string) => React.ReactNode | null;
}

/**
 * Shared session/role gate for every authenticated route group. Each portal's
 * layout supplies its own `role`, `publicPaths`, and (optionally) a
 * `pendingState` renderer for portal-specific blocking states -- the
 * session/loading/role/suspension control flow itself is not duplicated
 * per portal.
 */
export function AuthGate({ children, role, publicPaths, pendingState }: AuthGateProps) {
  const { session, me, loading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const isPublic = publicPaths.includes(pathname);

  useEffect(() => {
    if (loading) return;
    if (!session && !isPublic) {
      router.replace("/login");
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

  if (me && me.role !== role) {
    return (
      <CenteredMessage title="Wrong portal">
        <p className="max-w-sm text-sm text-muted-foreground">
          This account isn&apos;t a {role} account.
        </p>
        <a href="/login" className="text-sm font-medium text-primary hover:underline">
          Back to sign in
        </a>
      </CenteredMessage>
    );
  }

  if (me) {
    const pending = pendingState?.(me, pathname);
    if (pending) {
      return <>{pending}</>;
    }
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

export function CenteredMessage({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-3 p-6 text-center">
      <h1 className="text-xl font-semibold">{title}</h1>
      {children}
    </main>
  );
}
