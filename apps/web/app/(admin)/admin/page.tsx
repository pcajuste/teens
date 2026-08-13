"use client";

import { useEffect, useState } from "react";
import { AdminShell } from "@/components/admin/admin-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import type { AdminParentSuspendedRep, AdminQueueEntry } from "@/lib/types";

type AccountType = "brand" | "recruiter";

function QueueSection({ type, title }: { type: AccountType; title: string }) {
  const [entries, setEntries] = useState<AdminQueueEntry[] | null>(null);
  const [rejecting, setRejecting] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function load() {
    const rows = await api.get<AdminQueueEntry[]>(`/admin/queue/${type}s`);
    setEntries(rows);
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [type]);

  async function approve(userId: string) {
    setError(null);
    try {
      await api.post(`/admin/approve/${type}/${userId}`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not approve.");
    }
  }

  async function reject(userId: string) {
    if (!reason.trim()) return;
    setError(null);
    try {
      await api.post(`/admin/reject/${type}/${userId}`, { reason });
      setRejecting(null);
      setReason("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reject.");
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        {entries === null ? (
          <Skeleton className="h-20 w-full" />
        ) : entries.length === 0 ? (
          <EmptyState
            title="Nothing pending"
            description={`No ${type}s awaiting admin approval.`}
          />
        ) : (
          entries.map((entry) => (
            <div
              key={entry.user_id}
              className="rounded-lg border border-border p-3"
            >
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-medium">{entry.display_name}</p>
                  <p className="text-xs text-muted-foreground">{entry.email}</p>
                </div>
                <Badge variant="warning">
                  {entry.pending_reason.replace(/_/g, " ")}
                </Badge>
              </div>
              {rejecting === entry.user_id ? (
                <div className="mt-3 flex flex-col gap-2">
                  <Textarea
                    placeholder="Reason for rejection (required, emailed to applicant)"
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                  />
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="destructive"
                      disabled={!reason.trim()}
                      onClick={() => reject(entry.user_id)}
                    >
                      Confirm reject
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setRejecting(null);
                        setReason("");
                      }}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="mt-3 flex gap-2">
                  <Button size="sm" onClick={() => approve(entry.user_id)}>
                    Approve
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setRejecting(entry.user_id)}
                  >
                    Reject
                  </Button>
                </div>
              )}
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

function RepConsentQueue() {
  const [entries, setEntries] = useState<AdminQueueEntry[] | null>(null);

  useEffect(() => {
    api.get<AdminQueueEntry[]>("/admin/queue/talents").then(setEntries);
  }, []);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Talents awaiting parent consent</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="mb-3 text-xs text-muted-foreground">
          Talents never require admin approval -- this is visibility only into
          who&apos;s waiting on the parental double opt-in.
        </p>
        {entries === null ? (
          <Skeleton className="h-16 w-full" />
        ) : entries.length === 0 ? (
          <EmptyState
            title="No talents waiting"
            description="Every under-16 signup has been resolved by their parent."
          />
        ) : (
          <ul className="flex flex-col gap-2">
            {entries.map((e) => (
              <li
                key={e.user_id}
                className="rounded-lg border border-border p-3 text-sm"
              >
                {e.display_name} --{" "}
                <span className="text-muted-foreground">{e.email}</span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function ParentSuspensionQueue() {
  const [entries, setEntries] = useState<AdminParentSuspendedRep[] | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);

  async function load() {
    const rows = await api.get<AdminParentSuspendedRep[]>(
      "/admin/parent-suspensions",
    );
    setEntries(rows);
  }

  useEffect(() => {
    load();
  }, []);

  async function reverse(repId: string) {
    setError(null);
    try {
      await api.post(`/admin/parent-suspensions/${repId}/reverse`);
      await load();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not reverse suspension.",
      );
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Parent-suspended accounts</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <p className="text-xs text-muted-foreground">
          Only suspensions a parent initiated can be reversed here -- an
          admin-initiated suspension can only be lifted by admin editing it
          directly.
        </p>
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        {entries === null ? (
          <Skeleton className="h-16 w-full" />
        ) : entries.length === 0 ? (
          <EmptyState title="No parent suspensions" />
        ) : (
          entries.map((e) => (
            <div
              key={e.talent_id}
              className="flex items-center justify-between rounded-lg border border-border p-3"
            >
              <div>
                <p className="text-sm font-medium">{e.display_name}</p>
                <p className="text-xs text-muted-foreground">
                  Suspended{" "}
                  {new Date(e.suspended_by_parent_at).toLocaleString()}
                </p>
              </div>
              <Button
                size="sm"
                variant="outline"
                onClick={() => reverse(e.talent_id)}
              >
                Reverse suspension
              </Button>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

export default function AdminQueuesPage() {
  return (
    <AdminShell title="Approval queues">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <QueueSection type="brand" title="Brands awaiting approval" />
        <QueueSection type="recruiter" title="Recruiters awaiting approval" />
        <RepConsentQueue />
        <ParentSuspensionQueue />
      </div>
    </AdminShell>
  );
}
