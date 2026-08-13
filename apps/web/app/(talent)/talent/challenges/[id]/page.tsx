"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { TalentShell } from "@/components/talent/talent-shell";
import { api, ApiError } from "@/lib/api";
import type {
  QuizResult,
  TalentAvailableChallenge,
  TalentChallengeSubmissionResponse,
  SubmitChallengeRequest,
} from "@/lib/types";

export default function ChallengeDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const challengeId = params.id;

  const [challenge, setChallenge] = useState<TalentAvailableChallenge | null>(
    null,
  );
  const [alreadySubmitted, setAlreadySubmitted] = useState(false);
  const [disclosureAcknowledged, setDisclosureAcknowledged] = useState(false);
  const [submissionText, setSubmissionText] = useState("");
  const [submissionFileUrl, setSubmissionFileUrl] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [quizAnswers, setQuizAnswers] = useState<number[]>([]);
  const [quizResult, setQuizResult] = useState<QuizResult | null>(null);
  const [quizSubmitting, setQuizSubmitting] = useState(false);

  useEffect(() => {
    api
      .get<TalentAvailableChallenge[]>("/talents/challenges/available")
      .then((list) => {
        const found = list.find((c) => c.id === challengeId) ?? null;
        setChallenge(found);
        if (!found) {
          setAlreadySubmitted(true);
        }
      })
      .catch((err) =>
        setError(
          err instanceof ApiError
            ? err.message
            : "Could not load this challenge.",
        ),
      )
      .finally(() => setLoading(false));
  }, [challengeId]);

  async function handleSubmit() {
    setPending(true);
    setError(null);
    try {
      const body: SubmitChallengeRequest = {
        submission_text: submissionText.trim() || null,
        submission_file_urls: submissionFileUrl.trim()
          ? [submissionFileUrl.trim()]
          : [],
        disclosure_acknowledged: disclosureAcknowledged,
      };
      await api.post<TalentChallengeSubmissionResponse>(
        `/talents/challenges/${challengeId}/submit`,
        body,
      );
      if (challenge && challenge.quiz_questions.length > 0) {
        setQuizAnswers(new Array(challenge.quiz_questions.length).fill(-1));
      }
      setSubmitted(true);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not submit your work.",
      );
    } finally {
      setPending(false);
    }
  }

  async function handleQuizSubmit() {
    setQuizSubmitting(true);
    setError(null);
    try {
      const result = await api.post<QuizResult>(`/talents/challenges/${challengeId}/quiz/submit`, {
        answers: quizAnswers,
      });
      setQuizResult(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not submit the quiz.");
    } finally {
      setQuizSubmitting(false);
    }
  }

  if (loading) {
    return (
      <TalentShell title="Challenge" backHref="/talent">
        <Skeleton className="h-48 w-full" />
      </TalentShell>
    );
  }

  if (submitted) {
    const quizQuestions = challenge?.quiz_questions ?? [];
    const hasQuiz = quizQuestions.length > 0;
    const canSubmitQuiz = hasQuiz && quizAnswers.every((a) => a >= 0);

    return (
      <TalentShell title="Challenge" backHref="/talent">
        <Card className="p-6 text-center">
          <p className="text-lg font-semibold">Submitted.</p>
          <p className="mt-1 text-sm text-muted-foreground">
            You&apos;ll hear from us if a brand wants to work with you.
          </p>
        </Card>

        {hasQuiz && !quizResult ? (
          <Card className="mt-4 p-5">
            <p className="text-sm font-semibold">This challenge has a quiz.</p>
            <div className="mt-3 flex flex-col gap-4">
              {quizQuestions.map((q, qi) => (
                <div key={qi} className="flex flex-col gap-2">
                  <p className="text-sm font-medium">{q.question}</p>
                  {q.options.map((option, oi) => (
                    <label key={oi} className="flex items-center gap-2 text-sm">
                      <input
                        type="radio"
                        name={`quiz-${qi}`}
                        checked={quizAnswers[qi] === oi}
                        onChange={() =>
                          setQuizAnswers((prev) => prev.map((a, i) => (i === qi ? oi : a)))
                        }
                      />
                      {option}
                    </label>
                  ))}
                </div>
              ))}
              <Button disabled={!canSubmitQuiz || quizSubmitting} onClick={handleQuizSubmit} className="w-fit">
                {quizSubmitting ? "Submitting…" : "Submit quiz"}
              </Button>
            </div>
          </Card>
        ) : null}

        {quizResult ? (
          <Card className="mt-4 p-5">
            <p className="text-sm font-semibold">
              You scored {quizResult.score}/{quizResult.total}
              {quizResult.passed ? " -- nice work!" : ""}
            </p>
          </Card>
        ) : null}

        <Button className="mt-4" onClick={() => router.push("/talent")}>
          Back to dashboard
        </Button>
      </TalentShell>
    );
  }

  if (!challenge) {
    return (
      <TalentShell title="Challenge" backHref="/talent">
        <p className="text-sm text-muted-foreground">
          {alreadySubmitted
            ? "You've already submitted to this challenge, or it's no longer available."
            : "This challenge could not be found."}
        </p>
      </TalentShell>
    );
  }

  const textAllowed =
    challenge.submission_format === "text" ||
    challenge.submission_format === "both";
  const fileAllowed =
    challenge.submission_format === "file" ||
    challenge.submission_format === "both";
  const canSubmit =
    disclosureAcknowledged &&
    (submissionText.trim().length > 0 || submissionFileUrl.trim().length > 0);

  return (
    <TalentShell title={challenge.title} backHref="/talent">
      <div className="flex flex-col gap-6">
        {error ? (
          <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        ) : null}

        <Card className="p-5">
          <div className="mb-2 flex items-center justify-between gap-2">
            <Badge variant="outline">{challenge.category}</Badge>
            {challenge.closes_at ? (
              <span className="text-xs text-muted-foreground">
                Closes {new Date(challenge.closes_at).toLocaleDateString()}
              </span>
            ) : null}
          </div>
          <p className="text-sm">{challenge.brief}</p>
          <p className="mt-3 text-sm font-medium">What to submit</p>
          <p className="text-sm text-muted-foreground">
            {challenge.submission_prompt}
          </p>
        </Card>

        {/* Mandatory disclosure box -- cannot be hidden or scrolled past
           before the submission form is reachable (spec: talent portal
           frontend addition). The checkbox is what sends
           disclosure_acknowledged: true to the server. */}
        <Card className="border-2 border-primary/40 bg-primary/5 p-5">
          <p className="text-sm font-semibold">This challenge is unpaid.</p>
          <p className="mt-1 text-sm text-muted-foreground">
            You are sharing your creative work to help a brand discover talent.
            If the brand loves your submission, they may invite you to a paid
            campaign and Teenure will pay you a $7.50 discovery bonus. This is
            not guaranteed.
          </p>
          <label className="mt-3 flex items-center gap-2 text-sm">
            <Checkbox
              checked={disclosureAcknowledged}
              onCheckedChange={(checked) =>
                setDisclosureAcknowledged(checked === true)
              }
            />
            I understand this challenge is unpaid.
          </label>
        </Card>

        {disclosureAcknowledged ? (
          <Card className="p-5">
            <div className="flex flex-col gap-4">
              {textAllowed ? (
                <div>
                  <Label htmlFor="submission_text">Your submission</Label>
                  <Textarea
                    id="submission_text"
                    value={submissionText}
                    onChange={(e) => setSubmissionText(e.target.value)}
                    rows={5}
                    maxLength={2000}
                  />
                  <p className="mt-1 text-right text-xs text-muted-foreground">
                    {submissionText.length}/2000
                  </p>
                </div>
              ) : null}
              {fileAllowed ? (
                <div>
                  <Label htmlFor="submission_file_url">File URL</Label>
                  <input
                    id="submission_file_url"
                    className="mt-1 w-full rounded-md border border-input bg-white/4 px-3 py-2 text-sm"
                    placeholder="https://…"
                    value={submissionFileUrl}
                    onChange={(e) => setSubmissionFileUrl(e.target.value)}
                  />
                </div>
              ) : null}
              <Button
                size="lg"
                disabled={!canSubmit || pending}
                onClick={handleSubmit}
              >
                {pending ? "Submitting…" : "Submit My Work"}
              </Button>
            </div>
          </Card>
        ) : null}
      </div>
    </TalentShell>
  );
}
