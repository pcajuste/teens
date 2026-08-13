"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthShell } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getParentSession } from "@/lib/parent-session";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

export default function ParentLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [pending, setPending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (getParentSession()) {
      router.replace("/parent/dashboard");
    }
  }, [router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    try {
      // Not routed through lib/parent-api.ts -- this endpoint needs no
      // Authorization header (there's no session yet).
      await fetch(`${API_URL}/parent/auth/request-link`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ parent_email: email }),
      });
    } catch {
      // Network failure: still show "check your email" below --
      // the backend never confirms whether the address is linked to
      // a parent_record, and we don't want the frontend to leak that
      // distinction either by branching on success vs. failure here.
    } finally {
      setPending(false);
      setSent(true);
    }
  }

  return (
    <AuthShell
      title="Parent portal"
      subtitle="Sign in with your email to check in on your teen's Teenure activity."
    >
      {sent ? (
        <div className="flex flex-col gap-3 text-center">
          <p className="text-sm text-foreground">Check your email</p>
          <p className="text-sm text-text-2">
            If that email is linked to a Teenure parent account, we&apos;ve sent a sign-in link to it. The
            link expires in 15 minutes.
          </p>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="parent-email">Email</Label>
            <Input
              id="parent-email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          {error ? (
            <p className="text-[13px] text-danger">{error}</p>
          ) : null}

          <Button type="submit" disabled={pending} size="lg" className="mt-1 w-full">
            {pending ? "Sending..." : "Send sign-in link"}
          </Button>
        </form>
      )}
    </AuthShell>
  );
}
