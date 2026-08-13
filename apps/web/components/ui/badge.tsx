import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

// DS Section 3B: the chip system carries the platform's entire semantic
// color architecture. Every status chip must map to exactly one of
// these -- picking the wrong one is a meaning error, not a style choice.
//   active   (teal)   -- invited/accepted/in-progress/available/verified-account
//   earned   (gold)   -- confirmed/passed/badge-awarded/converted/partnership-active
//   done     (green)  -- paid/email-verified/module-completed
//   pending  (neutral)-- submitted/draft/awaiting review
//   danger   (red)    -- flagged/disputed/fraud/compliance-concern
//   verified (gold, solid) -- the "VERIFIED ✓" identity badge specifically
const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-md border border-transparent px-2 py-0.5 text-xs font-medium whitespace-nowrap",
  {
    variants: {
      variant: {
        // Legacy names kept so ~60 existing call sites keep working;
        // each now routes through the correct DS token by default.
        default: "bg-primary text-primary-foreground",
        secondary: "bg-secondary text-secondary-foreground",
        outline: "border-border-dim bg-transparent text-text-2",
        destructive: "bg-danger-dim text-danger border-danger-border",
        success: "bg-green-dim text-green border-green-border",
        warning: "bg-secondary text-text-2",
        info: "bg-teal-dim text-teal border-teal-border",
        // DS-named variants for explicit earned/active/done/pending use.
        active: "rounded-full bg-teal-dim text-teal border-teal-border font-semibold tracking-wide",
        earned: "rounded-full bg-gold-dim text-gold border-gold-border font-semibold tracking-wide",
        done: "rounded-full bg-green-dim text-green border-green-border font-semibold tracking-wide",
        pending: "rounded-full bg-white/5 text-text-2 border-border-muted font-medium",
        verified:
          "rounded-md bg-gradient-to-br from-gold to-[#D4851A] text-[#0A0A12] font-extrabold tracking-wide px-2.5",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

function Badge({
  className,
  variant,
  ...props
}: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return <span data-slot="badge" className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
