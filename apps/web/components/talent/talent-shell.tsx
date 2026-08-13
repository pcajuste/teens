"use client";

import { PortalShell } from "@/components/portal-shell";
import { useAuth } from "@/lib/auth-context";

interface TalentShellProps {
  title?: string;
  backHref?: string;
  children: React.ReactNode;
}

const NAV = [
  { href: "/talent", label: "Dashboard" },
  { href: "/talent/learning", label: "Learning Hub" },
  { href: "/talent/scholarships", label: "Scholarships" },
  { href: "/talent/insight-feedback", label: "Insight & Feedback" },
  { href: "/talent/profile-preview", label: "Preview profile" },
];

/** Shared page shell for every authenticated /talent/* screen -- the DS
 * sidebar pattern (Section 3E/6), same shape as every other portal shell. */
export function TalentShell({ title, backHref, children }: TalentShellProps) {
  const { signOut } = useAuth();

  return (
    <PortalShell
      portalLabel="Talent Portal"
      homeHref="/talent"
      navItems={NAV}
      title={title}
      backHref={backHref}
      onSignOut={() => signOut()}
    >
      {children}
    </PortalShell>
  );
}
