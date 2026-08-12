"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { BrandShell } from "@/components/brand/brand-shell";
import { api, ApiError } from "@/lib/api";
import { BASE_CATEGORIES, CATEGORY_LABELS, type Category } from "@/lib/categories";
import type { Challenge, ChallengeCreateRequest, ChallengeSubmissionFormat } from "@/lib/types";

export default function NewChallengePage() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [brief, setBrief] = useState("");
  const [category, setCategory] = useState<Category>(BASE_CATEGORIES[0]);
  const [submissionFormat, setSubmissionFormat] = useState<ChallengeSubmissionFormat>("both");
  const [submissionPrompt, setSubmissionPrompt] = useState("");
  const [maxSubmissions, setMaxSubmissions] = useState<string>("");
  const [closesAt, setClosesAt] = useState<string>("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleCreate(activate: boolean) {
    setPending(true);
    setError(null);
    try {
      const body: ChallengeCreateRequest = {
        title,
        brief,
        category,
        submission_format: submissionFormat,
        submission_prompt: submissionPrompt,
        target_cities: [],
        max_submissions: maxSubmissions ? Number(maxSubmissions) : null,
        closes_at: closesAt ? new Date(closesAt).toISOString() : null,
      };
      const created = await api.post<Challenge>("/brands/challenges", body);
      if (activate) {
        await api.post<Challenge>(`/brands/challenges/${created.id}/activate`);
      }
      router.push(`/brand/challenges/${created.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create this challenge.");
    } finally {
      setPending(false);
    }
  }

  const canSubmit = title.trim() && brief.trim() && submissionPrompt.trim();

  return (
    <BrandShell title="New challenge" backHref="/brand/challenges">
      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="flex flex-col gap-4 p-5">
          <div>
            <Label htmlFor="title">Title</Label>
            <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="brief">Brief</Label>
            <Textarea id="brief" rows={4} value={brief} onChange={(e) => setBrief(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="category">Category</Label>
            <select
              id="category"
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={category}
              onChange={(e) => setCategory(e.target.value as Category)}
            >
              {BASE_CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {CATEGORY_LABELS[c]}
                </option>
              ))}
            </select>
          </div>
          <div>
            <Label htmlFor="submission_format">Submission format</Label>
            <select
              id="submission_format"
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={submissionFormat}
              onChange={(e) => setSubmissionFormat(e.target.value as ChallengeSubmissionFormat)}
            >
              <option value="both">Text and/or file</option>
              <option value="text">Text only</option>
              <option value="file">File only</option>
            </select>
          </div>
          <div>
            <Label htmlFor="submission_prompt">Submission prompt</Label>
            <Textarea
              id="submission_prompt"
              rows={3}
              placeholder="What to create, how long, what format"
              value={submissionPrompt}
              onChange={(e) => setSubmissionPrompt(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="max_submissions">Max submissions (optional)</Label>
              <Input
                id="max_submissions"
                type="number"
                min={1}
                value={maxSubmissions}
                onChange={(e) => setMaxSubmissions(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="closes_at">Close date (optional)</Label>
              <Input id="closes_at" type="date" value={closesAt} onChange={(e) => setClosesAt(e.target.value)} />
            </div>
          </div>

          {error ? <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p> : null}

          <div className="flex gap-3 pt-2">
            <Button variant="outline" disabled={!canSubmit || pending} onClick={() => handleCreate(false)}>
              Save as draft
            </Button>
            <Button disabled={!canSubmit || pending} onClick={() => handleCreate(true)}>
              Create and activate
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Challenges are free -- no Stripe charge. They&apos;re a brand acquisition tool at this stage.
          </p>
        </Card>

        {/* Preview panel -- exactly what a rep will see. */}
        <Card className="p-5">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Rep preview</p>
          <p className="text-lg font-semibold">{title || "Challenge title"}</p>
          <p className="mt-1 text-sm text-muted-foreground">{CATEGORY_LABELS[category]}</p>
          <p className="mt-3 text-sm">{brief || "Your brief will appear here."}</p>
          <p className="mt-3 text-sm font-medium">What to submit</p>
          <p className="text-sm text-muted-foreground">{submissionPrompt || "Your submission prompt will appear here."}</p>
          <div className="mt-4 rounded-lg border-2 border-primary/40 bg-primary/5 p-3 text-xs text-muted-foreground">
            This challenge is unpaid. Reps see a mandatory disclosure before they can submit, and Teenure pays a
            $7.50 discovery bonus only if you convert their submission to a paid campaign invitation.
          </div>
        </Card>
      </div>
    </BrandShell>
  );
}
