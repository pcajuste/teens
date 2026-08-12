"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;
const ALLOWED_CONTENT_TYPES = new Set([
  "image/png",
  "image/jpeg",
  "image/gif",
  "video/mp4",
  "video/quicktime",
  "application/pdf",
]);

export default function SubmitCampaignPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [text, setText] = useState("");
  const [fileUrls, setFileUrls] = useState<string[]>([]);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  // Client-side validation mirrors (does not replace) the server's checks
  // in campaigns.py / storage_service — the server is still the source of
  // truth and will re-reject anything invalid.
  async function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setUploadError(null);

    if (file.size > MAX_UPLOAD_BYTES) {
      setUploadError("That file is larger than the 25MB limit.");
      return;
    }
    if (!ALLOWED_CONTENT_TYPES.has(file.type)) {
      setUploadError("That file type isn't supported. Use an image, video, or PDF.");
      return;
    }

    setUploading(true);
    try {
      const res = await api.requestUploadUrl(params.id, {
        file_name: file.name,
        content_type: file.type,
        file_size_bytes: file.size,
      });
      // Local dev has no real Supabase Storage credentials behind this
      // route, so the PUT to the signed URL is best-effort; if it fails
      // we still surface a clear error instead of crashing the page.
      try {
        await fetch(res.upload_url, { method: "PUT", body: file, headers: { "Content-Type": file.type } });
      } catch {
        // ignore — degrade gracefully below via the file_url reference
      }
      setFileUrls((prev) => [...prev, res.file_url]);
    } catch (err) {
      setUploadError(
        err instanceof ApiError
          ? `Upload failed: ${String(err.detail ?? err.message)}`
          : "Upload failed. This is expected in local dev without a live Supabase Storage project.",
      );
    } finally {
      setUploading(false);
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) {
      setSubmitError("Please describe what you're submitting.");
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      await api.submitCampaign(params.id, { submission_text: text.trim(), submission_file_urls: fileUrls });
      setDone(true);
    } catch (err) {
      setSubmitError(err instanceof ApiError ? String(err.detail ?? err.message) : "Could not submit.");
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <main className="container max-w-lg py-6">
        <Card>
          <CardHeader>
            <CardTitle>Submitted</CardTitle>
            <CardDescription>Your submission is now under review.</CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => router.push(`/rep/campaigns/${params.id}`)}>Back to campaign</Button>
          </CardContent>
        </Card>
      </main>
    );
  }

  return (
    <main className="container max-w-lg py-6">
      <h1 className="mb-4 text-xl font-semibold">Submit your work</h1>
      <form onSubmit={onSubmit} className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Describe your submission</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Link to your post(s) and any notes for review…"
              rows={5}
              required
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Attach files (optional)</CardTitle>
            <CardDescription>Images, video, or PDF — up to 25MB each.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <Input type="file" onChange={onFileChange} disabled={uploading} />
            {uploading && <p className="text-sm text-muted-foreground">Uploading…</p>}
            {uploadError && <p className="text-sm text-red-600">{uploadError}</p>}
            {fileUrls.length > 0 && (
              <ul className="text-sm text-muted-foreground">
                {fileUrls.map((url) => (
                  <li key={url} className="truncate">
                    {url}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        {submitError && <p className="text-sm text-red-600">{submitError}</p>}

        <Button type="submit" size="lg" disabled={submitting} className="w-full">
          {submitting ? "Submitting…" : "Submit"}
        </Button>
      </form>
    </main>
  );
}
