import * as React from "react";
import { cn } from "@/lib/utils";

type Variant = "default" | "outline" | "success" | "warning" | "muted";

const variantClasses: Record<Variant, string> = {
  default: "bg-primary text-primary-foreground",
  outline: "border border-border text-foreground",
  success: "bg-green-100 text-green-800",
  warning: "bg-amber-100 text-amber-800",
  muted: "bg-muted text-muted-foreground",
};

export function Badge({
  className,
  variant = "default",
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { variant?: Variant }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        variantClasses[variant],
        className,
      )}
      {...props}
    />
  );
}
