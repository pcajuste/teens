"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { TalentShell } from "@/components/talent/talent-shell";
import { api, ApiError } from "@/lib/api";
import type { Internship, InternshipApplication } from "@/lib/types";

const COMPENSATION_LABEL: Record<string, string> = {
  paid: "Paid",
  stipend: "Stipend",
  unpaid: "Unpaid",
};

export default function TalentInternshipsPage() {
  const [internships, setInternships] = useState<Internship[] | null>(null);
  const [applications, setApplications] = useState<InternshipApplication[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [applyingTo, setApplyingTo] = useState<string | null>(null);
  const [responseText, setResponseText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function load() {
    Promise.all([
      api.get<Internship[]>("/talents/internships/available"),
      api.get<InternshipApplication[]>("/talents/internships/applications"),
    ])
      .then(([available, mine]) => {
        setInternships(available);
        setApplications(mine);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load internships."));
  }

  useEffect(load, []);

  const appliedIds = new Set(applications.map((a) => a.internship_id));

  async function submitApplication(internshipId: string) {
    setSubmitting(true);
    setError(null);
    try {
      await api.post(`/talents/internships/${internshipId}/apply`, { response_text: responseText });
      setApplyingTo(null);
      setResponseText("");
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not submit your application.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <TalentShell title="Internships & Apprenticeships">
      {error ? <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p> : null}

      {internships === null ? (
        <Skeleton className="h-28 w-full" />
      ) : internships.length === 0 ? (
        <EmptyState title="No internships open right now" description="Check back soon." />
      ) : (
        <div className="flex flex-col gap-3">
          {internships.map((i) => {
            const applied = appliedIds.has(i.id);
            return (
              <Card key={i.id}>
                <CardContent className="flex flex-col gap-2">
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-semibold">{i.role_title}</p>
                    <Badge variant="earned">{COMPENSATION_LABEL[i.compensation_type]}</Badge>
                  </div>
                  <p className="text-sm text-text-2">{i.description}</p>
                  <p className="text-sm text-text-2">{i.time_commitment}</p>
                  <p className="text-sm text-text-2">{i.requirements_text}</p>
                  <p className="text-xs text-text-3">Deadline {new Date(i.deadline).toLocaleDateString()}</p>

                  {applied ? (
                    <Badge variant="done" className="w-fit">
                      Applied
                    </Badge>
                  ) : applyingTo === i.id ? (
                    <div className="flex flex-col gap-2">
                      <Textarea
                        rows={4}
                        placeholder="Your response..."
                        value={responseText}
                        onChange={(e) => setResponseText(e.target.value)}
                      />
                      <div className="flex gap-2">
                        <Button size="sm" disabled={submitting} onClick={() => submitApplication(i.id)}>
                          {submitting ? "Submitting..." : "Submit application"}
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => setApplyingTo(null)}>
                          Cancel
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <Button size="sm" className="w-fit" onClick={() => setApplyingTo(i.id)}>
                      Apply
                    </Button>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </TalentShell>
  );
}
