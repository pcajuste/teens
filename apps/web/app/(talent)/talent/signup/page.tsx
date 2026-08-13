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

  useEffect(() => {
    initPublicAnalytics();
    trackEvent("signup_started", { role: "talent" });
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      const result = await api.post<SignupResponse>("/auth/signup", {
        email,
        password,
        role: "talent",
        date_of_birth: dateOfBirth,
        parent_email: parentEmail || undefined,
      });

      if (result.account_status === "pending") {
        // Account created but blocked on parental consent -- this is the
        // frontend-observable proxy for "parental consent requested"
        // (there is no separate consent-landing page in this repo for
        // the parent's email-link click itself to fire an event from).
        trackEvent("parental_consent_requested", { role: "talent" });
        setPendingConsent(true);
        return;
      }

      trackEvent("signup_completed", {
        role: "talent",
        account_status: result.account_status,
      });

      const { error: signInError } = await supabase.auth.signInWithPassword({
        email,
        password,
      });
      if (signInError) {
        setError("Account created. Please sign in.");
        router.push("/login");
        return;
      }
      router.push("/talent/onboarding");
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
      <AuthShell title="Almost there">
        <div className="flex flex-col items-center gap-4 text-center">
          <span className="flex size-12 items-center justify-center rounded-full bg-info/10 text-info">
            <MailIcon />
          </span>
          <p className="text-sm text-muted-foreground">
            Because you&apos;re under 16, we&apos;ve emailed your parent or
            guardian at{" "}
            <span className="font-medium text-foreground">{parentEmail}</span>{" "}
            to ask for consent. Once they approve, you can sign in and finish
            setting up your profile.
          </p>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Create your Teenure account"
      subtitle="Build a verified record of what you do outside class."
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
          <div className="flex flex-col gap-1.5 rounded-lg bg-accent/60 p-3">
            <Label htmlFor="parentEmail">Parent or guardian email</Label>
            <Input
              id="parentEmail"
              type="email"
              required
              value={parentEmail}
              onChange={(e) => setParentEmail(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Because you&apos;re under 16, a parent or guardian must approve
              your account.
            </p>
          </div>
        ) : null}

        {error ? (
          <p className="text-[13px] text-danger">
            {error}
          </p>
        ) : null}

        <Button
          type="submit"
          disabled={pending}
          size="lg"
          className="mt-1 w-full"
        >
          {pending ? "Creating account..." : "Sign up"}
        </Button>
      </form>
    </AuthShell>
  );
}

function MailIcon() {
  return (
    <svg
      width="22"
      height="22"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="2" y="4" width="20" height="16" rx="2" />
      <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
    </svg>
  );
}
