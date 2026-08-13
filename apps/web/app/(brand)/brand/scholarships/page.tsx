"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { BrandShell } from "@/components/brand/brand-shell";
import { api, ApiError } from "@/lib/api";
import type { ModerationStatus, Scholarship, ScholarshipApplicationBrandView } from "@/lib/types";

const MODERATION_VARIANT: Record<ModerationStatus, "pending" | "active" | "done"> = {
  draft: "pending",
  pending_review: "pending",
  approved: "done",
  rejected: "pending",
};

const MODERATION_LABEL: Record<ModerationStatus, string> = {
  draft: "Draft",
  pending_review: "In review",
  approved: "Approved",
  rejected: "Rejected",
};

const EMPTY_FORM = {
  title: "",
  award_amount_cents: "",
  number_of_awards: "1",
  application_requirements: "",
  why_text: "",
  deadline: "",
};

export default function BrandScholarshipsPage() {
  const [scholarships, setScholarships] = useState<Scholarship[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [creating, setCreating] = useState(false);
  const [applicationsFor, setApplicationsFor] = useState<string | null>(null);
  const [applications, setApplications] = useState<ScholarshipApplicationBrandView[] | null>(null);

  function load() {
    api
      .get<Scholarship[]>("/brands/scholarships")
      .then(setScholarships)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load your scholarships."));
  }

  useEffect(load, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setError(null);
    try {
      await api.post("/brands/scholarships", {
        title: form.title,
        award_amount_cents: Math.round(parseFloat(form.award_amount_cents) * 100),
        number_of_awards: parseInt(form.number_of_awards, 10),
        eligibility_criteria: [],
        application_requirements: form.application_requirements,
        why_text: form.why_text,
        deadline: new Date(form.deadline).toISOString(),
      });
      setForm(EMPTY_FORM);
      load();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not create this scholarship.",
      );
    } finally {
      setCreating(false);
    }
  }

  async function submitForReview(id: string) {
    await api.post(`/brands/scholarships/${id}/submit-for-review`);
    load();
  }

  async function activate(id: string) {
    try {
      await api.post(`/brands/scholarships/${id}/activate`);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not activate this scholarship.");
    }
  }

  async function viewApplications(id: string) {
    setApplicationsFor(id);
    const rows = await api.get<ScholarshipApplicationBrandView[]>(`/brands/scholarships/${id}/applications`);
    setApplications(rows);
  }

  async function award(scholarshipId: string, applicationId: string) {
    await api.post(`/brands/scholarships/${scholarshipId}/applications/${applicationId}/award`);
    viewApplications(scholarshipId);
  }

  async function decline(scholarshipId: string, applicationId: string) {
    await api.post(`/brands/scholarships/${scholarshipId}/applications/${applicationId}/decline`);
    viewApplications(scholarshipId);
  }

  return (
    <BrandShell title="Scholarships">
      {error ? <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p> : null}

      <Card>
        <CardContent>
          <form onSubmit={handleCreate} className="flex flex-col gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="title">Title</Label>
              <Input id="title" required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="award">Award amount ($)</Label>
                <Input
                  id="award"
                  type="number"
                  required
                  min={1}
                  value={form.award_amount_cents}
                  onChange={(e) => setForm({ ...form, award_amount_cents: e.target.value })}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="numAwards"># of awards</Label>
                <Input
                  id="numAwards"
                  type="number"
                  required
                  min={1}
                  value={form.number_of_awards}
                  onChange={(e) => setForm({ ...form, number_of_awards: e.target.value })}
                />
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="requirements">Application requirements</Label>
              <Textarea
                id="requirements"
                required
                rows={2}
                value={form.application_requirements}
                onChange={(e) => setForm({ ...form, application_requirements: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="why">Why we're offering this (max 150 words)</Label>
              <Textarea
                id="why"
                required
                rows={3}
                value={form.why_text}
                onChange={(e) => setForm({ ...form, why_text: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="deadline">Deadline</Label>
              <Input
                id="deadline"
                type="date"
                required
                value={form.deadline}
                onChange={(e) => setForm({ ...form, deadline: e.target.value })}
              />
            </div>
            <Button type="submit" disabled={creating} className="w-fit">
              {creating ? "Creating..." : "Create scholarship"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {scholarships === null ? (
        <Skeleton className="h-28 w-full" />
      ) : scholarships.length === 0 ? (
        <EmptyState title="No scholarships yet" description="Create your first scholarship above." />
      ) : (
        <div className="flex flex-col gap-3">
          {scholarships.map((s) => (
            <Card key={s.id}>
              <CardContent className="flex flex-col gap-2">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-semibold">{s.title}</p>
                  <div className="flex gap-2">
                    <Badge variant={MODERATION_VARIANT[s.moderation_status]}>{MODERATION_LABEL[s.moderation_status]}</Badge>
                    <Badge variant={s.status === "active" ? "active" : "pending"}>{s.status}</Badge>
                  </div>
                </div>
                <p className="text-sm text-text-2">
                  ${(s.award_amount_cents / 100).toLocaleString()} x {s.number_of_awards} awards -- deadline{" "}
                  {new Date(s.deadline).toLocaleDateString()}
                </p>
                {s.rejection_reason ? <p className="text-sm text-danger">Rejected: {s.rejection_reason}</p> : null}
                <div className="flex flex-wrap gap-2">
                  {s.moderation_status === "draft" ? (
                    <Button size="sm" variant="outline" onClick={() => submitForReview(s.id)}>
                      Submit for review
                    </Button>
                  ) : null}
                  {s.moderation_status === "approved" && s.status === "draft" ? (
                    <Button size="sm" onClick={() => activate(s.id)}>
                      Activate
                    </Button>
                  ) : null}
                  <Button size="sm" variant="ghost" onClick={() => viewApplications(s.id)}>
                    Applications
                  </Button>
                </div>

                {applicationsFor === s.id && applications ? (
                  <div className="mt-2 flex flex-col gap-2 border-t border-border-muted pt-2">
                    {applications.length === 0 ? (
                      <p className="text-sm text-text-2">No applications yet.</p>
                    ) : (
                      applications.map((a) => (
                        <div key={a.id} className="flex items-center justify-between gap-2 text-sm">
                          <span className="text-text-2">{a.response_text.slice(0, 80)}</span>
                          <div className="flex items-center gap-2">
                            <Badge variant="pending">{a.status}</Badge>
                            {a.status === "submitted" ? (
                              <>
                                <Button size="sm" onClick={() => award(s.id, a.id)}>
                                  Award
                                </Button>
                                <Button size="sm" variant="outline" onClick={() => decline(s.id, a.id)}>
                                  Decline
                                </Button>
                              </>
                            ) : null}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                ) : null}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </BrandShell>
  );
}
