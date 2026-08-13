"use client";

import { useEffect, useState } from "react";
import { RecruiterShell } from "@/components/recruiter/recruiter-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import type { RecruiterMessage } from "@/lib/types";

export default function RecruiterMessagesPage() {
  const [messages, setMessages] = useState<RecruiterMessage[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    load();
  }, []);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const rows = await api.get<RecruiterMessage[]>("/recruiters/messages");
      setMessages(rows);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not load your messages.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <RecruiterShell
      title="Messages"
      action={
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={load}
          disabled={loading}
        >
          Refresh
        </Button>
      }
    >
      {error ? (
        <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      ) : null}

      {loading ? (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
      ) : !messages || messages.length === 0 ? (
        <EmptyState
          title="No messages sent yet"
          description="Contact a talent from search results to start a conversation. Each message costs 1 credit."
          action={
            <a href="/recruiter">
              <Button type="button" size="sm">
                Go to search
              </Button>
            </a>
          }
        />
      ) : (
        <div className="flex flex-col gap-3">
          {messages.map((m) => (
            <Card key={m.id}>
              <CardContent>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-semibold">{m.talent_display_name}</p>
                    <p className="text-xs text-muted-foreground">
                      Sent {new Date(m.messaged_at).toLocaleString()}
                    </p>
                  </div>
                  <Badge variant={m.read_at ? "success" : "secondary"}>
                    {m.read_at
                      ? `Read ${new Date(m.read_at).toLocaleDateString()}`
                      : "Not yet read"}
                  </Badge>
                </div>
                <p className="mt-2 text-sm">{m.message_text}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </RecruiterShell>
  );
}
