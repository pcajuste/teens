"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth-context";

const PUBLIC_PATHS = new Set(["/brand/signup", "/brand/login"]);

// Reachable even while account_status='pending' -- a pending brand must
// be able to submit their company profile, since submitting it is what
// admin review (Prompt 13) actually reviews. Every other authenticated
// route stays blocked behind the "under review" state.
const ALLOWED_WHILE_PENDING_PATHS = new Set(["/brand/onboarding"]);

export function BrandGate({ children }: { children: React.ReactNode }) {
  const { session, me, loading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const isPublic = PUBLIC_PATHS.has(pathname);

  useEffect(() => {
    if (loading) return;
    if (!session && !isPublic) {
      router.replace("/brand/login");
    }
  }, [loading, session, isPublic, router]);

  if (isPublic) {
    return <>{children}</>;
  }

  if (loading) {
    return <CenteredMessage title="Loading..." />;
  }

  if (!session) {
    return <CenteredMessage title="Redirecting to sign in..." />;
  }

  if (me?.pending_reason === "pending_admin_approval" && !ALLOWED_WHILE_PENDING_PATHS.has(pathname)) {
    return (
      <CenteredMessage title="Your account is under review">
        <p className="max-w-sm text-sm text-muted-foreground">
          Every brand on Teenure is verified before they can run campaigns. We&apos;ll email you
          as soon as your account is approved -- usually within one business day.
        </p>
        <a href="/brand/onboarding" className="text-sm font-medium text-primary hover:underline">
          Finish your company profile
        </a>
      </CenteredMessage>
    );
  }

  if (me?.account_status === "suspended" || me?.account_status === "rejected") {
    return (
      <CenteredMessage title="Account unavailable">
        <p className="max-w-sm text-sm text-muted-foreground">
          Your account is currently {me.account_status}. Contact support for more information.
        </p>
      </CenteredMessage>
    );
  }

  return <>{children}</>;
}

function CenteredMessage({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-3 bg-secondary/30 p-6 text-center">
      <span className="flex size-12 items-center justify-center rounded-full bg-accent text-accent-foreground">
        <ShieldIcon />
      </span>
      <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
      {children}
    </main>
  );
}

function ShieldIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" />
    </svg>
  );
}
