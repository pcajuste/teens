"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CATEGORY_LABELS, type Category } from "@/lib/categories";
import { api, ApiError } from "@/lib/api";
import type { AchievementRecord } from "@/lib/types";

// Fetches GET /reps/me/achievement-record, which wraps the exact same
// data as GET /reps/me/profile-preview (see AchievementRecordResponse
// in apps/api/app/schemas/reps.py) -- this page just renders it as a
// clean, printable document. There is no server-side PDF generation:
// the rep uses their browser's native "Print > Save as PDF", which is
// enough for MVP scope and avoids adding a PDF dependency to apps/api.
export default function AchievementRecordPage() {
  const [data, setData] = useState<AchievementRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<AchievementRecord>("/reps/me/achievement-record")
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load achievement record."));
  }, []);

  const record = data?.record;

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col gap-6 p-6 print:p-0">
      <div className="flex items-center justify-between print:hidden">
        <h1 className="text-xl font-semibold">Teenure Achievement Record</h1>
        <div className="flex items-center gap-4">
          <Link href="/rep/profile-preview" className="text-sm font-medium underline">
            Back
          </Link>
          {record ? (
            <button
              type="button"
              onClick={() => window.print()}
              className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground"
            >
              Print / Save as PDF
            </button>
          ) : null}
        </div>
      </div>

      {error ? <p className="text-sm text-destructive print:hidden">{error}</p> : null}

      {record ? (
        <article className="flex flex-col gap-5 rounded-lg border border-border p-6 print:border-0 print:p-0">
          <header className="border-b border-border pb-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              Teenure Achievement Record
            </p>
            <h2 className="text-2xl font-semibold">{record.display_name || "Unnamed rep"}</h2>
            <p className="text-sm text-muted-foreground">
              {record.school_name || "No school listed"}
              {record.graduation_year ? ` · Class of ${record.graduation_year}` : ""}
            </p>
            <p className="text-sm text-muted-foreground">
              {record.city}
              {record.state ? `, ${record.state}` : ""}
            </p>
            <p className="mt-2 text-xs text-muted-foreground">
              Generated {new Date(data.generated_at).toLocaleDateString()} · every entry below is
              confirmed by the brand that ran the campaign, not self-reported.
            </p>
          </header>

          {record.bio ? <p className="text-sm">{record.bio}</p> : null}

          {record.categories.length > 0 ? (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Categories
              </p>
              <p className="mt-1 text-sm">
                {record.categories.map((c) => CATEGORY_LABELS[c as Category] ?? c).join(", ")}
              </p>
            </div>
          ) : null}

          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-lg border border-border p-3 print:border">
              <p className="text-xs text-muted-foreground">Campaigns completed</p>
              <p className="text-lg font-semibold">{record.total_campaigns_completed}</p>
            </div>
            <div className="rounded-lg border border-border p-3 print:border">
              <p className="text-xs text-muted-foreground">Average brand rating</p>
              <p className="text-lg font-semibold">{record.average_rating?.toFixed(1) ?? "—"}</p>
            </div>
          </div>

          <footer className="border-t border-border pt-3 text-xs text-muted-foreground">
            Verified via teenure.com. This record reflects only brand-confirmed campaigns -- no
            self-reported claims, no public posts.
          </footer>
        </article>
      ) : null}
    </main>
  );
}
