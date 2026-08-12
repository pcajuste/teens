import * as React from "react";
import { cn } from "@/lib/utils";

// Plain native checkbox styled to a comfortable touch target (min 24px box,
// 44px+ tap target via padding on the wrapping label in call sites).
// Deliberately NOT pre-checked anywhere it's used — every call site must
// pass checked={state} explicitly.
export const Checkbox = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      type="checkbox"
      className={cn(
        "h-5 w-5 shrink-0 rounded border border-border accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
        className,
      )}
      {...props}
    />
  ),
);
Checkbox.displayName = "Checkbox";
