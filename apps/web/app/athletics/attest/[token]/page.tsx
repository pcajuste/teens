"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import type { CoachAttestationDecision, CoachAttestationToken } from "@/lib/types";
import { SPORT_LABELS, SPORT_STATS_FIELDS, SEASON_LEVEL_LABELS, type SupportedSport } from "@/lib/sports";

// ATHLETICS-7 deliverable 2: the coach attestation landing page. The
// most sensitive public page on the platform -- a coach may open this
// on a shared/public device, so it exposes only display_name and
// season stats, has no navigation, no signup CTA, no link anywhere
// else on the platform. Mirrors the verified-light styling of
// apps/web/app/verified/[token]/page.tsx (the other credential-document
// public page in this codebase) rather than the marketing shell, since
// that page is this codebase's existing precedent for "no nav header."
type Reason = "expired" | "already_used" | "superseded" | "not_found" | "already_resolved" | null | undefined;

function reasonMessage(reason: Reason, talentFirstName: string): string {
  switch (reason) {
    case "expired":
      return `This link has expired. Ask ${talentFirstName} to send a new request.`;
    case "already_used":
    case "already_resolved":
      return "This season has already been confirmed. Nothing more to do.";
    case "superseded":
      return "A newer link was sent. Check your email for the most recent one.";
    case "not_found":
    default:
      return "This link is not valid. It may have been copied incorrectly.";
  }
}

function firstName(displayName: string | null | undefined): string {
  if (!displayName) return "the talent";
  return displayName.trim().split(/\s+/)[0];
}

function renderStatValue(value: unknown): string {
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (value == null) return "—";
  return String(value);
}

interface Achievement {
  title: string;
  type: string;
  season_year: number;
}

export default function CoachAttestationPage() {
  const params = useParams<{ token: string }>();
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState<CoachAttestationToken | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [confirming, setConfirming] = useState(false);
  const [declining, setDeclining] = useState(false);
  const [declineConfirmOpen, setDeclineConfirmOpen] = useState(false);
  const [outcome, setOutcome] = useState<CoachAttestationDecision | null>(null);
  const [outcomeAction, setOutcomeAction] = useState<"confirm" | "decline" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<CoachAttestationToken>(`/athletics/attest/${encodeURIComponent(params.token)}`)
      .then(setToken)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load this link."))
      .finally(() => setLoading(false));
  }, [params.token]);

  async function handleConfirm() {
    setConfirming(true);
    setActionError(null);
    try {
      const decision = await api.post<CoachAttestationDecision>(
        `/athletics/attest/${encodeURIComponent(params.token)}/confirm`,
      );
      setOutcome(decision);
      setOutcomeAction("confirm");
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setConfirming(false);
    }
  }

  async function handleDecline() {
    setDeclining(true);
    setActionError(null);
    try {
      const decision = await api.post<CoachAttestationDecision>(
        `/athletics/attest/${encodeURIComponent(params.token)}/decline`,
      );
      setOutcome(decision);
      setOutcomeAction("decline");
      setDeclineConfirmOpen(false);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setDeclining(false);
    }
  }

  const talentName = token?.talent_display_name ?? "this talent";
  const fName = firstName(token?.talent_display_name);

  return (
    <main className="verified-light min-h-screen bg-[var(--vl-bg)] text-[var(--vl-ink)]">
      <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-6 p-6">
        {loading ? (
          <p className="text-center text-sm text-[var(--vl-text-2)]">Loading...</p>
        ) : error ? (
          <div className="rounded-[var(--r-lg)] border border-[var(--vl-border)] bg-[var(--vl-surface)] p-8 text-center">
            <p className="text-base font-medium">This link is not valid.</p>
            <p className="mt-2 text-sm text-[var(--vl-text-2)]">{error}</p>
          </div>
        ) : outcome ? (
          outcome.success ? (
            <div className="rounded-[var(--r-lg)] border border-[var(--vl-border)] bg-[var(--vl-surface)] p-8 text-center">
              <p className="text-base font-medium">
                {outcomeAction === "decline"
                  ? `Got it. ${talentName} has been notified.`
                  : `Done. ${talentName}'s season is now verified.`}
              </p>
            </div>
          ) : (
            <div className="rounded-[var(--r-lg)] border border-[var(--vl-border)] bg-[var(--vl-surface)] p-8 text-center">
              <p className="text-base font-medium">{reasonMessage(outcome.reason as Reason, fName)}</p>
            </div>
          )
        ) : token && !token.valid ? (
          <div className="rounded-[var(--r-lg)] border border-[var(--vl-border)] bg-[var(--vl-surface)] p-8 text-center">
            <p className="text-base font-medium">{reasonMessage(token.reason as Reason, fName)}</p>
          </div>
        ) : token && token.valid ? (
          <div className="flex flex-col gap-5 rounded-[var(--r-lg)] border border-[var(--vl-border)] bg-[var(--vl-bg)] p-6 shadow-sm">
            <h1 className="text-xl font-bold tracking-tight">
              Confirm {talentName}&rsquo;s season record
            </h1>

            <div className="rounded-[var(--r-md)] bg-[var(--vl-surface)] p-4">
              <p className="text-sm font-semibold">
                {SPORT_LABELS[token.sport as SupportedSport] ?? token.sport} &middot; {token.season_year}
              </p>
              <p className="mt-1 text-sm text-[var(--vl-text-2)]">
                {token.team_name}
                {token.level ? ` · ${SEASON_LEVEL_LABELS[token.level as keyof typeof SEASON_LEVEL_LABELS] ?? token.level}` : ""}
              </p>
            </div>

            {token.sport_stats ? (
              <div className="flex flex-col gap-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-[var(--vl-text-2)]">
                  Season stats
                </p>
                <div className="grid grid-cols-2 gap-x-4 gap-y-2">
                  {(SPORT_STATS_FIELDS[token.sport as SupportedSport] ?? [])
                    .filter((f) => token.sport_stats?.[f.key] !== undefined)
                    .map((f) => (
                      <div key={f.key} className="flex flex-col">
                        <span className="text-xs text-[var(--vl-text-2)]">{f.label}</span>
                        <span className="text-sm font-medium">
                          {renderStatValue(token.sport_stats?.[f.key])}
                        </span>
                      </div>
                    ))}
                </div>
              </div>
            ) : null}

            {Array.isArray((token.sport_stats as { achievements?: Achievement[] } | undefined)?.achievements) &&
            ((token.sport_stats as { achievements?: Achievement[] }).achievements?.length ?? 0) > 0 ? (
              <div className="flex flex-col gap-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-[var(--vl-text-2)]">
                  Achievements
                </p>
                <div className="flex flex-col gap-1">
                  {(token.sport_stats as { achievements: Achievement[] }).achievements.map((a, i) => (
                    <p key={i} className="text-sm">
                      {a.title} <span className="text-[var(--vl-text-2)]">({a.type})</span>
                    </p>
                  ))}
                </div>
              </div>
            ) : null}

            {actionError ? (
              <p className="rounded-[var(--r-md)] bg-[var(--vl-danger)]/10 px-3 py-2 text-sm text-[var(--vl-danger)]">
                {actionError}
              </p>
            ) : null}

            <div className="flex flex-col gap-2">
              <Button type="button" size="lg" className="w-full" disabled={confirming} onClick={handleConfirm}>
                {confirming ? "Confirming..." : "Yes, confirm this record"}
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={declining}
                onClick={() => setDeclineConfirmOpen(true)}
              >
                I can&rsquo;t confirm this
              </Button>
            </div>
          </div>
        ) : null}

        {declineConfirmOpen ? (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
            role="dialog"
            aria-modal="true"
          >
            <div className="w-full max-w-sm rounded-[var(--r-lg)] border border-[var(--vl-border)] bg-[var(--vl-bg)] p-6 shadow-md">
              <h2 className="text-base font-semibold">Are you sure?</h2>
              <p className="mt-2 text-sm text-[var(--vl-text-2)]">
                {talentName} will be notified that you couldn&rsquo;t confirm this record. They can correct any
                errors and try again.
              </p>
              {actionError ? (
                <p className="mt-3 rounded-[var(--r-md)] bg-[var(--vl-danger)]/10 px-3 py-2 text-sm text-[var(--vl-danger)]">
                  {actionError}
                </p>
              ) : null}
              <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setDeclineConfirmOpen(false)}
                  disabled={declining}
                >
                  Cancel
                </Button>
                <Button type="button" variant="destructive" onClick={handleDecline} disabled={declining}>
                  {declining ? "Sending..." : "Confirm"}
                </Button>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </main>
  );
}
