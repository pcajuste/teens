"use client";

import { useState } from "react";
import { parentApi } from "@/lib/parent-api";
import { ApiError } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

/**
 * Parent Portal magic-link request screen (Prompt 4A deliverable 7,
 * email entry only per the spec). Always shows the same success state
 * regardless of whether the email is actually linked to a
 * parent_records row — POST /parent/auth/request-link never confirms
 * or denies a match, so neither does this screen.
 */
export default function ParentLoginPage() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await parentApi.requestLink(email);
      setSent(true);
    } catch (err) {
      // Rate-limiting (429) is the only failure mode this screen ever
      // surfaces distinctly -- everything else (unknown email included)
      // still shows the same "sent" state, per the non-enumeration
      // requirement.
      if (err instanceof ApiError && err.status === 429) {
        setError("You've requested a link recently. Please wait a few minutes and try again.");
      } else {
        setSent(true);
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="container flex min-h-screen max-w-sm flex-col justify-center gap-6 py-16">
      <div className="text-center">
        <h1 className="text-2xl font-semibold">Teenure Parent Portal</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Check in on your teen&apos;s account, review campaign invitations, and manage their settings.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Sign in</CardTitle>
          <CardDescription>
            Enter the email address linked to your teen&apos;s account. We&apos;ll send you a one-time
            login link — no password needed.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {sent ? (
            <p className="text-sm text-muted-foreground">
              If that email is linked to a Teenure account, we&apos;ve sent a login link to it. The
              link expires in 15 minutes and can only be used once.
            </p>
          ) : (
            <form onSubmit={onSubmit} className="space-y-4">
              <Input
                type="email"
                required
                placeholder="parent@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
              {error && <p className="text-sm text-red-600">{error}</p>}
              <Button type="submit" disabled={submitting} className="w-full">
                {submitting ? "Sending…" : "Send login link"}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
