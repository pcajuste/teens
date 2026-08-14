"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { RecruiterShell } from "@/components/recruiter/recruiter-shell";
import { CreditConfirmDialog } from "@/components/recruiter/credit-confirm-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import { trackEvent } from "@/lib/analytics";
import { SPORT_LABELS, type SupportedSport } from "@/lib/sports";
import type { AthleticTalentDetail } from "@/lib/types";

// ATHLETICS-7 deliverable 1: reached after credit spend on
// GET /recruiters/talents/:id?track=athletics. No brand-track fields
// (total_earnings_cents, campaigns, ratings) -- irrelevant to an
// athletic recruiter.
export default function AthleticTalentDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [detail, setDetail] = useState<AthleticTalentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [messageText, setMessageText] = useState("");
  const [contactOpen, setContactOpen] = useState(false);
  const [contactNotice, setContactNotice] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<AthleticTalentDetail>(`/recruiters/talents/${params.id}?track=athletics`)
      .then((d) => {
        setDetail(d);
        trackEvent("athletic_talent_detail_viewed", { track: "athletics" });
      })
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Could not load this profile."),
      )
      .finally(() => setLoading(false));
  }, [params.id]);

  async function handleSave() {
    if (!detail) return;
    try {
      await api.post(`/recruiters/talents/${detail.talent_id}/save`, {});
      setContactNotice("Saved to your default list.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save this talent.");
    }
  }

  function openContactDialog() {
    setMessageText("");
    setContactNotice(null);
    setContactOpen(true);
  }

  async function confirmSendMessage() {
    if (!detail) return;
    if (!messageText.trim()) {
      throw new Error("Write a message before sending.");
    }
    try {
      await api.post(`/recruiters/talents/${detail.talent_id}/contact`, {
        message_text: messageText,
      });
      trackEvent("recruiter_profile_contacted", {});
      setContactOpen(false);
      setContactNotice(
        "Message sent. The talent will see it in their inbox and get an alert email.",
      );
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.code === "already_contacted"
            ? "You've already contacted this talent."
            : err.message
          : "Could not send this message.";
      throw new Error(message);
    }
  }

  if (loading) {
    return (
      <RecruiterShell title="Athlete profile" backHref="/recruiter">
        <Skeleton className="h-64 w-full" />
      </RecruiterShell>
    );
  }

  if (error || !detail) {
    return (
      <RecruiterShell title="Athlete profile" backHref="/recruiter">
        <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error ?? "Could not load this profile."}
        </p>
      </RecruiterShell>
    );
  }

  return (
    <RecruiterShell title="Athlete profile" backHref="/recruiter">
      <Card>
        <CardContent>
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold tracking-tight">{detail.display_name}</h2>
              <p className="text-sm text-text-2">
                {detail.school_name} · Class of {detail.graduation_year}
              </p>
              <p className="text-sm text-text-2">
                {detail.city}, {detail.state}
              </p>
            </div>
            <Button type="button" variant="ghost" size="sm" onClick={() => router.push("/recruiter")}>
              Back to search
            </Button>
          </div>

          {detail.bio ? <p className="mt-3 text-sm">{detail.bio}</p> : null}

          <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-text-2">
            <span>
              <span className="text-teal">✓</span> {detail.athletic_seasons_completed} seasons completed
            </span>
            <span>{detail.athletic_completeness_score}% complete</span>
            <Badge variant={detail.nil_acknowledged ? "done" : "pending"}>
              {detail.nil_acknowledged ? "NIL rules acknowledged" : "NIL acknowledgment pending"}
            </Badge>
            {detail.athletic_recruiter_interest_count > 1 ? (
              <Badge variant="secondary">
                You + {detail.athletic_recruiter_interest_count - 1} others
              </Badge>
            ) : null}
          </div>

          <div className="mt-5 flex flex-col gap-3">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-text-2">Sport profiles</h3>
            {detail.sport_profiles.length === 0 ? (
              <p className="text-sm text-text-2">No sport profiles yet.</p>
            ) : (
              detail.sport_profiles.map((sp) => (
                <div key={sp.id} className="rounded-lg border border-border-muted p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-medium">{SPORT_LABELS[sp.sport as SupportedSport] ?? sp.sport}</p>
                    {sp.gpa != null ? <span className="text-sm text-text-2">GPA {sp.gpa.toFixed(2)}</span> : null}
                  </div>
                  {sp.positions.length > 0 ? (
                    <p className="mt-1 text-sm text-text-2">{sp.positions.join(", ")}</p>
                  ) : null}
                  <div className="mt-2 flex flex-wrap gap-3 text-sm">
                    {sp.hudl_url ? (
                      <a
                        href={sp.hudl_url}
                        target="_blank"
                        rel="noreferrer"
                        className="font-medium text-primary hover:underline"
                      >
                        Hudl film
                      </a>
                    ) : null}
                    {sp.maxpreps_url ? (
                      <a
                        href={sp.maxpreps_url}
                        target="_blank"
                        rel="noreferrer"
                        className="font-medium text-primary hover:underline"
                      >
                        MaxPreps
                      </a>
                    ) : null}
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="mt-5 flex flex-col gap-3">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-text-2">Recent seasons</h3>
            {detail.recent_seasons.length === 0 ? (
              <p className="text-sm text-text-2">No attested seasons yet.</p>
            ) : (
              detail.recent_seasons.map((s, i) => (
                <div key={i} className="rounded-lg border border-border-muted p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-medium">
                      {SPORT_LABELS[s.sport as SupportedSport] ?? s.sport} · {s.season_year}
                    </p>
                    <Badge variant={s.status === "verified" ? "done" : "earned"}>
                      {s.status === "verified" ? "Platform Verified" : "Coach Verified"}
                    </Badge>
                  </div>
                  <p className="mt-1 text-sm text-text-2">
                    {s.team_name} · {s.level}
                  </p>
                </div>
              ))
            )}
          </div>

          {contactNotice ? (
            <p className="mt-4 rounded-lg bg-success/15 px-3 py-2 text-sm text-success">{contactNotice}</p>
          ) : null}

          <div className="mt-5 flex gap-2">
            <Button type="button" onClick={openContactDialog}>
              Message this athlete
            </Button>
            <Button type="button" variant="outline" onClick={handleSave}>
              Save
            </Button>
          </div>
        </CardContent>
      </Card>

      <CreditConfirmDialog
        open={contactOpen}
        title="Send message"
        description="This will use 1 contact credit. You can only message each talent once."
        confirmLabel="Use 1 credit & send"
        confirmDisabled={!messageText.trim()}
        onCancel={() => setContactOpen(false)}
        onConfirm={confirmSendMessage}
      >
        <Label htmlFor="message_text">Message</Label>
        <Textarea
          id="message_text"
          className="mt-1.5"
          rows={4}
          value={messageText}
          onChange={(e) => setMessageText(e.target.value)}
          placeholder="Introduce yourself and why you're reaching out..."
        />
      </CreditConfirmDialog>
    </RecruiterShell>
  );
}
