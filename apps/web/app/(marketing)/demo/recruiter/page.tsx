"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import { trackEvent } from "@/lib/analytics";
import { DemoPageViewTracker } from "@/components/demo/demo-chrome";
import {
  BASE_CATEGORIES,
  CATEGORY_LABELS,
  type Category,
} from "@/lib/categories";
import type { RecruiterSearchCard } from "@/lib/types";

// Build Prompt 12A part 1. Unlike /demo/talent, this page genuinely
// calls the FastAPI backend -- GET /demo/recruiter-search, which runs
// the exact same repository query as the authenticated
// GET /recruiters/talents/search (Build Prompt 11), just without a
// session or a credit charge. Results are the same no-PII card shape
// a signed-in recruiter sees; "view full profile" isn't offered here
// at all, since that's the credit-gated action this preview exists to
// sell, not give away.
interface Filters {
  graduation_year: string;
  city: string;
  state: string;
  categories: Category[];
  min_campaigns: string;
  min_rating: string;
}

const EMPTY_FILTERS: Filters = {
  graduation_year: "",
  city: "",
  state: "",
  categories: [],
  min_campaigns: "",
  min_rating: "",
};

function buildQuery(filters: Filters): string {
  const params = new URLSearchParams();
  if (filters.graduation_year) params.set("graduation_year", filters.graduation_year);
  if (filters.city) params.set("city", filters.city);
  if (filters.state) params.set("state", filters.state);
  if (filters.categories.length) params.set("categories", filters.categories.join(","));
  if (filters.min_campaigns) params.set("min_campaigns", filters.min_campaigns);
  if (filters.min_rating) params.set("min_rating", filters.min_rating);
  return params.toString();
}

export default function DemoRecruiterSearchPage() {
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [results, setResults] = useState<RecruiterSearchCard[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    runSearch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function runSearch() {
    setSearching(true);
    setError(null);
    try {
      const query = buildQuery(filters);
      const cards = await api.get<RecruiterSearchCard[]>(
        `/demo/recruiter-search${query ? `?${query}` : ""}`,
      );
      setResults(cards);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not run this search.");
    } finally {
      setSearching(false);
    }
  }

  function toggleCategory(c: Category) {
    setFilters((prev) => ({
      ...prev,
      categories: prev.categories.includes(c)
        ? prev.categories.filter((x) => x !== c)
        : [...prev.categories, c],
    }));
  }

  function handleStartTrial() {
    trackEvent("demo_cta_clicked", { demo: "recruiter" });
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-6 p-4 pb-16">
      <DemoPageViewTracker demo="recruiter_search" />

      <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-center text-sm font-medium text-amber-800 dark:text-amber-300">
        Demo — live search against real seed profiles, no sign-in required. No
        credit is ever spent browsing this preview.
      </div>

      <header className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold">See what a recruiter search looks like</h1>
        <p className="text-sm text-text-2">
          Every card below is a real, no-PII search result -- the same shape a
          signed-in recruiter sees. Viewing a full profile requires a free
          trial account.
        </p>
      </header>

      <Card>
        <CardContent className="flex flex-col gap-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="graduation_year">Graduation year</Label>
              <Input
                id="graduation_year"
                type="number"
                inputMode="numeric"
                value={filters.graduation_year}
                onChange={(e) =>
                  setFilters((prev) => ({ ...prev, graduation_year: e.target.value }))
                }
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="city">City</Label>
              <Input
                id="city"
                value={filters.city}
                onChange={(e) => setFilters((prev) => ({ ...prev, city: e.target.value }))}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="state">State</Label>
              <Input
                id="state"
                value={filters.state}
                onChange={(e) => setFilters((prev) => ({ ...prev, state: e.target.value }))}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="min_campaigns">Min. campaigns completed</Label>
              <Input
                id="min_campaigns"
                type="number"
                inputMode="numeric"
                value={filters.min_campaigns}
                onChange={(e) =>
                  setFilters((prev) => ({ ...prev, min_campaigns: e.target.value }))
                }
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="min_rating">Min. average rating</Label>
              <Input
                id="min_rating"
                type="number"
                step="0.1"
                min={0}
                max={5}
                inputMode="decimal"
                value={filters.min_rating}
                onChange={(e) =>
                  setFilters((prev) => ({ ...prev, min_rating: e.target.value }))
                }
              />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label>Categories</Label>
            <div className="flex flex-wrap gap-2">
              {BASE_CATEGORIES.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => toggleCategory(c)}
                  className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                    filters.categories.includes(c)
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border-muted bg-transparent text-text-2 hover:text-foreground"
                  }`}
                >
                  {CATEGORY_LABELS[c]}
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button type="button" onClick={runSearch} disabled={searching}>
              {searching ? "Searching..." : "Search"}
            </Button>
            <Button type="button" variant="ghost" onClick={() => setFilters(EMPTY_FILTERS)}>
              Clear filters
            </Button>
          </div>
        </CardContent>
      </Card>

      {error ? (
        <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
      ) : null}

      {searching && results === null ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-40 w-full" />
          ))}
        </div>
      ) : results && results.length === 0 ? (
        <EmptyState
          title="No talents match these filters"
          description="Try widening your graduation year range, clearing city/state, or removing a category."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {results?.map((card) => (
            <Card key={card.talent_id}>
              <CardContent>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-semibold">
                      {card.city}, {card.state}
                    </p>
                    <p className="text-sm text-text-2">Class of {card.graduation_year}</p>
                  </div>
                  {card.school_type ? <Badge variant="pending">{card.school_type}</Badge> : null}
                </div>
                <div className="mt-2 flex flex-wrap gap-1">
                  {card.categories.map((c) => (
                    <Badge key={c} variant="active">
                      {CATEGORY_LABELS[c as Category] ?? c}
                    </Badge>
                  ))}
                </div>
                <div className="mt-3 flex items-center gap-4 text-sm text-text-2">
                  <span>{card.total_campaigns_completed} campaigns</span>
                  <span>
                    {card.average_rating != null ? (
                      <span className={card.average_rating >= 4.5 ? "font-semibold text-gold" : undefined}>
                        {card.average_rating.toFixed(1)}★
                      </span>
                    ) : (
                      "No rating yet"
                    )}
                  </span>
                  <span>{card.profile_completeness_score}% complete</span>
                </div>
                <div className="mt-4">
                  <Link href="/recruiter/signup" onClick={handleStartTrial}>
                    <Button type="button" size="sm">
                      Start your free trial
                    </Button>
                  </Link>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </main>
  );
}
