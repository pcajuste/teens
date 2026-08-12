"use client";

import { useAuth } from "@/lib/auth-context";
import { RepNav } from "@/components/rep/rep-nav";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * Gate for the entire rep portal. GET /auth/me works for ANY authenticated
 * user regardless of account_status, so we always call it first and branch
 * on account_status/role client-side — a pending rep must see a "waiting on
 * your parent" / "pending admin approval" screen here, never a raw 403 from
 * a downstream /reps/* call.
 */
export default function RepLayout({ children }: { children: React.ReactNode }) {
  const { loading, session, me, error } = useAuth();

  if (loading) {
    return (
      <main className="container flex min-h-screen items-center justify-center py-16">
        <p className="text-muted-foreground">Loading your account…</p>
      </main>
    );
  }

  if (!session) {
    return (
      <main className="container flex min-h-screen flex-col items-center justify-center gap-4 py-16 text-center">
        <h1 className="text-xl font-semibold">Sign in to continue</h1>
        <p className="text-muted-foreground">
          You need to be signed in to view the rep portal.
        </p>
      </main>
    );
  }

  if (error || !me) {
    return (
      <main className="container flex min-h-screen flex-col items-center justify-center gap-4 py-16 text-center">
        <h1 className="text-xl font-semibold">Something went wrong</h1>
        <p className="text-muted-foreground">
          {error ?? "We couldn't load your account. Please try again shortly."}
        </p>
      </main>
    );
  }

  if (me.role !== "rep") {
    return (
      <main className="container flex min-h-screen flex-col items-center justify-center gap-4 py-16 text-center">
        <h1 className="text-xl font-semibold">This portal is for reps</h1>
        <p className="text-muted-foreground">
          Your account role ({me.role}) doesn&apos;t have access to the rep portal.
        </p>
      </main>
    );
  }

  if (me.account_status !== "active") {
    const isParentPending = me.pending_reason?.toLowerCase().includes("parent");
    return (
      <main className="container flex min-h-screen flex-col items-center justify-center gap-4 py-16 text-center">
        <Card className="max-w-sm">
          <CardHeader>
            <CardTitle>
              {isParentPending ? "Waiting on your parent" : "Pending approval"}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <p>
              {isParentPending
                ? "We've sent your parent or guardian an email to confirm your account. Once they approve it, you'll get full access to the rep portal."
                : "Your account is still being reviewed. We'll let you know as soon as it's ready."}
            </p>
            {me.pending_reason && <p className="text-xs">Status: {me.pending_reason}</p>}
          </CardContent>
        </Card>
      </main>
    );
  }

  return (
    <div className="flex min-h-screen flex-col">
      <div className="hidden sm:block">
        <RepNav />
      </div>
      <div className="flex-1 pb-16 sm:pb-0">{children}</div>
      <div className="sm:hidden">
        <RepNav />
      </div>
    </div>
  );
}
