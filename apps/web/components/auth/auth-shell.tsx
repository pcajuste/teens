import Link from "next/link";
import { LogoWordmark, LOGO_SIZES } from "@/components/logo";

interface AuthShellProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}

// DS Section 11: minimal decorative color, no gold anywhere (auth isn't
// an earned moment). Logo centered above the form card.
export function AuthShell({ title, subtitle, children, footer }: AuthShellProps) {
  return (
    <main className="flex min-h-screen flex-col bg-background">
      <div className="flex flex-1 flex-col items-center justify-center px-4 py-12">
        <div className="w-full max-w-sm">
          <Link href="/" className="mb-8 flex items-center justify-center">
            <LogoWordmark darkMode height={LOGO_SIZES.wordmark} />
          </Link>

          <div className="rounded-[var(--r-xl)] border border-border-muted bg-surface-2 p-8 shadow-[var(--shadow-card)] sm:px-12 sm:py-10">
            <div className="mb-6 flex flex-col gap-1.5 text-center">
              <h1 className="text-xl font-semibold tracking-tight text-foreground">{title}</h1>
              {subtitle ? <p className="text-sm text-text-2">{subtitle}</p> : null}
            </div>
            {children}
          </div>

          {footer ? <div className="mt-6 text-center text-sm text-text-2">{footer}</div> : null}
        </div>
      </div>
    </main>
  );
}
