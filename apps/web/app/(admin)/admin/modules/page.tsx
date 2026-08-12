"use client";

import { useEffect, useState } from "react";
import { AdminShell } from "@/components/admin/admin-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import type { AdminModule, ContentBlockType } from "@/lib/types";

interface DraftQuizQuestion {
  question: string;
  options: string[];
  correct_index: number;
}

interface DraftBlock {
  type: ContentBlockType;
  text: string; // for text/video_url/image_url
  questions: DraftQuizQuestion[]; // for quiz
}

function emptyQuestion(): DraftQuizQuestion {
  return { question: "", options: ["", "", "", ""], correct_index: 0 };
}

/** Admin module management + builder (Build Prompt 8H frontend spec).
 * Single page: list with quality signals, a content-block builder for
 * creating new draft modules, and a preview toggle that renders
 * exactly what a rep sees -- correct answers hidden client-side too,
 * on top of the server never sending them in the first place. */
export default function AdminModulesPage() {
  const [modules, setModules] = useState<AdminModule[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showBuilder, setShowBuilder] = useState(false);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("");
  const [estimatedMinutes, setEstimatedMinutes] = useState(5);
  const [badgeTitle, setBadgeTitle] = useState("");
  const [badgeDescription, setBadgeDescription] = useState("");
  const [badgeColor, setBadgeColor] = useState("#6C3FC5");
  const [passingScore, setPassingScore] = useState<number | "">("");
  const [blocks, setBlocks] = useState<DraftBlock[]>([]);
  const [preview, setPreview] = useState(false);
  const [pending, setPending] = useState(false);

  async function load() {
    try {
      setModules(await api.get<AdminModule[]>("/admin/modules"));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load modules.");
    }
  }

  useEffect(() => {
    load();
  }, []);

  function addBlock(type: ContentBlockType) {
    setBlocks((prev) => [
      ...prev,
      type === "quiz" ? { type, text: "", questions: [emptyQuestion()] } : { type, text: "", questions: [] },
    ]);
  }

  function removeBlock(index: number) {
    setBlocks((prev) => prev.filter((_, i) => i !== index));
  }

  function moveBlock(index: number, direction: -1 | 1) {
    setBlocks((prev) => {
      const next = [...prev];
      const target = index + direction;
      if (target < 0 || target >= next.length) return prev;
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  }

  const hasQuiz = blocks.some((b) => b.type === "quiz");

  async function handleCreate() {
    setPending(true);
    setError(null);
    try {
      const content_blocks = blocks.map((b) =>
        b.type === "quiz"
          ? { type: b.type, content: b.questions }
          : { type: b.type, content: b.text }
      );
      await api.post("/admin/modules", {
        title,
        description,
        category: category.trim() || null,
        estimated_minutes: estimatedMinutes,
        badge_title: badgeTitle,
        badge_description: badgeDescription,
        badge_color: badgeColor,
        badge_icon: null,
        passing_score: hasQuiz ? (passingScore === "" ? null : Number(passingScore)) : null,
        content_blocks,
      });
      setShowBuilder(false);
      setTitle("");
      setDescription("");
      setCategory("");
      setBadgeTitle("");
      setBadgeDescription("");
      setBlocks([]);
      setPassingScore("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create module.");
    } finally {
      setPending(false);
    }
  }

  async function handleActivate(id: string) {
    try {
      await api.post(`/admin/modules/${id}/activate`, {});
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not activate module.");
    }
  }

  async function handleArchive(id: string) {
    try {
      await api.post(`/admin/modules/${id}/archive`, {});
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not archive module.");
    }
  }

  return (
    <AdminShell
      title="Learning modules"
      action={<Button onClick={() => setShowBuilder((v) => !v)}>{showBuilder ? "Cancel" : "New module"}</Button>}
    >
      {error ? <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p> : null}

      {showBuilder ? (
        <Card>
          <CardHeader>
            <CardTitle>{preview ? "Preview (rep view — correct answers hidden)" : "Build a module"}</CardTitle>
          </CardHeader>
          <CardContent>
            {!preview ? (
              <div className="flex flex-col gap-4">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <Label htmlFor="m-title">Title</Label>
                    <Input id="m-title" value={title} onChange={(e) => setTitle(e.target.value)} />
                  </div>
                  <div>
                    <Label htmlFor="m-category">Category (optional)</Label>
                    <Input id="m-category" value={category} onChange={(e) => setCategory(e.target.value)} />
                  </div>
                </div>
                <div>
                  <Label htmlFor="m-description">Description</Label>
                  <Textarea id="m-description" value={description} onChange={(e) => setDescription(e.target.value)} rows={2} />
                </div>
                <div className="grid gap-3 sm:grid-cols-3">
                  <div>
                    <Label htmlFor="m-minutes">Estimated minutes</Label>
                    <Input
                      id="m-minutes"
                      type="number"
                      value={estimatedMinutes}
                      onChange={(e) => setEstimatedMinutes(Number(e.target.value))}
                    />
                  </div>
                  <div>
                    <Label htmlFor="m-badge-title">Badge title</Label>
                    <Input id="m-badge-title" value={badgeTitle} onChange={(e) => setBadgeTitle(e.target.value)} />
                  </div>
                  <div>
                    <Label htmlFor="m-badge-color">Badge color</Label>
                    <Input
                      id="m-badge-color"
                      type="color"
                      value={badgeColor}
                      onChange={(e) => setBadgeColor(e.target.value)}
                    />
                  </div>
                </div>
                <div>
                  <Label htmlFor="m-badge-desc">Badge description</Label>
                  <Textarea id="m-badge-desc" value={badgeDescription} onChange={(e) => setBadgeDescription(e.target.value)} rows={2} />
                </div>

                {hasQuiz ? (
                  <div>
                    <Label htmlFor="m-passing-score">Passing score (1-100)</Label>
                    <Input
                      id="m-passing-score"
                      type="number"
                      min={1}
                      max={100}
                      value={passingScore}
                      onChange={(e) => setPassingScore(e.target.value === "" ? "" : Number(e.target.value))}
                    />
                  </div>
                ) : null}

                <div className="flex flex-col gap-3">
                  <p className="text-sm font-semibold">Content blocks</p>
                  {blocks.map((block, i) => (
                    <div key={i} className="rounded-lg border border-border p-3">
                      <div className="mb-2 flex items-center justify-between">
                        <Badge variant="outline">{block.type}</Badge>
                        <div className="flex gap-1">
                          <Button size="sm" variant="ghost" onClick={() => moveBlock(i, -1)}>
                            ↑
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => moveBlock(i, 1)}>
                            ↓
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => removeBlock(i)}>
                            Remove
                          </Button>
                        </div>
                      </div>
                      {block.type !== "quiz" ? (
                        <Textarea
                          value={block.text}
                          onChange={(e) =>
                            setBlocks((prev) => prev.map((b, bi) => (bi === i ? { ...b, text: e.target.value } : b)))
                          }
                          rows={block.type === "text" ? 4 : 1}
                          placeholder={block.type === "text" ? "Body text…" : "https://…"}
                        />
                      ) : (
                        <div className="flex flex-col gap-3">
                          {block.questions.map((q, qi) => (
                            <div key={qi} className="rounded-md bg-secondary/40 p-2">
                              <Input
                                className="mb-2"
                                placeholder="Question"
                                value={q.question}
                                onChange={(e) =>
                                  setBlocks((prev) =>
                                    prev.map((b, bi) =>
                                      bi === i
                                        ? {
                                            ...b,
                                            questions: b.questions.map((qq, qqi) =>
                                              qqi === qi ? { ...qq, question: e.target.value } : qq
                                            ),
                                          }
                                        : b
                                    )
                                  )
                                }
                              />
                              {q.options.map((opt, oi) => (
                                <label key={oi} className="mb-1 flex min-h-9 items-center gap-2 text-sm">
                                  <input
                                    type="radio"
                                    name={`correct-${i}-${qi}`}
                                    checked={q.correct_index === oi}
                                    onChange={() =>
                                      setBlocks((prev) =>
                                        prev.map((b, bi) =>
                                          bi === i
                                            ? {
                                                ...b,
                                                questions: b.questions.map((qq, qqi) =>
                                                  qqi === qi ? { ...qq, correct_index: oi } : qq
                                                ),
                                              }
                                            : b
                                        )
                                      )
                                    }
                                  />
                                  <Input
                                    value={opt}
                                    placeholder={`Option ${oi + 1}`}
                                    onChange={(e) =>
                                      setBlocks((prev) =>
                                        prev.map((b, bi) =>
                                          bi === i
                                            ? {
                                                ...b,
                                                questions: b.questions.map((qq, qqi) =>
                                                  qqi === qi
                                                    ? {
                                                        ...qq,
                                                        options: qq.options.map((o, ooi) => (ooi === oi ? e.target.value : o)),
                                                      }
                                                    : qq
                                                ),
                                              }
                                            : b
                                        )
                                      )
                                    }
                                  />
                                </label>
                              ))}
                            </div>
                          ))}
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() =>
                              setBlocks((prev) =>
                                prev.map((b, bi) => (bi === i ? { ...b, questions: [...b.questions, emptyQuestion()] } : b))
                              )
                            }
                          >
                            Add question
                          </Button>
                        </div>
                      )}
                    </div>
                  ))}
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" variant="outline" onClick={() => addBlock("text")}>
                      + Text
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => addBlock("video_url")}>
                      + Video
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => addBlock("image_url")}>
                      + Image
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => addBlock("quiz")}>
                      + Quiz
                    </Button>
                  </div>
                </div>

                <div className="flex gap-2">
                  <Button variant="outline" onClick={() => setPreview(true)} disabled={blocks.length === 0}>
                    Preview as rep
                  </Button>
                  <Button onClick={handleCreate} disabled={pending || !title || !description || blocks.length === 0}>
                    {pending ? "Creating…" : "Create draft"}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                <p className="text-lg font-semibold">{title || "Untitled module"}</p>
                <p className="text-sm text-muted-foreground">{description}</p>
                {blocks.map((block, i) => (
                  <div key={i}>
                    {block.type === "text" ? <p className="text-sm">{block.text}</p> : null}
                    {block.type === "video_url" ? (
                      <p className="text-sm text-muted-foreground">[video: {block.text}]</p>
                    ) : null}
                    {block.type === "image_url" ? (
                      <p className="text-sm text-muted-foreground">[image: {block.text}]</p>
                    ) : null}
                    {block.type === "quiz"
                      ? block.questions.map((q, qi) => (
                          <div key={qi} className="mb-3 rounded-md border border-border p-3">
                            <p className="text-sm font-medium">{q.question}</p>
                            <div className="mt-2 flex flex-col gap-1">
                              {q.options.map((opt, oi) => (
                                <label key={oi} className="flex min-h-9 items-center gap-2 text-sm">
                                  <input type="radio" disabled />
                                  {opt}
                                </label>
                              ))}
                            </div>
                            {/* correct_index deliberately never rendered here -- admin
                               preview shows exactly what a rep sees. */}
                          </div>
                        ))
                      : null}
                  </div>
                ))}
                <Button variant="outline" onClick={() => setPreview(false)}>
                  Back to builder
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      ) : null}

      {modules === null ? (
        <Skeleton className="h-48 w-full" />
      ) : modules.length === 0 ? (
        <EmptyState title="No modules yet" description="Create the first module to open the Learning Hub." />
      ) : (
        <div className="flex flex-col gap-3">
          {modules.map((m) => (
            <Card key={m.id}>
              <CardContent className="flex flex-col gap-2 p-4">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span
                      className="inline-block size-3 rounded-full"
                      style={{ backgroundColor: m.badge_color }}
                      aria-hidden="true"
                    />
                    <p className="text-sm font-semibold">{m.title}</p>
                    <Badge variant="outline">{m.status}</Badge>
                  </div>
                  <div className="flex gap-2">
                    {m.status === "draft" ? (
                      <Button size="sm" onClick={() => handleActivate(m.id)}>
                        Activate
                      </Button>
                    ) : null}
                    {m.status === "active" ? (
                      <Button size="sm" variant="outline" onClick={() => handleArchive(m.id)}>
                        Archive
                      </Button>
                    ) : null}
                  </div>
                </div>
                <p className="text-sm text-muted-foreground">{m.description}</p>
                <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                  <span>{m.completion_count} completions</span>
                  <span>{m.pass_rate !== null ? `${Math.round(m.pass_rate * 100)}% pass rate` : "no completions yet"}</span>
                  <span>{m.average_attempts !== null ? `${m.average_attempts} avg attempts` : ""}</span>
                  {m.in_progress_count > 0 ? <span>{m.in_progress_count} in progress</span> : null}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </AdminShell>
  );
}
