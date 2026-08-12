"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Countdown } from "@/components/rep/countdown";
import { WithdrawButton } from "@/components/rep/withdraw-button";
import { api, ApiError } from "@/lib/api";
import type { CampaignParticipation, CampaignSummary } from "@/lib/types";

const ALLOWED_FILE_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/heic",
  "video/mp4",
  "video/quicktime",
]);
const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;

const STATUS_STEPS = ["submitted", "under_review", "confirmed", "paid"];

function money(cents: number | null): string {
  if (cents === null) return "—";
  return `$${(cents / 100).toFixed(2)}`;
}

export default function CampaignDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const campaignId = params.id;

  const [campaign, setCampaign] = useState<CampaignSummary | null>(null);
  const [participation, setParticipation] = useState<CampaignParticipation | null>(null);
  const [ftcAccepted, setFtcAccepted] = useState(false);
  const [submissionText, setSubmissionText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [fileUrls, setFileUrls] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function load() {
    try {
      const [available, active, history] = await Promise.all([
        api.get<CampaignSummary[]>("/reps/campaigns/available"),
        api.get<CampaignParticipation[]>("/reps/campaigns/active"),
        api.get<CampaignParticipation[]>("/reps/campaigns/history"),
      ]);
      const found = available.find((c) => c.id === campaignId) ?? null;
      setCampaign(found);
      const cr = [...active, ...history].find((p) => p.campaign_id === campaignId) ?? null;
      setParticipation(cr);
      setSubmissionText(cr?.submission_text ?? "");
      setFileUrls(cr?.submission_file_urls ?? []);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load this campaign.");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaignId]);

  async function handleApply() {
    setPending(true);
    setError(null);
    try {
      await api.post(`/campaigns/${campaignId}/apply`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not apply.");
    } finally {
      setPending(false);
    }
  }

  async function handleAccept() {
    setPending(true);
    setError(null);
    try {
      // ftc_disclosure_accepted only ever becomes true from this
      // explicit checkbox click -- never pre-checked, never set
      // programmatically elsewhere (Section 9 non-negotiable).
      await api.post(`/campaigns/${campaignId}/accept`, { ftc_disclosure_accepted: ftcAccepted });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not accept.");
    } finally {
      setPending(false);
    }
  }

  async function handleDecline() {
    setPending(true);
    setError(null);
    try {
      await api.post(`/campaigns/${campaignId}/decline`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not decline.");
    } finally {
      setPending(false);
    }
  }

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
      const uploadedUrls = [...fileUrls];
      for (const file of files) {
        const form = new FormData();
        form.append("file", file);
        const result = await api.postForm<{ url: string; storage_key: string }>(
          `/campaigns/${campaignId}/submission-files`,
          form
        );
        uploadedUrls.push(result.url);
      }
      setFileUrls(uploadedUrls);
      setFiles([]);

      await api.post(`/campaigns/${campaignId}/submit`, {
        submission_text: submissionText,
        submission_file_urls: uploadedUrls,
      });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not submit.");
    } finally {
      setPending(false);
    }
  }

  if (!campaign && !participation && !error) {
    return (
      <main className="flex min-h-screen items-center justify-center p-6">
        <p className="text-sm text-muted-foreground">Loading...</p>
      </main>
    );
  }

  const title = campaign?.title ?? "Campaign";

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col gap-5 p-4 pb-16">
      <button onClick={() => router.push("/rep")} className="text-left text-sm font-medium underline">
        Back to dashboard
      </button>

      <div>
        <h1 className="text-xl font-semibold">{title}</h1>
        {campaign ? <p className="text-sm text-muted-foreground">{campaign.product_name}</p> : null}
      </div>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      {campaign ? (
        <section className="flex flex-col gap-2 rounded-lg border border-border p-3">
          <div>
            <p className="text-xs font-medium text-muted-foreground">Goal</p>
            <p className="text-sm">{campaign.campaign_goal}</p>
          </div>
          <div>
            <p className="text-xs font-medium text-muted-foreground">Deliverables</p>
            <p className="text-sm">{campaign.deliverables_description}</p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {campaign.target_categories.map((c) => (
              <Badge key={c} variant="outline">
                {c}
              </Badge>
            ))}
          </div>
          <div className="flex items-center justify-between pt-1">
            <p className="text-xs font-medium text-muted-foreground">Payout</p>
            <p className="text-base font-semibold">{money(campaign.payout_per_rep_cents)}</p>
          </div>
        </section>
      ) : null}

      {!participation && campaign ? (
        <Button onClick={handleApply} disabled={pending} className="h-11 w-full">
          {pending ? "Applying..." : "Apply to this campaign"}
        </Button>
      ) : null}

      {participation ? (
        <ParticipationSection
          participation={participation}
          ftcAccepted={ftcAccepted}
          setFtcAccepted={setFtcAccepted}
          onAccept={handleAccept}
          onDecline={handleDecline}
          onWithdrawn={load}
          pending={pending}
        />
      ) : null}

      {participation && (participation.status === "accepted" || participation.status === "revision_requested") ? (
        <section className="flex flex-col gap-3 rounded-lg border border-border p-3">
          <h2 className="text-sm font-semibold">Submit your work</h2>
          {participation.revision_note ? (
            <p className="rounded-md bg-amber-500/10 p-2 text-sm text-amber-700 dark:text-amber-400">
              Revision requested: {participation.revision_note}
            </p>
          ) : null}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="submissionText">Description</Label>
            <Textarea
              id="submissionText"
              rows={4}
              value={submissionText}
              onChange={(e) => setSubmissionText(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="files">Photo or video proof</Label>
            <input
              id="files"
              type="file"
              multiple
              accept="image/jpeg,image/png,image/webp,image/heic,video/mp4,video/quicktime"
              onChange={handleFileSelect}
              className="min-h-11 text-sm"
            />
            <p className="text-xs text-muted-foreground">JPEG, PNG, WEBP, HEIC, MP4, or MOV. Up to 25MB each.</p>
            {(fileUrls.length > 0 || files.length > 0) && (
              <p className="text-xs text-muted-foreground">
                {fileUrls.length + files.length} file(s) attached
              </p>
            )}
          </div>
          <Button
            onClick={handleSubmit}
            disabled={pending || !participation.ftc_disclosure_accepted}
            className="h-11 w-full"
          >
            {pending ? "Submitting..." : "Submit"}
          </Button>
          {!participation.ftc_disclosure_accepted ? (
            <p className="text-xs text-destructive">
              You must accept the FTC sponsorship disclosure before submitting.
            </p>
          ) : null}
        </section>
      ) : null}

      {participation && ["submitted", "under_review", "confirmed", "paid"].includes(participation.status) ? (
        <StatusTracker status={participation.status} />
      ) : null}
    </main>
  );
}

function ParticipationSection({
  participation,
  ftcAccepted,
  setFtcAccepted,
  onAccept,
  onDecline,
  onWithdrawn,
  pending,
}: {
  participation: CampaignParticipation;
  ftcAccepted: boolean;
  setFtcAccepted: (v: boolean) => void;
  onAccept: () => void;
  onDecline: () => void;
  onWithdrawn: () => void;
  pending: boolean;
}) {
  if (participation.parent_approval_status === "pending") {
    return (
      <section className="flex flex-col gap-2 rounded-lg border border-amber-500/30 bg-amber-500/5 p-3">
        <p className="text-sm font-medium text-amber-700 dark:text-amber-400">
          Waiting on a parent&apos;s approval
        </p>
        {participation.parent_approval_deadline ? (
          <Countdown deadline={participation.parent_approval_deadline} />
        ) : null}
      </section>
    );
  }

  if (participation.parent_approval_status === "blocked") {
    return (
      <section className="flex flex-col gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3">
        <p className="text-sm font-medium text-destructive">Your parent has blocked this campaign.</p>
      </section>
    );
  }

  if (participation.status === "applied" || participation.status === "invited") {
    return (
      <section className="flex flex-col gap-3 rounded-lg border border-border p-3">
        <div className="flex items-start gap-3">
          <Checkbox
            id="ftc"
            checked={ftcAccepted}
            onCheckedChange={(checked) => setFtcAccepted(checked === true)}
          />
          <Label htmlFor="ftc" className="flex-col items-start gap-1 font-normal">
            <span className="font-medium">FTC sponsorship disclosure</span>
            <span className="text-xs text-muted-foreground">
              I understand I must disclose that this is a paid partnership when I post about it.
            </span>
          </Label>
        </div>
        {participation.parent_approval_deadline ? (
          <Countdown deadline={participation.parent_approval_deadline} />
        ) : null}
        <div className="flex gap-2">
          <Button onClick={onAccept} disabled={pending || !ftcAccepted} className="h-11 flex-1">
            Accept
          </Button>
          <Button onClick={onDecline} disabled={pending} variant="outline" className="h-11 flex-1">
            Decline
          </Button>
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-border p-3">
      <WithdrawButton campaignId={participation.campaign_id} onWithdrawn={onWithdrawn} />
    </section>
  );
}

function StatusTracker({ status }: { status: string }) {
  const currentIndex = STATUS_STEPS.indexOf(status);
  return (
    <section className="flex flex-col gap-2 rounded-lg border border-border p-3">
      <h2 className="text-sm font-semibold">Status</h2>
      <div className="flex items-center justify-between">
        {STATUS_STEPS.map((step, i) => (
          <div key={step} className="flex flex-1 flex-col items-center gap-1">
            <div
              className={`size-3 rounded-full ${i <= currentIndex ? "bg-primary" : "bg-muted"}`}
            />
            <span className="text-center text-[0.65rem] text-muted-foreground">
              {step.replace("_", " ")}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
