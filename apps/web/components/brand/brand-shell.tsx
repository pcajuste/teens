"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

interface BrandShellProps {
  title?: string;
  backHref?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}

/** Shared page shell for every authenticated /brand/* screen -- same
 * shape as components/rep/rep-shell.tsx, reusing the same tokens and
 * top-bar pattern so the two portals read as one product (Section 0A). */
export function BrandShell({ title, backHref, action, children }: BrandShellProps) {
  const { signOut } = useAuth();

  return (
    <div className="min-h-screen bg-secondary/30">
      <header className="border-b border-border bg-card">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4">
          <Link href="/brand" className="flex items-center gap-2">
            <span className="flex size-7 items-center justify-center rounded-md bg-primary text-xs font-bold text-primary-foreground">
              T
            </span>
            <span className="text-base font-semibold tracking-tight">Teenure</span>
            <span className="ml-1 rounded-md bg-accent px-1.5 py-0.5 text-[0.65rem] font-semibold uppercase tracking-wide text-accent-foreground">
              Brand
            </span>
          </Link>
          <div className="flex items-center gap-4">
            <Link href="/brand/challenges" className="text-sm font-medium text-muted-foreground hover:text-foreground">
              Challenges
            </Link>
            <Link href="/brand/exclusivity" className="text-sm font-medium text-muted-foreground hover:text-foreground">
              Market tools
            </Link>
            <Link href="/brand/onboarding" className="text-sm font-medium text-muted-foreground hover:text-foreground">
              Company profile
            </Link>
            <button onClick={() => signOut()} className="text-sm font-medium text-muted-foreground hover:text-foreground">
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-8 pb-16">
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
