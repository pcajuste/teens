"use client";

import { useState } from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { SPORT_STATS_FIELDS, type SupportedSport } from "@/lib/sports";

interface SportStatsFormProps {
  sport: string;
  value: Record<string, unknown>;
  onChange: (next: Record<string, unknown>) => void;
  /** Inline 422 message from the server (invalid_sport_stats), if any. */
  serverError?: string | null;
}

/**
 * Renders the sport-specific stats form driven by SPORT_STATS_FIELDS.
 * Unknown sport types (the "other" schema bucket, or any sport string
 * not in SUPPORTED_SPORTS) fall back to a single JSON text field per
 * the ATHLETICS-6 spec ("Unknown sport type ('other'): a single JSON
 * text field with validation warning"), shared between the sport
 * profile form and the season creation form (both call PUT/POST with a
 * sport_stats object shaped the same way).
 */
export function SportStatsForm({ sport, value, onChange, serverError }: SportStatsFormProps) {
  const fields = SPORT_STATS_FIELDS[sport as SupportedSport];
  const [rawJson, setRawJson] = useState(() => JSON.stringify(value, null, 2));
  const [jsonError, setJsonError] = useState<string | null>(null);

  if (!fields) {
    return (
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="sport_stats_json">Stats (JSON)</Label>
        <p className="text-xs text-muted-foreground">
          This sport doesn&apos;t have a structured form yet -- enter stats as JSON, e.g.{" "}
          {'{"event": "shot put", "personal_best": "42ft"}'}.
        </p>
        <Textarea
          id="sport_stats_json"
          rows={5}
          value={rawJson}
          onChange={(e) => {
            const text = e.target.value;
            setRawJson(text);
            try {
              const parsed = text.trim() ? JSON.parse(text) : {};
              setJsonError(null);
              onChange(parsed);
            } catch {
              setJsonError("Not valid JSON yet -- keep typing or fix a stray comma/quote.");
            }
          }}
        />
        {jsonError ? <p className="text-xs text-warning-foreground">{jsonError}</p> : null}
        {serverError ? <p className="text-sm text-destructive">{serverError}</p> : null}
      </div>
    );
  }

  function setField(key: string, fieldValue: unknown) {
    onChange({ ...value, [key]: fieldValue });
  }

  return (
    <div className="flex flex-col gap-3">
      {fields.map((f) => {
        const current = value[f.key];
        if (f.type === "bool") {
          return (
            <label key={f.key} className="flex min-h-[44px] items-center gap-2 text-sm">
              <Checkbox
                checked={current === true}
                onCheckedChange={(checked) => setField(f.key, checked === true)}
              />
              {f.label}
            </label>
          );
        }
        if (f.type === "str") {
          return (
            <div key={f.key} className="flex flex-col gap-1.5">
              <Label htmlFor={`stat-${f.key}`}>{f.label}</Label>
              <Input
                id={`stat-${f.key}`}
                value={typeof current === "string" ? current : ""}
                onChange={(e) => setField(f.key, e.target.value)}
              />
            </div>
          );
        }
        // int/float
        return (
          <div key={f.key} className="flex flex-col gap-1.5">
            <Label htmlFor={`stat-${f.key}`}>
              {f.label}
              {f.min !== null && f.max !== null ? (
                <span className="ml-1 text-xs font-normal text-muted-foreground">
                  ({f.min}–{f.max})
                </span>
              ) : null}
            </Label>
            <Input
              id={`stat-${f.key}`}
              type="number"
              inputMode="decimal"
              step={f.type === "float" ? "any" : 1}
              min={f.min ?? undefined}
              max={f.max ?? undefined}
              value={typeof current === "number" ? current : ""}
              onChange={(e) => {
                const raw = e.target.value;
                if (raw === "") {
                  const next = { ...value };
                  delete next[f.key];
                  onChange(next);
                  return;
                }
                setField(f.key, f.type === "int" ? parseInt(raw, 10) : parseFloat(raw));
              }}
            />
          </div>
        );
      })}
      {serverError ? <p className="text-sm text-destructive">{serverError}</p> : null}
    </div>
  );
}
