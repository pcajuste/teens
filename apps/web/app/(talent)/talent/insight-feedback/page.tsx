"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { TalentShell } from "@/components/talent/talent-shell";
import { api, ApiError } from "@/lib/api";
import type { InsightInvitation } from "@/lib/types";

// Build Prompt 8I: panel selection is system-driven, never a
// talent-initiated application -- this page is opt-in-to-be-eligible
// plus responding to invitations already assigned, not a browse/apply
// flow like Scholarships.
export default function TalentInsightFeedbackPage() {
  const [optedIn, setOptedIn] = useState<boolean | null>(null);
  const [invitations, setInvitations] = useState<InsightInvitation[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ratingsByInvite, setRatingsByInvite] = useState<Record<string, number>>({});
  const [submittingId, setSubmittingId] = useState<string | null>(null);

  function load() {
    api
      .get<{ opted_in: boolean }>("/talents/insight/opt-in")
      .then((r) => setOptedIn(r.opted_in))
      .catch(() => undefined);
    api
      .get<InsightInvitation[]>("/talents/insight/invitations")
      .then(setInvitations)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load invitations."));
  }

  useEffect(load, []);

  async function handleOptInToggle(checked: boolean) {
    setOptedIn(checked);
    try {
      await api.put(`/talents/insight/opt-in?opted_in=${checked}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save your preference.");
    }
  }

  async function submitResponse(panelMemberId: string) {
    const score = ratingsByInvite[panelMemberId];
    if (!score) return;
    setSubmittingId(panelMemberId);
    setError(null);
    try {
      await api.post(`/talents/insight/invitations/${panelMemberId}/respond`, {
        ratings: [{ question: "Overall rating", score }],
      });
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not submit your feedback.");
    } finally {
      setSubmittingId(null);
    }
  }

  return (
    <TalentShell title="Insight & Feedback">
      {error ? <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p> : null}

      <Card>
        <CardContent>
          <label className="flex items-center gap-3">
            <Checkbox checked={optedIn ?? false} onCheckedChange={(checked) => handleOptInToggle(checked === true)} />
            <span className="text-sm">
              I want to be eligible for Insight &amp; Feedback panels -- private sessions where brands share
              pre-release material for my feedback, paid, never public. Brands only ever see a pseudonym, never my
              name.
            </span>
          </label>
        </CardContent>
      </Card>

      {invitations === null ? (
        <Skeleton className="h-28 w-full" />
      ) : invitations.length === 0 ? (
        <EmptyState
          title="No invitations yet"
          description="When a brand's panel criteria matches your profile, an invitation will appear here."
        />
      ) : (
        <div className="flex flex-col gap-3">
          {invitations.map((inv) => (
            <Card key={inv.panel_member_id}>
              <CardContent className="flex flex-col gap-2">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-semibold">{inv.campaign_title}</p>
                  <Badge variant="earned">${(inv.compensation_cents / 100).toFixed(2)}</Badge>
                </div>
                <p className="text-sm text-text-2">{inv.business_question}</p>
                <p className="text-xs text-text-3">{inv.confidentiality_terms}</p>

                {inv.responded_at ? (
                  <Badge variant="done" className="w-fit">
                    Feedback submitted
                  </Badge>
                ) : (
                  <div className="flex flex-col gap-2">
                    <div className="flex gap-2">
                      {[1, 2, 3, 4, 5].map((score) => (
                        <button
                          key={score}
                          type="button"
                          onClick={() => setRatingsByInvite({ ...ratingsByInvite, [inv.panel_member_id]: score })}
                          className={`size-9 rounded-full border text-sm font-medium ${
                            ratingsByInvite[inv.panel_member_id] === score
                              ? "border-primary bg-primary/10 text-primary"
                              : "border-border-muted text-text-2"
                          }`}
                        >
                          {score}
                        </button>
                      ))}
                    </div>
                    <Button
                      size="sm"
                      className="w-fit"
                      disabled={!ratingsByInvite[inv.panel_member_id] || submittingId === inv.panel_member_id}
                      onClick={() => submitResponse(inv.panel_member_id)}
                    >
                      {submittingId === inv.panel_member_id ? "Submitting..." : "Submit feedback"}
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </TalentShell>
  );
}
