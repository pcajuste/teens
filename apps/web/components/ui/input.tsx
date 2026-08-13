import * as React from "react";

import { cn } from "@/lib/utils";

// DS Section 3D: `verified` marks a field as confirmed/verified (e.g.
// an FTC-gate field once the disclosure is accepted) with a gold
// border -- use sparingly, only for genuinely verified states. This is
// the one Input-level place gold is allowed to appear.
function Input({
  className,
  type,
  verified,
  ...props
}: React.ComponentProps<"input"> & { verified?: boolean }) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "flex h-9 w-full min-w-0 rounded-lg border border-input bg-white/4 px-3 py-1 text-sm shadow-xs transition-[color,box-shadow] outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50 focus-visible:border-teal-border focus-visible:ring-3 focus-visible:ring-teal-dim aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20",
        verified && "border-gold-border",
        className
      )}
      {...props}
    />
  );
}

export { Input };
