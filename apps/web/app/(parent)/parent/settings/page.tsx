"use client";

import { useEffect, useState } from "react";
import { ParentShell } from "@/components/parent/parent-shell";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { parentApi, ParentApiError } from "@/lib/parent-api";
import type { ParentAccountControlResponse, ParentDigestPreview, ParentSettings } from "@/lib/parent-types";

function money(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

export default function ParentSettingsPage() {
  const [settings, setSettings] = useState<ParentSettings | null>(null);
  const [digest, setDigest] = useState<ParentDigestPreview | null>(null);
  const [accountStatus, setAccountStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [approvalLocked, setApprovalLocked] = useState(false);
  const [pendingToggle, setPendingToggle] = useState<"approval" | "digest" | null>(null);
  const [confirmAction, setConfirmAction] = useState<"suspend" | "unsuspend" | null>(null);

  async function load() {
    setLoading(true);
    try {
      const [settingsRes, digestRes] = await Promise.all([
        parentApi.get<ParentSettings>("/parent/settings"),
        parentApi.get<ParentDigestPreview>("/parent/digest/preview"),
      ]);
      setSettings(settingsRes);
      setDigest(digestRes);
    } catch (err) {
      setError(err instanceof ParentApiError ? err.message : "Could not load settings.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function toggleApproval() {
    if (!settings) return;
    setPendingToggle("approval");
    setError(null);
    try {
      const res = await parentApi.put<ParentSettings>("/parent/settings/approval-required", {
        enabled: !settings.campaign_approval_required,
      });
      setSettings(res);
      setApprovalLocked(false);
    } catch (err) {
      if (err instanceof ParentApiError && err.code === "approval_required_locked_under_16") {
        setApprovalLocked(true);
      } else {
        setError(err instanceof ParentApiError ? err.message : "Could not update the approval setting.");
      }
    } finally {
      setPendingToggle(null);
    }
  }

  async function toggleDigest() {
    if (!settings) return;
    setPendingToggle("digest");
    setError(null);
    try {
      const res = await parentApi.put<ParentSettings>("/parent/settings/digest", {
        enabled: !settings.digest_enabled,
      });
      setSettings(res);
    } catch (err) {
      setError(err instanceof ParentApiError ? err.message : "Could not update the digest setting.");
    } finally {
      setPendingToggle(null);
    }
  }

  async function handleAccountAction() {
    if (!confirmAction) return;
    const res = await parentApi.post<ParentAccountControlResponse>(`/parent/account/${confirmAction}`);
    setAccountStatus(res.account_status);
    setConfirmAction(null);
  }

  return (
    <ParentShell title="Settings">
      {error ? <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p> : null}

      {loading ? (
        <div className="flex flex-col gap-4">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      ) : settings ? (
        <div className="flex flex-col gap-6">
          <Card className="p-5">
            <p className="text-sm font-semibold">Campaign approval required</p>
            <p className="mt-1 text-sm text-muted-foreground">
              When on, every campaign your teen is matched to needs your approval before they can accept it.
            </p>
            {approvalLocked ? (
              <p className="mt-2 rounded-lg bg-warning/20 px-3 py-2 text-sm text-warning-foreground">
                Campaign approval is always required for reps under 16 and can&apos;t be turned off.
              </p>
            ) : null}
            <Button
              className="mt-3"
              variant={settings.campaign_approval_required ? "secondary" : "default"}
              onClick={toggleApproval}
              disabled={pendingToggle === "approval" || approvalLocked}
            >
              {settings.campaign_approval_required ? "Turn off" : "Turn on"}
            </Button>
          </Card>

          <Card className="p-5">
            <p className="text-sm font-semibold">Monthly email digest</p>
            <p className="mt-1 text-sm text-muted-foreground">
              A monthly summary of campaign activity, earnings, and profile changes.
            </p>
            <Button
              className="mt-3"
              variant={settings.digest_enabled ? "secondary" : "default"}
              onClick={toggleDigest}
              disabled={pendingToggle === "digest"}
            >
              {settings.digest_enabled ? "Turn off" : "Turn on"}
            </Button>

            {digest ? (
              <div className="mt-4 rounded-lg border border-border bg-muted/30 p-3">
                <p className="mb-2 text-xs font-medium text-muted-foreground">Next digest preview</p>
                <ul className="flex flex-col gap-1 text-sm">
                  <li>Campaigns completed this month: {digest.campaigns_completed_this_month}</li>
                  <li>Earnings this month: {money(digest.earnings_this_month_cents)}</li>
                  <li>Lifetime earnings: {money(digest.lifetime_earnings_cents)}</li>
                  <li>
                    Profile completeness: {digest.profile_completeness_score}%
                    {digest.profile_completeness_change !== null
                      ? ` (${digest.profile_completeness_change >= 0 ? "+" : ""}${digest.profile_completeness_change} since last digest)`
                      : ""}
                  </li>
                  <li>Active categories: {digest.active_categories.join(", ") || "none"}</li>
                </ul>
              </div>
            ) : null}
          </Card>

          <Card className="p-5">
            <p className="text-sm font-semibold">Account controls</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Suspending immediately pauses your teen&apos;s account. You can unsuspend it later if you were the
              one who suspended it.
            </p>
            {accountStatus ? (
              <p className="mt-2 text-sm text-muted-foreground">Current status: {accountStatus}</p>
            ) : null}
            <div className="mt-3 flex gap-2">
              <Button variant="destructive" onClick={() => setConfirmAction("suspend")}>
                Suspend account
              </Button>
              <Button variant="outline" onClick={() => setConfirmAction("unsuspend")}>
                Unsuspend account
              </Button>
            </div>
          </Card>
        </div>
      ) : null}

      {confirmAction ? (
        <ConfirmDialog
          open={true}
          title={confirmAction === "suspend" ? "Suspend this account?" : "Unsuspend this account?"}
          description={
            confirmAction === "suspend"
              ? "Your teen won't be able to use Teenure until you or an admin unsuspend the account."
              : "This restores access if you were the one who suspended the account. If it was suspended by an admin, this won't work."
          }
          confirmLabel={confirmAction === "suspend" ? "Suspend" : "Unsuspend"}
          confirmVariant={confirmAction === "suspend" ? "destructive" : "default"}
          onCancel={() => setConfirmAction(null)}
          onConfirm={handleAccountAction}
        />
      ) : null}
    </ParentShell>
  );
}
