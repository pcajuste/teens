"use client";

import { useState } from "react";
import type { Badge as RepBadge } from "@/lib/types";

/** Colored chip rendering one verified badge -- tap/hover reveals
 * badge_description and earned_at (Build Prompt 8H frontend spec).
 * Wraps cleanly on narrow (375px) screens since it's plain inline-flex
 * content, no fixed width. */
export function BadgeChip({ badge }: { badge: RepBadge }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        className="inline-flex min-h-8 items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold text-white shadow-sm"
        style={{ backgroundColor: badge.badge_color }}
      >
        {badge.badge_title}
      </button>
      {open ? (
        <div className="absolute left-0 top-full z-10 mt-1 w-56 rounded-md border border-border bg-card p-2.5 text-xs shadow-lg">
          <p className="font-medium">{badge.badge_title}</p>
          <p className="mt-1 text-muted-foreground">{badge.badge_description}</p>
          <p className="mt-1 text-muted-foreground">
            Earned {new Date(badge.earned_at).toLocaleDateString()}
          </p>
        </div>
      ) : null}
    </div>
  );
}

export function BadgeChipRow({ badges }: { badges: RepBadge[] }) {
  if (badges.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {badges.map((b) => (
        <BadgeChip key={b.module_id} badge={b} />
      ))}
    </div>
  );
}
