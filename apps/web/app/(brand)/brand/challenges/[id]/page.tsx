"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { BrandShell } from "@/components/brand/brand-shell";
import { api, ApiError } from "@/lib/api";
import type {
  BrandChallengeSubmission,
  Campaign,
  Challenge,
} from "@/lib/types";

function money(cents: number | null): string {
  if (cents === null) return "—";
  return `$${(cents / 100).toFixed(2)}`;
}

export default function BrandChallengeDetailPage() {
  const params = useParams<{ id: string }>();
  const challengeId = params.id;

  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [submissions, setSubmissions] = useState<BrandChallengeSubmission[]>(
    [],
  );
  const [activeCampaigns, setActiveCampaigns] = useState<Campaign[]>([]);
  const [selectedCampaign, setSelectedCampaign] = useState<
    Record<string, string>
  >({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);

  async function load() {
    try {
      const [challenges, subs, campaigns] = await Promise.all([
        api.get<Challenge[]>("/brands/challenges"),
        api.get<BrandChallengeSubmission[]>(
          `/brands/challenges/${challengeId}/submissions`,
        ),
        api.get<Campaign[]>("/brands/campaigns"),
      ]);
      setChallenge(challenges.find((c) => c.id === challengeId) ?? null);
      setSubmissions(subs);
      setActiveCampaigns(campaigns.filter((c) => c.status === "active"));
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not load this challenge.",
      );
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
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not activate this challenge.",
      );
    } finally {
      setBusy(null);
    }
  }

  const [contentForm, setContentForm] = useState({
    goal_text: "",
    rules_text: "",
    judging_criteria: "",
    prize_reward_text: "",
    why_text: "",
  });
  const [savingContent, setSavingContent] = useState(false);

  useEffect(() => {
    if (!challenge) return;
    setContentForm({
      goal_text: challenge.goal_text ?? "",
      rules_text: challenge.rules_text ?? "",
      judging_criteria: challenge.judging_criteria ?? "",
      prize_reward_text: challenge.prize_reward_text ?? "",
      why_text: challenge.why_text ?? "",
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [challenge?.id]);

  async function handleSaveContent() {
    setSavingContent(true);
    setError(null);
    try {
      await api.put<Challenge>(`/brands/challenges/${challengeId}/content`, contentForm);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save these details.");
    } finally {
      setSavingContent(false);
    }
  }

  async function handleSubmitForReview() {
    setBusy("submit-for-review");
    try {
      await api.post<Challenge>(`/brands/challenges/${challengeId}/submit-for-review`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not submit this challenge for review.");
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
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not close this challenge.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function handleReview(submissionId: string) {
    setBusy(submissionId);
    try {
      await api.post(
        `/brands/challenges/${challengeId}/submissions/${submissionId}/review`,
        {},
      );
      await load();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not mark this submission reviewed.",
      );
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
      await api.post(
        `/brands/challenges/${challengeId}/submissions/${submissionId}/convert`,
        {
          campaign_id: campaignId,
        },
      );
      await load();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not convert this submission.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function handleDecline(submissionId: string) {
    setBusy(submissionId);
    try {
      await api.post(
        `/brands/challenges/${challengeId}/submissions/${submissionId}/decline`,
        {},
      );
      await load();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not decline this submission.",
      );
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
        <p className="text-sm text-text-2">Challenge not found.</p>
      </BrandShell>
    );
  }

  const zeroConversionWarning =
    challenge.status === "closed" &&
    challenge.submissions_count >= 30 &&
    challenge.conversion_count === 0;

  return (
    <BrandShell title={challenge.title} backHref="/brand/challenges">
      <div className="flex flex-col gap-6">
        {error ? (
          <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        ) : null}

        <Card className="p-5">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Badge variant={challenge.status === "active" ? "active" : "pending"}>
                {challenge.status}
              </Badge>
              <Badge variant={challenge.moderation_status === "approved" ? "done" : "pending"}>
                {challenge.moderation_status === "pending_review" ? "In review" : challenge.moderation_status}
              </Badge>
              <span className="text-sm text-text-2">
                {challenge.submissions_count} submissions ·{" "}
                {challenge.conversion_count} converted
                {challenge.conversion_rate != null
                  ? ` (${Math.round(challenge.conversion_rate * 100)}%)`
                  : ""}
              </span>
            </div>
            <div className="flex gap-2">
              {challenge.status === "draft" && challenge.moderation_status === "draft" ? (
                <Button size="sm" variant="outline" disabled={busy === "submit-for-review"} onClick={handleSubmitForReview}>
                  Submit for review
                </Button>
              ) : null}
              {challenge.status === "draft" && challenge.moderation_status === "approved" ? (
                <Button
                  size="sm"
                  disabled={busy === "activate"}
                  onClick={handleActivate}
                >
                  Activate
                </Button>
              ) : null}
              {challenge.status === "active" ? (
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy === "close"}
                  onClick={handleClose}
                >
                  Close
                </Button>
              ) : null}
            </div>
          </div>
          <p className="mt-3 text-sm">{challenge.brief}</p>
        </Card>

        {challenge.status === "draft" ? (
          <Card className="p-5">
            <p className="mb-3 text-sm font-semibold">Skills Challenge details</p>
            <div className="flex flex-col gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="goalText">Goal</Label>
                <Textarea
                  id="goalText"
                  rows={2}
                  value={contentForm.goal_text}
                  onChange={(e) => setContentForm({ ...contentForm, goal_text: e.target.value })}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="rulesText">Rules</Label>
                <Textarea
                  id="rulesText"
                  rows={2}
                  value={contentForm.rules_text}
                  onChange={(e) => setContentForm({ ...contentForm, rules_text: e.target.value })}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="judgingCriteria">Judging criteria</Label>
                <Textarea
                  id="judgingCriteria"
                  rows={2}
                  value={contentForm.judging_criteria}
                  onChange={(e) => setContentForm({ ...contentForm, judging_criteria: e.target.value })}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="prizeReward">Prize / reward</Label>
                <Input
                  id="prizeReward"
                  value={contentForm.prize_reward_text}
                  onChange={(e) => setContentForm({ ...contentForm, prize_reward_text: e.target.value })}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="whyText">Why we're offering this (required, max 150 words)</Label>
                <Textarea
                  id="whyText"
                  rows={3}
                  value={contentForm.why_text}
                  onChange={(e) => setContentForm({ ...contentForm, why_text: e.target.value })}
                />
              </div>
              <Button size="sm" className="w-fit" disabled={savingContent} onClick={handleSaveContent}>
                {savingContent ? "Saving..." : "Save details"}
              </Button>
            </div>
          </Card>
        ) : null}

        {zeroConversionWarning ? (
          <Card className="border-teal-border bg-teal-dim p-4 text-sm text-foreground">
            Consider using challenges to discover talents for active campaigns.
            Talents invest time in submissions -- converting the best ones builds
            your brand reputation on Teenure.
          </Card>
        ) : null}

        <section className="flex flex-col gap-3">
          <h2 className="text-sm font-semibold text-text-3">
            Submissions
          </h2>
          {submissions.length === 0 ? (
            <EmptyState
              title="No submissions yet"
              description="Talents who match this challenge can submit their work."
            />
          ) : (
            <div className="flex flex-col gap-3">
              {submissions.map((s) => (
                <Card key={s.id} className="p-5">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="font-medium">{s.talent.display_name}</p>
                      <p className="text-sm text-text-2">
                        {s.talent.city} · {s.talent.categories.join(", ")} ·
                        completeness {s.talent.profile_completeness_score}
                      </p>
                      <p className="text-sm text-text-2">
                        {s.talent.campaigns_completed} campaigns completed
                        {s.talent.challenge_conversion_rate != null
                          ? ` · ${Math.round(s.talent.challenge_conversion_rate * 100)}% challenge conversion`
                          : ""}
                      </p>
                    </div>
                    {/* DS Section 7: a converted submission is the earned
                        moment (gold bonus paid to the talent) -- everything
                        else is a neutral in-progress state. */}
                    <Badge variant={s.status === "converted" ? "earned" : "pending"}>
                      {s.status}
                    </Badge>
                  </div>

                  {s.submission_text ? (
                    <p className="mt-3 text-sm">{s.submission_text}</p>
                  ) : null}
                  {s.submission_file_urls.length > 0 ? (
                    <ul className="mt-2 flex flex-col gap-1">
                      {s.submission_file_urls.map((url) => (
                        <li key={url}>
                          <a
                            href={url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-sm text-primary hover:underline"
                          >
                            {url}
                          </a>
                        </li>
                      ))}
                    </ul>
                  ) : null}

                  {s.status === "converted" ? (
                    <p className="mt-3 text-sm text-text-2">
                      Converted ·{" "}
                      <span className="font-semibold text-gold">{money(s.payout_cents)} discovery bonus</span>{" "}
                      ({s.payout_status ?? "pending"})
                    </p>
                  ) : (
                    <div className="mt-4 flex flex-wrap items-center gap-2">
                      {s.status === "submitted" ? (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={busy === s.id}
                          onClick={() => handleReview(s.id)}
                        >
                          Mark reviewed
                        </Button>
                      ) : null}
                      <select
                        className="rounded-md border border-input bg-white/4 px-2 py-1.5 text-sm"
                        value={selectedCampaign[s.id] ?? ""}
                        onChange={(e) =>
                          setSelectedCampaign((prev) => ({
                            ...prev,
                            [s.id]: e.target.value,
                          }))
                        }
                      >
                        <option value="">Select campaign…</option>
                        {activeCampaigns.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.title}
                          </option>
                        ))}
                      </select>
                      <Button
                        size="sm"
                        disabled={busy === s.id}
                        onClick={() => handleConvert(s.id)}
                      >
                        Convert
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={busy === s.id}
                        onClick={() => handleDecline(s.id)}
                      >
                        Decline
                      </Button>
                    </div>
                  )}
                  {s.status !== "converted" ? (
                    <p className="mt-2 text-xs text-text-2">
                      Converting sends the Talent a campaign invitation and a
                      $7.50 Teenure discovery bonus. This does not create a
                      billing event -- the campaign budget was set at campaign
                      activation.
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
