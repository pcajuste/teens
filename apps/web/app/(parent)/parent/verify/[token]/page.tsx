"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { parentApi } from "@/lib/parent-api";
import { setParentSession } from "@/lib/parent-session";
import { ApiError } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * Landing page for the magic-link email's URL
 * (`{NEXT_PUBLIC_APP_URL}/parent/verify/{token}`, matching
 * app.services.email_service.send_parent_magic_link_email). Calls
 * GET /parent/auth/verify/:token once on mount, stores the returned
 * session token, and redirects to the dashboard.
 */
export default function ParentVerifyPage() {
  const params = useParams<{ token: string }>();
  const router = useRouter();
  const [status, setStatus] = useState<"loading" | "error">("loading");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function run() {
      try {
        const res = await parentApi.verify(params.token);
        if (cancelled) return;
        setParentSession(res);
        router.replace("/parent");
      } catch (err) {
        if (cancelled) return;
        setStatus("error");
        if (err instanceof ApiError) {
          setMessage(String(err.detail ?? err.message));
        } else {
          setMessage("Something went wrong verifying your login link.");
        }
      }
    }
    run();
    return () => {
      cancelled = true;
    };
  }, [params.token, router]);

  if (status === "loading") {
    return (
      <main className="container flex min-h-screen items-center justify-center py-16">
        <p className="text-muted-foreground">Signing you in…</p>
      </main>
    );
  }

  return (
    <main className="container flex min-h-screen max-w-sm flex-col items-center justify-center gap-4 py-16 text-center">
      <Card>
        <CardHeader>
          <CardTitle>Couldn&apos;t sign you in</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>{message}</p>
          <p>
            Login links expire after 15 minutes and can only be used once. Request a new one from the{" "}
            <a href="/parent/login" className="underline">
              sign-in page
            </a>
            .
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
