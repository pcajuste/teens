"use client";

import { useEffect, useState } from "react";
import { parentApi } from "@/lib/parent-api";
import { ApiError } from "@/lib/api";
import type { ParentSettings } from "@/lib/types";
import { VALUES_FILTER_CATEGORIES, VALUES_FILTER_DESCRIPTIONS } from "@/lib/constants";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";

/**
 * Values filter configuration + approval-required toggle + digest toggle
 * (Prompt 4A deliverables 4/5/7). The approval-required toggle is
 * age-gated server-side (16-17 only) -- a 403 here is expected and
 * explained inline, not a bug to route around.
 */
export default function ParentSettingsPage() {
  const [settings, setSettings] = useState<ParentSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [approvalError, setApprovalError] = useState<string | null>(null);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);

  useEffect(() => {
    parentApi
      .getSettings()
      .then(setSettings)
      .catch((err) => setError(err instanceof ApiError ? String(err.detail ?? err.message) : "Could not load settings."))
      .finally(() => setLoading(false));
  }, []);

  async function toggleFilter(category: string) {
    if (!settings) return;
    const next = settings.values_filters.includes(category)
      ? settings.values_filters.filter((c) => c !== category)
      : [...settings.values_filters, category];
    setSaving(true);
    try {
      const updated = await parentApi.updateValuesFilters(next);
      setSettings(updated);
      setSavedMessage("Filters saved.");
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? err.message) : "Could not update filters.");
    } finally {
      setSaving(false);
    }
  }

  async function toggleApprovalRequired() {
    if (!settings) return;
    setApprovalError(null);
    setSaving(true);
    try {
      const updated = await parentApi.updateApprovalRequired(!settings.campaign_approval_required);
      setSettings(updated);
    } catch (err) {
      setApprovalError(
        err instanceof ApiError
          ? String(err.detail ?? err.message)
          : "Could not update the approval requirement.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function toggleDigest() {
    if (!settings) return;
    setSaving(true);
    try {
      setSettings(await parentApi.updateDigestEnabled(!settings.digest_enabled));
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? err.message) : "Could not update the digest setting.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <main className="container py-6">
        <p className="text-muted-foreground">Loading…</p>
      </main>
    );
  }

  if (error || !settings) {
    return (
      <main className="container py-6">
        <p className="text-sm text-red-600">{error ?? "Could not load settings."}</p>
      </main>
    );
  }

  return (
    <main className="container max-w-lg space-y-4 py-6">
      <h1 className="text-xl font-semibold">Settings</h1>

      <Card>
        <CardHeader>
          <CardTitle>Campaign approval</CardTitle>
          <CardDescription>
            When enabled, your teen can&apos;t accept a campaign until you approve it.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <label className="flex min-h-11 cursor-pointer items-center gap-3">
            <Checkbox checked={settings.campaign_approval_required} onChange={toggleApprovalRequired} disabled={saving} />
            <span className="text-sm">Require my approval before campaigns are accepted</span>
          </label>
          {approvalError && <p className="text-sm text-red-600">{approvalError}</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Values filters</CardTitle>
          <CardDescription>
            Block entire categories of campaigns — your teen will never see them as an option, and
            brands are never told why.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {VALUES_FILTER_CATEGORIES.map((category) => (
            <label key={category} className="flex min-h-11 cursor-pointer items-start gap-3">
              <Checkbox
                checked={settings.values_filters.includes(category)}
                onChange={() => toggleFilter(category)}
                disabled={saving}
              />
              <span className="text-sm">
                <span className="font-medium capitalize">{category.replace(/_/g, " ")}</span>
                <br />
                <span className="text-muted-foreground">{VALUES_FILTER_DESCRIPTIONS[category]}</span>
              </span>
            </label>
          ))}
          {savedMessage && <p className="text-sm text-green-700">{savedMessage}</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Monthly digest</CardTitle>
          <CardDescription>
            A monthly email summarizing campaign activity, earnings, and profile changes. Never
            includes message content, submission files, or brand contact details.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <label className="flex min-h-11 cursor-pointer items-center gap-3">
            <Checkbox checked={settings.digest_enabled} onChange={toggleDigest} disabled={saving} />
            <span className="text-sm">Send me a monthly digest email</span>
          </label>
        </CardContent>
      </Card>
    </main>
  );
}
