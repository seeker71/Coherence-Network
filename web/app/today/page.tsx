import type { Metadata } from "next";
import Link from "next/link";

import TodayTopIdeaQuickLaunch from "@/components/today/TodayTopIdeaQuickLaunch";
import { getApiBase } from "@/lib/api";
import { fetchJsonOrNull } from "@/lib/fetch";
import { formatConfidence, formatCount, formatUsd, humanizeStatus } from "@/lib/humanize";

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
  description: "One-screen priority view for ideas, tasks, and immediate next actions.",
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

function deriveTaskIdea(task: Task, ideasById: Map<string, Idea>): { ideaId: string; ideaName: string } {
  const context = task.context && typeof task.context === "object" && !Array.isArray(task.context) ? task.context : null;
  const contextIdeaId = context ? String(context.idea_id || "").trim() : "";
  const contextIdeaName = context ? String(context.idea_name || "").trim() : "";

  if (contextIdeaId) {
    const lookupName = ideasById.get(contextIdeaId)?.name || "";
    return { ideaId: contextIdeaId, ideaName: contextIdeaName || lookupName || "Linked idea" };
  }
  return { ideaId: "", ideaName: "Unlinked task" };
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
        title: "Resolve the top blocked task",
        detail: shortText(blockedTasks[0].direction, 180),
        href: `/tasks?task_id=${encodeURIComponent(blockedTasks[0].id)}`,
        cta: "Open blocked task",
      }
    : activeTasks[0]
      ? {
          title: "Update progress on an active task",
          detail: shortText(activeTasks[0].direction, 180),
          href: `/tasks?task_id=${encodeURIComponent(activeTasks[0].id)}`,
          cta: "Update task now",
        }
      : topIdea
        ? {
            title: "Create the next task from your top idea",
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
    <main className="min-h-screen px-4 py-8 sm:px-6 lg:px-8">
      <div className="mx-auto w-full max-w-6xl space-y-6">
        <section className="rounded-2xl border border-border/70 bg-card/60 p-5 sm:p-7 space-y-3">
          <p className="text-sm text-muted-foreground">Daily execution view</p>
          <h1 className="text-3xl font-semibold tracking-tight">Today's Priorities</h1>
          <p className="max-w-3xl text-muted-foreground">
            One screen for what to do next: key idea opportunities, task pressure, and direct links to act.
          </p>
          <div className="flex flex-wrap gap-2">
            <Link href="/ideas" className="rounded border px-3 py-1.5 text-sm hover:bg-accent">
              Ideas
            </Link>
            <Link href="/tasks" className="rounded border px-3 py-1.5 text-sm hover:bg-accent">
              Tasks In Motion
            </Link>
            <Link href="/flow" className="rounded border px-3 py-1.5 text-sm hover:bg-accent">
              Flow
            </Link>
            <Link href="/demo" className="rounded border px-3 py-1.5 text-sm hover:bg-accent">
              Demo Path
            </Link>
          </div>
        </section>

        <section className="grid grid-cols-2 gap-3 sm:grid-cols-4 text-sm">
          <div className="rounded-xl border p-3">
            <p className="text-muted-foreground">Ideas in focus</p>
            <p className="text-xl font-semibold">{formatCount(topIdeas.length)}</p>
          </div>
          <div className="rounded-xl border p-3">
            <p className="text-muted-foreground">Active tasks</p>
            <p className="text-xl font-semibold">{formatCount(activeTasks.length)}</p>
          </div>
          <div className="rounded-xl border p-3">
            <p className="text-muted-foreground">Blocked tasks</p>
            <p className="text-xl font-semibold">{formatCount(blockedTasks.length)}</p>
          </div>
          <div className="rounded-xl border p-3">
            <p className="text-muted-foreground">Top idea upside</p>
            <p className="text-xl font-semibold">{formatUsd(topIdea?.value_gap || 0)}</p>
          </div>
        </section>

        <section className="rounded-xl border p-4 space-y-2">
          <h2 className="text-lg font-semibold">Start Here</h2>
          <p className="font-medium">{mainNextAction.title}</p>
          <p className="text-sm text-muted-foreground">{mainNextAction.detail}</p>
          <Link href={mainNextAction.href} className="inline-block rounded border px-3 py-1.5 text-sm hover:bg-accent">
            {mainNextAction.cta}
          </Link>
        </section>

        {topIdea ? (
          <TodayTopIdeaQuickLaunch ideaId={topIdea.id} ideaName={topIdea.name} />
        ) : null}

        <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <article className="rounded-xl border p-4 space-y-3">
            <h2 className="text-lg font-semibold">Top Ideas To Move Today</h2>
            {topIdeas.length === 0 ? (
              <p className="text-sm text-muted-foreground">No ideas available yet.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {topIdeas.map((idea) => (
                  <li key={idea.id} className="rounded border p-3 space-y-1">
                    <Link
                      href={`/ideas/${encodeURIComponent(idea.id)}`}
                      className="font-medium underline hover:text-foreground"
                      title={`Idea ID: ${idea.id}`}
                    >
                      {idea.name}
                    </Link>
                    <p className="text-muted-foreground">{shortText(idea.description, 140)}</p>
                    <p className="text-muted-foreground">
                      {humanizeStatus(idea.manifestation_status)} | Confidence {formatConfidence(idea.confidence)} | Remaining upside {formatUsd(idea.value_gap)}
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <Link href={`/ideas/${encodeURIComponent(idea.id)}`} className="underline hover:text-foreground" title={`Idea ID: ${idea.id}`}>
                        Open idea
                      </Link>
                      <Link href={`/flow?idea_id=${encodeURIComponent(idea.id)}`} className="underline hover:text-foreground" title={`Idea ID: ${idea.id}`}>
                        Open flow
                      </Link>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </article>

          <article className="rounded-xl border p-4 space-y-3">
            <h2 className="text-lg font-semibold">Tasks Requiring Attention</h2>
            {tasksToReview.length === 0 ? (
              <p className="text-sm text-muted-foreground">No tasks available yet.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {tasksToReview.map((task) => (
                  <li key={task.id} className="rounded border p-3 space-y-1">
                    <Link
                      href={`/tasks?task_id=${encodeURIComponent(task.id)}`}
                      className="font-medium underline hover:text-foreground"
                      title={`Task ID: ${task.id}`}
                    >
                      {humanizeStatus(task.status)} {task.task_type} task
                    </Link>
                    <p className="text-muted-foreground">{shortText(task.direction, 140)}</p>
                    <p className="text-muted-foreground">
                      Idea {task.ideaName}
                      {task.ideaId ? (
                        <>
                          {" "}|{" "}
                          <Link
                            href={`/ideas/${encodeURIComponent(task.ideaId)}`}
                            className="underline hover:text-foreground"
                            title={`Idea ID: ${task.ideaId}`}
                          >
                            Open idea
                          </Link>
                        </>
                      ) : null}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </article>
        </section>

        <p className="text-xs text-muted-foreground">
          API target for this page: <span className="font-mono">{apiBase}</span>
        </p>
      </div>
    </main>
  );
}
