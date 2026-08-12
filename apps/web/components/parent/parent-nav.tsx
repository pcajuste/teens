"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Home, CheckSquare, Sliders, UserCog } from "lucide-react";

const links = [
  { href: "/parent", label: "Dashboard", icon: Home },
  { href: "/parent/campaigns", label: "Approvals", icon: CheckSquare },
  { href: "/parent/settings", label: "Settings", icon: Sliders },
  { href: "/parent/account", label: "Account", icon: UserCog },
];

export function ParentNav() {
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
