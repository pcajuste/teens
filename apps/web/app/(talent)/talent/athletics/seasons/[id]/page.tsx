"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AthleticsGate } from "@/components/talent/athletics-gate";
import { SeasonStatusChip } from "@/components/talent/season-status-chip";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import { SEASON_LEVEL_LABELS, SEASON_TYPE_LABELS, SPORT_LABELS, type SupportedSport } from "@/lib/sports";
import type { AthleticSeason, RequestCoachAttestationResponse } from "@/lib/types";

export default function SeasonDetailPage() {
  const params = useParams<{ id: string }>();
  return (
    <AthleticsGate
      title="Season"
      backHref="/talent/athletics/seasons"
      render={() => <SeasonDetail seasonId={params.id} />}
    />
  );
}

function SeasonDetail({ seasonId }: { seasonId: string }) {
  const router = useRouter();
  const [season, setSeason] = useState<AthleticSeason | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [confirmingWithdraw, setConfirmingWithdraw] = useState(false);
  const [coachEmail, setCoachEmail] = useState("");
  const [rateLimitHours, setRateLimitHours] = useState<number | null>(null);
  const [requesting, setRequesting] = useState(false);

  function load() {
    api
      .get<AthleticSeason>(`/talents/athletics/seasons/${seasonId}`)
      .then((s) => {
        setSeason(s);
        setCoachEmail(s.coach_email ?? "");
      })
      .catch((err) => {
        if (err instanceof ApiError && err.code === "athletic_season_not_found") {
          setNotFound(true);
          return;
        }
        setError(err instanceof ApiError ? err.message : "Could not load this season.");
      });
  }

  useEffect(load, [seasonId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleRequestAttestation() {
    setRequesting(true);
    setError(null);
    setRateLimitHours(null);
    try {
      await api.post<RequestCoachAttestationResponse>(`/talents/athletics/seasons/${seasonId}/request-attestation`);
      load();
    } catch (err) {
      if (err instanceof ApiError && err.code === "rate_limited") {
        const hours = (err.detail?.hours_until_resend_allowed as number | undefined) ?? null;
        setRateLimitHours(hours);
      } else {
        setError(err instanceof ApiError ? err.message : "Could not request attestation.");
      }
    } finally {
      setRequesting(false);
    }
  }

  async function handleDelete() {
    await api.delete(`/talents/athletics/seasons/${seasonId}`);
    router.push("/talent/athletics/seasons");
  }

  async function handleWithdraw() {
    await api.post<AthleticSeason>(`/talents/athletics/seasons/${seasonId}/withdraw-attestation`);
    setConfirmingWithdraw(false);
    load();
  }

  if (notFound) {
    return <p className="text-sm text-muted-foreground">This season could not be found.</p>;
  }

  if (error) {
    return <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>;
  }

  if (!season) {
    return <Skeleton className="h-64 w-full" />;
  }

  const declined = season.status === "pending_attestation" && season.coach_attestation_status === "declined";

  return (
    <div className="flex flex-col gap-6">
      <Card className="flex flex-col gap-2 p-5">
        <div className="flex items-center justify-between gap-2">
          <p className="text-lg font-semibold">
            {SPORT_LABELS[season.sport as SupportedSport] ?? season.sport} · {season.season_year}
          </p>
          <SeasonStatusChip season={season} />
        </div>
        <p className="text-sm text-muted-foreground">
          {season.team_name} · {SEASON_LEVEL_LABELS[season.level as keyof typeof SEASON_LEVEL_LABELS] ?? season.level} ·{" "}
          {SEASON_TYPE_LABELS[season.season_type as keyof typeof SEASON_TYPE_LABELS] ?? season.season_type}
        </p>
      </Card>

      {Object.keys(season.sport_stats).length > 0 ? (
        <Card className="flex flex-col gap-2 p-5">
          <p className="text-sm font-semibold">Stats</p>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            {Object.entries(season.sport_stats)
              .filter(([key]) => key !== "achievements")
              .map(([key, value]) => (
                <div key={key} className="flex flex-col">
                  <dt className="text-xs text-muted-foreground">{key.replace(/_/g, " ")}</dt>
                  <dd className="font-medium">{String(value)}</dd>
                </div>
              ))}
          </dl>
        </Card>
      ) : null}

      {/* ── draft ── */}
      {season.status === "draft" ? (
        <Card className="flex flex-col gap-3 p-5">
          <div className="flex gap-2">
            <Button
              variant="outline"
              className="flex-1"
              onClick={() => router.push(`/talent/athletics/seasons/new?edit=${season.id}`)}
            >
              Edit
            </Button>
            <Button variant="destructive" className="flex-1" onClick={() => setConfirmingDelete(true)}>
              Delete
            </Button>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="coach_email_inline">Coach email</Label>
            <Input
              id="coach_email_inline"
              type="email"
              value={coachEmail}
              onChange={(e) => setCoachEmail(e.target.value)}
              placeholder="coach@school.edu"
            />
          </div>

          <div title={!season.coach_email ? "Add a coach email first" : undefined}>
            <Button
              className="w-full"
              disabled={!season.coach_email || requesting}
              onClick={handleRequestAttestation}
            >
              {requesting ? "Requesting…" : "Request attestation"}
            </Button>
          </div>
          {!season.coach_email ? (
            <p className="text-xs text-muted-foreground">Add a coach email first, then save the season to request attestation.</p>
          ) : null}
          {rateLimitHours !== null ? (
            <p className="text-sm text-warning-foreground">
              You can request again in {Math.ceil(rateLimitHours)} hours.
            </p>
          ) : null}
        </Card>
      ) : null}

      {/* ── pending attestation ── */}
      {season.status === "pending_attestation" ? (
        <Card className="flex flex-col gap-3 p-5">
          {declined ? (
            <>
              <p className="text-sm font-semibold text-destructive">
                The coach was unable to confirm this record.
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={() => router.push(`/talent/athletics/seasons/new?edit=${season.id}`)}
                >
                  Edit and re-request
                </Button>
                <Button variant="destructive" className="flex-1" onClick={() => setConfirmingWithdraw(true)}>
                  Withdraw and start over
                </Button>
              </div>
            </>
          ) : (
            <>
              <p className="text-sm font-semibold">Awaiting coach confirmation</p>
              <p className="text-sm text-muted-foreground">
                {season.coach_name ? `We emailed ${season.coach_name} to confirm this season.` : "Waiting for your coach to respond."}
              </p>
              <Button variant="outline" onClick={() => setConfirmingWithdraw(true)}>
                Withdraw attestation request
              </Button>
            </>
          )}
        </Card>
      ) : null}

      {/* ── attested ── */}
      {season.status === "attested" ? (
        <Card className="flex flex-col gap-2 p-5">
          <Badge variant="earned" className="w-fit">
            Coach Verified
          </Badge>
          <p className="text-sm">Verified by {season.coach_name ?? "your coach"}</p>
          {season.coach_attested_at ? (
            <p className="text-xs text-muted-foreground">
              Attested {new Date(season.coach_attested_at).toLocaleDateString()}
            </p>
          ) : null}
          <p className="text-xs text-muted-foreground">Attested records are locked and can&apos;t be edited.</p>
        </Card>
      ) : null}

      {/* ── verified ── */}
      {season.status === "verified" ? (
        <Card className="flex flex-col gap-2 p-5">
          <Badge variant="done" className="w-fit">
            Platform Verified
          </Badge>
          <p className="text-sm">Verified by {season.coach_name ?? "your coach"}</p>
          {season.coach_attested_at ? (
            <p className="text-xs text-muted-foreground">
              Coach attested {new Date(season.coach_attested_at).toLocaleDateString()}
            </p>
          ) : null}
          {season.admin_verified_at ? (
            <p className="text-xs text-muted-foreground">
              Platform verified {new Date(season.admin_verified_at).toLocaleDateString()}
            </p>
          ) : null}
        </Card>
      ) : null}

      <ConfirmDialog
        open={confirmingDelete}
        title="Delete this season?"
        description="This can't be undone."
        confirmVariant="destructive"
        confirmLabel="Delete"
        onCancel={() => setConfirmingDelete(false)}
        onConfirm={handleDelete}
      />

      <ConfirmDialog
        open={confirmingWithdraw}
        title="Withdraw attestation request?"
        description="Your coach's link will stop working and the season goes back to draft."
        confirmLabel="Withdraw"
        onCancel={() => setConfirmingWithdraw(false)}
        onConfirm={handleWithdraw}
      />
    </div>
  );
}
