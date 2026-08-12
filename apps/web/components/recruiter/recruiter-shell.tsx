"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

interface RecruiterShellProps {
  title?: string;
  backHref?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}

/** Shared page shell for every authenticated /recruiter/* screen -- same
 * shape as components/brand/brand-shell.tsx and components/rep/rep-shell.tsx,
 * reusing the same tokens and top-bar pattern so all three portals read as
 * one product (Section 0A). Desktop-primary audience (college admissions /
 * employer staff), so the top bar carries a few more persistent nav links
 * than the rep shell, matching brand-shell's density. */
export function RecruiterShell({ title, backHref, action, children }: RecruiterShellProps) {
  const { signOut } = useAuth();

  return (
    <div className="min-h-screen bg-secondary/30">
      <header className="border-b border-border bg-card">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-6">
            <Link href="/recruiter" className="flex items-center gap-2">
              <span className="flex size-7 items-center justify-center rounded-md bg-primary text-xs font-bold text-primary-foreground">
                T
              </span>
              <span className="text-base font-semibold tracking-tight">Teenure</span>
              <span className="ml-1 rounded-md bg-accent px-1.5 py-0.5 text-[0.65rem] font-semibold uppercase tracking-wide text-accent-foreground">
                Recruiter
              </span>
            </Link>
            <nav className="hidden items-center gap-5 sm:flex">
              <Link href="/recruiter" className="text-sm font-medium text-muted-foreground hover:text-foreground">
                Search
              </Link>
              <Link href="/recruiter/saved" className="text-sm font-medium text-muted-foreground hover:text-foreground">
                Saved
              </Link>
              <Link href="/recruiter/messages" className="text-sm font-medium text-muted-foreground hover:text-foreground">
                Messages
              </Link>
              <Link href="/recruiter/subscription" className="text-sm font-medium text-muted-foreground hover:text-foreground">
                Subscription
              </Link>
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/recruiter/profile" className="text-sm font-medium text-muted-foreground hover:text-foreground">
              Institution profile
            </Link>
            <button onClick={() => signOut()} className="text-sm font-medium text-muted-foreground hover:text-foreground">
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8 pb-16">
        {backHref ? (
          <Link href={backHref} className="w-fit text-sm font-medium text-muted-foreground hover:text-foreground">
            ← Back
          </Link>
        ) : null}
        {title || action ? (
          <div className="flex items-center justify-between gap-4">
            {title ? <h1 className="text-2xl font-semibold tracking-tight">{title}</h1> : <span />}
            {action}
          </div>
        ) : null}
        {children}
      </main>
    </div>
  );
}
