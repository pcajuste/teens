"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthShell } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import { initPublicAnalytics, trackEvent } from "@/lib/analytics";
import type { SignupResponse } from "@/lib/types";

export default function BrandSignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    initPublicAnalytics();
    trackEvent("signup_started", { role: "brand" });
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      // Brands are always adults acting on behalf of a company -- the
      // age-gate/consent fields on SignupRequest don't apply to them
      // conceptually, but the backend still requires a date_of_birth on
      // every signup regardless of role, so a fixed adult placeholder is
      // sent here rather than asking a brand contact for their own DOB,
      // which would be a strange and unnecessary data ask for this role.
      await api.post<SignupResponse>("/auth/signup", {
        email,
        password,
        role: "brand",
        date_of_birth: "1990-01-01",
      });

      trackEvent("signup_completed", { role: "brand" });

      const { error: signInError } = await supabase.auth.signInWithPassword({ email, password });
      if (signInError) {
        router.push("/login");
        return;
      }
      router.push("/brand/onboarding");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setPending(false);
    }
  }

  return (
    <AuthShell
      title="Create your brand account"
      subtitle="Run authentic campaigns with verified high school reps."
      footer={
        <>
          Already have an account?{" "}
          <a href="/login" className="font-medium text-primary hover:underline">
            Sign in
          </a>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="email">Work email</Label>
          <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>

        {error ? (
          <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
        ) : null}

        <Button type="submit" disabled={pending} size="lg" className="mt-1 w-full">
          {pending ? "Creating account..." : "Sign up"}
        </Button>

        <p className="text-center text-xs text-muted-foreground">
          Every brand account is reviewed before campaigns can go live.
        </p>
      </form>
    </AuthShell>
  );
}
