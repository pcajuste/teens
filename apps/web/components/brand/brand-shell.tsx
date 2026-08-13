"use client";

import { PortalShell } from "@/components/portal-shell";
import { useAuth } from "@/lib/auth-context";

interface BrandShellProps {
  title?: string;
  backHref?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}

const NAV = [
  { href: "/brand", label: "Campaigns" },
  { href: "/brand/challenges", label: "Challenges" },
  { href: "/brand/exclusivity", label: "Market tools" },
  { href: "/brand/onboarding", label: "Company profile" },
];

/** Shared page shell for every authenticated /brand/* screen -- the DS
 * sidebar pattern (Section 3E/7), same shape as every other portal shell. */
export function BrandShell({ title, backHref, action, children }: BrandShellProps) {
  const { signOut } = useAuth();

  return (
    <PortalShell
      portalLabel="Brand Portal"
      homeHref="/brand"
      navItems={NAV}
      title={title}
      backHref={backHref}
      action={action}
      containerWidth="max-w-5xl"
      onSignOut={() => signOut()}
    >
      {children}
    </PortalShell>
  );
}
