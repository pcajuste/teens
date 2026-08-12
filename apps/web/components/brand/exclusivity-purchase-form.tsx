"use client";

import { useState } from "react";
import {
  Elements,
  PaymentElement,
  useElements,
  useStripe,
} from "@stripe/react-stripe-js";
import { Button } from "@/components/ui/button";
import { getStripe } from "@/lib/stripe-client";

/** Standard Stripe Elements payment form, confirming the platform-account
 * PaymentIntent created by POST /brands/exclusivity/purchase (Build Prompt
 * 8C: "Stripe Elements payment form ... Standard web payment UX -- no
 * novelty needed"). This is the first Stripe Elements usage in apps/web --
 * no prior pattern existed to match, so this follows Stripe's own
 * recommended PaymentElement + confirmPayment shape. */
function InnerForm({ onSuccess }: { onSuccess: () => void }) {
  const stripe = useStripe();
  const elements = useElements();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!stripe || !elements) return;
    setSubmitting(true);
    setError(null);

    const { error: submitError } = await elements.submit();
    if (submitError) {
      setError(submitError.message ?? "Payment details are incomplete.");
      setSubmitting(false);
      return;
    }

    const { error: confirmError, paymentIntent } = await stripe.confirmPayment({
      elements,
      redirect: "if_required",
    });

    if (confirmError) {
      setError(confirmError.message ?? "Payment could not be completed.");
      setSubmitting(false);
      return;
    }

    if (paymentIntent && (paymentIntent.status === "succeeded" || paymentIntent.status === "processing")) {
      onSuccess();
    } else {
      setError("Payment did not complete. Please try again.");
    }
    setSubmitting(false);
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <PaymentElement />
      {error ? (
        <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
      ) : null}
      <Button type="submit" size="lg" disabled={!stripe || submitting} className="w-full">
        {submitting ? "Processing payment..." : "Confirm purchase"}
      </Button>
    </form>
  );
}

/** Wraps InnerForm in the Elements provider, keyed to the PaymentIntent's
 * client_secret from POST /brands/exclusivity/purchase. */
export function ExclusivityPurchaseForm({
  clientSecret,
  onSuccess,
}: {
  clientSecret: string;
  onSuccess: () => void;
}) {
  return (
    <Elements stripe={getStripe()} options={{ clientSecret }}>
      <InnerForm onSuccess={onSuccess} />
    </Elements>
  );
}
