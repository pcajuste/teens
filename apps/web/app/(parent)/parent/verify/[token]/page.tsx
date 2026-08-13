"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AuthShell } from "@/components/auth/auth-shell";
import { setParentSession } from "@/lib/parent-session";
import type { ParentVerifyResponse } from "@/lib/parent-types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

type VerifyState = "checking" | "success" | "invalid" | "used" | "expired" | "portal_closed" | "error";

// Maps app/routers/parent_auth.py's error codes to distinct,
// user-facing messages -- "portal has closed" in particular must read
// as its own thing, not a generic auth failure (Build Prompt 4A
// acceptance criteria).
const MESSAGE_BY_STATE: Record<Exclude<VerifyState, "checking" | "success">, { title: string; body: string }> = {
  invalid: {
    title: "This sign-in link isn't valid",
    body: "The link may have been mistyped or already replaced by a newer one. Request a new sign-in link.",
  },
  used: {
    title: "This sign-in link was already used",
    body: "Each sign-in link works once. Request a new one to sign back in.",
  },
  expired: {
    title: "This sign-in link has expired",
    body: "Sign-in links expire after 15 minutes. Request a new one.",
  },
  portal_closed: {
    title: "The parent portal has closed",
    body: "Your child is now 18, so the parent portal for their account is no longer available.",
  },
  error: {
    title: "Something went wrong",
    body: "We couldn't verify this sign-in link. Please try again.",
  },
};

export default function ParentVerifyPage() {
  const params = useParams<{ token: string }>();
  const router = useRouter();
  const [state, setState] = useState<VerifyState>("checking");

  useEffect(() => {
    let cancelled = false;

    async function verify() {
      try {
        const res = await fetch(`${API_URL}/parent/auth/verify/${encodeURIComponent(params.token)}`);
        if (cancelled) return;

        if (!res.ok) {
          let code = "error";
          try {
            const body = await res.json();
            code = body?.error?.code ?? "error";
          } catch {
            // non-JSON error body -- fall back to generic
          }
          if (code === "invalid_magic_link") setState("invalid");
          else if (code === "magic_link_already_used") setState("used");
          else if (code === "magic_link_expired") setState("expired");
          else if (code === "portal_closed") setState("portal_closed");
          else setState("error");
          return;
        }

        const body = (await res.json()) as ParentVerifyResponse;
        setParentSession({ session_token: body.session_token, expires_at: body.expires_at });
        setState("success");
        router.replace("/parent/dashboard");
      } catch {
        if (!cancelled) setState("error");
      }
    }

    verify();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.token]);

  if (state === "checking" || state === "success") {
    return (
      <AuthShell title="Signing you in..." subtitle="Verifying your sign-in link, one moment.">
        <div />
      </AuthShell>
    );
  }

  const { title, body } = MESSAGE_BY_STATE[state];

  return (
    <AuthShell title={title}>
      <div className="flex flex-col gap-4 text-center">
        <p className="text-sm text-text-2">{body}</p>
        <a href="/parent" className="text-sm font-medium text-primary hover:underline">
          Back to sign-in
        </a>
      </div>
    </AuthShell>
  );
}
