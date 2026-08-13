"use client";

import { PortalShell } from "@/components/portal-shell";
import { useAuth } from "@/lib/auth-context";

interface RecruiterShellProps {
  title?: string;
  backHref?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}

const NAV = [
  { href: "/recruiter", label: "Search" },
  { href: "/recruiter/saved", label: "Saved" },
  { href: "/recruiter/messages", label: "Messages" },
  { href: "/recruiter/subscription", label: "Subscription" },
  { href: "/recruiter/profile", label: "Institution profile" },
];

/** Shared page shell for every authenticated /recruiter/* screen -- the
 * DS sidebar pattern (Section 3E/8), same shape as every other portal shell. */
export function RecruiterShell({ title, backHref, action, children }: RecruiterShellProps) {
  const { signOut } = useAuth();

  return (
    <PortalShell
      portalLabel="Recruiter Portal"
      homeHref="/recruiter"
      navItems={NAV}
      title={title}
      backHref={backHref}
      action={action}
      containerWidth="max-w-6xl"
      onSignOut={() => signOut()}
    >
      {children}
    </PortalShell>
  );
}
