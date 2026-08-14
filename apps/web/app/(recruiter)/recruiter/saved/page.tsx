"use client";

import { useEffect, useMemo, useState } from "react";
import { RecruiterShell } from "@/components/recruiter/recruiter-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import type { RecruiterSavedProfile } from "@/lib/types";

type Track = "brand" | "athletics";

export default function RecruiterSavedPage() {
  const [track, setTrack] = useState<Track>("brand");
  const [saved, setSaved] = useState<RecruiterSavedProfile[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [renaming, setRenaming] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

  useEffect(() => {
    load(track);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [track]);

  async function load(forTrack: Track = track) {
    setLoading(true);
    setError(null);
    try {
      const rows = await api.get<RecruiterSavedProfile[]>(
        `/recruiters/saved?track=${forTrack}`,
      );
      setSaved(rows);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not load saved profiles.",
      );
    } finally {
      setLoading(false);
    }
  }

  const lists = useMemo(() => {
    const map = new Map<string, RecruiterSavedProfile[]>();
    for (const row of saved ?? []) {
      const key = row.list_name ?? "Default";
      map.set(key, [...(map.get(key) ?? []), row]);
    }
    return map;
  }, [saved]);

  async function handleUnsave(repId: string) {
    setNotice(null);
    try {
      await api.delete(`/recruiters/talents/${repId}/save`);
      setSaved((prev) =>
        prev ? prev.filter((r) => r.talent_id !== repId) : prev,
      );
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not remove this talent.",
      );
    }
  }

  async function handleMoveToList(repId: string, listName: string) {
    setNotice(null);
    try {
      const updated = await api.post<RecruiterSavedProfile>(
        `/recruiters/talents/${repId}/save`,
        { list_name: listName },
      );
      setSaved((prev) =>
        prev ? prev.map((r) => (r.talent_id === repId ? updated : r)) : prev,
      );
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not move this talent.",
      );
    }
  }

  function startRename(listName: string) {
    setRenaming(listName);
    setRenameValue(listName);
    setNotice(null);
  }

  async function submitRename(oldName: string) {
    const newName = renameValue.trim();
    if (!newName || newName === oldName) {
      setRenaming(null);
      return;
    }
    // No dedicated "rename list" endpoint exists -- a list is just a label
    // (list_name) on each saved-profile row, not a separate resource, per
    // recruiter_saved_profiles_repository.py. Renaming re-saves every talent
    // currently in that list under the new label.
    const rows = lists.get(oldName) ?? [];
    setError(null);
    try {
      await Promise.all(
        rows.map((r) =>
          api.post(`/recruiters/talents/${r.talent_id}/save`, {
            list_name: newName,
          }),
        ),
      );
      setNotice(`Renamed "${oldName}" to "${newName}".`);
      setRenaming(null);
      await load();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not rename this list.",
      );
    }
  }

  return (
    <RecruiterShell title="Saved profiles">
      <div className="flex gap-2 border-b border-border-muted">
        <button
          type="button"
          onClick={() => setTrack("brand")}
          className={`px-3 py-2 text-sm font-medium ${
            track === "brand"
              ? "border-b-2 border-primary text-foreground"
              : "text-text-2 hover:text-foreground"
          }`}
        >
          Saved
        </button>
        <button
          type="button"
          onClick={() => setTrack("athletics")}
          className={`px-3 py-2 text-sm font-medium ${
            track === "athletics"
              ? "border-b-2 border-primary text-foreground"
              : "text-text-2 hover:text-foreground"
          }`}
        >
          Athletes I&rsquo;m tracking
        </button>
      </div>
      {error ? (
        <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      ) : null}
      {notice ? (
        <p className="rounded-lg bg-success/15 px-3 py-2 text-sm text-success">
          {notice}
        </p>
      ) : null}

      {loading ? (
        <div className="flex flex-col gap-4">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : !saved || saved.length === 0 ? (
        <EmptyState
          title="No saved talents yet"
          description="Save talents from search results to organize them into lists for later outreach."
          action={
            <a href="/recruiter">
              <Button type="button" size="sm">
                Go to search
              </Button>
            </a>
          }
        />
      ) : (
        <div className="flex flex-col gap-6">
          {Array.from(lists.entries()).map(([listName, rows]) => (
            <Card key={listName}>
              <CardContent>
                <div className="flex items-center justify-between gap-2">
                  {renaming === listName ? (
                    <div className="flex items-center gap-2">
                      <Input
                        value={renameValue}
                        onChange={(e) => setRenameValue(e.target.value)}
                        className="h-8 w-48"
                      />
                      <Button
                        type="button"
                        size="sm"
                        onClick={() => submitRename(listName)}
                      >
                        Save
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => setRenaming(null)}
                      >
                        Cancel
                      </Button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <h2 className="text-base font-semibold">{listName}</h2>
                      <Badge variant="secondary">{rows.length}</Badge>
                    </div>
                  )}
                  {renaming !== listName ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() => startRename(listName)}
                    >
                      Rename list
                    </Button>
                  ) : null}
                </div>

                <div className="mt-3 flex flex-col divide-y divide-border">
                  {rows.map((row: RecruiterSavedProfile) => (
                    <div
                      key={row.talent_id}
                      className="flex flex-wrap items-center justify-between gap-2 py-2"
                    >
                      <span className="text-sm text-text-2">
                       talent #{row.talent_id.slice(0, 8)}
                      </span>
                      <div className="flex items-center gap-2">
                        <select
                          className="h-8 rounded-md border border-input bg-white/4 px-2 text-xs"
                          value={listName}
                          onChange={(e) =>
                            handleMoveToList(row.talent_id, e.target.value)
                          }
                        >
                          {Array.from(
                            new Set([...Array.from(lists.keys()), listName]),
                          ).map((name) => (
                            <option key={name} value={name}>
                              {name}
                            </option>
                          ))}
                          <option value="Default">Default</option>
                        </select>
                        <Button
                          type="button"
                          size="sm"
                          variant="destructive"
                          onClick={() => handleUnsave(row.talent_id)}
                        >
                          Remove
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </RecruiterShell>
  );
}
