"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getParentSession } from "@/lib/parent-session";
import { ParentNav } from "@/components/parent/parent-nav";

const PUBLIC_PATHS = new Set<string>();

/**
 * Gate for the parent portal (Prompt 4A deliverable 7). Unlike the rep
 * portal, there is no /parent/me-style "always works" endpoint to branch
 * on -- the parent session token itself is the only signal we have
 * client-side, so this just checks whether one is stored. An expired or
 * portal-closed token still fails on the first real /parent/* call (each
 * page below handles that 401/403 itself, per app.core.parent_security).
 */
export default function ParentLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [checked, setChecked] = useState(false);

  const isPublicPath = pathname?.startsWith("/parent/login") || pathname?.startsWith("/parent/verify");

  useEffect(() => {
    if (isPublicPath) {
      setChecked(true);
      return;
    }
    const session = getParentSession();
    if (!session) {
      router.replace("/parent/login");
      return;
    }
    setChecked(true);
  }, [isPublicPath, router]);

  if (isPublicPath) {
    return <>{children}</>;
  }

  if (!checked) {
    return (
      <main className="container flex min-h-screen items-center justify-center py-16">
        <p className="text-muted-foreground">Loading…</p>
      </main>
    );
  }

  return (
    <div className="flex min-h-screen flex-col">
      <div className="hidden sm:block">
        <ParentNav />
      </div>
      <div className="flex-1 pb-16 sm:pb-0">{children}</div>
      <div className="sm:hidden">
        <ParentNav />
      </div>
    </div>
  );
}
