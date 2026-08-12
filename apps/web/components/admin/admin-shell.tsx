"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";

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
  { href: "/admin/modules", label: "Modules" },
  { href: "/admin/analytics", label: "Analytics" },
];

/** Shared shell for /admin/* -- internal-only, so this leans toward
 * density/efficiency for staff working queues all day rather than the
 * first-impression polish of the external portals (Build Prompt 13's
 * own framing), while still using the same design tokens as every
 * other portal, not a fourth divergent style. The safety-report lane
 * is a standalone, visually distinct nav item (red dot) rather than
 * folded into "Queues" -- it's the platform's highest-priority queue
 * per deliverable 7's acceptance criterion. */
export function AdminShell({ title, action, children }: AdminShellProps) {
  const { signOut } = useAuth();
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-secondary/30">
      <header className="border-b border-border bg-card">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-6">
            <Link href="/admin" className="flex items-center gap-2">
              <span className="flex size-7 items-center justify-center rounded-md bg-primary text-xs font-bold text-primary-foreground">
                T
              </span>
              <span className="text-base font-semibold tracking-tight">Teenure</span>
              <span className="ml-1 rounded-md bg-foreground px-1.5 py-0.5 text-[0.65rem] font-semibold uppercase tracking-wide text-background">
                Admin
              </span>
            </Link>
            <nav className="hidden items-center gap-5 sm:flex">
              {NAV.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "text-sm font-medium text-muted-foreground hover:text-foreground",
                    pathname === item.href && "text-foreground"
                  )}
                >
                  {item.label}
                </Link>
              ))}
              <Link
                href="/admin/safety"
                className={cn(
                  "flex items-center gap-1.5 text-sm font-semibold text-destructive hover:text-destructive/80",
                  pathname === "/admin/safety" && "underline"
                )}
              >
                <span className="size-1.5 rounded-full bg-destructive" aria-hidden="true" />
                Safety reports
              </Link>
            </nav>
          </div>
          <button onClick={() => signOut()} className="text-sm font-medium text-muted-foreground hover:text-foreground">
            Sign out
          </button>
        </div>
      </header>
      <main className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-6">
        {title || action ? (
          <div className="flex items-center justify-between gap-4">
            {title ? <h1 className="text-xl font-semibold tracking-tight">{title}</h1> : <span />}
            {action}
          </div>
        ) : null}
        {children}
      </main>
    </div>
  );
}
