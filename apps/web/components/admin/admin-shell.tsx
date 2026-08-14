"use client";

import { PortalShell } from "@/components/portal-shell";
import { useAuth } from "@/lib/auth-context";

interface AdminShellProps {
  title?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}

const NAV = [
  { href: "/admin", label: "Queues" },
  { href: "/admin/campaigns", label: "Campaigns" },
  { href: "/admin/payments", label: "Payments" },
  { href: "/admin/exclusivity", label: "Exclusivity" },
  { href: "/admin/athletics", label: "Athletics" },
  { href: "/admin/modules", label: "Modules" },
  { href: "/admin/content-templates", label: "Content review" },
  { href: "/admin/analytics", label: "Analytics" },
  { href: "/admin/safety", label: "Safety reports", dangerDot: true },
];

/** Shared shell for /admin/* -- internal-only, so this leans toward
 * density/efficiency for staff working queues all day (Build Prompt
 * 13's own framing) while using the same DS sidebar pattern and tokens
 * as every other portal, not a fourth divergent style (DS Section 10:
 * "utilitarian, function over form", not "different design system").
 * The safety-report lane keeps its red dot as a standalone nav item --
 * the platform's highest-priority queue per deliverable 7. */
export function AdminShell({ title, action, children }: AdminShellProps) {
  const { signOut } = useAuth();

  return (
    <PortalShell
      portalLabel="Admin Portal"
      homeHref="/admin"
      navItems={NAV}
      title={title}
      action={action}
      containerWidth="max-w-6xl"
      onSignOut={() => signOut()}
    >
      {children}
    </PortalShell>
  );
}
