import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";
import { withWorkspaceScope } from "@/lib/workspace";
import { getActiveWorkspaceFromCookie } from "@/lib/workspace-server";

export const metadata: Metadata = {
  title: "Messages",
  description: "Workspace message board.",
};

type Message = {
  id: string;
  from_contributor_id: string;
  to_contributor_id: string | null;
  to_workspace_id: string | null;
  subject: string | null;
  body: string;
  read: boolean;
  created_at: string;
};

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export default async function MessagesPage() {
  const API = getApiBase();
  const workspaceId = await getActiveWorkspaceFromCookie();
  let messages: Message[] = [];
  let error: string | null = null;

  try {
    const url = withWorkspaceScope(
      `${API}/api/workspaces/coherence-network/messages?limit=50`,
      workspaceId,
    );
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const json = await res.json();
    messages = Array.isArray(json) ? json : [];
  } catch (e) {
    error = String(e);
  }

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-5xl mx-auto space-y-8">
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 sm:p-7 space-y-3">
        <p className="text-sm text-muted-foreground">Workspace</p>
        <h1 className="text-3xl md:text-4xl font-light tracking-tight">
          Messages
        </h1>
        <p className="max-w-3xl text-muted-foreground">
          Messages sent to this workspace. A shared board for announcements,
          updates, and coordination.
        </p>
        <div className="flex flex-wrap gap-2">
          <Link
            href="/teams"
            className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200"
          >
            Team
          </Link>
          <Link
            href="/activity"
            className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200"
          >
            Activity
          </Link>
          <Link
            href="/projects"
            className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200"
          >
            Projects
          </Link>
        </div>
      </section>

      {error ? (
        <p className="text-sm text-destructive">
          Could not load messages: {error}
        </p>
      ) : null}

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3">
        <p className="text-sm text-muted-foreground">
          {messages.length} {messages.length === 1 ? "message" : "messages"}
        </p>

        {messages.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No messages in this workspace yet.
          </p>
        ) : (
          <ul className="space-y-3 text-sm">
            {messages.map((msg) => (
              <li
                key={msg.id}
                className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-2"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Link
                      href={`/contributors?contributor_id=${encodeURIComponent(msg.from_contributor_id)}`}
                      className="font-medium hover:underline"
                    >
                      {msg.from_contributor_id}
                    </Link>
                    {msg.subject ? (
                      <span className="text-muted-foreground">
                        &mdash; {msg.subject}
                      </span>
                    ) : null}
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {formatTimestamp(msg.created_at)}
                  </span>
                </div>
                <p className="text-muted-foreground whitespace-pre-wrap">
                  {msg.body}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
