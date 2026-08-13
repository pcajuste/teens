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
import type { CompensationType, Internship, InternshipApplicationBrandView, ModerationStatus } from "@/lib/types";

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
  role_title: "",
  description: "",
  time_commitment: "",
  compensation_type: "paid" as CompensationType,
  compensation_why: "",
  requirements_text: "",
  application_process_text: "",
  why_text: "",
  deadline: "",
};

export default function BrandInternshipsPage() {
  const [internships, setInternships] = useState<Internship[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [creating, setCreating] = useState(false);
  const [applicationsFor, setApplicationsFor] = useState<string | null>(null);
  const [applications, setApplications] = useState<InternshipApplicationBrandView[] | null>(null);

  function load() {
    api
      .get<Internship[]>("/brands/internships")
      .then(setInternships)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load your internships."));
  }

  useEffect(load, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setError(null);
    try {
      await api.post("/brands/internships", {
        role_title: form.role_title,
        description: form.description,
        time_commitment: form.time_commitment,
        compensation_type: form.compensation_type,
        compensation_why: form.compensation_why,
        requirements_text: form.requirements_text,
        application_process_text: form.application_process_text,
        why_text: form.why_text,
        deadline: new Date(form.deadline).toISOString(),
      });
      setForm(EMPTY_FORM);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create this internship.");
    } finally {
      setCreating(false);
    }
  }

  async function submitForReview(id: string) {
    await api.post(`/brands/internships/${id}/submit-for-review`);
    load();
  }

  async function activate(id: string) {
    try {
      await api.post(`/brands/internships/${id}/activate`);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not activate this internship.");
    }
  }

  async function viewApplications(id: string) {
    setApplicationsFor(id);
    const rows = await api.get<InternshipApplicationBrandView[]>(`/brands/internships/${id}/applications`);
    setApplications(rows);
  }

  async function accept(internshipId: string, applicationId: string) {
    await api.post(`/brands/internships/${internshipId}/applications/${applicationId}/accept`);
    viewApplications(internshipId);
  }

  async function decline(internshipId: string, applicationId: string) {
    await api.post(`/brands/internships/${internshipId}/applications/${applicationId}/decline`);
    viewApplications(internshipId);
  }

  return (
    <BrandShell title="Internships & Apprenticeships">
      {error ? <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p> : null}

      <Card>
        <CardContent>
          <form onSubmit={handleCreate} className="flex flex-col gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="role_title">Role title</Label>
              <Input
                id="role_title"
                required
                value={form.role_title}
                onChange={(e) => setForm({ ...form, role_title: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="description">Description of the role</Label>
              <Textarea
                id="description"
                required
                rows={3}
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="time_commitment">Time commitment</Label>
                <Input
                  id="time_commitment"
                  required
                  placeholder="e.g. 8 hrs/week, 10 weeks"
                  value={form.time_commitment}
                  onChange={(e) => setForm({ ...form, time_commitment: e.target.value })}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="compensation_type">Compensation</Label>
                <select
                  id="compensation_type"
                  className="h-9 rounded-md border border-border-muted bg-surface-1 px-3 text-sm"
                  value={form.compensation_type}
                  onChange={(e) => setForm({ ...form, compensation_type: e.target.value as CompensationType })}
                >
                  <option value="paid">Paid</option>
                  <option value="stipend">Stipend</option>
                  <option value="unpaid">Unpaid</option>
                </select>
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="compensation_why">Why this compensation</Label>
              <Textarea
                id="compensation_why"
                required
                rows={2}
                value={form.compensation_why}
                onChange={(e) => setForm({ ...form, compensation_why: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="requirements_text">Requirements (age minimum, skills, etc.)</Label>
              <Textarea
                id="requirements_text"
                required
                rows={2}
                value={form.requirements_text}
                onChange={(e) => setForm({ ...form, requirements_text: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="application_process_text">Application process (must stay on-platform)</Label>
              <Textarea
                id="application_process_text"
                required
                rows={2}
                value={form.application_process_text}
                onChange={(e) => setForm({ ...form, application_process_text: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="why_text">Why we're offering this (max 150 words)</Label>
              <Textarea
                id="why_text"
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
              {creating ? "Creating..." : "Create internship"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {internships === null ? (
        <Skeleton className="h-28 w-full" />
      ) : internships.length === 0 ? (
        <EmptyState title="No internships yet" description="Create your first internship or apprenticeship above." />
      ) : (
        <div className="flex flex-col gap-3">
          {internships.map((i) => (
            <Card key={i.id}>
              <CardContent className="flex flex-col gap-2">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-semibold">{i.role_title}</p>
                  <div className="flex gap-2">
                    <Badge variant={MODERATION_VARIANT[i.moderation_status]}>{MODERATION_LABEL[i.moderation_status]}</Badge>
                    <Badge variant={i.status === "active" ? "active" : "pending"}>{i.status}</Badge>
                  </div>
                </div>
                <p className="text-sm text-text-2">
                  {i.time_commitment} -- {i.compensation_type} -- deadline {new Date(i.deadline).toLocaleDateString()}
                </p>
                {i.rejection_reason ? <p className="text-sm text-danger">Rejected: {i.rejection_reason}</p> : null}
                <div className="flex flex-wrap gap-2">
                  {i.moderation_status === "draft" ? (
                    <Button size="sm" variant="outline" onClick={() => submitForReview(i.id)}>
                      Submit for review
                    </Button>
                  ) : null}
                  {i.moderation_status === "approved" && i.status === "draft" ? (
                    <Button size="sm" onClick={() => activate(i.id)}>
                      Activate
                    </Button>
                  ) : null}
                  <Button size="sm" variant="ghost" onClick={() => viewApplications(i.id)}>
                    Applications
                  </Button>
                </div>

                {applicationsFor === i.id && applications ? (
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
                                <Button size="sm" onClick={() => accept(i.id, a.id)}>
                                  Accept
                                </Button>
                                <Button size="sm" variant="outline" onClick={() => decline(i.id, a.id)}>
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
