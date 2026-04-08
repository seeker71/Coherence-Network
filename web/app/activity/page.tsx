import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";
import { withWorkspaceScope } from "@/lib/workspace";
import { getActiveWorkspaceFromCookie } from "@/lib/workspace-server";

export const metadata: Metadata = {
  title: "Activity",
  description: "Workspace activity feed.",
};

type ActivityEvent = {
  id: string;
  event_type: string;
  workspace_id: string;
  actor_contributor_id: string | null;
  subject_type: string | null;
  subject_id: string | null;
  subject_name: string | null;
  summary: string;
  created_at: string;
};

type ActivityFeedResponse = {
  workspace_id: string;
  events: ActivityEvent[];
  total: number;
  has_more: boolean;
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

function eventTypeBadgeClass(eventType: string): string {
  if (eventType.startsWith("idea_")) return "bg-blue-500/10 text-blue-500";
  if (eventType.startsWith("spec_")) return "bg-purple-500/10 text-purple-500";
  if (eventType.startsWith("task_")) return "bg-amber-500/10 text-amber-500";
  if (eventType.startsWith("member_")) return "bg-green-500/10 text-green-500";
  if (eventType.startsWith("project_")) return "bg-teal-500/10 text-teal-500";
  if (eventType.startsWith("message_")) return "bg-pink-500/10 text-pink-500";
  if (eventType.startsWith("contribution_"))
    return "bg-emerald-500/10 text-emerald-500";
  if (eventType.startsWith("governance_"))
    return "bg-indigo-500/10 text-indigo-500";
  return "bg-muted text-muted-foreground";
}

function formatEventType(eventType: string): string {
  return eventType.replace(/_/g, " ");
}

function subjectLink(event: ActivityEvent): string | null {
  if (!event.subject_type || !event.subject_id) return null;
  switch (event.subject_type) {
    case "idea":
      return `/ideas/${encodeURIComponent(event.subject_id)}`;
    case "spec":
      return `/specs/${encodeURIComponent(event.subject_id)}`;
    case "task":
      return `/tasks?task_id=${encodeURIComponent(event.subject_id)}`;
    case "contributor":
      return `/contributors?contributor_id=${encodeURIComponent(event.subject_id)}`;
    case "project":
      return `/projects/${encodeURIComponent(event.subject_id)}`;
    default:
      return null;
  }
}

export default async function ActivityPage() {
  const API = getApiBase();
  const workspaceId = await getActiveWorkspaceFromCookie();
  let data: ActivityFeedResponse | null = null;
  let error: string | null = null;

  try {
    const url = withWorkspaceScope(
      `${API}/api/workspaces/coherence-network/activity?limit=50`,
      workspaceId,
    );
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = (await res.json()) as ActivityFeedResponse;
  } catch (e) {
    error = String(e);
  }

  const events = data?.events ?? [];

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-5xl mx-auto space-y-8">
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 sm:p-7 space-y-3">
        <p className="text-sm text-muted-foreground">Workspace</p>
        <h1 className="text-3xl md:text-4xl font-light tracking-tight">
          Activity Feed
        </h1>
        <p className="max-w-3xl text-muted-foreground">
          Recent events across the workspace. Ideas created, specs added, tasks
          completed, and more.
        </p>
        <div className="flex flex-wrap gap-2">
          <Link
            href="/teams"
            className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200"
          >
            Team
          </Link>
          <Link
            href="/messages"
            className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200"
          >
            Messages
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
          Could not load activity: {error}
        </p>
      ) : null}

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            {events.length} events{data?.has_more ? " (more available)" : ""}
          </p>
          <p className="text-xs text-muted-foreground">
            Total: {data?.total ?? 0}
          </p>
        </div>

        {events.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No activity recorded for this workspace yet.
          </p>
        ) : (
          <div className="relative">
            {/* Timeline line */}
            <div className="absolute left-3 top-0 bottom-0 w-px bg-border/40" />

            <ul className="space-y-3 text-sm">
              {events.map((event) => {
                const href = subjectLink(event);
                return (
                  <li key={event.id} className="relative pl-8">
                    {/* Timeline dot */}
                    <div className="absolute left-[9px] top-3 h-1.5 w-1.5 rounded-full bg-muted-foreground/60" />

                    <div className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-1.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${eventTypeBadgeClass(event.event_type)}`}
                        >
                          {formatEventType(event.event_type)}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {formatTimestamp(event.created_at)}
                        </span>
                      </div>

                      <p className="text-foreground">{event.summary}</p>

                      <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                        {event.actor_contributor_id ? (
                          <Link
                            href={`/contributors?contributor_id=${encodeURIComponent(event.actor_contributor_id)}`}
                            className="hover:underline hover:text-foreground"
                          >
                            {event.actor_contributor_id}
                          </Link>
                        ) : null}
                        {href ? (
                          <Link
                            href={href}
                            className="hover:underline hover:text-foreground"
                          >
                            {event.subject_name || event.subject_id}
                          </Link>
                        ) : null}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </section>
    </main>
  );
}
