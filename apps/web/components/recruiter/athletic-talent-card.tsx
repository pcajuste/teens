"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { SPORT_LABELS, type SupportedSport } from "@/lib/sports";
import type { AthleticRecruiterSearchCard } from "@/lib/types";

interface AthleticTalentCardProps {
  card: AthleticRecruiterSearchCard;
  onViewProfile: (talentId: string) => void;
  onSave: (talentId: string) => void;
}

// ATHLETICS-7 deliverable 1: no PII, same rule as the brand talent
// card -- no display_name, school_name, or bio anywhere in this
// component.
export function AthleticTalentCard({ card, onViewProfile, onSave }: AthleticTalentCardProps) {
  return (
    <Card className="hover:shadow-md">
      <CardContent>
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="font-semibold">
              {card.city}, {card.state}
            </p>
            <p className="text-sm text-text-2">Class of {card.graduation_year}</p>
          </div>
          {card.school_type ? <Badge variant="pending">{card.school_type}</Badge> : null}
        </div>

        <div className="mt-2 flex flex-wrap gap-1">
          {card.sports.map((s) => (
            <Badge key={s} variant="active">
              {SPORT_LABELS[s as SupportedSport] ?? s}
            </Badge>
          ))}
        </div>

        {card.top_sport_positions.length > 0 ? (
          <p className="mt-2 text-sm text-text-2">{card.top_sport_positions.join(" / ")}</p>
        ) : null}

        <div className="mt-3 flex items-center gap-4 text-sm text-text-2">
          <span>{card.athletic_seasons_completed} seasons</span>
          <span>{card.athletic_completeness_score}% complete</span>
          {card.has_film_url ? (
            <span title="Film available" aria-label="Film available">
              🎬
            </span>
          ) : null}
        </div>

        {card.athletic_recruiter_interest_count > 0 ? (
          <Badge variant="secondary" className="mt-2">
            {card.athletic_recruiter_interest_count} interested
          </Badge>
        ) : null}

        <div className="mt-4 flex gap-2">
          <Button type="button" size="sm" onClick={() => onViewProfile(card.talent_id)}>
            View full profile
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={() => onSave(card.talent_id)}>
            Save
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
