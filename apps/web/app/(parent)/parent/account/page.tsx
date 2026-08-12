"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { parentApi } from "@/lib/parent-api";
import { clearParentSession } from "@/lib/parent-session";
import { ApiError } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

/**
 * Account controls (Prompt 4A deliverable 6/7): parent-initiated
 * suspend/unsuspend, each behind a confirmation dialog. Suspension is
 * reversible by the parent only if the parent initiated it -- an
 * admin-initiated suspension returns 403 here, which we surface plainly
 * rather than silently failing.
 */
export default function ParentAccountPage() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function handleAuthError(err: unknown): boolean {
    if (err instanceof ApiError && (err.status === 401 || err.status === 403 && String(err.detail).toLowerCase().includes("closed"))) {
      clearParentSession();
      router.replace("/parent/login");
      return true;
    }
    return false;
  }

  async function suspend() {
    if (!confirm("Suspend your teen's Teenure account? They won't be able to accept new campaigns until you unsuspend it. They'll be notified, and Teenure's admin team is alerted.")) {
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await parentApi.suspendAccount();
      setMessage("Account suspended. Your teen has been notified.");
    } catch (err) {
      if (handleAuthError(err)) return;
      setError(err instanceof ApiError ? String(err.detail ?? err.message) : "Could not suspend the account.");
    } finally {
      setBusy(false);
    }
  }

  async function unsuspend() {
    if (!confirm("Reactivate your teen's Teenure account?")) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await parentApi.unsuspendAccount();
      setMessage("Account reactivated.");
    } catch (err) {
      if (handleAuthError(err)) return;
      if (err instanceof ApiError && err.status === 403) {
        setError(
          "This account wasn't suspended by you, so it can't be reactivated here. " +
            "Contact Teenure support if it was suspended by an admin.",
        );
      } else {
        setError(err instanceof ApiError ? String(err.detail ?? err.message) : "Could not reactivate the account.");
      }
    } finally {
      setBusy(false);
    }
  }

  function signOut() {
    clearParentSession();
    router.replace("/parent/login");
  }

  return (
    <main className="container max-w-lg space-y-6 py-6">
      <h1 className="text-xl font-semibold">Account controls</h1>

      {message && <p className="text-sm text-green-700">{message}</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      <Card>
        <CardHeader>
          <CardTitle>Suspend account</CardTitle>
          <CardDescription>
            Immediately pauses your teen's ability to accept campaigns. You (or an admin) can reverse
            this any time.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-2 sm:flex-row">
          <Button onClick={suspend} disabled={busy} variant="destructive">
            Suspend account
          </Button>
          <Button onClick={unsuspend} disabled={busy} variant="outline">
            Unsuspend account
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Sign out</CardTitle>
          <CardDescription>Ends your parent portal session on this device.</CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={signOut} variant="outline">
            Sign out
          </Button>
        </CardContent>
      </Card>
    </main>
  );
}
