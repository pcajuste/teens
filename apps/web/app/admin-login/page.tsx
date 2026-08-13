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

/** Dedicated admin sign-in, deliberately separate from the shared
 * /login page (Build Prompt 13 auth note: admin must not be reachable
 * via role-detection fallthrough from that page). Still reuses
 * AuthGate for the loading/redirect mechanics once signed in --
 * see apps/web/app/(admin)/layout.tsx. */
export default function AdminLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      if (me.role !== "admin") {
        await supabase.auth.signOut();
        setError("This account is not an admin account.");
        setPending(false);
        return;
      }
      router.push("/admin");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load your account.");
      setPending(false);
    }
  }

  return (
    <AuthShell title="Admin sign-in" subtitle="Internal use only.">
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
          <p className="text-[13px] text-danger">{error}</p>
        ) : null}

        <Button type="submit" disabled={pending} size="lg" className="mt-1 w-full">
          {pending ? "Signing in..." : "Sign in"}
        </Button>
      </form>
    </AuthShell>
  );
}
