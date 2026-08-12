"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Home, User, Inbox } from "lucide-react";

// Structural enforcement of Section 1A: this is the entire nav surface for
// the rep portal. There is intentionally no "browse reps" or "messages to
// other reps" link/route anywhere in this file or the rest of app/(rep)/.
const links = [
  { href: "/rep", label: "Dashboard", icon: Home },
  { href: "/rep/profile", label: "Profile", icon: User },
  { href: "/rep/inbox", label: "Inbox", icon: Inbox },
];

export function RepNav() {
  const pathname = usePathname();
  return (
    <nav className="sticky bottom-0 z-10 flex border-t border-border bg-background sm:static sm:border-t-0 sm:border-b">
      <div className="container flex justify-around py-1 sm:justify-start sm:gap-6 sm:py-3">
        {links.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex min-h-11 min-w-11 flex-1 flex-col items-center justify-center gap-0.5 rounded-md px-2 py-1 text-xs sm:flex-none sm:flex-row sm:gap-2 sm:text-sm",
                active ? "text-primary font-semibold" : "text-muted-foreground",
              )}
            >
              <Icon className="h-5 w-5" />
              {label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
