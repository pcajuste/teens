"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { AuthShell } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

type ConsentState = "review" | "approving" | "approved" | "invalid" | "used" | "expired" | "error";

// Maps app/routers/auth.py's POST /auth/parent-verify/{token} error
// codes to distinct copy -- this is the double opt-in gate itself
// (Section 9: under-16 talents cannot activate without it), so each
// failure mode needs to read as its own thing rather than a generic
// "something went wrong."
const MESSAGE_BY_STATE: Record<Exclude<ConsentState, "review" | "approving" | "approved">, { title: string; body: string }> = {
  invalid: {
    title: "This consent link isn't valid",
    body: "The link may have been mistyped. Ask your teen to resend the parental consent email from their sign-in page.",
  },
  used: {
    title: "This consent link was already used",
    body: "You've already given consent for this account.",
  },
  expired: {
    title: "This consent link has expired",
    body: "Consent links expire after 72 hours. Ask your teen to resend the parental consent email from their sign-in page.",
  },
  error: {
    title: "Something went wrong",
    body: "We couldn't process your consent right now. Please try again.",
  },
};

export default function ParentConsentPage() {
  const params = useParams<{ token: string }>();
  const [state, setState] = useState<ConsentState>("review");

  async function approve() {
    setState("approving");
    try {
      const res = await fetch(`${API_URL}/auth/parent-verify/${encodeURIComponent(params.token)}`, {
        method: "POST",
      });

      if (!res.ok) {
        let code = "error";
        try {
          const body = await res.json();
          code = body?.error?.code ?? "error";
        } catch {
          // non-JSON error body -- fall back to generic
        }
        if (code === "invalid_token") setState("invalid");
        else if (code === "token_already_used") setState("used");
        else if (code === "token_expired") setState("expired");
        else setState("error");
        return;
      }

      setState("approved");
    } catch {
      setState("error");
    }
  }

  if (state === "approved") {
    return (
      <AuthShell title="You're all set">
        {/* DS Section 11: auth screens carry no gold -- the one spec
            exception is this brief post-approval pulse, since consent
            is itself an earned/credential-adjacent moment. */}
        <div className="flex flex-col items-center gap-3 text-center">
          <p className="animate-pulse text-sm font-medium text-gold">
            Approved. Your child can now accept campaigns.
          </p>
          <p className="text-sm text-text-2">You can close this page.</p>
        </div>
      </AuthShell>
    );
  }

  if (state === "review" || state === "approving") {
    return (
      <AuthShell
        title="Give permission for your teen to join Teenure"
        subtitle="Review before approving -- this activates their account."
      >
        <div className="flex flex-col gap-5 pt-2">
          <p className="text-[16px] leading-relaxed text-foreground">
            Your teen has started signing up for Teenure, a platform where
            teens complete brand campaigns for pay and build a verified
            record of their work for college and job applications.
          </p>
          <p className="text-[16px] leading-relaxed text-foreground">
            Because they&apos;re under 16, we need your permission before
            their account can go live. You&apos;ll also get access to a
            parent portal where you can review and approve campaigns,
            filter out content categories you don&apos;t want them exposed
            to, and get a monthly summary of their activity.
          </p>

          <Button size="lg" className="w-full" disabled={state === "approving"} onClick={approve}>
            {state === "approving" ? "Approving..." : "I approve"}
          </Button>
          <a href="/" className="text-center text-sm text-text-3 hover:underline">
            Not now
          </a>
        </div>
      </AuthShell>
    );
  }

  const { title, body } = MESSAGE_BY_STATE[state];

  return (
    <AuthShell title={title}>
      <div className="flex flex-col gap-4 text-center">
        <p className="text-sm text-text-2">{body}</p>
        <a href="/" className="text-sm font-medium text-primary hover:underline">
          Back to Teenure
        </a>
      </div>
    </AuthShell>
  );
}
