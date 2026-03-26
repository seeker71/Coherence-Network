import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "Agent",
  description: "Agent execution monitoring and task orchestration status.",
};

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
      success_runs: number;
      success_rate: number;
      codex_runs: number;
      by_executor: Record<string, { count: number; completed: number; failed: number }>;
      by_agent: Record<string, { count: number; completed: number; failed: number }>;
      by_tool: Record<string, { count: number; completed: number; failed: number; success_rate: number }>;
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
        tool: string;
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
  const toolRows = Object.entries(execution?.by_tool ?? {}).sort((a, b) => b[1].count - a[1].count);
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
        Live overview of pipeline activity, model usage, and execution tracking coverage.
      </p>

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-4 text-sm">
        <h2 className="text-xl font-semibold">Pipeline Snapshot</h2>
        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-xl border border-border/20 bg-background/40 p-3">
            <p className="text-muted-foreground text-xs">Running</p>
            <p className="text-lg font-semibold">{data.pipeline.running_count}</p>
          </div>
          <div className="rounded-xl border border-border/20 bg-background/40 p-3">
            <p className="text-muted-foreground text-xs">Pending</p>
            <p className="text-lg font-semibold">{data.pipeline.pending_count}</p>
          </div>
          <div className="rounded-xl border border-border/20 bg-background/40 p-3">
            <p className="text-muted-foreground text-xs">Recently completed</p>
            <p className="text-lg font-semibold">{data.pipeline.recent_completed_count}</p>
          </div>
        </div>
        {data.pipeline.attention_flags.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            <span className="text-muted-foreground text-xs">Attention flags:</span>
            {data.pipeline.attention_flags.map((flag) => (
              <span key={flag} className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-amber-500/10 text-amber-500">
                {flag}
              </span>
            ))}
          </div>
        )}
        {Object.entries(data.pipeline.running_by_phase).length > 0 && (
          <div className="space-y-1">
            <p className="text-muted-foreground text-xs">Running by phase</p>
            {Object.entries(data.pipeline.running_by_phase).map(([phase, count]) => (
              <div key={phase} className="flex justify-between rounded-xl border border-border/20 bg-background/40 p-2">
                <span>{phase}</span>
                <span className="text-muted-foreground">{count}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-4 text-sm">
        <h2 className="text-xl font-semibold">Usage Tracking Coverage</h2>
        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-xl border border-border/20 bg-background/40 p-3">
            <p className="text-muted-foreground text-xs">Health</p>
            <p className="text-lg font-semibold">
              <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                data.remaining_usage.health === "ok" || data.remaining_usage.health === "healthy"
                  ? "bg-green-500/10 text-green-500"
                  : data.remaining_usage.health === "degraded"
                    ? "bg-amber-500/10 text-amber-500"
                    : "bg-red-500/10 text-red-500"
              }`}>
                {data.remaining_usage.health}
              </span>
            </p>
          </div>
          <div className="rounded-xl border border-border/20 bg-background/40 p-3">
            <p className="text-muted-foreground text-xs">Coverage</p>
            <p className="text-lg font-semibold">{(data.remaining_usage.coverage_rate * 100).toFixed(1)}%</p>
          </div>
          <div className="rounded-xl border border-border/20 bg-background/40 p-3">
            <p className="text-muted-foreground text-xs">Remaining to full</p>
            <p className="text-lg font-semibold">{data.remaining_usage.remaining_to_full_coverage}</p>
          </div>
        </div>
        {data.remaining_usage.untracked_task_ids.length > 0 && (
          <div className="space-y-1">
            <p className="text-muted-foreground text-xs">Untracked tasks</p>
            {data.remaining_usage.untracked_task_ids.map((taskId) => (
              <div key={taskId} className="rounded-xl border border-border/20 bg-background/40 p-2">
                <Link href={`/tasks?task_id=${encodeURIComponent(taskId)}`} className="underline hover:text-foreground">
                  {taskId}
                </Link>
              </div>
            ))}
          </div>
        )}
        {data.remaining_usage.untracked_task_ids.length === 0 && (
          <p className="text-muted-foreground">No untracked completed/failed tasks.</p>
        )}
      </section>

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3 text-sm">
        <h2 className="text-xl font-semibold">Usage by Model</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-border/30 text-muted-foreground text-xs">
                <th className="py-2 pr-3">Model</th>
                <th className="py-2 pr-3 text-right">Requests</th>
                <th className="py-2 pr-3 text-right">Statuses</th>
              </tr>
            </thead>
            <tbody>
              {modelRows.map(([model, row]) => (
                <tr key={model} className="border-b border-border/10">
                  <td className="py-2 pr-3 font-medium">{model}</td>
                  <td className="py-2 pr-3 text-right">{row.count}</td>
                  <td className="py-2 pr-3 text-right">
                    <span className="flex flex-wrap justify-end gap-1">
                      {Object.entries(row.by_status).map(([s, c]) => (
                        <span key={s} className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                          s.startsWith("2") ? "bg-green-500/10 text-green-500"
                            : s.startsWith("4") ? "bg-amber-500/10 text-amber-500"
                              : s.startsWith("5") ? "bg-red-500/10 text-red-500"
                                : "bg-muted text-muted-foreground"
                        }`}>
                          {s}: {c}
                        </span>
                      ))}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {modelRows.length === 0 && <p className="text-muted-foreground py-2">No usage recorded yet.</p>}
        </div>
      </section>

      <section className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3">
          <h2 className="text-xl font-semibold">Execution by Executor</h2>
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-xl border border-border/20 bg-background/40 p-3">
              <p className="text-muted-foreground text-xs">Tracked runs</p>
              <p className="text-lg font-semibold">{execution?.tracked_runs ?? 0}</p>
            </div>
            <div className="rounded-xl border border-border/20 bg-background/40 p-3">
              <p className="text-muted-foreground text-xs">Success rate</p>
              <p className="text-lg font-semibold">{((execution?.success_rate ?? 0) * 100).toFixed(1)}%</p>
            </div>
          </div>
          <div className="space-y-1">
            {executorRows.map(([executor, row]) => (
              <div key={executor} className="flex justify-between rounded-xl border border-border/20 bg-background/40 p-2">
                <span className="font-medium">{executor}</span>
                <span className="flex gap-2 text-xs">
                  <span className="text-muted-foreground">{row.count} total</span>
                  <span className="text-green-500">{row.completed} ok</span>
                  {row.failed > 0 && <span className="text-red-500">{row.failed} failed</span>}
                </span>
              </div>
            ))}
            {executorRows.length === 0 && <p className="text-muted-foreground">No execution runs yet.</p>}
          </div>
        </div>

        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3">
          <h2 className="text-xl font-semibold">Execution by Agent</h2>
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-xl border border-border/20 bg-background/40 p-3">
              <p className="text-muted-foreground text-xs">Codex runs</p>
              <p className="text-lg font-semibold">{execution?.codex_runs ?? 0}</p>
            </div>
            <div className="rounded-xl border border-border/20 bg-background/40 p-3">
              <p className="text-muted-foreground text-xs">Tracked task runs</p>
              <p className="text-lg font-semibold">{coverage?.tracked_task_runs ?? 0}</p>
            </div>
          </div>
          <div className="space-y-1">
            {agentRows.map(([agent, row]) => (
              <div key={agent} className="flex justify-between rounded-xl border border-border/20 bg-background/40 p-2">
                <span className="font-medium">{agent}</span>
                <span className="flex gap-2 text-xs">
                  <span className="text-muted-foreground">{row.count} total</span>
                  <span className="text-green-500">{row.completed} ok</span>
                  {row.failed > 0 && <span className="text-red-500">{row.failed} failed</span>}
                </span>
              </div>
            ))}
            {agentRows.length === 0 && <p className="text-muted-foreground">No agent runs yet.</p>}
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3 text-sm">
        <h2 className="text-xl font-semibold">Tool Usage</h2>
        <p className="text-muted-foreground text-xs">
          Counts, success rates, and failures from worker runtime telemetry.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-border/30 text-muted-foreground text-xs">
                <th className="py-2 pr-3">Tool</th>
                <th className="py-2 pr-3 text-right">Total</th>
                <th className="py-2 pr-3 text-right">OK</th>
                <th className="py-2 pr-3 text-right">Failed</th>
                <th className="py-2 pr-3 text-right">Success rate</th>
              </tr>
            </thead>
            <tbody>
              {toolRows.map(([tool, row]) => (
                <tr key={tool} className="border-b border-border/10">
                  <td className="py-2 pr-3 font-medium">{tool}</td>
                  <td className="py-2 pr-3 text-right">{row.count}</td>
                  <td className="py-2 pr-3 text-right text-green-500">{row.completed}</td>
                  <td className="py-2 pr-3 text-right">{row.failed > 0 ? <span className="text-red-500">{row.failed}</span> : <span className="text-muted-foreground">0</span>}</td>
                  <td className="py-2 pr-3 text-right">{(row.success_rate * 100).toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
          {toolRows.length === 0 && <p className="text-muted-foreground py-2">No tool usage events yet.</p>}
        </div>
      </section>

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3 text-sm">
        <h2 className="text-xl font-semibold">Recent Tracked Runs</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-border/30 text-muted-foreground text-xs">
                <th className="py-2 pr-3">Task</th>
                <th className="py-2 pr-3">Tool</th>
                <th className="py-2 pr-3">Executor</th>
                <th className="py-2 pr-3 text-right">Status</th>
                <th className="py-2 pr-3 text-right">Duration</th>
              </tr>
            </thead>
            <tbody>
              {(execution?.recent_runs ?? []).slice(0, 20).map((run) => (
                <tr key={run.event_id} className="border-b border-border/10">
                  <td className="py-2 pr-3">
                    <Link
                      href={`/tasks?task_id=${encodeURIComponent(run.task_id)}`}
                      className="underline hover:text-foreground"
                    >
                      {run.task_id}
                    </Link>
                    <span className="block text-xs text-muted-foreground">{run.endpoint}</span>
                  </td>
                  <td className="py-2 pr-3">{run.tool}</td>
                  <td className="py-2 pr-3">{run.executor}</td>
                  <td className="py-2 pr-3 text-right">
                    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                      run.status_code >= 200 && run.status_code < 300 ? "bg-green-500/10 text-green-500"
                        : run.status_code >= 400 ? "bg-red-500/10 text-red-500"
                          : "bg-muted text-muted-foreground"
                    }`}>
                      {run.status_code}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-right text-muted-foreground">{run.runtime_ms.toFixed(1)} ms</td>
                </tr>
              ))}
            </tbody>
          </table>
          {(execution?.recent_runs ?? []).length === 0 && (
            <p className="text-muted-foreground py-2">No tracked execution events yet.</p>
          )}
        </div>
      </section>
    </main>
  );
}
