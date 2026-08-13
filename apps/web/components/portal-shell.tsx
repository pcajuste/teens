"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogoWordmark, LOGO_SIZES } from "@/components/logo";
import { cn } from "@/lib/utils";

// DS Section 3E: the sidebar nav pattern shared by every portal
// (talent/brand/recruiter/parent/admin). Desktop (md+): fixed 240px
// sidebar per spec. Below md, the sidebar collapses to a top bar with
// a horizontally-scrollable nav row -- the DS prompt doesn't address
// mobile explicitly, but every portal in this codebase is mobile-first
// (375px is a tested requirement elsewhere), so a fixed 240px sidebar
// that never adapts would be a regression, not a faithful application
// of the spec's intent.

export interface PortalNavItem {
  href: string;
  label: string;
  dangerDot?: boolean; // admin's safety-reports lane: red dot, not folded into a generic item
}

interface PortalShellProps {
  portalLabel: string;
  homeHref: string;
  navItems: PortalNavItem[];
  title?: string;
  backHref?: string;
  action?: React.ReactNode;
  onSignOut: () => void;
  containerWidth?: string;
  children: React.ReactNode;
}

export function PortalShell({
  portalLabel,
  homeHref,
  navItems,
  title,
  backHref,
  action,
  onSignOut,
  containerWidth = "max-w-3xl",
  children,
}: PortalShellProps) {
  const pathname = usePathname();

  const navLink = (item: PortalNavItem, mobile: boolean) => {
    const active = pathname === item.href;
    return (
      <Link
        key={item.href}
        href={item.href}
        className={cn(
          mobile
            ? "shrink-0 whitespace-nowrap rounded-[var(--r-sm)] px-3 py-1.5 text-sm font-medium"
            : "flex items-center gap-2 rounded-[var(--r-md)] px-3.5 py-2 text-sm font-medium transition-colors duration-150",
          active
            ? mobile
              ? "bg-teal-dim text-teal"
              : "border-l-[3px] border-teal bg-teal-dim pl-[11px] font-semibold text-teal"
            : "text-text-2 hover:bg-secondary hover:text-foreground"
        )}
      >
        {item.dangerDot ? (
          <span className="inline-flex items-center gap-1.5">
            <span className="size-1.5 rounded-full bg-danger" aria-hidden="true" />
            {item.label}
          </span>
        ) : (
          item.label
        )}
      </Link>
    );
  };

  return (
    <div className="min-h-screen bg-background md:flex">
      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-screen w-[240px] shrink-0 flex-col border-r border-border-muted bg-surface-1 px-3 py-6 md:flex">
        <Link href={homeHref} className="flex flex-col gap-3 px-2 pb-8">
          <LogoWordmark darkMode height={LOGO_SIZES.wordmark} />
          <span className="text-xs font-semibold uppercase tracking-[0.1em] text-text-2">{portalLabel}</span>
        </Link>
        <nav className="flex flex-1 flex-col gap-1">{navItems.map((item) => navLink(item, false))}</nav>
        <button
          onClick={onSignOut}
          className="mt-auto rounded-[var(--r-md)] px-3.5 py-2 text-left text-sm font-medium text-text-2 hover:bg-secondary hover:text-foreground"
        >
          Sign out
        </button>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile top bar */}
        <header className="border-b border-border-muted bg-card md:hidden">
          <div className="flex items-center justify-between px-4 py-3">
            <Link href={homeHref} className="flex items-center gap-2.5">
              <LogoWordmark darkMode height={LOGO_SIZES.wordmark} />
              <span className="h-4 w-px bg-border-dim" aria-hidden="true" />
              <span className="text-xs font-semibold uppercase tracking-wide text-text-2">{portalLabel}</span>
            </Link>
            <button onClick={onSignOut} className="text-sm font-medium text-text-2 hover:text-foreground">
              Sign out
            </button>
          </div>
          {navItems.length > 0 ? (
            <nav className="flex gap-2 overflow-x-auto px-4 pb-3">{navItems.map((item) => navLink(item, true))}</nav>
          ) : null}
        </header>

        <main className={cn("mx-auto flex w-full flex-col gap-6 px-4 py-8 pb-16", containerWidth)}>
          {backHref ? (
            <Link href={backHref} className="w-fit text-sm font-medium text-text-2 hover:text-foreground">
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
    </div>
  );
}
