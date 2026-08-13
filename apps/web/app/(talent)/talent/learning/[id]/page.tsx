"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { TalentShell } from "@/components/talent/talent-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import { trackEvent } from "@/lib/analytics";
import type {
  ContentBlockPublic,
  ModuleCompleteResponse,
  ModuleContent,
  ModuleStartResponse,
  QuizQuestionPublic,
} from "@/lib/types";

type Stage = "disclosure" | "content" | "quiz" | "pass" | "fail";

/** Module player (Build Prompt 8H frontend spec): disclosure modal ->
 * content blocks in sequence with scroll-tracked submit visibility ->
 * quiz (one question at a time, no going back, one-shot submit) ->
 * pass/fail screen. No confetti, no score on the pass screen -- the
 * badge is the reward. */
export default function ModulePlayerPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const moduleId = params.id;

  const [module, setModule] = useState<ModuleContent | null>(null);
  const [alreadyPassed, setAlreadyPassed] = useState(false);
  const [cooldownMessage, setCooldownMessage] = useState<string | null>(null);
  const [stage, setStage] = useState<Stage>("disclosure");
  const [disclosureChecked, setDisclosureChecked] = useState(false);
  const [scrolledToEnd, setScrolledToEnd] = useState(false);
  const [quizIndex, setQuizIndex] = useState(0);
  const [answers, setAnswers] = useState<number[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [result, setResult] = useState<ModuleCompleteResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const contentEndRef = useRef<HTMLDivElement>(null);

  const nonQuizBlocks = useMemo(
    () => module?.content_blocks.filter((b) => b.type !== "quiz") ?? [],
    [module],
  );
  const quizQuestions = useMemo<QuizQuestionPublic[]>(() => {
    const quizBlock = module?.content_blocks.find((b) => b.type === "quiz");
    return quizBlock ? (quizBlock.content as QuizQuestionPublic[]) : [];
  }, [module]);

  useEffect(() => {
    api
      .get<ModuleContent>(`/talents/modules/${moduleId}`)
      .catch(() => null)
      .then((m) => setModule(m));
  }, [moduleId]);

  useEffect(() => {
    function onScroll() {
      if (!contentEndRef.current) return;
      const rect = contentEndRef.current.getBoundingClientRect();
      if (rect.top <= window.innerHeight) setScrolledToEnd(true);
    }
    window.addEventListener("scroll", onScroll);
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, [stage]);

  async function acknowledgeDisclosure() {
    setPending(true);
    setError(null);
    try {
      const res = await api.post<ModuleStartResponse>(
        `/talents/modules/${moduleId}/start`,
        {
          disclosure_acknowledged: true,
        },
      );
      setModule(res.module);
      trackEvent("module_started", {
        module_id: moduleId,
        category: res.module.category,
      });
      setStage("content");
    } catch (err) {
      if (err instanceof ApiError && err.code === "already_completed") {
        setAlreadyPassed(true);
      } else if (err instanceof ApiError && err.code === "retake_cooldown") {
        setCooldownMessage(err.message);
      } else {
        setError(
          err instanceof ApiError
            ? err.message
            : "Could not start this module.",
        );
      }
    } finally {
      setPending(false);
    }
  }

  function proceedToQuizOrComplete() {
    if (quizQuestions.length === 0) {
      void submitCompletion([]);
    } else {
      setStage("quiz");
    }
  }

  function nextQuestion() {
    if (selected === null) return;
    const nextAnswers = [...answers, selected];
    setAnswers(nextAnswers);
    setSelected(null);
    if (quizIndex + 1 < quizQuestions.length) {
      setQuizIndex((i) => i + 1);
    } else {
      void submitCompletion(nextAnswers);
    }
  }

  async function submitCompletion(finalAnswers: number[]) {
    setPending(true);
    setError(null);
    try {
      const res = await api.post<ModuleCompleteResponse>(
        `/talents/modules/${moduleId}/complete`,
        {
          answers: finalAnswers,
        },
      );
      setResult(res);
      if (res.passed) {
        trackEvent("module_passed", {
          module_id: moduleId,
          quiz_score: res.quiz_score,
          category: module?.category,
        });
        if (res.badge) {
          trackEvent("badge_earned", {
            badge_title: res.badge.badge_title,
            category: module?.category,
          });
        }
        setStage("pass");
      } else {
        trackEvent("module_failed", {
          module_id: moduleId,
          quiz_score: res.quiz_score,
          category: module?.category,
        });
        setStage("fail");
      }
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not submit this module.",
      );
    } finally {
      setPending(false);
    }
  }

  if (alreadyPassed) {
    return (
      <TalentShell title="Module" backHref="/talent/learning">
        <Card className="p-6 text-center">
          <p className="text-lg font-semibold">
            You&apos;ve already earned this badge.
          </p>
          <Button className="mt-4" onClick={() => router.push("/talent/learning")}>
            Back to Learning Hub
          </Button>
        </Card>
      </TalentShell>
    );
  }

  if (cooldownMessage) {
    return (
      <TalentShell title="Module" backHref="/talent/learning">
        <Card className="p-6 text-center">
          <p className="text-lg font-semibold">Almost there.</p>
          <p className="mt-2 text-sm text-muted-foreground">
            {cooldownMessage}
          </p>
          <Button className="mt-4" onClick={() => router.push("/talent/learning")}>
            Back to Learning Hub
          </Button>
        </Card>
      </TalentShell>
    );
  }

  if (!module) {
    return (
      <TalentShell title="Module" backHref="/talent/learning">
        <Skeleton className="h-64 w-full" />
      </TalentShell>
    );
  }

  return (
    <TalentShell title={module.title} backHref="/talent/learning">
      <div className="flex flex-col gap-5">
        {error ? (
          <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        ) : null}

        {stage === "disclosure" ? (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
            <Card className="w-full max-w-sm p-6">
              <p className="text-lg font-semibold">Before you start</p>
              <p className="mt-2 text-sm text-muted-foreground">
                This module is unpaid. Completing it earns a verified{" "}
                {module.badge_title} badge that appears on your profile and is
                visible to brands and colleges. If your school has a Teenure
                curriculum agreement, you may be eligible for a completion
                stipend — check with your counselor.
              </p>
              <label className="mt-4 flex items-start gap-2 text-sm">
                <Checkbox
                  checked={disclosureChecked}
                  onCheckedChange={(c) => setDisclosureChecked(c === true)}
                />
                I understand this module is unpaid and I am completing it to
                earn a verified credential.
              </label>
              <Button
                className="mt-4 w-full"
                size="lg"
                disabled={!disclosureChecked || pending}
                onClick={acknowledgeDisclosure}
              >
                {pending ? "Starting…" : "Start module"}
              </Button>
            </Card>
          </div>
        ) : null}

        {stage === "content" ? (
          <ProgressBar
            current={0}
            total={nonQuizBlocks.length + (quizQuestions.length > 0 ? 1 : 0)}
          />
        ) : null}
        {stage === "quiz" ? (
          <ProgressBar
            current={nonQuizBlocks.length > 0 ? 1 : 0}
            total={nonQuizBlocks.length + (quizQuestions.length > 0 ? 1 : 0)}
          />
        ) : null}

        {stage === "content" ? (
          <div className="flex flex-col gap-4">
            {nonQuizBlocks.map((block, i) => (
              <ContentBlockView key={i} block={block} />
            ))}
            <div ref={contentEndRef} />
            {scrolledToEnd ? (
              <Button
                size="lg"
                onClick={proceedToQuizOrComplete}
                disabled={pending}
              >
                {quizQuestions.length > 0
                  ? "Continue to quiz"
                  : pending
                    ? "Submitting…"
                    : "Complete module"}
              </Button>
            ) : (
              <p className="text-center text-xs text-muted-foreground">
                Scroll to the end to continue
              </p>
            )}
          </div>
        ) : null}

        {stage === "quiz" && quizQuestions[quizIndex] ? (
          <Card className="p-5">
            <p className="text-xs text-muted-foreground">
              Question {quizIndex + 1} of {quizQuestions.length}
            </p>
            <p className="mt-2 text-base font-semibold">
              {quizQuestions[quizIndex].question}
            </p>
            <div className="mt-4 flex flex-col gap-2">
              {quizQuestions[quizIndex].options.map((opt, oi) => (
                <label
                  key={oi}
                  className="flex min-h-11 items-center gap-3 rounded-lg border border-border p-3 text-sm hover:border-primary/40"
                >
                  <input
                    type="radio"
                    name="quiz-option"
                    checked={selected === oi}
                    onChange={() => setSelected(oi)}
                  />
                  {opt}
                </label>
              ))}
            </div>
            <Button
              className="mt-4 w-full"
              size="lg"
              disabled={selected === null || pending}
              onClick={nextQuestion}
            >
              {quizIndex + 1 < quizQuestions.length
                ? "Next Question"
                : pending
                  ? "Submitting…"
                  : "Submit Quiz"}
            </Button>
          </Card>
        ) : null}

        {stage === "pass" && result?.badge ? (
          <Card className="p-6 text-center">
            <div
              className="mx-auto flex size-16 items-center justify-center rounded-full text-2xl font-bold text-white"
              style={{ backgroundColor: result.badge.badge_color }}
            >
              ✓
            </div>
            <p className="mt-4 text-lg font-semibold">
              {result.badge.badge_title}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              {result.badge.badge_description}
            </p>
            <p className="mt-3 text-sm">
              This badge has been added to your profile.
            </p>
            <div className="mt-5 flex flex-col gap-2">
              <Button
                size="lg"
                onClick={() => router.push("/talent/profile-preview")}
              >
                View My Profile
              </Button>
              <Button
                size="lg"
                variant="outline"
                onClick={() => router.push("/talent/learning")}
              >
                Continue Learning
              </Button>
            </div>
          </Card>
        ) : null}

        {stage === "fail" && result ? (
          <Card className="p-6">
            <p className="text-lg font-semibold">
              Almost there — review and try again in 24 hours.
            </p>
            <div className="mt-4 flex flex-col gap-3">
              {(result.correct_answers ?? []).map((wa) => (
                <div
                  key={wa.question_index}
                  className="rounded-lg border border-border p-3 text-sm"
                >
                  <p className="font-medium">
                    {quizQuestions[wa.question_index]?.question}
                  </p>
                  <p className="mt-1 text-muted-foreground">
                    Correct answer:{" "}
                    {
                      quizQuestions[wa.question_index]?.options[
                        wa.correct_index
                      ]
                    }
                  </p>
                </div>
              ))}
            </div>
            <Button
              className="mt-4 w-full"
              size="lg"
              onClick={() => router.push("/talent/learning")}
            >
              Back to Learning Hub
            </Button>
          </Card>
        ) : null}
      </div>
    </TalentShell>
  );
}

function ProgressBar({ current, total }: { current: number; total: number }) {
  const pct = total > 0 ? Math.round((current / total) * 100) : 0;
  return (
    <div className="h-1.5 w-full rounded-full bg-muted">
      <div
        className="h-1.5 rounded-full bg-primary transition-all"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function ContentBlockView({ block }: { block: ContentBlockPublic }) {
  if (block.type === "text") {
    return (
      <p className="max-w-prose text-sm leading-relaxed">
        {block.content as string}
      </p>
    );
  }
  if (block.type === "video_url") {
    return (
      <video
        controls
        className="w-full rounded-lg"
        src={block.content as string}
      >
        Your browser does not support embedded video.
      </video>
    );
  }
  if (block.type === "image_url") {
    // eslint-disable-next-line @next/next/no-img-element
    return (
      <img
        src={block.content as string}
        alt="Module illustration"
        className="w-full rounded-lg"
      />
    );
  }
  return null;
}
