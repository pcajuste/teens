"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AuthShell } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { supabase } from "@/lib/supabase";
import { api, ApiError } from "@/lib/api";
import type { MeResponse } from "@/lib/types";

// Single credentials page for every role. Role is looked up server-side via
// GET /auth/me after sign-in -- the client never chooses where to land, so a
// forged redirect/role query param can't send a rep into the brand portal.
const PORTAL_PATH_BY_ROLE: Record<string, string> = {
  rep: "/rep",
  brand: "/brand",
  recruiter: "/recruiter",
  admin: "/admin",
};

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resent, setResent] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);

    const { error: signInError } = await supabase.auth.signInWithPassword({ email, password });
    if (signInError) {
      setError(signInError.message);
      setPending(false);
      return;
    }

    try {
      const me = await api.get<MeResponse>("/auth/me");
      router.push(PORTAL_PATH_BY_ROLE[me.role] ?? "/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load your account.");
      setPending(false);
    }
  }

  async function handleResendConsent() {
    try {
      await api.post("/auth/resend-consent", { email });
      setResent(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not resend consent email.");
    }
  }

  return (
    <AuthShell
      title="Sign in to Teenure"
      footer={
        <div className="flex flex-col gap-2">
          <p>
            New here?{" "}
            <a href="/rep/signup" className="font-medium text-primary hover:underline">
              Sign up as a rep
            </a>
            ,{" "}
            <a href="/brand/signup" className="font-medium text-primary hover:underline">
              brand
            </a>
            , or{" "}
            <a href="/recruiter/signup" className="font-medium text-primary hover:underline">
              recruiter
            </a>
            .
          </p>
          <button type="button" onClick={handleResendConsent} className="text-primary hover:underline">
            Resend parental consent email
          </button>
          {resent ? <p className="text-xs">If that email needs a consent link, we&apos;ve sent one.</p> : null}
        </div>
      }
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>

        {error ? (
          <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
        ) : null}

        <Button type="submit" disabled={pending} size="lg" className="mt-1 w-full">
          {pending ? "Signing in..." : "Sign in"}
        </Button>
      </form>
    </AuthShell>
  );
}
