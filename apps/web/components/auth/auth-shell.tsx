import Link from "next/link";

interface AuthShellProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}

/** Shared shell for every auth screen (talent/brand/recruiter signup &
 * login) so the platform reads as one product from the very first
 * screen a user sees, per Section 0A's acceptance criterion. */
export function AuthShell({ title, subtitle, children, footer }: AuthShellProps) {
  return (
    <main className="flex min-h-screen flex-col bg-secondary/30">
      <div className="flex flex-1 flex-col items-center justify-center px-4 py-12">
        <div className="w-full max-w-sm">
          <Link href="/" className="mb-8 flex items-center justify-center gap-2">
            <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">
              T
            </span>
            <span className="text-lg font-semibold tracking-tight text-foreground">Teenure</span>
          </Link>

          <div className="rounded-xl border border-border bg-card p-8 shadow-sm">
            <div className="mb-6 flex flex-col gap-1.5 text-center">
              <h1 className="text-xl font-semibold tracking-tight text-foreground">{title}</h1>
              {subtitle ? <p className="text-sm text-muted-foreground">{subtitle}</p> : null}
            </div>
            {children}
          </div>

          {footer ? <div className="mt-6 text-center text-sm text-muted-foreground">{footer}</div> : null}
        </div>
      </div>
    </main>
  );
}
