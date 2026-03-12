import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";
import { fetchJsonOrNull } from "@/lib/fetch";
import {
  formatCount,
  formatConfidence,
  formatUsd,
  humanizeIdeaPriority,
  humanizeManifestationStatus,
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
  description: "Guided 5-minute MVP demo path from choosing an idea to showing visible progress.",
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
            Walk one idea from selection to visible progress without reading internal records or system jargon.
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
            <p className="text-muted-foreground">Work in progress</p>
            <p className="text-xl font-semibold">{formatCount(activeTasks)}</p>
          </div>
          <div className="rounded-xl border p-3">
            <p className="text-muted-foreground">Finished work</p>
            <p className="text-xl font-semibold">{formatCount(completedTasks)}</p>
          </div>
          <div className="rounded-xl border p-3">
            <p className="text-muted-foreground">Ideas with full story visible</p>
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
                  Why it stands out now: {humanizeIdeaPriority(spotlightIdea.free_energy_score)} | {humanizeManifestationStatus(spotlightIdea.manifestation_status)}
                </p>
                <p className="text-sm text-muted-foreground">
                  Confidence {formatConfidence(spotlightIdea.confidence)} | Value still available {formatUsd(spotlightIdea.value_gap)}
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
                    Open progress trail
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
              <li>Open Ideas and choose the one that looks most worth moving next.</li>
              <li>Update what has been learned so far on the idea page.</li>
              <li>Create the next piece of work from that same page.</li>
              <li>Open Progress and confirm the path from idea to work is visible.</li>
              <li>Open Work and update one work card so the loop closes in the app.</li>
              <li>Capture desktop and mobile screens to check the story is clear.</li>
            </ol>
          </article>
        </section>
      </div>
    </main>
  );
}
