"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Countdown } from "@/components/rep/countdown";
import { api, ApiError } from "@/lib/api";
import type { MilestoneParticipation } from "@/lib/types";

const MILESTONE_STEPS = ["pending", "submitted", "confirmed", "paid"];

const ALLOWED_FILE_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/heic",
  "video/mp4",
  "video/quicktime",
]);
const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;

function money(cents: number | null): string {
  if (cents === null) return "—";
  return `$${(cents / 100).toFixed(2)}`;
}

function MilestoneStatusTracker({ status }: { status: string }) {
  const currentIndex = MILESTONE_STEPS.indexOf(status);
  return (
    <div className="flex items-center justify-between">
      {MILESTONE_STEPS.map((step, i) => (
        <div key={step} className="flex flex-1 flex-col items-center gap-1">
          <div className={`size-2.5 rounded-full ${i <= currentIndex ? "bg-primary" : "bg-muted"}`} />
          <span className="text-center text-[0.6rem] text-muted-foreground">{step}</span>
        </div>
      ))}
    </div>
  );
}

/** Per-milestone submission form, mirroring the flat campaign
 * submission form on the campaign detail page (text + file upload,
 * uploaded via the same POST .../submission-files endpoint) but wired
 * to POST .../milestones/:milestone_id/submit (Build Prompt 8B frontend
 * note: "mirrors the flat campaign submission interface ... applied
 * per milestone rather than per campaign"). */
function MilestoneSubmitForm({
  campaignId,
  milestone,
  onSubmitted,
}: {
  campaignId: string;
  milestone: MilestoneParticipation;
  onSubmitted: () => void;
}) {
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(e.target.files ?? []);
    for (const f of selected) {
      if (!ALLOWED_FILE_TYPES.has(f.type)) {
        setError(`${f.name}: unsupported file type.`);
        return;
      }
      if (f.size > MAX_UPLOAD_BYTES) {
        setError(`${f.name}: exceeds the 25MB upload limit.`);
        return;
      }
    }
    setError(null);
    setFiles((prev) => [...prev, ...selected]);
  }

  async function handleSubmit() {
    setPending(true);
    setError(null);
    try {
      const uploadedUrls: string[] = [];
      for (const file of files) {
        const form = new FormData();
        form.append("file", file);
        const result = await api.postForm<{ url: string; storage_key: string }>(
          `/campaigns/${campaignId}/submission-files`,
          form
        );
        uploadedUrls.push(result.url);
      }
      await api.post(`/campaigns/${campaignId}/milestones/${milestone.campaign_milestone_id}/submit`, {
        submission_text: text,
        submission_file_urls: uploadedUrls,
      });
      onSubmitted();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not submit this milestone.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="mt-2 flex flex-col gap-2 rounded-lg border border-border bg-secondary/20 p-3">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={`milestone-submit-text-${milestone.id}`}>Description</Label>
        <Textarea
          id={`milestone-submit-text-${milestone.id}`}
          rows={3}
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={`milestone-submit-files-${milestone.id}`}>Photo or video proof</Label>
        <input
          id={`milestone-submit-files-${milestone.id}`}
          type="file"
          multiple
          accept="image/jpeg,image/png,image/webp,image/heic,video/mp4,video/quicktime"
          onChange={handleFileSelect}
          className="min-h-11 text-sm"
        />
        {files.length > 0 ? (
          <p className="text-xs text-muted-foreground">{files.length} file(s) attached</p>
        ) : null}
      </div>
      {error ? <p className="text-xs text-destructive">{error}</p> : null}
      <Button size="sm" onClick={handleSubmit} disabled={pending}>
        {pending ? "Submitting..." : "Submit milestone"}
      </Button>
    </div>
  );
}

/** Rep-facing milestone list for a milestone campaign's detail page
 * (Build Prompt 8B frontend note: "show each milestone with its title,
 * description, payout amount, current status, and whether it is
 * currently actionable ... never have to guess what they need to do
 * next"). `actionable` is trusted from the server (GET
 * /reps/campaigns/active), never re-derived here. */
export function MilestoneList({
  campaignId,
  milestones,
  payoutPerRepCents,
  onChanged,
}: {
  campaignId: string;
  milestones: MilestoneParticipation[];
  payoutPerRepCents: number | null;
  onChanged: () => void;
}) {
  const sorted = [...milestones].sort((a, b) => a.milestone_number - b.milestone_number);

  return (
    <div className="flex flex-col gap-3">
      {sorted.map((m) => {
        const estimatedPayoutCents =
          m.payout_cents ??
          (payoutPerRepCents !== null ? Math.floor((payoutPerRepCents * m.payout_percentage) / 100) : null);
        const autoReleaseDeadline =
          m.verification_method === "rep_submission" && m.status === "submitted" && m.submitted_at
            ? new Date(new Date(m.submitted_at).getTime() + 24 * 60 * 60 * 1000).toISOString()
            : null;

        return (
          <Card key={m.id}>
            <CardHeader>
              <div className="flex items-center justify-between gap-2">
                <CardTitle>
                  {m.milestone_number}. {m.title}
                </CardTitle>
                <Badge variant={m.status === "paid" || m.status === "confirmed" ? "success" : "secondary"}>
                  {m.status}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {m.description ? <p className="text-sm text-muted-foreground">{m.description}</p> : null}
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">{m.payout_percentage}% of payout</span>
                <span className="font-semibold">{money(estimatedPayoutCents)}</span>
              </div>

              <MilestoneStatusTracker status={m.status} />

              {!m.actionable && m.status === "pending" ? (
                <p className="rounded-md bg-muted/60 px-2.5 py-1.5 text-xs text-muted-foreground">
                  Not yet — finish the earlier milestone(s) first.
                </p>
              ) : null}

              {autoReleaseDeadline ? (
                <p className="text-xs text-muted-foreground">
                  Auto-releases in <Countdown deadline={autoReleaseDeadline} /> unless the brand disputes it
                </p>
              ) : null}

              {m.actionable && m.status === "pending" ? (
                <MilestoneSubmitForm campaignId={campaignId} milestone={m} onSubmitted={onChanged} />
              ) : null}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
