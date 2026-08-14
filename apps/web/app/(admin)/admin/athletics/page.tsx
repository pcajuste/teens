"use client";

import { useEffect, useState } from "react";
import { AdminShell } from "@/components/admin/admin-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import { SPORT_LABELS, type SupportedSport } from "@/lib/sports";
import type {
  AdminAthleticSeason,
  AdminNilStateRule,
  AdminUpdateNilStateRuleRequest,
  AdminUpdateNilStateRuleResponse,
} from "@/lib/types";

const STATUS_FILTERS = ["all", "draft", "pending_attestation", "attested", "verified"] as const;
type StatusFilter = (typeof STATUS_FILTERS)[number];

export default function AdminAthleticsPage() {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [seasons, setSeasons] = useState<AdminAthleticSeason[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [flagTarget, setFlagTarget] = useState<AdminAthleticSeason | null>(null);
  const [flagReason, setFlagReason] = useState("");

  const [rules, setRules] = useState<AdminNilStateRule[] | null>(null);
  const [editingRule, setEditingRule] = useState<AdminNilStateRule | null>(null);
  const [editEligible, setEditEligible] = useState(true);
  const [editNotes, setEditNotes] = useState("");
  const [editEffectiveDate, setEditEffectiveDate] = useState("");

  function loadSeasons(filter: StatusFilter) {
    const path =
      filter === "all"
        ? "/admin/athletics/seasons?limit=200"
        : `/admin/athletics/seasons?status=${filter}&limit=200`;
    api
      .get<AdminAthleticSeason[]>(path)
      .then(setSeasons)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load athletic seasons."));
  }

  function loadRules() {
    api
      .get<AdminNilStateRule[]>("/admin/nil-rules")
      .then(setRules)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load NIL rules."));
  }

  useEffect(() => {
    loadSeasons(statusFilter);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  useEffect(() => {
    loadRules();
  }, []);

  async function handleVerify(season: AdminAthleticSeason) {
    setNotice(null);
    setError(null);
    try {
      await api.post(`/admin/athletics/seasons/${season.id}/verify`);
      setNotice(`Verified ${season.talent_display_name}'s ${season.sport} season.`);
      loadSeasons(statusFilter);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not verify this season.");
    }
  }

  async function confirmFlag() {
    if (!flagTarget) return;
    if (!flagReason.trim()) {
      throw new Error("A flag reason is required.");
    }
    await api.post(`/admin/athletics/seasons/${flagTarget.id}/flag`, { reason: flagReason.trim() });
    setFlagTarget(null);
    setFlagReason("");
    loadSeasons(statusFilter);
  }

  function startEditRule(rule: AdminNilStateRule) {
    setEditingRule(rule);
    setEditEligible(rule.nil_eligible);
    setEditNotes(rule.notes ?? "");
    setEditEffectiveDate(rule.effective_date.slice(0, 10));
  }

  async function confirmEditRule() {
    if (!editingRule) return;
    const body: AdminUpdateNilStateRuleRequest = {
      nil_eligible: editEligible,
      notes: editNotes.trim() || null,
      effective_date: editEffectiveDate,
    };
    await api.put<AdminUpdateNilStateRuleResponse>(`/admin/nil-rules/${editingRule.state}`, body);
    setEditingRule(null);
    loadRules();
  }

  return (
    <AdminShell title="Athletics">
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {notice ? (
        <p className="rounded-lg bg-success/15 px-3 py-2 text-sm text-success">{notice}</p>
      ) : null}

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-4">
            <CardTitle>Season queue ({seasons?.length ?? "..."})</CardTitle>
            <div className="flex items-center gap-2">
              <Label htmlFor="status-filter" className="text-xs">
                Status
              </Label>
              <select
                id="status-filter"
                className="min-h-9 rounded-md border border-input bg-white/4 px-2 text-sm"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
              >
                {STATUS_FILTERS.map((s) => (
                  <option key={s} value={s}>
                    {s === "all" ? "All" : s}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {seasons === null ? (
            <Skeleton className="h-32 w-full" />
          ) : seasons.length === 0 ? (
            <EmptyState title="No seasons" description="No athletic seasons match this filter." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border-muted text-left text-text-2">
                    <th className="py-2 pr-4">Talent</th>
                    <th className="py-2 pr-4">Sport</th>
                    <th className="py-2 pr-4">Year</th>
                    <th className="py-2 pr-4">Team</th>
                    <th className="py-2 pr-4">Coach attestation</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2 pr-4">Admin verified</th>
                    <th className="py-2 pr-4" />
                  </tr>
                </thead>
                <tbody>
                  {seasons.map((s) => (
                    <tr key={s.id} className="border-b border-border-muted/60">
                      <td className="py-2 pr-4">{s.talent_display_name}</td>
                      <td className="py-2 pr-4">{SPORT_LABELS[s.sport as SupportedSport] ?? s.sport}</td>
                      <td className="py-2 pr-4">{s.season_year}</td>
                      <td className="py-2 pr-4">{s.team_name}</td>
                      <td className="py-2 pr-4">{s.coach_attestation_status}</td>
                      <td className="py-2 pr-4">
                        <Badge variant={s.status === "verified" ? "done" : s.status === "attested" ? "earned" : "pending"}>
                          {s.status}
                        </Badge>
                      </td>
                      <td className="py-2 pr-4">{s.admin_verified ? "Yes" : "No"}</td>
                      <td className="py-2 pr-4">
                        <div className="flex gap-2">
                          {s.status === "attested" && !s.admin_verified ? (
                            <Button size="sm" onClick={() => handleVerify(s)}>
                              Verify
                            </Button>
                          ) : null}
                          <Button size="sm" variant="outline" onClick={() => setFlagTarget(s)}>
                            Flag
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>NIL state rules</CardTitle>
        </CardHeader>
        <CardContent>
          {rules === null ? (
            <Skeleton className="h-32 w-full" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border-muted text-left text-text-2">
                    <th className="py-2 pr-4">State</th>
                    <th className="py-2 pr-4">NIL eligible</th>
                    <th className="py-2 pr-4">Notes</th>
                    <th className="py-2 pr-4">Effective date</th>
                    <th className="py-2 pr-4">Last updated</th>
                    <th className="py-2 pr-4" />
                  </tr>
                </thead>
                <tbody>
                  {rules.map((r) => (
                    <tr key={r.state} className="border-b border-border-muted/60">
                      <td className="py-2 pr-4">{r.state}</td>
                      <td className="py-2 pr-4">
                        <Badge variant={r.nil_eligible ? "done" : "pending"}>{r.nil_eligible ? "Yes" : "No"}</Badge>
                      </td>
                      <td className="py-2 pr-4">{r.notes ?? "—"}</td>
                      <td className="py-2 pr-4">{new Date(r.effective_date).toLocaleDateString()}</td>
                      <td className="py-2 pr-4">{new Date(r.last_updated_at).toLocaleDateString()}</td>
                      <td className="py-2 pr-4">
                        <Button size="sm" variant="outline" onClick={() => startEditRule(r)}>
                          Edit
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <ConfirmDialog
        open={flagTarget !== null}
        title="Flag athletic season"
        description={
          flagTarget
            ? `Flag ${flagTarget.talent_display_name}'s ${flagTarget.sport} season (${flagTarget.season_year}). Reverts admin_verified to false if it was true. The talent is not notified.`
            : ""
        }
        confirmLabel="Flag season"
        confirmVariant="destructive"
        confirmDisabled={!flagReason.trim()}
        onCancel={() => {
          setFlagTarget(null);
          setFlagReason("");
        }}
        onConfirm={confirmFlag}
      >
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="flag-reason">Flag reason (required)</Label>
          <Textarea
            id="flag-reason"
            rows={2}
            value={flagReason}
            onChange={(e) => setFlagReason(e.target.value)}
            placeholder="e.g. Stats look implausible for this level of play"
          />
        </div>
      </ConfirmDialog>

      <ConfirmDialog
        open={editingRule !== null}
        title={editingRule ? `Edit NIL rule: ${editingRule.state}` : ""}
        description="Updating a rule to not-eligible revokes any existing talent acknowledgments for that state."
        confirmLabel="Save"
        onCancel={() => setEditingRule(null)}
        onConfirm={confirmEditRule}
      >
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setEditEligible((v) => !v)}
              className={`rounded-full border px-3 py-1 text-xs font-medium ${
                editEligible
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border-muted bg-transparent text-text-2"
              }`}
            >
              NIL eligible: {editEligible ? "Yes" : "No"}
            </button>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="rule-effective-date">Effective date</Label>
            <Input
              id="rule-effective-date"
              type="date"
              value={editEffectiveDate}
              onChange={(e) => setEditEffectiveDate(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="rule-notes">Notes</Label>
            <Textarea
              id="rule-notes"
              rows={2}
              value={editNotes}
              onChange={(e) => setEditNotes(e.target.value)}
            />
          </div>
        </div>
      </ConfirmDialog>
    </AdminShell>
  );
}
