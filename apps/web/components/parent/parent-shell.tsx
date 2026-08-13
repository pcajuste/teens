"use client";

import { useRouter } from "next/navigation";
import { PortalShell } from "@/components/portal-shell";
import { clearParentSession } from "@/lib/parent-session";

const NAV = [
  { href: "/parent/dashboard", label: "Dashboard" },
  { href: "/parent/campaigns", label: "Campaigns" },
  { href: "/parent/filters", label: "Values filters" },
  { href: "/parent/settings", label: "Settings" },
];

interface ParentShellProps {
  title?: string;
  children: React.ReactNode;
}

/** Shared page shell for every authenticated /parent/* screen -- the DS
 * sidebar pattern (Section 3E/9: same canvas/surface tokens as every
 * other portal, deliberately no lighter/warmer palette for parents),
 * even though its session mechanism (localStorage token, not Supabase)
 * is entirely different under the hood. */
export function ParentShell({ title, children }: ParentShellProps) {
  const router = useRouter();

  function handleSignOut() {
    clearParentSession();
    router.replace("/parent");
  }

  return (
    <PortalShell portalLabel="Parent Portal" homeHref="/parent/dashboard" navItems={NAV} title={title} onSignOut={handleSignOut}>
      {children}
    </PortalShell>
  );
}
