import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

// DS Section 3C: standard/earned/featured. "earned" gets a gold top
// edge (a genuinely earned item -- confirmed campaign, awarded badge,
// released payout); "featured" gets a teal top edge (a primary
// highlight, used sparingly, never for an earned state). Picking
// "earned" for something not yet earned is the same category error as
// a gold button.
const cardVariants = cva(
  "relative flex flex-col gap-4 overflow-hidden rounded-[var(--r-lg)] border border-border-muted bg-card p-4 text-card-foreground shadow-sm transition-all duration-200 before:pointer-events-none before:absolute before:inset-x-5 before:top-0 before:h-px",
  {
    variants: {
      variant: {
        standard: "before:content-none hover:bg-secondary hover:-translate-y-0.5",
        earned: "before:content-[''] before:bg-gradient-to-r before:from-transparent before:via-gold before:to-transparent",
        featured:
          "border-border-token shadow-[var(--shadow-card)] before:content-[''] before:bg-gradient-to-r before:from-transparent before:via-teal before:to-transparent",
      },
    },
    defaultVariants: {
      variant: "standard",
    },
  }
);

function Card({ className, variant, ...props }: React.ComponentProps<"div"> & VariantProps<typeof cardVariants>) {
  return <div data-slot="card" className={cn(cardVariants({ variant }), className)} {...props} />;
}

function CardHeader({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="card-header" className={cn("flex flex-col gap-1", className)} {...props} />;
}

function CardTitle({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div data-slot="card-title" className={cn("text-base font-semibold leading-tight", className)} {...props} />
  );
}

function CardDescription({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div data-slot="card-description" className={cn("text-sm text-muted-foreground", className)} {...props} />
  );
}

function CardContent({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="card-content" className={cn("flex flex-col gap-2", className)} {...props} />;
}

function CardFooter({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="card-footer" className={cn("flex items-center gap-2", className)} {...props} />;
}

export { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter };
