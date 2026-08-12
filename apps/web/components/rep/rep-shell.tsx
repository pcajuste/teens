"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

interface RepShellProps {
  title?: string;
  backHref?: string;
  children: React.ReactNode;
}

/** Shared page shell for every authenticated /rep/* screen -- top bar +
 * a consistent max-width container, so the portal reads as one product
 * across screens (Section 0A). */
export function RepShell({ title, backHref, children }: RepShellProps) {
  const { signOut } = useAuth();

  return (
    <div className="min-h-screen bg-secondary/30">
      <header className="border-b border-border bg-card">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-4">
          <Link href="/rep" className="flex items-center gap-2">
            <span className="flex size-7 items-center justify-center rounded-md bg-primary text-xs font-bold text-primary-foreground">
              T
            </span>
            <span className="text-base font-semibold tracking-tight">Teenure</span>
          </Link>
          <div className="flex items-center gap-4">
            <Link href="/rep/learning" className="text-sm font-medium text-muted-foreground hover:text-foreground">
              Learning Hub
            </Link>
            <Link href="/rep/profile-preview" className="text-sm font-medium text-muted-foreground hover:text-foreground">
              Preview profile
            </Link>
            <button onClick={() => signOut()} className="text-sm font-medium text-muted-foreground hover:text-foreground">
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-8 pb-16">
        {backHref ? (
          <Link href={backHref} className="w-fit text-sm font-medium text-muted-foreground hover:text-foreground">
            ← Back
          </Link>
        ) : null}
        {title ? <h1 className="text-2xl font-semibold tracking-tight">{title}</h1> : null}
        {children}
      </main>
    </div>
  );
}
