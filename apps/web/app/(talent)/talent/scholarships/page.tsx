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
import type { Scholarship, ScholarshipApplication } from "@/lib/types";

export default function TalentScholarshipsPage() {
  const [scholarships, setScholarships] = useState<Scholarship[] | null>(null);
  const [applications, setApplications] = useState<ScholarshipApplication[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [applyingTo, setApplyingTo] = useState<string | null>(null);
  const [responseText, setResponseText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function load() {
    Promise.all([
      api.get<Scholarship[]>("/talents/scholarships/available"),
      api.get<ScholarshipApplication[]>("/talents/scholarships/applications"),
    ])
      .then(([available, mine]) => {
        setScholarships(available);
        setApplications(mine);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load scholarships."));
  }

  useEffect(load, []);

  const appliedIds = new Set(applications.map((a) => a.scholarship_id));

  async function submitApplication(scholarshipId: string) {
    setSubmitting(true);
    setError(null);
    try {
      await api.post(`/talents/scholarships/${scholarshipId}/apply`, { response_text: responseText });
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
    <TalentShell title="Scholarships">
      {error ? <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p> : null}

      {scholarships === null ? (
        <Skeleton className="h-28 w-full" />
      ) : scholarships.length === 0 ? (
        <EmptyState title="No scholarships open right now" description="Check back soon." />
      ) : (
        <div className="flex flex-col gap-3">
          {scholarships.map((s) => {
            const applied = appliedIds.has(s.id);
            return (
              <Card key={s.id}>
                <CardContent className="flex flex-col gap-2">
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-semibold">{s.title}</p>
                    <Badge variant="earned">${(s.award_amount_cents / 100).toLocaleString()}</Badge>
                  </div>
                  <p className="text-sm text-text-2">{s.why_text}</p>
                  <p className="text-sm text-text-2">{s.application_requirements}</p>
                  <p className="text-xs text-text-3">Deadline {new Date(s.deadline).toLocaleDateString()}</p>

                  {applied ? (
                    <Badge variant="done" className="w-fit">
                      Applied
                    </Badge>
                  ) : applyingTo === s.id ? (
                    <div className="flex flex-col gap-2">
                      <Textarea
                        rows={4}
                        placeholder="Your response..."
                        value={responseText}
                        onChange={(e) => setResponseText(e.target.value)}
                      />
                      <div className="flex gap-2">
                        <Button size="sm" disabled={submitting} onClick={() => submitApplication(s.id)}>
                          {submitting ? "Submitting..." : "Submit application"}
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => setApplyingTo(null)}>
                          Cancel
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <Button size="sm" className="w-fit" onClick={() => setApplyingTo(s.id)}>
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
