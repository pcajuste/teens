import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** Shared page-level hero/header block used by every marketing subpage. */
export function MarketingHero({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  children?: ReactNode;
}) {
  return (
    <div className="border-b border-border bg-muted/30">
      <div className="mx-auto max-w-3xl px-4 py-16 sm:px-6 sm:py-20">
        {eyebrow ? (
          <p className="text-sm font-medium uppercase tracking-wide text-primary">{eyebrow}</p>
        ) : null}
        <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h1>
        {description ? (
          <p className="mt-4 text-base leading-relaxed text-muted-foreground sm:text-lg">{description}</p>
        ) : null}
        {children}
      </div>
    </div>
  );
}

export function Section({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return <section className={cn("mx-auto max-w-3xl px-4 py-12 sm:px-6", className)}>{children}</section>;
}

export function SectionHeading({ children }: { children: ReactNode }) {
  return <h2 className="text-xl font-semibold tracking-tight sm:text-2xl">{children}</h2>;
}
