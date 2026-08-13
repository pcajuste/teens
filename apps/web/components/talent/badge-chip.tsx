"use client";

import { useState } from "react";
import type { Badge as RepBadge } from "@/lib/types";

// DS Section 6: badge chips render in teal, not each module's arbitrary
// admin-set badge_color -- the badge is a platform fact about the
// talent (informational), not the in-the-moment earned transaction
// (that's the gold reveal on the pass screen itself, a separate
// surface from this chip). badge_color is intentionally unused here.
export function BadgeChip({ badge }: { badge: RepBadge }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        className="inline-flex min-h-8 items-center gap-1.5 rounded-full border border-teal-border bg-teal-dim px-3 py-1 text-xs font-semibold text-teal"
      >
        {badge.badge_title}
      </button>
      {open ? (
        <div className="absolute left-0 top-full z-10 mt-1 w-56 rounded-md border border-border-muted bg-card p-2.5 text-xs shadow-lg">
          <p className="font-medium">{badge.badge_title}</p>
          <p className="mt-1 text-text-2">{badge.badge_description}</p>
          <p className="mt-1 text-text-2">
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
