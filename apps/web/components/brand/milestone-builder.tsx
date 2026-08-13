"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { MilestoneRequest, VerificationMethod } from "@/lib/types";

export const MIN_MILESTONES = 2;
export const MAX_MILESTONES = 5;

export function emptyMilestone(number: number): MilestoneRequest {
  return {
    milestone_number: number,
    title: "",
    description: null,
    verification_method: "brand_confirmation",
    payout_percentage: 0,
    sequence_required: true,
  };
}

export function milestonesPercentageTotal(
  milestones: MilestoneRequest[],
): number {
  return milestones.reduce((sum, m) => sum + (m.payout_percentage || 0), 0);
}

/** Milestone builder step for the brief builder (Build Prompt 8B
 * frontend note: "add/remove milestone controls, title/description
 * fields, verification method selector, and a live payout percentage
 * calculator ... clear error state when percentages do not sum to
 * 100"). Server is still the source of truth for every cross-milestone
 * rule (sequential numbering, at least one sequence_required,
 * non-sequential trailing-only, exact 100% sum) -- this only enforces
 * the percentage-sum total and the 2-5 count client-side as a UX guard
 * so a brand isn't surprised by a validation error after submitting. */
export function MilestoneBuilder({
  milestones,
  onChange,
}: {
  milestones: MilestoneRequest[];
  onChange: (milestones: MilestoneRequest[]) => void;
}) {
  const total = milestonesPercentageTotal(milestones);
  const remaining = 100 - total;

  function update(index: number, patch: Partial<MilestoneRequest>) {
    onChange(milestones.map((m, i) => (i === index ? { ...m, ...patch } : m)));
  }

  function addMilestone() {
    if (milestones.length >= MAX_MILESTONES) return;
    onChange([...milestones, emptyMilestone(milestones.length + 1)]);
  }

  function removeMilestone(index: number) {
    if (milestones.length <= MIN_MILESTONES) return;
    onChange(
      milestones
        .filter((_, i) => i !== index)
        .map((m, i) => ({ ...m, milestone_number: i + 1 })),
    );
  }

  return (
    <div className="flex flex-col gap-4 rounded-xl border border-border bg-card p-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold">Milestones</p>
        <p
          className={`text-sm font-medium ${remaining === 0 ? "text-success" : "text-destructive"}`}
        >
          {remaining === 0
            ? "100% allocated"
            : `${remaining}% remaining to allocate`}
        </p>
      </div>

      {milestones.map((m, i) => (
        <div
          key={i}
          className="flex flex-col gap-2 rounded-lg border border-border p-3"
        >
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-muted-foreground">
              Milestone {m.milestone_number}
            </p>
            {milestones.length > MIN_MILESTONES ? (
              <button
                type="button"
                onClick={() => removeMilestone(i)}
                className="text-xs text-destructive underline"
              >
                Remove
              </button>
            ) : null}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`milestone-title-${i}`}>Title</Label>
            <Input
              id={`milestone-title-${i}`}
              required
              value={m.title}
              onChange={(e) => update(i, { title: e.target.value })}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`milestone-description-${i}`}>Description</Label>
            <Textarea
              id={`milestone-description-${i}`}
              rows={2}
              value={m.description ?? ""}
              onChange={(e) =>
                update(i, { description: e.target.value || null })
              }
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`milestone-verification-${i}`}>
                Verification method
              </Label>
              <select
                id={`milestone-verification-${i}`}
                className="min-h-11 rounded-md border border-input bg-background px-3 text-sm"
                value={m.verification_method}
                onChange={(e) =>
                  update(i, {
                    verification_method: e.target.value as VerificationMethod,
                  })
                }
              >
                <option value="brand_confirmation">
                  Brand confirms manually
                </option>
                <option value="talent_submission">
                 talent submission (24h auto-release)
                </option>
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`milestone-percentage-${i}`}>Payout %</Label>
              <Input
                id={`milestone-percentage-${i}`}
                type="number"
                min={1}
                max={100}
                required
                value={m.payout_percentage || ""}
                onChange={(e) =>
                  update(i, { payout_percentage: Number(e.target.value) })
                }
              />
            </div>
          </div>

          <div className="flex items-center gap-2">
            <input
              id={`milestone-sequence-${i}`}
              type="checkbox"
              checked={m.sequence_required}
              onChange={(e) =>
                update(i, { sequence_required: e.target.checked })
              }
            />
            <Label htmlFor={`milestone-sequence-${i}`} className="font-normal">
              Must be completed in order (sequence required)
            </Label>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`milestone-threshold-${i}`}>
              Count/threshold (optional)
            </Label>
            <Input
              id={`milestone-threshold-${i}`}
              type="number"
              min={1}
              placeholder="Leave blank for a single-submission milestone"
              value={m.threshold_count ?? ""}
              onChange={(e) =>
                update(i, {
                  threshold_count:
                    e.target.value === "" ? null : Number(e.target.value),
                })
              }
            />
            <p className="text-xs text-muted-foreground">
              Only set this for a milestone the Talent completes by repeated
              submission (e.g. &quot;publish 3 pieces of content&quot;). The Talent will
              see live &quot;X of Y&quot; progress instead of a flat pending/done state.
            </p>
          </div>
        </div>
      ))}

      <Button
        type="button"
        variant="outline"
        onClick={addMilestone}
        disabled={milestones.length >= MAX_MILESTONES}
      >
        Add milestone
      </Button>
      <p className="text-xs text-muted-foreground">
        2–5 milestones per campaign. Payout percentages must sum to exactly 100%
        before you can create this campaign.
      </p>
    </div>
  );
}
