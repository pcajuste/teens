"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import type { SignupResponse } from "@/lib/types";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [parentEmail, setParentEmail] = useState("");
  const [needsParentEmail, setNeedsParentEmail] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingConsent, setPendingConsent] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      const result = await api.post<SignupResponse>("/auth/signup", {
        email,
        password,
        role: "rep",
        date_of_birth: dateOfBirth,
        parent_email: parentEmail || undefined,
      });

      if (result.account_status === "pending") {
        setPendingConsent(true);
        return;
      }

      const { error: signInError } = await supabase.auth.signInWithPassword({ email, password });
      if (signInError) {
        setError("Account created. Please sign in.");
        router.push("/rep/login");
        return;
      }
      router.push("/rep/onboarding");
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === "parent_email_required") {
          setNeedsParentEmail(true);
          setError(err.message);
        } else if (err.code === "age_not_permitted") {
          setError(err.message);
        } else if (err.code === "email_already_registered") {
          setError(err.message);
        } else {
          setError(err.message);
        }
      } else {
        setError("Something went wrong. Please try again.");
      }
    } finally {
      setPending(false);
    }
  }

  if (pendingConsent) {
    return (
      <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-3 p-6 text-center">
        <h1 className="text-xl font-semibold">Almost there</h1>
        <p className="text-sm text-muted-foreground">
          Because you&apos;re under 16, we&apos;ve emailed your parent or guardian at {parentEmail} to ask
          for consent. Once they approve, you can sign in and finish setting up your profile.
        </p>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-6 p-6">
      <div>
        <h1 className="text-xl font-semibold">Create your Teenure account</h1>
        <p className="text-sm text-muted-foreground">Build a verified record of what you do outside class.</p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
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
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="dob">Date of birth</Label>
          <Input
            id="dob"
            type="date"
            required
            value={dateOfBirth}
            onChange={(e) => setDateOfBirth(e.target.value)}
          />
        </div>
        {needsParentEmail ? (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="parentEmail">Parent or guardian email</Label>
            <Input
              id="parentEmail"
              type="email"
              required
              value={parentEmail}
              onChange={(e) => setParentEmail(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Because you&apos;re under 16, a parent or guardian must approve your account.
            </p>
          </div>
        ) : null}

        {error ? <p className="text-sm text-destructive">{error}</p> : null}

        <Button type="submit" disabled={pending} className="h-10 w-full">
          {pending ? "Creating account..." : "Sign up"}
        </Button>
      </form>

      <p className="text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <a href="/rep/login" className="font-medium underline">
          Sign in
        </a>
      </p>
    </main>
  );
}
