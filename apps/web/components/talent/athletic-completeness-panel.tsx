import Link from "next/link";
import type { AthleticSeason, NilEligibility, SportProfile } from "@/lib/types";

interface ChecklistItem {
  label: string;
  points: number;
  done: boolean;
  href: string;
}

/**
 * ATHLETICS-6 dashboard checklist, parallel to the brand track's
 * CompletenessPanel. The five items map 1:1 to the weights the backend
 * uses to compute athletic_completeness_score (recompute_all_completeness_scores /
 * ATHLETICS-4) -- there is no per-item breakdown in the API response, so
 * "done" is derived client-side from the same underlying data
 * (sport profiles / seasons / nil) the score is computed from.
 */
function buildChecklist(
  sportProfiles: SportProfile[],
  seasons: AthleticSeason[],
  nil: NilEligibility | null
): ChecklistItem[] {
  const hasSportProfile = sportProfiles.length > 0;
  const hasGpa = sportProfiles.some((sp) => sp.gpa !== null);
  const hasAttestedSeason = seasons.some((s) => s.status === "attested" || s.status === "verified");
  const hasFilmUrl = sportProfiles.some((sp) => !!sp.hudl_url || !!sp.maxpreps_url);
  const nilAcknowledged = !!nil?.school_association_rules_acknowledged;

  return [
    { label: "Sport profile set up", points: 30, done: hasSportProfile, href: "/talent/athletics/sports" },
    { label: "GPA added", points: 20, done: hasGpa, href: "/talent/athletics/sports" },
    { label: "Season attested", points: 20, done: hasAttestedSeason, href: "/talent/athletics/seasons" },
    { label: "Film URL added", points: 15, done: hasFilmUrl, href: "/talent/athletics/sports" },
    { label: "NIL rules acknowledged", points: 15, done: nilAcknowledged, href: "/talent/athletics/nil" },
  ];
}

export function AthleticCompletenessPanel({
  score,
  sportProfiles,
  seasons,
  nil,
}: {
  score: number;
  sportProfiles: SportProfile[];
  seasons: AthleticSeason[];
  nil: NilEligibility | null;
}) {
  const checklist = buildChecklist(sportProfiles, seasons, nil);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">Athletic completeness</p>
        <p className="text-sm font-semibold">{score}%</p>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-teal transition-[width]"
          style={{ width: `${score}%` }}
        />
      </div>
      <ul className="flex flex-col gap-1.5">
        {checklist.map((item) => (
          <li key={item.label}>
            {item.done ? (
              <span className="flex min-h-[44px] items-center gap-2 text-sm text-muted-foreground">
                <span className="text-green" aria-hidden="true">
                  ✓
                </span>
                {item.label}{" "}
                <span className="text-xs text-muted-foreground">({item.points} pts)</span>
              </span>
            ) : (
              <Link
                href={item.href}
                className="flex min-h-[44px] items-center gap-2 text-sm font-medium text-teal hover:underline"
              >
                <span aria-hidden="true">○</span>
                {item.label}{" "}
                <span className="text-xs text-muted-foreground">({item.points} pts)</span>
              </Link>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
