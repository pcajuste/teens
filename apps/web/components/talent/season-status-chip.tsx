import { Badge } from "@/components/ui/badge";
import { seasonStatusDisplay } from "@/lib/sports";
import type { AthleticSeason } from "@/lib/types";

export function SeasonStatusChip({ season }: { season: Pick<AthleticSeason, "status" | "coach_attestation_status"> }) {
  const { label, variant } = seasonStatusDisplay(season);
  // Badge has no "destructive" pill variant in the rounded/DS-named set
  // (active/earned/done/pending) -- "destructive" (red, square corners)
  // is the closest existing danger token, matching DS Section 3B's
  // "danger (red) -- flagged/disputed/fraud/compliance-concern" chip.
  return (
    <Badge variant={variant} className="min-h-[28px] px-2.5 py-1">
      {label}
    </Badge>
  );
}
