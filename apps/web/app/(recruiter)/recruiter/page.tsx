"use client";

import { useEffect, useState } from "react";
import { RecruiterShell } from "@/components/recruiter/recruiter-shell";
import { LogoMark } from "@/components/logo";
import { CreditConfirmDialog } from "@/components/recruiter/credit-confirm-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import { trackEvent } from "@/lib/analytics";
import {
  BASE_CATEGORIES,
  CATEGORY_LABELS,
  type Category,
} from "@/lib/categories";
import type {
  RecruiterCredits,
  RecruiterTalentDetail,
  RecruiterSearchCard,
} from "@/lib/types";

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
  if (filters.graduation_year)
    params.set("graduation_year", filters.graduation_year);
  if (filters.city) params.set("city", filters.city);
  if (filters.state) params.set("state", filters.state);
  if (filters.categories.length)
    params.set("categories", filters.categories.join(","));
  if (filters.min_campaigns) params.set("min_campaigns", filters.min_campaigns);
  if (filters.min_rating) params.set("min_rating", filters.min_rating);
  return params.toString();
}

export default function RecruiterSearchPage() {
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [results, setResults] = useState<RecruiterSearchCard[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [credits, setCredits] = useState<RecruiterCredits | null>(null);

  // Profile-view credit flow
  const [pendingRepId, setPendingRepId] = useState<string | null>(null);
  const [detail, setDetail] = useState<RecruiterTalentDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);

  // Contact/message credit flow
  const [messageText, setMessageText] = useState("");
  const [contactOpen, setContactOpen] = useState(false);
  const [contactNotice, setContactNotice] = useState<string | null>(null);

  useEffect(() => {
    runSearch();
    loadCredits();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadCredits() {
    try {
      const c = await api.get<RecruiterCredits>("/recruiters/credits");
      setCredits(c);
    } catch {
      // Non-fatal for the search screen itself.
    }
  }

  async function runSearch() {
    setSearching(true);
    setError(null);
    try {
      const query = buildQuery(filters);
      const cards = await api.get<RecruiterSearchCard[]>(
        `/recruiters/talents/search${query ? `?${query}` : ""}`,
      );
      setResults(cards);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not run this search.",
      );
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

  function handleViewProfile(repId: string) {
    setDetailError(null);
    setDetail(null);
    setPendingRepId(repId);
  }

  async function confirmViewProfile() {
    if (!pendingRepId) return;
    try {
      // The response  is the sole source of truth for the new credit
      // balance -- no local decrement anywhere in this flow.
      const talent = await api.get<RecruiterTalentDetail>(
        `/recruiters/talents/${pendingRepId}`,
      );
      // Aggregate-safe properties only -- no talent identity (name, id,
      // school) in the event payload, per Prompt 19 deliverable 3.
      trackEvent("recruiter_profile_viewed", {
        categories: talent.categories ?? undefined,
      });
      setDetail(talent);
      setPendingRepId(null);
      await loadCredits();
    } catch (err) {
      throw new Error(
        err instanceof ApiError ? err.message : "Could not load this profile.",
      );
    }
  }

  function openContactDialog() {
    setMessageText("");
    setContactNotice(null);
    setContactOpen(true);
  }

  async function confirmSendMessage() {
    if (!detail) return;
    if (!messageText.trim()) {
      throw new Error("Write a message before sending.");
    }
    try {
      await api.post(`/recruiters/talents/${detail.talent_id}/contact`, {
        message_text: messageText,
      });
      // Opaque event only -- no talent id/identity in properties.
      trackEvent("recruiter_profile_contacted", {});
      setContactOpen(false);
      setContactNotice(
        "Message sent. The talent will see it in their inbox and get an alert email.",
      );
      await loadCredits();
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.code === "already_contacted"
            ? "You've already contacted this talent."
            : err.message
          : "Could not send this message.";
      throw new Error(message);
    }
  }

  async function handleSave(repId: string) {
    try {
      await api.post(`/recruiters/talents/${repId}/save`, {});
      setContactNotice("Saved to your default list.");
    } catch (err) {
      setDetailError(
        err instanceof ApiError ? err.message : "Could not save this talent.",
      );
    }
  }

  return (
    <RecruiterShell
      title="Search talents"
      action={
        credits ? (
          <div className="flex items-center gap-2">
            {/* DS Section 8: >5 credits is neutral information; 1-3 is
                gold (scarcity of a premium resource warrants the
                credential accent); 0 is danger. */}
            <Badge
              className={
                credits.contact_credits_remaining === 0
                  ? "border-danger-border bg-danger-dim text-danger"
                  : credits.contact_credits_remaining <= 3
                    ? "border-gold-border bg-gold-dim text-gold"
                    : undefined
              }
              variant={credits.contact_credits_remaining === 0 ? "destructive" : "secondary"}
            >
              {credits.contact_credits_remaining} credit
              {credits.contact_credits_remaining === 1 ? "" : "s"} left
            </Badge>
            {credits.low_credit_warning ? (
              <a
                href="/recruiter/subscription"
                className="text-xs font-medium text-primary hover:underline"
              >
                Top up
              </a>
            ) : null}
          </div>
        ) : undefined
      }
    >
      <Card>
        <CardContent>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="grad_year">Graduation year</Label>
              <Input
                id="grad_year"
                type="number"
                inputMode="numeric"
                value={filters.graduation_year}
                onChange={(e) =>
                  setFilters((prev) => ({
                    ...prev,
                    graduation_year: e.target.value,
                  }))
                }
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="city">City</Label>
              <Input
                id="city"
                value={filters.city}
                onChange={(e) =>
                  setFilters((prev) => ({ ...prev, city: e.target.value }))
                }
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="state">State</Label>
              <Input
                id="state"
                value={filters.state}
                onChange={(e) =>
                  setFilters((prev) => ({ ...prev, state: e.target.value }))
                }
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
                  setFilters((prev) => ({
                    ...prev,
                    min_campaigns: e.target.value,
                  }))
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
                  setFilters((prev) => ({
                    ...prev,
                    min_rating: e.target.value,
                  }))
                }
              />
            </div>
          </div>

          <div className="mt-4 flex flex-col gap-1.5">
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

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Button type="button" onClick={runSearch} disabled={searching}>
              {searching ? "Searching..." : "Search"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setFilters(EMPTY_FILTERS);
              }}
            >
              Clear filters
            </Button>
          </div>
        </CardContent>
      </Card>

      {error ? (
        <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      ) : null}
      {contactNotice ? (
        <p className="rounded-lg bg-success/15 px-3 py-2 text-sm text-success">
          {contactNotice}
        </p>
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
            <Card key={card.talent_id} className="hover:shadow-md">
              <CardContent>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-semibold">
                      {card.city}, {card.state}
                    </p>
                    <p className="text-sm text-text-2">
                      Class of {card.graduation_year}
                    </p>
                  </div>
                  {card.school_type ? (
                    <Badge variant="pending">{card.school_type}</Badge>
                  ) : null}
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
                      // DS Section 7/8: an exceptional track record (>=4.5)
                      // is a credential signal worth surfacing in gold.
                      <span className={card.average_rating >= 4.5 ? "font-semibold text-gold" : undefined}>
                        {card.average_rating.toFixed(1)}★
                      </span>
                    ) : (
                      "No rating yet"
                    )}
                  </span>
                  <span>{card.profile_completeness_score}% complete</span>
                </div>
                <div className="mt-4 flex gap-2">
                  <Button
                    type="button"
                    size="sm"
                    onClick={() => handleViewProfile(card.talent_id)}
                  >
                    View full profile
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => handleSave(card.talent_id)}
                  >
                    Save
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Step 1: explicit cost confirmation before any credit is spent. */}
      <CreditConfirmDialog
        open={pendingRepId !== null}
        title="View full profile"
        description="This will use 1 contact credit and reveal this talent's name, school, and social handles."
        onCancel={() => setPendingRepId(null)}
        onConfirm={confirmViewProfile}
      />

      {detail ? (
        <div
          className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-4"
          role="dialog"
          aria-modal="true"
        >
          <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-xl border border-border bg-card p-6 shadow-md">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold tracking-tight">
                  {detail.display_name}
                </h2>
                <p className="text-sm text-text-2">
                  {detail.school_name} · Class of {detail.graduation_year}
                </p>
                <p className="text-sm text-text-2">
                  {detail.city}, {detail.state}
                </p>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setDetail(null)}
              >
                Close
              </Button>
            </div>

            {detail.bio ? <p className="mt-3 text-sm">{detail.bio}</p> : null}

            <div className="mt-3 flex flex-wrap gap-1">
              {detail.categories.map((c) => (
                <Badge key={c} variant="active">
                  {CATEGORY_LABELS[c as Category] ?? c}
                </Badge>
              ))}
            </div>

            {/* DS Section 8: every verified data point gets a small
                teal checkmark next to the label. */}
            <div className="mt-3 flex flex-col gap-1 text-sm text-text-2">
              {detail.instagram_handle ? (
                <span>
                  <span className="text-teal">✓</span> Instagram: @{detail.instagram_handle}
                </span>
              ) : null}
              {detail.tiktok_handle ? (
                <span>
                  <span className="text-teal">✓</span> TikTok: @{detail.tiktok_handle}
                </span>
              ) : null}
              <span>
                <span className="text-teal">✓</span> {detail.total_campaigns_completed} campaigns completed
              </span>
              <span>
                <span className="text-teal">✓</span>{" "}
                <span className="font-semibold text-gold">
                  ${(detail.total_earnings_cents / 100).toFixed(2)} earned
                </span>
              </span>
              <span>
                {detail.average_rating != null ? (
                  <>
                    <span className="text-teal">✓</span>{" "}
                    <span className={detail.average_rating >= 4.5 ? "font-semibold text-gold" : undefined}>
                      {detail.average_rating.toFixed(1)}★ average rating
                    </span>
                  </>
                ) : (
                  "No rating yet"
                )}
              </span>
            </div>

            {detailError ? (
              <p className="mt-3 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {detailError}
              </p>
            ) : null}

            <div className="mt-5 flex gap-2">
              <Button type="button" onClick={openContactDialog}>
                Message this talent
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => handleSave(detail.talent_id)}
              >
                Save
              </Button>
            </div>

            <p className="mt-4 flex items-center gap-1.5 text-xs text-text-3">
              <LogoMark darkMode size={14} /> Powered by Teenure
            </p>
          </div>
        </div>
      ) : null}

      {/* Step 2: a second explicit cost confirmation for the separate credit-spending action (contact) -- the
          message textarea lives inside this same dialog so composing and confirming the spend is one step. */}
      <CreditConfirmDialog
        open={contactOpen}
        title="Send message"
        description="This will use 1 contact credit. You can only message each talent once."
        confirmLabel="Use 1 credit & send"
        confirmDisabled={!messageText.trim()}
        onCancel={() => setContactOpen(false)}
        onConfirm={confirmSendMessage}
      >
        <Label htmlFor="message_text">Message</Label>
        <Textarea
          id="message_text"
          className="mt-1.5"
          rows={4}
          value={messageText}
          onChange={(e) => setMessageText(e.target.value)}
          placeholder="Introduce yourself and why you're reaching out..."
        />
      </CreditConfirmDialog>
    </RecruiterShell>
  );
}
