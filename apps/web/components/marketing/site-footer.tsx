import Link from "next/link";
import { LogoWordmark } from "@/components/logo";

const COLUMNS: { title: string; links: { href: string; label: string }[] }[] = [
  {
    title: "Platform",
    links: [
      { href: "/talents", label: "For talents" },
      { href: "/brands", label: "For brands" },
      { href: "/recruiters", label: "For recruiters" },
      { href: "/schools", label: "For schools" },
    ],
  },
  {
    title: "Family",
    links: [
      { href: "/parents", label: "For parents" },
      { href: "/trust", label: "Trust & compliance" },
      { href: "/demo/talent", label: "See a talent profile" },
    ],
  },
  {
    title: "Legal",
    links: [
      { href: "/privacy", label: "Privacy policy" },
      { href: "/terms", label: "Terms of service" },
    ],
  },
];

export function SiteFooter() {
  return (
    <footer className="border-t border-border-muted">
      <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
        <div className="grid grid-cols-2 gap-8 sm:grid-cols-4">
          <div className="col-span-2 sm:col-span-1">
            <LogoWordmark darkMode height={22} />
            <p className="mt-2 max-w-[22ch] text-sm text-text-3">
              A verified professional achievement record for teenagers.
            </p>
          </div>
          {COLUMNS.map((col) => (
            <div key={col.title}>
              <p className="text-xs font-medium uppercase tracking-wide text-text-3">
                {col.title}
              </p>
              <ul className="mt-3 flex flex-col gap-2">
                {col.links.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className="text-sm text-text-3 transition-colors hover:text-text-2"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="mt-10 flex flex-col gap-2 border-t border-border-muted pt-6 text-xs text-text-3 sm:flex-row sm:items-center sm:justify-between">
          <p>
            &copy; {new Date().getFullYear()} Teenure. All rights reserved.
          </p>
          <p>
            No public feed. No profile photos. No talent-to-talent contact — by
            design.
          </p>
        </div>
      </div>
    </footer>
  );
}
