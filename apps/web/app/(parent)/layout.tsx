"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getParentSession } from "@/lib/parent-session";
import { CenteredMessage } from "@/lib/auth-gate";

// Routes reachable without a parent session: the magic-link request
// screen and the verify callback (which establishes the session
// itself). Everything else under /parent/* requires a valid,
// not-yet-expired stored session token.
const PUBLIC_PREFIXES = ["/parent/verify", "/parent/consent"];
const PUBLIC_EXACT = ["/parent"];

function isPublicPath(pathname: string): boolean {
  if (PUBLIC_EXACT.includes(pathname)) return true;
  return PUBLIC_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

/** Session gate for the parent portal. Deliberately does not reuse
 * lib/auth-gate.tsx/lib/auth-context.tsx -- those are built around a
 * Supabase Session object and this portal has no Supabase session at
 * all (parents aren't auth.users rows). Instead this checks for a
 * valid, unexpired token in localStorage (lib/parent-session.ts) on
 * mount and on every path change, and each API call in
 * lib/parent-api.ts clears that token on a 401 so a stale/revoked
 * session bounces back here too. */
export default function ParentLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [checked, setChecked] = useState(false);
  const [hasSession, setHasSession] = useState(false);

  useEffect(() => {
    const session = getParentSession();
    setHasSession(session !== null);
    setChecked(true);
  }, [pathname]);

  const isPublic = isPublicPath(pathname);

  useEffect(() => {
    if (!checked) return;
    if (!hasSession && !isPublic) {
      router.replace("/parent");
    }
  }, [checked, hasSession, isPublic, router]);

  if (isPublic) {
    return <>{children}</>;
  }

  if (!checked) {
    return <CenteredMessage title="Loading..." />;
  }

  if (!hasSession) {
    return <CenteredMessage title="Redirecting to sign in..." />;
  }

  return <>{children}</>;
}
