"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

/**
 * STUB, PER THE BUILD PROMPT'S OWN INSTRUCTION.
 *
 * Prompt 6's inbox deliverable reads from a recruiter-contact endpoint
 * that Prompt 11 (Recruiter Portal — Backend) builds later in the build
 * sequence. Per CLAUDE.md's mandatory phase order (Rep Portal before
 * Recruiter Portal) and the prompt text itself ("stub deliverable 6 with
 * static/seeded data until Prompt 11 lands"), this screen intentionally
 * uses hardcoded seed data below instead of a real API call. When Prompt
 * 11 ships a GET /reps/me/messages-style endpoint and a "mark read"
 * mechanism, swap SEED_MESSAGES for a real fetch and wire up onOpen to
 * call that mark-read endpoint.
 *
 * This is also read-only by design (Section 1A): there is no reply box,
 * reply button, or compose affordance anywhere in this file, because
 * there is no backing column or endpoint for a rep-authored reply.
 */
interface SeedMessage {
  id: string;
  senderInstitution: string;
  preview: string;
  body: string;
  sentAt: string;
  read: boolean;
}

const SEED_MESSAGES: SeedMessage[] = [
  {
    id: "seed-1",
    senderInstitution: "Ashcombe University — Admissions",
    preview: "We came across your verified achievement record and would love to learn more...",
    body: "Hi! We came across your verified achievement record through Teenure and would love to learn more about your work with local brands. Feel free to include a link to your profile in future applications.",
    sentAt: "2026-08-05T14:32:00Z",
    read: true,
  },
  {
    id: "seed-2",
    senderInstitution: "Northfield Tech Institute — Recruiting",
    preview: "Your campaign history in the tech category caught our eye...",
    body: "Your campaign history in the tech category caught our eye. We host a summer program for students with hands-on brand or project experience — details are on our site if you're interested.",
    sentAt: "2026-08-08T09:10:00Z",
    read: false,
  },
  {
    id: "seed-3",
    senderInstitution: "Rivermont College — Office of Admissions",
    preview: "Congratulations on completing your recent campaigns...",
    body: "Congratulations on completing your recent campaigns! Verified extracurricular achievement like this is something our admissions committee values highly. We'd encourage you to apply this cycle.",
    sentAt: "2026-08-10T18:00:00Z",
    read: false,
  },
];

export default function InboxPage() {
  const [messages, setMessages] = useState(SEED_MESSAGES);
  const [openId, setOpenId] = useState<string | null>(null);

  function open(id: string) {
    setOpenId((prev) => (prev === id ? null : id));
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, read: true } : m)));
  }

  return (
    <main className="container max-w-lg space-y-4 py-6">
      <h1 className="text-xl font-semibold">Inbox</h1>
      <p className="text-sm text-muted-foreground">
        Messages from recruiters who found your profile. This is read-only — there&apos;s no way to reply from
        Teenure.
      </p>
      <div className="space-y-2">
        {messages.map((m) => (
          <Card key={m.id} className="cursor-pointer" onClick={() => open(m.id)}>
            <CardHeader>
              <div className="flex items-center justify-between gap-2">
                <CardTitle className="text-sm">{m.senderInstitution}</CardTitle>
                {!m.read && <Badge>New</Badge>}
              </div>
              <CardDescription>{new Date(m.sentAt).toLocaleDateString()}</CardDescription>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              {openId === m.id ? m.body : m.preview}
            </CardContent>
          </Card>
        ))}
      </div>
    </main>
  );
}
