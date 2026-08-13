"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";
import { trackEvent } from "@/lib/analytics";
import {
  GOAL_TYPE_LABELS,
  MAX_ACTIVE_GOALS,
  type CreateGoalRequest,
  type Goal,
  type GoalSuggestion,
  type GoalType,
} from "@/lib/types";

// Build Prompt 5/6 deliverable 13/10: Goal Setting and Progress
// Tracking. Self-contained -- fetches its own data rather than
// threading goals through the dashboard's Promise.all, since goal
// mutations (create/abandon) only need to refetch this panel, not the
// whole dashboard.

const DEFAULT_TARGETS: Record<GoalType, number> = {
  campaigns_completed: 5,
  earnings_total: 50000, // $500, in cents
  categories_active: 2,
  badges_earned: 3,
  profile_completeness: 100,
};

function formatCurrentValue(goal: Goal): string {
  if (goal.goal_type === "earnings_total") {
    return `$${(goal.current_value / 100).toFixed(0)} / $${(goal.target_value / 100).toFixed(0)}`;
  }
  if (goal.goal_type === "profile_completeness") {
    return `${goal.current_value}% / ${goal.target_value}%`;
  }
  return `${goal.current_value} / ${goal.target_value}`;
}

function goalLabel(goalType: GoalType, targetValue: number): string {
  switch (goalType) {
    case "campaigns_completed":
      return `Complete ${targetValue} campaigns`;
    case "earnings_total":
      return `Earn $${(targetValue / 100).toFixed(0)}`;
    case "categories_active":
      return `Work in ${targetValue} categories`;
    case "badges_earned":
      return `Earn ${targetValue} badges`;
    case "profile_completeness":
      return `Reach ${targetValue}% profile completeness`;
  }
}

function GoalRow({ goal, onAbandon }: { goal: Goal; onAbandon: (id: string) => void }) {
  const isCompleted = goal.status === "completed";
  return (
    <div className={`flex flex-col gap-2 rounded-lg border p-3 ${isCompleted ? "border-success/40 bg-success/5" : "border-border"}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-col gap-0.5">
          <p className="text-sm font-medium">{goalLabel(goal.goal_type, goal.target_value)}</p>
          {isCompleted ? (
            <p className="text-xs font-medium text-success">Goal reached</p>
          ) : (
            <p className="text-xs text-muted-foreground">{formatCurrentValue(goal)}</p>
          )}
        </div>
        {!isCompleted ? (
          <button
            type="button"
            onClick={() => onAbandon(goal.id)}
            className="shrink-0 text-xs font-medium text-muted-foreground underline underline-offset-2"
          >
            Abandon
          </button>
        ) : null}
      </div>
      {!isCompleted ? (
        <>
          <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
            <div className="h-full rounded-full bg-primary transition-[width]" style={{ width: `${goal.progress_percentage}%` }} />
          </div>
          {goal.projected_completion_date ? (
            <p className="text-xs text-muted-foreground">
              At your current pace, projected {new Date(goal.projected_completion_date).toLocaleDateString()}
            </p>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

export function GoalsPanel() {
  const [goals, setGoals] = useState<Goal[] | null>(null);
  const [suggestions, setSuggestions] = useState<GoalSuggestion[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [addingType, setAddingType] = useState<GoalType | "">("");
  const [targetValue, setTargetValue] = useState<number>(DEFAULT_TARGETS.campaigns_completed);
  const [targetDate, setTargetDate] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);

  async function load() {
    try {
      const [goalsRes, suggestionsRes] = await Promise.all([
        api.get<Goal[]>("/talents/goals"),
        api.get<GoalSuggestion[]>("/talents/goals/suggestions"),
      ]);
      setGoals(goalsRes);
      setSuggestions(suggestionsRes);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load your goals.");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const activeGoals = (goals ?? []).filter((g) => g.status === "active");
  const completedGoals = (goals ?? []).filter((g) => g.status === "completed");
  const atLimit = activeGoals.length >= MAX_ACTIVE_GOALS;

  async function createGoal(goalType: GoalType, value: number, date: string) {
    setSubmitting(true);
    setError(null);
    try {
      const body: CreateGoalRequest = { goal_type: goalType, target_value: value, target_date: date || null };
      await api.post<Goal>("/talents/goals", body);
      trackEvent("goal_created", { goal_type: goalType });
      setAddingType("");
      setTargetDate("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create that goal.");
    } finally {
      setSubmitting(false);
    }
  }

  async function abandonGoal(goalId: string) {
    setError(null);
    try {
      await api.delete(`/talents/goals/${goalId}`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not abandon that goal.");
    }
  }

  if (!goals) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Your goals</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {error ? <p className="text-sm text-destructive">{error}</p> : null}

        {activeGoals.length === 0 && completedGoals.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Set a goal to track your progress toward it right here on your dashboard.
          </p>
        ) : (
          <div className="flex flex-col gap-3">
            {activeGoals.map((g) => (
              <GoalRow key={g.id} goal={g} onAbandon={abandonGoal} />
            ))}
            {completedGoals.map((g) => (
              <GoalRow key={g.id} goal={g} onAbandon={abandonGoal} />
            ))}
          </div>
        )}

        {atLimit ? (
          <p className="text-sm text-muted-foreground">
            You have {MAX_ACTIVE_GOALS} active goals. Abandon one above to add a new one.
          </p>
        ) : addingType ? (
          <div className="flex flex-col gap-3 rounded-lg border border-border p-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="goalTarget">
                Target {addingType === "earnings_total" ? "(dollars)" : addingType === "profile_completeness" ? "(%)" : ""}
              </Label>
              <Input
                id="goalTarget"
                type="number"
                min={1}
                value={addingType === "earnings_total" ? targetValue / 100 : targetValue}
                onChange={(e) => {
                  const n = Number(e.target.value);
                  setTargetValue(addingType === "earnings_total" ? Math.round(n * 100) : n);
                }}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="goalDate">Target date (optional)</Label>
              <Input id="goalDate" type="date" value={targetDate} onChange={(e) => setTargetDate(e.target.value)} />
            </div>
            <div className="flex gap-2">
              <Button
                type="button"
                disabled={submitting}
                onClick={() => createGoal(addingType, targetValue, targetDate)}
                className="flex-1"
              >
                Add goal
              </Button>
              <Button type="button" variant="outline" onClick={() => setAddingType("")}>
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-2">
            {(Object.keys(GOAL_TYPE_LABELS) as GoalType[]).map((type) => (
              <button
                key={type}
                type="button"
                onClick={() => {
                  setAddingType(type);
                  setTargetValue(DEFAULT_TARGETS[type]);
                }}
                className="rounded-lg border border-border p-2 text-left text-sm font-medium hover:border-primary/40"
              >
                {GOAL_TYPE_LABELS[type]}
              </button>
            ))}
          </div>
        )}

        {!atLimit && suggestions.length > 0 ? (
          <div className="flex flex-col gap-2 border-t border-border pt-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Goals to consider</p>
            <div className="flex flex-col gap-2">
              {suggestions.map((s) => (
                <div key={s.goal_type} className="flex items-center justify-between gap-2 rounded-lg border border-border p-2">
                  <span className="text-sm">{s.label}</span>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={submitting}
                    onClick={() => createGoal(s.goal_type, s.suggested_target_value, "")}
                  >
                    Add
                  </Button>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
