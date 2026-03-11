import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";
import { fetchJsonOrNull } from "@/lib/fetch";
import { formatCount, formatConfidence, formatUsd, humanizeStatus } from "@/lib/humanize";

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
  summary?: {
    total_ideas: number;
    total_actual_value: number;
    total_value_gap: number;
  };
};

type FlowResponse = {
  summary?: {
    ideas: number;
    with_spec: number;
    with_process: number;
    with_implementation: number;
    with_validation: number;
    blocked_ideas: number;
  };
};

type AgentTask = {
  id: string;
  status: string;
};

type TaskListPayload =
  | AgentTask[]
  | {
      tasks?: AgentTask[];
      items?: AgentTask[];
    };

export const metadata: Metadata = {
  title: "Demo MVP",
  description: "Guided 5-minute MVP demo path from idea selection to measurable progress and execution proof.",
};

function extractTasks(payload: TaskListPayload | null): AgentTask[] {
  if (!payload) return [];
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload.tasks)) return payload.tasks;
  if (Array.isArray(payload.items)) return payload.items;
  return [];
}

export default async function DemoMvpPage() {
  const apiBase = getApiBase();
  const [ideasData, flowData, taskData] = await Promise.all([
    fetchJsonOrNull<IdeasResponse>(`${apiBase}/api/ideas`, { cache: "no-store" }, 5000),
    fetchJsonOrNull<FlowResponse>(`${apiBase}/api/inventory/flow?runtime_window_seconds=86400`, { cache: "no-store" }, 5000),
    fetchJsonOrNull<TaskListPayload>(`${apiBase}/api/agent/tasks?limit=100`, { cache: "no-store" }, 5000),
  ]);

  const ideas = [...(ideasData?.ideas ?? [])].sort((a, b) => b.free_energy_score - a.free_energy_score);
  const spotlightIdea = ideas[0] ?? null;
  const tasks = extractTasks(taskData);

  const activeStatuses = new Set(["pending", "queued", "in_progress", "running", "claimed"]);
  const activeTasks = tasks.filter((task) => activeStatuses.has(task.status)).length;
  const completedTasks = tasks.filter((task) => task.status === "completed").length;

  const flowSummary = flowData?.summary;
  const flowComplete = flowSummary
    ? Math.min(flowSummary.with_spec, flowSummary.with_process, flowSummary.with_implementation, flowSummary.with_validation)
    : 0;

  return (
    <main className="min-h-screen px-4 py-8 sm:px-6 lg:px-8">
      <div className="mx-auto w-full max-w-6xl space-y-6">
        <section className="rounded-2xl border border-border/70 bg-card/60 p-5 sm:p-7 space-y-3">
          <p className="text-sm text-muted-foreground">Demo path</p>
          <h1 className="text-3xl font-semibold tracking-tight">Demo MVP in 5 minutes</h1>
          <p className="max-w-3xl text-muted-foreground">
            Walk a single idea through discovery, progress updates, and execution proof without reading internal IDs or technical traces.
          </p>
          <div className="flex flex-wrap gap-2">
            <Link href="/ideas" className="rounded border px-3 py-1.5 text-sm hover:bg-accent">
              1. Choose idea
            </Link>
            <Link
              href={spotlightIdea ? `/ideas/${encodeURIComponent(spotlightIdea.id)}` : "/ideas"}
              className="rounded border px-3 py-1.5 text-sm hover:bg-accent"
            >
              2. Update progress
            </Link>
            <Link
              href={spotlightIdea ? `/flow?idea_id=${encodeURIComponent(spotlightIdea.id)}` : "/flow"}
              className="rounded border px-3 py-1.5 text-sm hover:bg-accent"
            >
              3. Verify flow
            </Link>
            <Link href="/tasks" className="rounded border px-3 py-1.5 text-sm hover:bg-accent">
              4. Review tasks
            </Link>
          </div>
        </section>

        <section className="grid grid-cols-2 gap-3 sm:grid-cols-4 text-sm">
          <div className="rounded-xl border p-3">
            <p className="text-muted-foreground">Ideas tracked</p>
            <p className="text-xl font-semibold">{formatCount(ideasData?.summary?.total_ideas ?? 0)}</p>
          </div>
          <div className="rounded-xl border p-3">
            <p className="text-muted-foreground">Active tasks</p>
            <p className="text-xl font-semibold">{formatCount(activeTasks)}</p>
          </div>
          <div className="rounded-xl border p-3">
            <p className="text-muted-foreground">Completed tasks</p>
            <p className="text-xl font-semibold">{formatCount(completedTasks)}</p>
          </div>
          <div className="rounded-xl border p-3">
            <p className="text-muted-foreground">Flow-complete ideas</p>
            <p className="text-xl font-semibold">{formatCount(flowComplete)}</p>
          </div>
        </section>

        <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <article className="rounded-xl border p-4 space-y-2">
            <h2 className="text-lg font-semibold">Spotlight idea</h2>
            {spotlightIdea ? (
              <>
                <p className="font-medium">{spotlightIdea.name}</p>
                <p className="text-sm text-muted-foreground">{spotlightIdea.description}</p>
                <p className="text-sm text-muted-foreground">
                  Status {humanizeStatus(spotlightIdea.manifestation_status)} | Confidence {formatConfidence(spotlightIdea.confidence)}
                </p>
                <p className="text-sm text-muted-foreground">
                  Actual value {formatUsd(spotlightIdea.actual_value)} | Remaining upside {formatUsd(spotlightIdea.value_gap)}
                </p>
                <div className="flex flex-wrap gap-2 pt-1">
                  <Link
                    href={`/ideas/${encodeURIComponent(spotlightIdea.id)}`}
                    className="rounded border px-3 py-1.5 text-sm hover:bg-accent"
                    title={`Idea ID: ${spotlightIdea.id}`}
                  >
                    Open idea detail
                  </Link>
                  <Link
                    href={`/flow?idea_id=${encodeURIComponent(spotlightIdea.id)}`}
                    className="rounded border px-3 py-1.5 text-sm hover:bg-accent"
                    title={`Idea ID: ${spotlightIdea.id}`}
                  >
                    Open flow trail
                  </Link>
                </div>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">No idea data available yet. Start by creating or importing ideas.</p>
            )}
          </article>

          <article className="rounded-xl border p-4 space-y-2">
            <h2 className="text-lg font-semibold">Demo checklist</h2>
            <ol className="list-decimal list-inside space-y-2 text-sm text-muted-foreground">
              <li>Open Ideas and choose one high-upside item.</li>
              <li>Update actual value/cost and confidence on the idea detail page.</li>
              <li>Create the next task from the idea detail page to start execution.</li>
              <li>Open Flow and confirm spec/process/implementation visibility.</li>
              <li>Open Tasks and update one task status to confirm the loop closes in-app.</li>
              <li>Capture one screenshot set for desktop and mobile readiness review.</li>
            </ol>
            <p className="text-xs text-muted-foreground">
              API target for this demo: <span className="font-mono">{apiBase}</span>
            </p>
          </article>
        </section>
      </div>
    </main>
  );
}
