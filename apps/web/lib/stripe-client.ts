import { loadStripe, type Stripe } from "@stripe/stripe-js";

// Lazily-created, memoized Stripe.js instance for platform-account
// payments (Category Exclusivity, Build Prompt 8C) -- this is a
// distinct payment surface from Stripe Connect (talent payouts), which
// this codebase does not collect card details for on the client at
// all. NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY is a publishable key, safe
// to ship to the browser (mirrors STRIPE_PUBLISHABLE_KEY in
// apps/api/app/core/config.py, which is the same key value).
let stripePromise: Promise<Stripe | null> | null = null;

export function getStripe(): Promise<Stripe | null> {
  if (!stripePromise) {
    const key = process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY ?? "";
    stripePromise = key ? loadStripe(key) : Promise.resolve(null);
  }
  return stripePromise;
}
