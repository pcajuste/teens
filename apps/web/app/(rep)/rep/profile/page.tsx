"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { ProfilePreview } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

/**
 * "Preview mode": renders from GET /reps/me/profile-preview, the exact
 * same serializer a brand/recruiter sees — not a re-derived view — so a
 * rep can genuinely verify what's public before opting into recruiter
 * visibility.
 */
export default function ProfilePreviewPage() {
  const [preview, setPreview] = useState<ProfilePreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getProfilePreview()
      .then(setPreview)
      .catch((err) => setError(err instanceof ApiError ? String(err.detail ?? err.message) : "Could not load your profile preview."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="container max-w-lg space-y-4 py-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Your profile</h1>
        <Link href="/rep/profile/edit">
          <Button variant="outline" size="sm">
            Edit
          </Button>
        </Link>
      </div>
      <p className="text-sm text-muted-foreground">
        This is exactly what a brand or recruiter sees — no more, no less.
      </p>

      {loading && <p className="text-muted-foreground">Loading…</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {preview && (
        <Card>
          <CardHeader>
            <CardTitle>{preview.display_name}</CardTitle>
            <CardDescription>
              {preview.school_name} · {preview.city}, {preview.state} · Class of {preview.graduation_year}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {preview.bio && <p className="text-sm">{preview.bio}</p>}
            <div className="flex flex-wrap gap-1.5">
              {preview.categories.map((c) => (
                <Badge key={c} variant="muted" className="capitalize">
                  {c}
                </Badge>
              ))}
            </div>
            <div className="flex gap-4 text-sm text-muted-foreground">
              {preview.instagram_handle && <span>IG {preview.instagram_handle}</span>}
              {preview.tiktok_handle && <span>TikTok {preview.tiktok_handle}</span>}
            </div>
            <div className="flex gap-4 border-t border-border pt-3 text-sm">
              <span>{preview.total_campaigns_completed} campaigns completed</span>
              {preview.average_rating != null && <span>★ {preview.average_rating.toFixed(1)}</span>}
            </div>
          </CardContent>
        </Card>
      )}
    </main>
  );
}
