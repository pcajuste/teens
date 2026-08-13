"use client";

import { useEffect, useState } from "react";
import { AdminShell } from "@/components/admin/admin-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import type { AdminSafetyReport } from "@/lib/types";

/** Highest-priority admin lane (Build Prompt 13 deliverable 7's
 * acceptance criterion: "visually distinct and clearly highest-
 * priority"). Deliberately its own page with a red banner and its own
 * standalone nav entry in AdminShell -- never folded into the general
 * campaign-oversight table -- so a report can never be scrolled past
 * or mistaken for a routine dispute. */
export default function AdminSafetyPage() {
  const [reports, setReports] = useState<AdminSafetyReport[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [resolvingId, setResolvingId] = useState<string | null>(null);
  const [note, setNote] = useState("");

  async function load() {
    const rows = await api.get<AdminSafetyReport[]>(
      "/admin/safety-reports?open_only=true",
    );
    setReports(rows);
  }

  useEffect(() => {
    load();
  }, []);

  async function resolve(id: string, status: "resolved" | "dismissed") {
    setError(null);
    try {
      await api.post(`/admin/safety-reports/${id}/resolve`, {
        status,
        resolution_note: note || null,
      });
      setResolvingId(null);
      setNote("");
      await load();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not resolve report.",
      );
    }
  }

  return (
    <AdminShell>
      <div className="rounded-xl border-2 border-destructive bg-destructive/10 px-4 py-3">
        <p className="text-sm font-semibold text-destructive">
          Safety report queue -- highest priority
        </p>
        <p className="text-xs text-destructive/80">
          Filed via the Talent portal&apos;s one-tap report mechanism. Review
          and resolve before working campaign disputes or payment issues.
        </p>
      </div>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {reports === null ? (
        <Skeleton className="h-32 w-full" />
      ) : reports.length === 0 ? (
        <EmptyState
          title="No open safety reports"
          description="The queue is clear."
        />
      ) : (
        <div className="flex flex-col gap-3">
          {reports.map((r) => (
            <Card key={r.id} className="border-destructive/40">
              <CardContent className="flex flex-col gap-2 p-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium">
                      {r.reporter_display_name}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(r.created_at).toLocaleString()} -- {r.reason}
                    </p>
                  </div>
                  <Badge variant="destructive">open</Badge>
                </div>
                {r.description ? (
                  <p className="text-sm">{r.description}</p>
                ) : null}

                {resolvingId === r.id ? (
                  <div className="flex flex-col gap-2">
                    <Textarea
                      placeholder="Resolution note (optional)"
                      value={note}
                      onChange={(e) => setNote(e.target.value)}
                    />
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        onClick={() => resolve(r.id, "resolved")}
                      >
                        Mark resolved
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => resolve(r.id, "dismissed")}
                      >
                        Dismiss
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          setResolvingId(null);
                          setNote("");
                        }}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  <Button
                    size="sm"
                    variant="danger"
                    onClick={() => setResolvingId(r.id)}
                  >
                    Review
                  </Button>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </AdminShell>
  );
}
