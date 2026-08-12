"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AuthShell } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import type { SignupResponse } from "@/lib/types";

export default function RecruiterSignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      // Recruiters are institution staff acting on behalf of a college or
      // employer, not signing up as themselves -- same fixed adult
      // date_of_birth placeholder used by the brand signup page, since
      // the backend requires one on every /auth/signup regardless of
      // role but the age gate has no meaning for this role.
      await api.post<SignupResponse>("/auth/signup", {
        email,
        password,
        role: "recruiter",
        date_of_birth: "1990-01-01",
      });

      const { error: signInError } = await supabase.auth.signInWithPassword({ email, password });
      if (signInError) {
        router.push("/login");
        return;
      }
      router.push("/recruiter/profile");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setPending(false);
    }
  }

  return (
    <AuthShell
      title="Create your recruiter account"
      subtitle="Search verified teen achievement records and connect with rising talent."
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
          <Label htmlFor="email">Institution email</Label>
          <Input
            id="email"
            type="email"
            placeholder="you@youruniversity.edu"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">A .edu address speeds up verification, but isn&apos;t required.</p>
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
          Every recruiter account is verified before you can search or contact reps, and requires an
          active subscription.
        </p>
      </form>
    </AuthShell>
  );
}
