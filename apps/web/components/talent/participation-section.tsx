"use client";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Countdown } from "@/components/talent/countdown";
import { WithdrawButton } from "@/components/talent/withdraw-button";
import type { CampaignParticipation } from "@/lib/types";

export function ParticipationSection({
  participation,
  ftcAccepted,
  setFtcAccepted,
  onAccept,
  onDecline,
  onWithdrawn,
  pending,
}: {
  participation: CampaignParticipation;
  ftcAccepted: boolean;
  setFtcAccepted: (v: boolean) => void;
  onAccept: () => void;
  onDecline: () => void;
  onWithdrawn: () => void;
  pending: boolean;
}) {
  if (participation.parent_approval_status === "pending") {
    return (
      <section className="flex flex-col gap-2 rounded-xl border border-warning/30 bg-warning/10 p-4">
        <p className="text-sm font-medium text-warning-foreground">
          Waiting on a parent&apos;s approval
        </p>
        {participation.parent_approval_deadline ? (
          <Countdown deadline={participation.parent_approval_deadline} />
        ) : null}
      </section>
    );
  }

  if (participation.parent_approval_status === "blocked") {
    return (
      <section className="flex flex-col gap-2 rounded-xl border border-destructive/30 bg-destructive/5 p-4">
        <p className="text-sm font-medium text-destructive">
          Your parent has blocked this campaign.
        </p>
      </section>
    );
  }

  if (
    participation.status === "applied" ||
    participation.status === "invited"
  ) {
    return (
      <section className="flex flex-col gap-3 rounded-xl border border-border bg-card p-5">
        <div className="flex items-start gap-3">
          <Checkbox
            id="ftc"
            checked={ftcAccepted}
            onCheckedChange={(checked) => setFtcAccepted(checked === true)}
          />
          <Label
            htmlFor="ftc"
            className="flex-col items-start gap-1 font-normal"
          >
            <span className="font-medium">FTC sponsorship disclosure</span>
            <span className="text-xs text-muted-foreground">
              I understand I must disclose that this is a paid partnership when
              I post about it.
            </span>
          </Label>
        </div>
        {participation.parent_approval_deadline ? (
          <Countdown deadline={participation.parent_approval_deadline} />
        ) : null}
        <div className="flex gap-2">
          <Button
            onClick={onAccept}
            disabled={pending || !ftcAccepted}
            size="lg"
            className="flex-1"
          >
            Accept
          </Button>
          <Button
            onClick={onDecline}
            disabled={pending}
            variant="outline"
            size="lg"
            className="flex-1"
          >
            Decline
          </Button>
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-border bg-card p-5">
      <WithdrawButton
        campaignId={participation.campaign_id}
        onWithdrawn={onWithdrawn}
      />
    </section>
  );
}
