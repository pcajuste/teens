"use client";

import { useEffect, useState } from "react";
import { ParentShell } from "@/components/parent/parent-shell";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { parentApi, ParentApiError } from "@/lib/parent-api";
import { trackEvent } from "@/lib/analytics";
import { PARENT_FILTER_CATEGORIES } from "@/lib/parent-categories";
import type { ParentSettings } from "@/lib/parent-types";

export default function ParentFiltersPage() {
  const [settings, setSettings] = useState<ParentSettings | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    parentApi
      .get<ParentSettings>("/parent/settings")
      .then((res) => {
        setSettings(res);
        setSelected(new Set(res.values_filters));
      })
      .catch((err) => setError(err instanceof ParentApiError ? err.message : "Could not load settings."))
      .finally(() => setLoading(false));
  }, []);

  function toggle(value: string) {
    setSaved(false);
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const res = await parentApi.put<ParentSettings>("/parent/settings/values-filters", {
        values_filters: Array.from(selected),
      });
      setSettings(res);
      setSelected(new Set(res.values_filters));
      setSaved(true);
      trackEvent("parent_values_filter_updated", { filter_count: res.values_filters.length });
    } catch (err) {
      setError(err instanceof ParentApiError ? err.message : "Could not save your filters.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <ParentShell title="Values filters">
      <p className="text-sm text-muted-foreground">
        Block categories of campaigns your teen should never be offered. Blocked campaigns are filtered out
        before your teen ever sees them, and brands are never told why a category is blocked.
      </p>

      {error ? <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p> : null}

      {loading ? (
        <Skeleton className="h-64 w-full" />
      ) : settings ? (
        <Card className="p-5">
          <div className="flex flex-col gap-4">
            {PARENT_FILTER_CATEGORIES.map((cat) => (
              <div key={cat.value} className="flex items-start gap-3">
                <Checkbox
                  id={`cat-${cat.value}`}
                  checked={selected.has(cat.value)}
                  onCheckedChange={() => toggle(cat.value)}
                />
                <Label htmlFor={`cat-${cat.value}`} className="flex flex-col items-start gap-0.5 font-normal">
                  <span className="text-sm font-medium">{cat.label}</span>
                  <span className="text-xs font-normal text-muted-foreground">{cat.description}</span>
                </Label>
              </div>
            ))}
          </div>

          <div className="mt-6 flex items-center gap-3">
            <Button onClick={handleSave} disabled={saving}>
              {saving ? "Saving..." : "Save filters"}
            </Button>
            {saved ? <p className="text-sm text-muted-foreground">Saved.</p> : null}
          </div>
        </Card>
      ) : null}
    </ParentShell>
  );
}
