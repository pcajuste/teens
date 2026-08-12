"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { BrandShell } from "@/components/brand/brand-shell";
import { ExclusivityPurchaseForm } from "@/components/brand/exclusivity-purchase-form";
import { api, ApiError } from "@/lib/api";
import { BASE_CATEGORIES, CATEGORY_LABELS, type Category } from "@/lib/categories";
import type {
  ExclusivityAgreement,
  ExclusivityAgreementStatus,
  ExclusivityCheckResponse,
  ExclusivityPricingResponse,
  ExclusivityPurchaseResponse,
} from "@/lib/types";

const todayPlusDays = (days: number) => {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
};

// Query params to GET /brands/exclusivity/check and /pricing are
// timezone-aware ISO datetimes (app/routers/exclusivity.py's
// _require_valid_window rejects naive datetimes) -- midnight UTC on the
// selected calendar day is the simplest unambiguous choice here.
function toIsoMidnightUtc(dateStr: string): string {
  return new Date(`${dateStr}T00:00:00Z`).toISOString();
}

function money(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

const STATUS_VARIANT: Record<ExclusivityAgreementStatus, "success" | "outline" | "secondary"> = {
  active: "success",
  expired: "outline",
  cancelled: "secondary",
};

type Step = "form" | "confirm" | "pay" | "done";

export default function BrandExclusivityPage() {
  const [category, setCategory] = useState<Category>(BASE_CATEGORIES[0]);
  const [city, setCity] = useState("");
  const [startDate, setStartDate] = useState(todayPlusDays(7));
  const [endDate, setEndDate] = useState(todayPlusDays(37));

  const [checking, setChecking] = useState(false);
  const [checkResult, setCheckResult] = useState<ExclusivityCheckResponse | null>(null);
  const [pricing, setPricing] = useState<ExclusivityPricingResponse | null>(null);
  const [checkError, setCheckError] = useState<string | null>(null);

  const [step, setStep] = useState<Step>("form");
  const [purchaseError, setPurchaseError] = useState<string | null>(null);
  const [purchasing, setPurchasing] = useState(false);
  const [purchaseResult, setPurchaseResult] = useState<ExclusivityPurchaseResponse | null>(null);

  const [agreements, setAgreements] = useState<ExclusivityAgreement[] | null>(null);
  const [agreementsError, setAgreementsError] = useState<string | null>(null);

  function loadAgreements() {
    api
      .get<ExclusivityAgreement[]>("/brands/exclusivity")
      .then(setAgreements)
      .catch((err) => setAgreementsError(err instanceof ApiError ? err.message : "Could not load your agreements."));
  }

  useEffect(() => {
    loadAgreements();
  }, []);

  async function checkAvailability() {
    setChecking(true);
    setCheckError(null);
    setCheckResult(null);
    setPricing(null);
    try {
      const params = new URLSearchParams({
        category,
        starts_at: toIsoMidnightUtc(startDate),
        ends_at: toIsoMidnightUtc(endDate),
      });
      if (city.trim()) params.set("city", city.trim());
      const [check, price] = await Promise.all([
        api.get<ExclusivityCheckResponse>(`/brands/exclusivity/check?${params.toString()}`),
        api.get<ExclusivityPricingResponse>(`/brands/exclusivity/pricing?${params.toString()}`),
      ]);
      setCheckResult(check);
      setPricing(price);
    } catch (err) {
      setCheckError(err instanceof ApiError ? err.message : "Could not check availability.");
    } finally {
      setChecking(false);
    }
  }

  async function startPurchase() {
    setPurchaseError(null);
    setPurchasing(true);
    try {
      const result = await api.post<ExclusivityPurchaseResponse>("/brands/exclusivity/purchase", {
        category,
        city: city.trim() || null,
        starts_at: toIsoMidnightUtc(startDate),
        ends_at: toIsoMidnightUtc(endDate),
      });
      setPurchaseResult(result);
      setStep("pay");
    } catch (err) {
      setPurchaseError(err instanceof ApiError ? err.message : "Could not start the purchase.");
      // A 409 here means someone else purchased this window between the
      // check and the purchase -- re-run the availability check so the
      // brand sees the up-to-date state rather than a stale "available".
      checkAvailability();
    } finally {
      setPurchasing(false);
    }
  }

  function handlePaymentSuccess() {
    setStep("done");
    loadAgreements();
  }

  function resetFlow() {
    setStep("form");
    setCheckResult(null);
    setPricing(null);
    setPurchaseResult(null);
    setPurchaseError(null);
  }

  return (
    <BrandShell title="Market tools" backHref="/brand">
      <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Category exclusivity</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Purchase sole rights to a category within a city (or every market) for a defined
                window. While your agreement is active, no other brand can create or activate a
                campaign in that category-and-city combination.
              </p>

              {step === "form" ? (
                <div className="mt-4 flex flex-col gap-4">
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="excl-category">Category</Label>
                    <select
                      id="excl-category"
                      className="min-h-11 rounded-md border border-input bg-background px-3 text-sm"
                      value={category}
                      onChange={(e) => {
                        setCategory(e.target.value as Category);
                        setCheckResult(null);
                        setPricing(null);
                      }}
                    >
                      {BASE_CATEGORIES.map((c) => (
                        <option key={c} value={c}>
                          {CATEGORY_LABELS[c]}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="excl-city">City (optional)</Label>
                    <Input
                      id="excl-city"
                      placeholder="Leave blank for exclusivity in every market"
                      value={city}
                      onChange={(e) => {
                        setCity(e.target.value);
                        setCheckResult(null);
                        setPricing(null);
                      }}
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor="excl-start">Start date</Label>
                      <Input
                        id="excl-start"
                        type="date"
                        value={startDate}
                        onChange={(e) => {
                          setStartDate(e.target.value);
                          setCheckResult(null);
                          setPricing(null);
                        }}
                      />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor="excl-end">End date</Label>
                      <Input
                        id="excl-end"
                        type="date"
                        value={endDate}
                        onChange={(e) => {
                          setEndDate(e.target.value);
                          setCheckResult(null);
                          setPricing(null);
                        }}
                      />
                    </div>
                  </div>

                  <Button type="button" onClick={checkAvailability} disabled={checking}>
                    {checking ? "Checking..." : "Check availability"}
                  </Button>

                  {checkError ? (
                    <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{checkError}</p>
                  ) : null}

                  {checkResult && !checkResult.available ? (
                    <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
                      This window is held by another brand. Try adjacent dates.
                    </p>
                  ) : null}

                  {checkResult?.available && pricing ? (
                    <div className="flex flex-col gap-3 rounded-lg border border-success/30 bg-success/10 p-4">
                      <p className="text-sm font-semibold text-success">Available</p>
                      <p className="text-sm text-foreground">
                        {pricing.days} days &times; {money(pricing.rate_per_day_cents)}/day ={" "}
                        <span className="font-semibold">{money(pricing.total_cents)} total</span>
                      </p>
                      <Button type="button" onClick={() => setStep("confirm")}>
                        Purchase exclusivity
                      </Button>
                    </div>
                  ) : null}
                </div>
              ) : null}

              {step === "confirm" && pricing ? (
                <div className="mt-4 flex flex-col gap-4 rounded-lg border border-border p-4">
                  <p className="text-sm font-semibold">Confirm your agreement</p>
                  <dl className="flex flex-col gap-1 text-sm">
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">Category</dt>
                      <dd>{CATEGORY_LABELS[category]}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">City</dt>
                      <dd>{city.trim() || "All markets"}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">Window</dt>
                      <dd>
                        {startDate} &rarr; {endDate}
                      </dd>
                    </div>
                    <div className="flex justify-between font-semibold">
                      <dt>Total</dt>
                      <dd>{money(pricing.total_cents)}</dd>
                    </div>
                  </dl>
                  {purchaseError ? (
                    <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{purchaseError}</p>
                  ) : null}
                  <div className="flex gap-2">
                    <Button type="button" variant="outline" onClick={resetFlow} disabled={purchasing}>
                      Back
                    </Button>
                    <Button type="button" onClick={startPurchase} disabled={purchasing}>
                      {purchasing ? "Starting..." : "Continue to payment"}
                    </Button>
                  </div>
                </div>
              ) : null}

              {step === "pay" && purchaseResult ? (
                <div className="mt-4 flex flex-col gap-4 rounded-lg border border-border p-4">
                  <p className="text-sm font-semibold">Pay {money(purchaseResult.fee_cents)}</p>
                  <ExclusivityPurchaseForm
                    clientSecret={purchaseResult.client_secret}
                    onSuccess={handlePaymentSuccess}
                  />
                </div>
              ) : null}

              {step === "done" && purchaseResult ? (
                <div className="mt-4 flex flex-col gap-3 rounded-lg border border-success/30 bg-success/10 p-4">
                  <p className="text-sm font-semibold text-success">Exclusivity purchased</p>
                  <p className="text-sm text-foreground">
                    You now hold exclusivity in {CATEGORY_LABELS[category]}
                    {city.trim() ? ` in ${city.trim()}` : " across every market"}, from{" "}
                    {new Date(purchaseResult.starts_at).toLocaleDateString()} through{" "}
                    {new Date(purchaseResult.ends_at).toLocaleDateString()}.
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Receipt total: {money(purchaseResult.fee_cents)} · agreement {purchaseResult.agreement_id}
                  </p>
                  <Button type="button" variant="outline" onClick={resetFlow} className="w-fit">
                    Purchase another
                  </Button>
                </div>
              ) : null}
            </CardContent>
          </Card>
        </div>

        <div className="flex flex-col gap-3">
          <p className="text-sm font-semibold text-muted-foreground">Your agreements</p>
          {agreementsError ? (
            <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{agreementsError}</p>
          ) : null}
          {agreements === null ? (
            <Skeleton className="h-24 w-full" />
          ) : agreements.length === 0 ? (
            <EmptyState title="No agreements yet" description="Purchases you make appear here." />
          ) : (
            <div className="flex flex-col gap-3">
              {agreements.map((a) => (
                <Card key={a.id}>
                  <CardContent className="flex flex-col gap-1 p-4">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-semibold">
                        {CATEGORY_LABELS[a.category as Category] ?? a.category}
                      </p>
                      <Badge variant={STATUS_VARIANT[a.status]}>{a.status}</Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">{a.city ?? "All markets"}</p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(a.starts_at).toLocaleDateString()} &rarr;{" "}
                      {new Date(a.ends_at).toLocaleDateString()}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Paid {money(a.fee_cents)}
                      {a.refund_cents ? ` · refunded ${money(a.refund_cents)}` : ""}
                    </p>
                    {a.status === "active" ? (
                      <a
                        href="mailto:support@teenure.com?subject=Cancel%20exclusivity%20agreement"
                        className="mt-1 text-xs font-medium text-primary underline"
                      >
                        Contact support to cancel
                      </a>
                    ) : null}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>
    </BrandShell>
  );
}
