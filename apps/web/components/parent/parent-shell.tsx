"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearParentSession } from "@/lib/parent-session";

const NAV_ITEMS = [
  { href: "/parent/dashboard", label: "Dashboard" },
  { href: "/parent/campaigns", label: "Campaigns" },
  { href: "/parent/filters", label: "Values filters" },
  { href: "/parent/settings", label: "Settings" },
];

interface ParentShellProps {
  title?: string;
  children: React.ReactNode;
}

/** Shared page shell for every authenticated /parent/* screen, mirroring
 * components/talent/talent-shell.tsx's structure/top-bar pattern so the parent
 * portal reads as the same product even though its session mechanism
 * (localStorage token, not Supabase) is entirely different under the
 * hood. */
export function ParentShell({ title, children }: ParentShellProps) {
  const pathname = usePathname();
  const router = useRouter();

  function handleSignOut() {
    clearParentSession();
    router.replace("/parent");
  }

  return (
    <div className="min-h-screen bg-secondary/30">
      <header className="border-b border-border bg-card">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-4">
          <Link href="/parent/dashboard" className="flex items-center gap-2">
            <span className="flex size-7 items-center justify-center rounded-md bg-primary text-xs font-bold text-primary-foreground">
              T
            </span>
            <span className="text-base font-semibold tracking-tight">
              Teenure Parent Portal
            </span>
          </Link>
          <button
            onClick={handleSignOut}
            className="text-sm font-medium text-muted-foreground hover:text-foreground"
          >
            Sign out
          </button>
        </div>
        <nav className="mx-auto flex max-w-3xl gap-4 px-4 pb-3">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`text-sm font-medium ${
                pathname === item.href
                  ? "text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </header>

      <main className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-8 pb-16">
        {title ? (
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        ) : null}
        {children}
      </main>
    </div>
  );
}
