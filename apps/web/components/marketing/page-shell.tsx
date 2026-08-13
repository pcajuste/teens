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
    <div
      className="border-b border-border-muted"
      style={{ background: "radial-gradient(ellipse at 30% 50%, rgba(13, 155, 122, 0.07) 0%, transparent 60%)" }}
    >
      <div className="mx-auto max-w-3xl px-4 py-16 sm:px-6 sm:py-20">
        {eyebrow ? (
          <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-teal">{eyebrow}</p>
        ) : null}
        <h1 className="text-3xl font-extrabold tracking-[-0.03em] sm:text-4xl">{title}</h1>
        {description ? (
          <p className="mt-4 text-base leading-relaxed text-text-2 sm:text-lg">{description}</p>
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
