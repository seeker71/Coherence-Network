import Link from "next/link";

import { getApiBase } from "@/lib/api";

type AgentVisibility = {
  pipeline: {
    running_count: number;
    pending_count: number;
    recent_completed_count: number;
    running_by_phase: Record<string, number>;
    attention_flags: string[];
  };
  usage: {
    by_model: Record<string, { count: number; by_status: Record<string, number> }>;
    execution?: {
      tracked_runs: number;
      failed_runs: number;
      codex_runs: number;
      by_executor: Record<string, { count: number; completed: number; failed: number }>;
      by_agent: Record<string, { count: number; completed: number; failed: number }>;
      coverage: {
        completed_or_failed_tasks: number;
        tracked_task_runs: number;
        coverage_rate: number;
        untracked_task_ids: string[];
      };
      recent_runs: Array<{
        event_id: string;
        task_id: string;
        endpoint: string;
        status_code: number;
        executor: string;
        agent_id: string;
        is_openai_codex: boolean;
        runtime_ms: number;
        recorded_at: string;
      }>;
    };
  };
  remaining_usage: {
    coverage_rate: number;
    remaining_to_full_coverage: number;
    untracked_task_ids: string[];
    health: string;
  };
};

async function loadAgentVisibility(): Promise<AgentVisibility> {
  const API = getApiBase();
  const res = await fetch(`${API}/api/agent/visibility`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`agent visibility HTTP ${res.status}`);
  }
  return (await res.json()) as AgentVisibility;
}

export default async function AgentPage() {
  const data = await loadAgentVisibility();
  const execution = data.usage.execution;
  const modelRows = Object.entries(data.usage.by_model).sort((a, b) => b[1].count - a[1].count);
  const executorRows = Object.entries(execution?.by_executor ?? {}).sort((a, b) => b[1].count - a[1].count);
  const agentRows = Object.entries(execution?.by_agent ?? {}).sort((a, b) => b[1].count - a[1].count);
  const coverage = execution?.coverage;

  return (
    <main className="min-h-screen p-8 max-w-6xl mx-auto space-y-6">
      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Home
        </Link>
        <Link href="/tasks" className="text-muted-foreground hover:text-foreground">
          Tasks
        </Link>
        <Link href="/usage" className="text-muted-foreground hover:text-foreground">
          Usage
        </Link>
        <Link href="/gates" className="text-muted-foreground hover:text-foreground">
          Gates
        </Link>
      </div>

      <h1 className="text-2xl font-bold">Agent Service Visibility</h1>
      <p className="text-muted-foreground">
        Pipeline execution status, usage telemetry, and remaining usage tracking gap for safe agent operation.
      </p>

      <section className="rounded border p-4 space-y-2 text-sm">
        <h2 className="font-semibold">Pipeline Snapshot</h2>
        <p className="text-muted-foreground">
          running {data.pipeline.running_count} | pending {data.pipeline.pending_count} | recent_completed{" "}
          {data.pipeline.recent_completed_count}
        </p>
        <p className="text-muted-foreground">
          attention_flags {data.pipeline.attention_flags.length > 0 ? data.pipeline.attention_flags.join(", ") : "none"}
        </p>
        <ul className="space-y-1">
          {Object.entries(data.pipeline.running_by_phase).map(([phase, count]) => (
            <li key={phase} className="flex justify-between rounded border p-2">
              <span>{phase}</span>
              <span className="text-muted-foreground">{count}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded border p-4 space-y-2 text-sm">
        <h2 className="font-semibold">Remaining Usage Tracking</h2>
        <p className="text-muted-foreground">
          health {data.remaining_usage.health} | coverage {(data.remaining_usage.coverage_rate * 100).toFixed(1)}% |
          remaining {data.remaining_usage.remaining_to_full_coverage}
        </p>
        <ul className="space-y-1">
          {data.remaining_usage.untracked_task_ids.length === 0 && (
            <li className="text-muted-foreground">No untracked completed/failed tasks.</li>
          )}
          {data.remaining_usage.untracked_task_ids.map((taskId) => (
            <li key={taskId} className="rounded border p-2">
              <Link href={`/tasks?task_id=${encodeURIComponent(taskId)}`} className="underline hover:text-foreground">
                {taskId}
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded border p-4 space-y-3 text-sm">
        <h2 className="font-semibold">Usage by Model</h2>
        <ul className="space-y-2">
          {modelRows.map(([model, row]) => (
            <li key={model} className="rounded border p-2 flex justify-between gap-3">
              <span>{model}</span>
              <span className="text-muted-foreground">
                count {row.count} | statuses{" "}
                {Object.entries(row.by_status)
                  .map(([status, count]) => `${status}:${count}`)
                  .join(", ")}
              </span>
            </li>
          ))}
          {modelRows.length === 0 && <li className="text-muted-foreground">No usage recorded yet.</li>}
        </ul>
      </section>

      <section className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
        <div className="rounded border p-4 space-y-2">
          <h2 className="font-semibold">Execution by Executor</h2>
          <p className="text-muted-foreground">
            tracked_runs {execution?.tracked_runs ?? 0} | failed_runs {execution?.failed_runs ?? 0}
          </p>
          <ul className="space-y-1">
            {executorRows.map(([executor, row]) => (
              <li key={executor} className="flex justify-between rounded border p-2">
                <span>{executor}</span>
                <span className="text-muted-foreground">
                  total {row.count} | ok {row.completed} | failed {row.failed}
                </span>
              </li>
            ))}
            {executorRows.length === 0 && <li className="text-muted-foreground">No execution runs yet.</li>}
          </ul>
        </div>

        <div className="rounded border p-4 space-y-2">
          <h2 className="font-semibold">Execution by Agent</h2>
          <p className="text-muted-foreground">
            codex_runs {execution?.codex_runs ?? 0} | tracked_task_runs {coverage?.tracked_task_runs ?? 0}
          </p>
          <ul className="space-y-1">
            {agentRows.map(([agent, row]) => (
              <li key={agent} className="flex justify-between rounded border p-2">
                <span>{agent}</span>
                <span className="text-muted-foreground">
                  total {row.count} | ok {row.completed} | failed {row.failed}
                </span>
              </li>
            ))}
            {agentRows.length === 0 && <li className="text-muted-foreground">No agent runs yet.</li>}
          </ul>
        </div>
      </section>

      <section className="rounded border p-4 space-y-2 text-sm">
        <h2 className="font-semibold">Recent Tracked Runs</h2>
        <ul className="space-y-2">
          {(execution?.recent_runs ?? []).slice(0, 20).map((run) => (
            <li key={run.event_id} className="rounded border p-2 flex justify-between gap-3">
              <span>
                <Link
                  href={`/tasks?task_id=${encodeURIComponent(run.task_id)}`}
                  className="underline hover:text-foreground"
                >
                  {run.task_id}
                </Link>{" "}
                {run.endpoint}
              </span>
              <span className="text-muted-foreground">
                {run.executor} | status {run.status_code} | {run.runtime_ms.toFixed(1)}ms
              </span>
            </li>
          ))}
          {(execution?.recent_runs ?? []).length === 0 && (
            <li className="text-muted-foreground">No tracked execution events yet.</li>
          )}
        </ul>
      </section>
    </main>
  );
}
