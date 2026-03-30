import type { Metadata } from "next";
import Link from "next/link";

import TodayTopIdeaQuickLaunch from "@/components/today/TodayTopIdeaQuickLaunch";
import { getApiBase } from "@/lib/api";
import { fetchJsonOrNull } from "@/lib/fetch";
import {
  explainIdeaPriority,
  formatConfidence,
  formatCount,
  formatUsd,
  humanizeIdeaPriority,
  humanizeManifestationStatus,
  humanizeStatus,
} from "@/lib/humanize";

type Idea = {
  id: string;
  name: string;
  description: string;
  potential_value: number;
  actual_value: number;
  value_gap: number;
  confidence: number;
  manifestation_status: string;
  free_energy_score: number;
};

type IdeasResponse = {
  ideas: Idea[];
};

type Task = {
  id: string;
  status: string;
  task_type: string;
  direction: string;
  output?: string | null;
  current_step?: string | null;
  context?: Record<string, unknown> | null;
};

type TaskListPayload =
  | Task[]
  | {
      tasks?: Task[];
      items?: Task[];
    };

type TaskRow = Task & {
  ideaId: string;
  ideaName: string;
};

export const metadata: Metadata = {
  title: "Today",
  description: "One-page view for the best next work, what needs attention, and how to keep progress moving.",
};

function extractTasks(payload: TaskListPayload | null): Task[] {
  if (!payload) return [];
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload.tasks)) return payload.tasks;
  if (Array.isArray(payload.items)) return payload.items;
  return [];
}

function shortText(value: string, maxLen = 140): string {
  const normalized = value.trim();
  if (normalized.length <= maxLen) return normalized;
  return `${normalized.slice(0, maxLen - 1)}...`;
}

function workTypeLabel(taskType: string): string {
  if (taskType === "impl") return "Build step";
  if (taskType === "review") return "Check-in";
  if (taskType === "spec") return "Plan";
  return "Work card";
}

function proofLabel(status: string): string {
  return humanizeManifestationStatus(status);
}

function deriveTaskIdea(task: Task, ideasById: Map<string, Idea>): { ideaId: string; ideaName: string } {
  const context = task.context && typeof task.context === "object" && !Array.isArray(task.context) ? task.context : null;
  const contextIdeaId = context ? String(context.idea_id || "").trim() : "";
  const contextIdeaName = context ? String(context.idea_name || "").trim() : "";

  if (contextIdeaId) {
    const lookupName = ideasById.get(contextIdeaId)?.name || "";
    return { ideaId: contextIdeaId, ideaName: contextIdeaName || lookupName || "Linked idea" };
  }
  return { ideaId: "", ideaName: "No linked idea yet" };
}

export default async function TodayPrioritiesPage() {
  const apiBase = getApiBase();
  const [ideasPayload, tasksPayload] = await Promise.all([
    fetchJsonOrNull<IdeasResponse>(`${apiBase}/api/ideas`, { cache: "no-store" }, 5000),
    fetchJsonOrNull<TaskListPayload>(`${apiBase}/api/agent/tasks?limit=100`, { cache: "no-store" }, 5000),
  ]);

  const ideas = ideasPayload?.ideas || [];
  const tasks = extractTasks(tasksPayload);
  const ideasById = new Map(ideas.map((idea) => [idea.id, idea]));

  const topIdeas = [...ideas].sort((a, b) => b.free_energy_score - a.free_energy_score).slice(0, 4);

  const taskRows: TaskRow[] = tasks.map((task) => {
    const linked = deriveTaskIdea(task, ideasById);
    return {
      ...task,
      ideaId: linked.ideaId,
      ideaName: linked.ideaName,
    };
  });

  const activeStatuses = new Set(["running", "pending", "claimed", "in_progress", "queued"]);
  const activeTasks = taskRows.filter((row) => activeStatuses.has(row.status));
  const blockedTasks = taskRows.filter((row) => row.status === "failed" || row.status === "needs_decision");

  const attentionPriority = (status: string): number => {
    if (status === "failed") return 0;
    if (status === "needs_decision") return 1;
    if (status === "running") return 2;
    if (status === "pending") return 3;
    return 9;
  };

  const tasksToReview = [...taskRows]
    .sort((a, b) => attentionPriority(a.status) - attentionPriority(b.status))
    .slice(0, 6);

  const topIdea = topIdeas[0] || null;
  const mainNextAction = blockedTasks[0]
    ? {
        title: "Unblock the most stuck work",
        detail: shortText(blockedTasks[0].direction, 180),
        href: `/tasks?task_id=${encodeURIComponent(blockedTasks[0].id)}`,
        cta: "Open stuck work",
      }
    : activeTasks[0]
      ? {
          title: "Check the work that is already moving",
          detail: shortText(activeTasks[0].direction, 180),
          href: `/tasks?task_id=${encodeURIComponent(activeTasks[0].id)}`,
          cta: "Open current work",
        }
      : topIdea
        ? {
            title: "Turn the best idea into the next piece of work",
            detail: shortText(topIdea.description, 180),
            href: `/ideas/${encodeURIComponent(topIdea.id)}`,
            cta: "Open top idea",
          }
        : {
            title: "No priorities yet",
            detail: "Seed demo data or create an idea to start planning today's work.",
            href: "/demo",
            cta: "Open demo path",
          };

  return (
    <main className="min-h-screen px-4 md:px-8 py-10 max-w-6xl mx-auto space-y-8">
      {/* Hero */}
      <section className="space-y-3">
        <p className="text-sm text-muted-foreground">Your one-page work view</p>
        <h1 className="text-3xl md:text-4xl font-light tracking-tight">
          What To Focus On Today
        </h1>
        <p className="max-w-3xl text-muted-foreground leading-relaxed">
          One screen for the best next work, what is blocked, and where to go to keep momentum.
        </p>
      </section>

      {/* Stats */}
      <section className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
          <p className="text-sm text-muted-foreground">Ideas to consider</p>
          <p className="text-2xl font-light text-primary">{formatCount(topIdeas.length)}</p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
          <p className="text-sm text-muted-foreground">Work in progress</p>
          <p className="text-2xl font-light text-primary">{formatCount(activeTasks.length)}</p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
          <p className="text-sm text-muted-foreground">Needs attention</p>
          <p className="text-2xl font-light text-primary">{formatCount(blockedTasks.length)}</p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
          <p className="text-sm text-muted-foreground">Best upside today</p>
          <p className="text-2xl font-light text-primary">{formatUsd(topIdea?.value_gap || 0)}</p>
        </div>
      </section>

      {/* Best Next Move */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 md:p-8 space-y-3">
        <h2 className="text-xl font-medium">Best Next Move</h2>
        <p className="font-medium text-foreground/90">{mainNextAction.title}</p>
        <p className="text-sm text-muted-foreground leading-relaxed">{mainNextAction.detail}</p>
        <Link
          href={mainNextAction.href}
          className="inline-block text-sm text-primary hover:text-foreground transition-colors duration-300"
        >
          {mainNextAction.cta} &rarr;
        </Link>
      </section>

      {topIdea ? (
        <TodayTopIdeaQuickLaunch ideaId={topIdea.id} ideaName={topIdea.name} />
      ) : null}

      {/* Two-column: Ideas + Tasks */}
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <article className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-4">
          <h2 className="text-xl font-medium">Best Places To Make Progress</h2>
          {topIdeas.length === 0 ? (
            <p className="text-sm text-muted-foreground">No ideas available yet. Once the API is running, top ideas will appear here.</p>
          ) : (
            <div className="space-y-3">
              {topIdeas.map((idea) => (
                <div key={idea.id} className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-2">
                  <Link
                    href={`/ideas/${encodeURIComponent(idea.id)}`}
                    className="font-medium hover:text-primary transition-colors duration-300"
                    title={`Idea ID: ${idea.id}`}
                  >
                    {idea.name}
                  </Link>
                  <p className="text-sm text-muted-foreground leading-relaxed">{shortText(idea.description, 140)}</p>
                  <div className="flex items-center gap-3">
                    <div className="flex-1 h-1.5 rounded-full bg-muted/40 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-primary/60"
                        style={{ width: `${Math.min(idea.confidence * 100, 100)}%` }}
                      />
                    </div>
                    <span className="text-xs text-muted-foreground whitespace-nowrap">
                      {formatConfidence(idea.confidence)}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {humanizeIdeaPriority(idea.free_energy_score)} &middot; {proofLabel(idea.manifestation_status)} &middot; {formatUsd(idea.value_gap)} available
                  </p>
                  <div className="flex flex-wrap gap-4 text-sm">
                    <Link
                      href={`/ideas/${encodeURIComponent(idea.id)}`}
                      className="text-primary hover:text-foreground transition-colors duration-300"
                      title={`Idea ID: ${idea.id}`}
                    >
                      Open idea &rarr;
                    </Link>
                    <Link
                      href={`/flow?idea_id=${encodeURIComponent(idea.id)}`}
                      className="text-muted-foreground hover:text-foreground transition-colors duration-300"
                      title={`Idea ID: ${idea.id}`}
                    >
                      View progress
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </article>

        <article className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-4">
          <h2 className="text-xl font-medium">Work That Needs Attention</h2>
          {tasksToReview.length === 0 ? (
            <p className="text-sm text-muted-foreground">No tasks available yet. Work cards appear here when tasks are created.</p>
          ) : (
            <div className="space-y-3">
              {tasksToReview.map((task) => (
                <div key={task.id} className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-2">
                  <Link
                    href={`/tasks?task_id=${encodeURIComponent(task.id)}`}
                    className="font-medium hover:text-primary transition-colors duration-300"
                    title={`Task ID: ${task.id}`}
                  >
                    {humanizeStatus(task.status)} {workTypeLabel(task.task_type)}
                  </Link>
                  <p className="text-sm text-muted-foreground leading-relaxed">{shortText(task.direction, 140)}</p>
                  <p className="text-xs text-muted-foreground">
                    Idea: {task.ideaName}
                    {task.ideaId ? (
                      <>
                        {" "}&middot;{" "}
                        <Link
                          href={`/ideas/${encodeURIComponent(task.ideaId)}`}
                          className="text-primary hover:text-foreground transition-colors duration-300"
                          title={`Idea ID: ${task.ideaId}`}
                        >
                          Open idea
                        </Link>
                      </>
                    ) : null}
                  </p>
                </div>
              ))}
            </div>
          )}
        </article>
      </section>
    </main>
  );
}
