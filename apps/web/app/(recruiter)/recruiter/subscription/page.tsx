"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RecruiterShell } from "@/components/recruiter/recruiter-shell";
import { api, ApiError } from "@/lib/api";
import type {
  RecruiterCreditTopUpResponse,
  RecruiterCredits,
  SubscriptionCheckoutResponse,
  SubscriptionPlan,
} from "@/lib/types";

const PLANS: { plan: SubscriptionPlan; label: string; blurb: string }[] = [
  { plan: "monthly", label: "Monthly", blurb: "Billed every month, cancel anytime." },
  { plan: "annual", label: "Annual", blurb: "Billed once a year." },
];

export default function RecruiterSubscriptionPage() {
  const searchParams = useSearchParams();
  const checkoutResult = searchParams.get("checkout");

  const [credits, setCredits] = useState<RecruiterCredits | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [subscribing, setSubscribing] = useState<SubscriptionPlan | null>(null);

  const [topUpCredits, setTopUpCredits] = useState("10");
  const [topUpPending, setTopUpPending] = useState(false);
  const [topUpNotice, setTopUpNotice] = useState<string | null>(null);

  useEffect(() => {
    loadCredits();
  }, []);

  async function loadCredits() {
    setLoading(true);
    setError(null);
    try {
      const c = await api.get<RecruiterCredits>("/recruiters/credits");
      setCredits(c);
    } catch (err) {
      // recruiter_profile_not_found / subscription not yet created is
      // expected before the dual activation gate passes -- the plan
      // picker below stays usable either way.
      if (err instanceof ApiError && err.code !== "recruiter_profile_not_found") {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleSubscribe(plan: SubscriptionPlan) {
    setSubscribing(plan);
    setError(null);
    try {
      const { checkout_url } = await api.post<SubscriptionCheckoutResponse>("/recruiters/subscribe", { plan });
      // Real Stripe-hosted Checkout Session (test mode) -- account
      // activation itself happens asynchronously on the
      // customer.subscription.created webhook once Stripe confirms
      // payment, not on this redirect.
      window.location.href = checkout_url;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start checkout.");
      setSubscribing(null);
    }
  }

  async function handleTopUp(e: React.FormEvent) {
    e.preventDefault();
    const credits = parseInt(topUpCredits, 10);
    if (!Number.isFinite(credits) || credits <= 0) return;
    setTopUpPending(true);
    setTopUpNotice(null);
    setError(null);
    try {
      const result = await api.post<RecruiterCreditTopUpResponse>("/recruiters/credits/top-up", { credits });
      // Card collection isn't wired up in this build yet -- same interim
      // state as the brand campaign-activation flow
      // (app/(brand)/brand/campaigns/[id]/page.tsx's handleActivate).
      // The PaymentIntent is real and server-created; credits land on
      // payment_intent.succeeded once a card is actually charged.
      setTopUpNotice(
        `Top-up started for ${credits} credit${credits === 1 ? "" : "s"} ` +
          `(PaymentIntent ready: ${result.stripe_payment_intent_client_secret.slice(0, 24)}...). ` +
          "Credits are added automatically once payment confirms."
      );
      await loadCredits();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start the top-up.");
    } finally {
      setTopUpPending(false);
    }
  }

  return (
    <RecruiterShell title="Subscription & credits">
      {checkoutResult === "success" ? (
        <p className="rounded-lg bg-success/15 px-3 py-2 text-sm text-success">
          Checkout complete. Your subscription activates as soon as Stripe confirms payment (and, if your
          institution isn&apos;t verified yet, once admin review finishes too).
        </p>
      ) : checkoutResult === "cancelled" ? (
        <p className="rounded-lg bg-warning/15 px-3 py-2 text-sm text-warning-foreground">Checkout was cancelled.</p>
      ) : null}

      {error ? <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p> : null}

      <Card>
        <CardHeader>
          <CardTitle>Contact credits</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading...</p>
          ) : credits ? (
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant={credits.low_credit_warning ? "warning" : "outline"} className="px-3 py-1.5 text-sm">
                {credits.contact_credits_remaining} remaining
              </Badge>
              {credits.credits_reset_date ? (
                <span className="text-sm text-muted-foreground">Resets {credits.credits_reset_date}</span>
              ) : null}
              {credits.low_credit_warning ? (
                <Badge variant="warning">Below 20% — consider a top-up</Badge>
              ) : null}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              No active subscription yet — subscribe below to start receiving contact credits.
            </p>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {PLANS.map(({ plan, label, blurb }) => (
          <Card key={plan}>
            <CardHeader>
              <CardTitle>{label}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">{blurb}</p>
              <Button
                type="button"
                className="mt-2"
                disabled={subscribing !== null}
                onClick={() => handleSubscribe(plan)}
              >
                {subscribing === plan ? "Redirecting to checkout..." : `Subscribe (${label.toLowerCase()})`}
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Top up credits</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleTopUp} className="flex flex-wrap items-end gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="topUpCredits">Number of credits</Label>
              <Input
                id="topUpCredits"
                type="number"
                min={1}
                className="w-32"
                value={topUpCredits}
                onChange={(e) => setTopUpCredits(e.target.value)}
              />
            </div>
            <Button type="submit" disabled={topUpPending}>
              {topUpPending ? "Starting..." : "Buy credits"}
            </Button>
          </form>
          {topUpNotice ? <p className="mt-3 text-sm text-muted-foreground">{topUpNotice}</p> : null}
        </CardContent>
      </Card>
    </RecruiterShell>
  );
}
