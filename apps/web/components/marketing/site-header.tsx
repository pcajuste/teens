import Link from "next/link";

const NAV_LINKS = [
  { href: "/talents", label: "Talents" },
  { href: "/brands", label: "Brands" },
  { href: "/recruiters", label: "Recruiters" },
  { href: "/parents", label: "Parents" },
  { href: "/schools", label: "Schools" },
  { href: "/trust", label: "Trust" },
];

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link href="/" className="text-base font-semibold tracking-tight">
          Teenure
        </Link>
        <nav className="hidden items-center gap-6 md:flex">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              {link.label}
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-2">
          <Link
            href="/login"
            className="hidden text-sm font-medium text-muted-foreground transition-colors hover:text-foreground sm:inline"
          >
            Log in
          </Link>
          <Link
            href="/talent/signup"
            className="inline-flex h-9 items-center justify-center rounded-lg bg-primary px-3.5 text-sm font-medium text-primary-foreground shadow-sm transition-all hover:bg-primary-hover hover:shadow-md"
          >
            Get started
          </Link>
        </div>
      </div>
    </header>
  );
}
