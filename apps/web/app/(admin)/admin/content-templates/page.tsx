"use client";

import { useEffect, useState } from "react";
import { AdminShell } from "@/components/admin/admin-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import type { Challenge, InsightCampaign, Internship, Scholarship } from "@/lib/types";

type QueueType = "scholarships" | "internships" | "challenges" | "insight-campaigns";

const QUEUE_LABEL: Record<QueueType, string> = {
  scholarships: "Scholarships",
  internships: "Internships & Apprenticeships",
  challenges: "Skills Challenges",
  "insight-campaigns": "Insight & Feedback",
};

export default function AdminContentTemplatesPage() {
  const [scholarships, setScholarships] = useState<Scholarship[] | null>(null);
  const [internships, setInternships] = useState<Internship[] | null>(null);
  const [challenges, setChallenges] = useState<Challenge[] | null>(null);
  const [insightCampaigns, setInsightCampaigns] = useState<InsightCampaign[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  function load() {
    api
      .get<Scholarship[]>("/admin/content-templates/scholarships/queue")
      .then(setScholarships)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load the review queue."));
    api.get<Internship[]>("/admin/content-templates/internships/queue").then(setInternships).catch(() => undefined);
    api.get<Challenge[]>("/admin/content-templates/challenges/queue").then(setChallenges).catch(() => undefined);
    api
      .get<InsightCampaign[]>("/admin/content-templates/insight-campaigns/queue")
      .then(setInsightCampaigns)
      .catch(() => undefined);
  }

  useEffect(load, []);

  async function approve(type: QueueType, id: string) {
    await api.post(`/admin/content-templates/${type}/${id}/approve`);
    load();
  }

  async function reject(type: QueueType, id: string) {
    await api.post(`/admin/content-templates/${type}/${id}/reject`, { reason: rejectReason || "Does not meet content guidelines." });
    setRejectingId(null);
    setRejectReason("");
    load();
  }

  const totalPending =
    (scholarships?.length ?? 0) + (internships?.length ?? 0) + (challenges?.length ?? 0) + (insightCampaigns?.length ?? 0);

  return (
    <AdminShell title="Content review" action={<Badge variant={totalPending > 0 ? "pending" : "done"}>{totalPending} pending</Badge>}>
      {error ? <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p> : null}

      <QueueSection
        title={QUEUE_LABEL.scholarships}
        items={scholarships}
        renderTitle={(s) => s.title}
        renderMeta={(s) => `$${(s.award_amount_cents / 100).toLocaleString()} x ${s.number_of_awards} -- why: "${s.why_text}"`}
        onApprove={(id) => approve("scholarships", id)}
        onReject={(id) => setRejectingId(id)}
        rejectingId={rejectingId}
        rejectReason={rejectReason}
        setRejectReason={setRejectReason}
        onConfirmReject={(id) => reject("scholarships", id)}
        onCancelReject={() => setRejectingId(null)}
      />

      <QueueSection
        title={QUEUE_LABEL.internships}
        items={internships}
        renderTitle={(i) => i.role_title}
        renderMeta={(i) =>
          `${i.time_commitment} -- ${i.compensation_type} -- why: "${i.why_text}"${
            i.compensation_type !== "paid" ? ` -- compensation rationale: "${i.compensation_why}"` : ""
          }`
        }
        onApprove={(id) => approve("internships", id)}
        onReject={(id) => setRejectingId(id)}
        rejectingId={rejectingId}
        rejectReason={rejectReason}
        setRejectReason={setRejectReason}
        onConfirmReject={(id) => reject("internships", id)}
        onCancelReject={() => setRejectingId(null)}
      />

      <QueueSection
        title={QUEUE_LABEL.challenges}
        items={challenges}
        renderTitle={(c) => c.title}
        renderMeta={(c) => `why: "${c.why_text ?? "(none provided)"}"`}
        onApprove={(id) => approve("challenges", id)}
        onReject={(id) => setRejectingId(id)}
        rejectingId={rejectingId}
        rejectReason={rejectReason}
        setRejectReason={setRejectReason}
        onConfirmReject={(id) => reject("challenges", id)}
        onCancelReject={() => setRejectingId(null)}
      />

      <QueueSection
        title={QUEUE_LABEL["insight-campaigns"]}
        items={insightCampaigns}
        renderTitle={(c) => c.title}
        renderMeta={(c) => `panel of ${c.panel_size} -- ${c.business_question}`}
        onApprove={(id) => approve("insight-campaigns", id)}
        onReject={(id) => setRejectingId(id)}
        rejectingId={rejectingId}
        rejectReason={rejectReason}
        setRejectReason={setRejectReason}
        onConfirmReject={(id) => reject("insight-campaigns", id)}
        onCancelReject={() => setRejectingId(null)}
      />
    </AdminShell>
  );
}

function QueueSection<T extends { id: string }>({
  title,
  items,
  renderTitle,
  renderMeta,
  onApprove,
  onReject,
  rejectingId,
  rejectReason,
  setRejectReason,
  onConfirmReject,
  onCancelReject,
}: {
  title: string;
  items: T[] | null;
  renderTitle: (item: T) => string;
  renderMeta: (item: T) => string;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  rejectingId: string | null;
  rejectReason: string;
  setRejectReason: (v: string) => void;
  onConfirmReject: (id: string) => void;
  onCancelReject: () => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm font-semibold text-text-3">{title}</p>
      {items === null ? (
        <Skeleton className="h-16 w-full" />
      ) : items.length === 0 ? (
        <p className="text-sm text-text-2">Nothing pending.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {items.map((item) => (
            <Card key={item.id}>
              <CardContent className="flex flex-col gap-2">
                <p className="font-medium">{renderTitle(item)}</p>
                <p className="text-sm text-text-2">{renderMeta(item)}</p>
                {rejectingId === item.id ? (
                  <div className="flex flex-col gap-2">
                    <input
                      className="rounded-md border border-border-muted bg-white/4 px-2 py-1 text-sm"
                      placeholder="Rejection reason"
                      value={rejectReason}
                      onChange={(e) => setRejectReason(e.target.value)}
                    />
                    <div className="flex gap-2">
                      <Button size="sm" variant="danger" onClick={() => onConfirmReject(item.id)}>
                        Confirm reject
                      </Button>
                      <Button size="sm" variant="ghost" onClick={onCancelReject}>
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex gap-2">
                    <Button size="sm" onClick={() => onApprove(item.id)}>
                      Approve
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => onReject(item.id)}>
                      Reject
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
