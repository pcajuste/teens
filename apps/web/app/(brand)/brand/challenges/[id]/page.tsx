"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { BrandShell } from "@/components/brand/brand-shell";
import { api, ApiError } from "@/lib/api";
import type { BrandChallengeSubmission, Campaign, Challenge } from "@/lib/types";

function money(cents: number | null): string {
  if (cents === null) return "—";
  return `$${(cents / 100).toFixed(2)}`;
}

export default function BrandChallengeDetailPage() {
  const params = useParams<{ id: string }>();
  const challengeId = params.id;

  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [submissions, setSubmissions] = useState<BrandChallengeSubmission[]>([]);
  const [activeCampaigns, setActiveCampaigns] = useState<Campaign[]>([]);
  const [selectedCampaign, setSelectedCampaign] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);

  async function load() {
    try {
      const [challenges, subs, campaigns] = await Promise.all([
        api.get<Challenge[]>("/brands/challenges"),
        api.get<BrandChallengeSubmission[]>(`/brands/challenges/${challengeId}/submissions`),
        api.get<Campaign[]>("/brands/campaigns"),
      ]);
      setChallenge(challenges.find((c) => c.id === challengeId) ?? null);
      setSubmissions(subs);
      setActiveCampaigns(campaigns.filter((c) => c.status === "active"));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load this challenge.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [challengeId]);

  async function handleActivate() {
    setBusy("activate");
    try {
      await api.post<Challenge>(`/brands/challenges/${challengeId}/activate`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not activate this challenge.");
    } finally {
      setBusy(null);
    }
  }

  async function handleClose() {
    setBusy("close");
    try {
      await api.post<Challenge>(`/brands/challenges/${challengeId}/close`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not close this challenge.");
    } finally {
      setBusy(null);
    }
  }

  async function handleReview(submissionId: string) {
    setBusy(submissionId);
    try {
      await api.post(`/brands/challenges/${challengeId}/submissions/${submissionId}/review`, {});
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not mark this submission reviewed.");
    } finally {
      setBusy(null);
    }
  }

  async function handleConvert(submissionId: string) {
    const campaignId = selectedCampaign[submissionId];
    if (!campaignId) {
      setError("Select a campaign to convert this submission into.");
      return;
    }
    setBusy(submissionId);
    try {
      await api.post(`/brands/challenges/${challengeId}/submissions/${submissionId}/convert`, {
        campaign_id: campaignId,
      });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not convert this submission.");
    } finally {
      setBusy(null);
    }
  }

  async function handleDecline(submissionId: string) {
    setBusy(submissionId);
    try {
      await api.post(`/brands/challenges/${challengeId}/submissions/${submissionId}/decline`, {});
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not decline this submission.");
    } finally {
      setBusy(null);
    }
  }

  if (loading) {
    return (
      <BrandShell title="Challenge" backHref="/brand/challenges">
        <Skeleton className="h-48 w-full" />
      </BrandShell>
    );
  }

  if (!challenge) {
    return (
      <BrandShell title="Challenge" backHref="/brand/challenges">
        <p className="text-sm text-muted-foreground">Challenge not found.</p>
      </BrandShell>
    );
  }

  const zeroConversionWarning =
    challenge.status === "closed" && challenge.submissions_count >= 30 && challenge.conversion_count === 0;

  return (
    <BrandShell title={challenge.title} backHref="/brand/challenges">
      <div className="flex flex-col gap-6">
        {error ? <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p> : null}

        <Card className="p-5">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Badge variant={challenge.status === "active" ? "success" : challenge.status === "draft" ? "outline" : "secondary"}>
                {challenge.status}
              </Badge>
              <span className="text-sm text-muted-foreground">
                {challenge.submissions_count} submissions · {challenge.conversion_count} converted
                {challenge.conversion_rate != null ? ` (${Math.round(challenge.conversion_rate * 100)}%)` : ""}
              </span>
            </div>
            <div className="flex gap-2">
              {challenge.status === "draft" ? (
                <Button size="sm" disabled={busy === "activate"} onClick={handleActivate}>
                  Activate
                </Button>
              ) : null}
              {challenge.status === "active" ? (
                <Button size="sm" variant="outline" disabled={busy === "close"} onClick={handleClose}>
                  Close
                </Button>
              ) : null}
            </div>
          </div>
          <p className="mt-3 text-sm">{challenge.brief}</p>
        </Card>

        {zeroConversionWarning ? (
          <Card className="border-warning/40 bg-warning/10 p-4 text-sm">
            Consider using challenges to discover reps for active campaigns. Reps invest time in submissions --
            converting the best ones builds your brand reputation on Teenure.
          </Card>
        ) : null}

        <section className="flex flex-col gap-3">
          <h2 className="text-sm font-semibold text-muted-foreground">Submissions</h2>
          {submissions.length === 0 ? (
            <EmptyState title="No submissions yet" description="Reps who match this challenge can submit their work." />
          ) : (
            <div className="flex flex-col gap-3">
              {submissions.map((s) => (
                <Card key={s.id} className="p-5">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="font-medium">{s.rep.display_name}</p>
                      <p className="text-sm text-muted-foreground">
                        {s.rep.city} · {s.rep.categories.join(", ")} · completeness {s.rep.profile_completeness_score}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {s.rep.campaigns_completed} campaigns completed
                        {s.rep.challenge_conversion_rate != null
                          ? ` · ${Math.round(s.rep.challenge_conversion_rate * 100)}% challenge conversion`
                          : ""}
                      </p>
                    </div>
                    <Badge variant={s.status === "converted" ? "success" : "secondary"}>{s.status}</Badge>
                  </div>

                  {s.submission_text ? <p className="mt-3 text-sm">{s.submission_text}</p> : null}
                  {s.submission_file_urls.length > 0 ? (
                    <ul className="mt-2 flex flex-col gap-1">
                      {s.submission_file_urls.map((url) => (
                        <li key={url}>
                          <a href={url} target="_blank" rel="noreferrer" className="text-sm text-primary hover:underline">
                            {url}
                          </a>
                        </li>
                      ))}
                    </ul>
                  ) : null}

                  {s.status === "converted" ? (
                    <p className="mt-3 text-sm text-muted-foreground">
                      Converted · {money(s.payout_cents)} discovery bonus ({s.payout_status ?? "pending"})
                    </p>
                  ) : (
                    <div className="mt-4 flex flex-wrap items-center gap-2">
                      {s.status === "submitted" ? (
                        <Button size="sm" variant="outline" disabled={busy === s.id} onClick={() => handleReview(s.id)}>
                          Mark reviewed
                        </Button>
                      ) : null}
                      <select
                        className="rounded-md border border-input bg-background px-2 py-1.5 text-sm"
                        value={selectedCampaign[s.id] ?? ""}
                        onChange={(e) => setSelectedCampaign((prev) => ({ ...prev, [s.id]: e.target.value }))}
                      >
                        <option value="">Select campaign…</option>
                        {activeCampaigns.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.title}
                          </option>
                        ))}
                      </select>
                      <Button size="sm" disabled={busy === s.id} onClick={() => handleConvert(s.id)}>
                        Convert
                      </Button>
                      <Button size="sm" variant="outline" disabled={busy === s.id} onClick={() => handleDecline(s.id)}>
                        Decline
                      </Button>
                    </div>
                  )}
                  {s.status !== "converted" ? (
                    <p className="mt-2 text-xs text-muted-foreground">
                      Converting sends the rep a campaign invitation and a $7.50 Teenure discovery bonus. This does
                      not create a billing event -- the campaign budget was set at campaign activation.
                    </p>
                  ) : null}
                </Card>
              ))}
            </div>
          )}
        </section>
      </div>
    </BrandShell>
  );
}
