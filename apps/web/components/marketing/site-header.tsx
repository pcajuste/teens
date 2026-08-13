"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogoWordmark } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const NAV_LINKS = [
  { href: "/talents", label: "Talents" },
  { href: "/brands", label: "Brands" },
  { href: "/recruiters", label: "Recruiters" },
  { href: "/parents", label: "Parents" },
  { href: "/schools", label: "Schools" },
  { href: "/trust", label: "Trust" },
];

// DS Section 5: sticky nav, ghost-styled links (teal-dim on the active
// tab), secondary "Log in", primary "Get started".
export function SiteHeader() {
  const pathname = usePathname();

  return (
    <header
      className="sticky top-0 z-40 border-b border-border-muted backdrop-blur-2xl"
      style={{ background: "rgba(10, 10, 18, 0.82)" }}
    >
      <div className="mx-auto flex h-[58px] max-w-6xl items-center justify-between px-4 sm:px-10">
        <Link href="/" className="flex items-center">
          <LogoWordmark darkMode height={30} />
        </Link>
        <nav className="hidden items-center gap-1 md:flex">
          {NAV_LINKS.map((link) => {
            const active = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  "rounded-[var(--r-sm)] px-3 py-1.5 text-[13.5px] font-medium transition-colors duration-150",
                  active ? "bg-teal-dim text-teal" : "text-text-2 hover:bg-teal-dim hover:text-foreground"
                )}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>
        <div className="flex items-center gap-2">
          <Link href="/login" className="hidden sm:inline">
            <Button variant="outline" size="sm">
              Log in
            </Button>
          </Link>
          <Link href="/talent/signup">
            <Button size="sm">Get started</Button>
          </Link>
        </div>
      </div>
    </header>
  );
}
