"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { supabase } from "@/lib/supabase";
import { api, ApiError } from "@/lib/api";

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
    router.push("/rep");
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
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-6 p-6">
      <h1 className="text-xl font-semibold">Sign in to Teenure</h1>

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

        {error ? <p className="text-sm text-destructive">{error}</p> : null}

        <Button type="submit" disabled={pending} className="h-10 w-full">
          {pending ? "Signing in..." : "Sign in"}
        </Button>
      </form>

      <div className="flex flex-col gap-2 text-center text-sm text-muted-foreground">
        <p>
          New here?{" "}
          <a href="/rep/signup" className="font-medium underline">
            Sign up
          </a>
        </p>
        <button type="button" onClick={handleResendConsent} className="underline">
          Resend parental consent email
        </button>
        {resent ? <p>If that email needs a consent link, we&apos;ve sent one.</p> : null}
      </div>
    </main>
  );
}
