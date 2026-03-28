"use client";

import Link from "next/link";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";

// ── Types ────────────────────────────────────────────────────────────────────

type NodeStreak = {
  completed: number;
  failed: number;
  timed_out: number;
  executing: number;
  total_resolved: number;
  success_rate: number;
  last_10: string[];
  providers_used: string[];
  by_provider: Record<string, { ok: number; fail: number; timeout: number; total: number; success_rate: number }>;
  attention: string;
  attention_detail: string;
};

type NodeSystemMetrics = {
  cpu_percent: number;
  memory_percent: number;
  memory_total_gb: number;
  memory_used_gb: number;
};

type NodeCapabilities = {
  executors: string[];
  system_metrics?: NodeSystemMetrics;
  git?: { local_sha: string; origin_sha: string; branch: string; up_to_date: string };
};

type NetworkNode = {
  node_id: string;
  hostname: string;
  os_type: string;
  providers: string[];
  status: string;
  last_seen_at: string;
  registered_at: string;
  capabilities: NodeCapabilities;
  streak?: NodeStreak;
};

type ActivityEvent = {
  id: string;
  task_id: string;
  node_id: string;
  node_name: string;
  provider: string;
  event_type: string;
  data: Record<string, unknown>;
  timestamp: string;
};

type ProviderStats = {
  providers: Record<
    string,
    {
      total_runs: number;
      successes: number;
      failures: number;
      success_rate: number;
      last_5_rate: number;
      avg_duration_s: number;
      selection_probability: number;
      blocked: boolean;
      needs_attention: boolean;
    }
  >;
  summary: {
    total_providers: number;
    healthy_providers: number;
    attention_needed: number;
    total_measurements: number;
  };
  alerts: Array<{ provider: string; metric: string; value: number; message: string }>;
};

type TaskSummary = {
  total: number;
  pending: number;
  running: number;
  completed: number;
  failed: number;
};

type PendingTask = {
  id: string;
  task_type: string;
  direction: string;
  created_at: string;
};

type DailySummary = {
  generated_at: string;
  host_runner?: {
    total_runs: number;
    failed_runs: number;
    completed_runs: number;
    running_runs: number;
    pending_runs: number;
    by_task_type: Record<string, Record<string, number>>;
  };
  tool_usage?: {
    worker_events: number;
    worker_failed_events: number;
    worker_failed_events_raw?: number;
    worker_failed_events_recoverable?: number;
    recovery_success_streak_target?: number;
  };
  friction?: {
    total_events: number;
    open_events: number;
    top_block_types: Array<{ key: string; count: number; energy_loss: number }>;
  };
  providers?: Array<{
    provider: string;
    status: string;
    data_source: string;
    notes: string[];
  }>;
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function elapsed(timestamp: string): string {
  const ms = Date.now() - new Date(timestamp).getTime();
  if (!Number.isFinite(ms) || ms < 0) return "just now";
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  return `${Math.floor(m / 60)}h ${m % 60}m ago`;
}

function fetchJson<T>(url: string): Promise<T> {
  return fetch(url, { signal: AbortSignal.timeout(8000) }).then((r) => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json() as Promise<T>;
  });
}

function statusColor(status: string): string {
  if (status === "online") return "bg-emerald-400";
  if (status === "offline") return "bg-red-400";
  return "bg-yellow-400";
}

function eventColor(eventType: string): string {
  if (eventType === "completed") return "bg-emerald-400";
  if (eventType === "failed" || eventType === "timeout") return "bg-red-400";
  if (eventType === "executing" || eventType === "heartbeat") return "bg-amber-400";
  return "bg-muted-foreground/40";
}

function healthColor(rate: number, blocked: boolean): string {
  if (blocked) return "text-red-400";
  if (rate >= 0.7) return "text-emerald-400";
  if (rate >= 0.4) return "text-yellow-400";
  return "text-red-400";
}

// ── Sub-components ────────────────────────────────────────────────────────────

function NodeCard({ node }: { node: NetworkNode }) {
  const lastSeen = elapsed(node.last_seen_at);
  const metrics = node.capabilities?.system_metrics;
  const git = node.capabilities?.git;
  const streak = node.streak;

  return (
    <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="relative flex h-2.5 w-2.5 shrink-0">
            <span className={`absolute inline-flex h-full w-full rounded-full ${statusColor(node.status)} ${node.status === "online" ? "animate-ping opacity-60" : ""}`} />
            <span className={`relative inline-flex h-2.5 w-2.5 rounded-full ${statusColor(node.status)}`} />
          </span>
          <div className="min-w-0">
            <p className="text-sm font-medium text-foreground truncate">{node.hostname}</p>
            <p className="text-xs text-muted-foreground">{node.os_type} · {lastSeen}</p>
          </div>
        </div>
        {streak && (
          <div className="text-right shrink-0">
            <p className={`text-sm font-medium ${streak.success_rate >= 0.8 ? "text-emerald-400" : streak.success_rate >= 0.5 ? "text-yellow-400" : "text-red-400"}`}>
              {Math.round(streak.success_rate * 100)}%
            </p>
            <p className="text-xs text-muted-foreground">{streak.total_resolved} tasks</p>
          </div>
        )}
      </div>

      {metrics && (
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="rounded-lg bg-card/40 px-2.5 py-1.5">
            <p className="text-muted-foreground">CPU</p>
            <p className={`font-medium ${metrics.cpu_percent > 80 ? "text-red-400" : metrics.cpu_percent > 60 ? "text-yellow-400" : "text-foreground"}`}>
              {metrics.cpu_percent}%
            </p>
          </div>
          <div className="rounded-lg bg-card/40 px-2.5 py-1.5">
            <p className="text-muted-foreground">RAM</p>
            <p className={`font-medium ${metrics.memory_percent > 90 ? "text-red-400" : metrics.memory_percent > 70 ? "text-yellow-400" : "text-foreground"}`}>
              {metrics.memory_percent}%
            </p>
          </div>
        </div>
      )}

      {node.providers.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {node.providers.slice(0, 4).map((p) => (
            <span key={p} className="rounded-md bg-card/60 border border-border/30 px-1.5 py-0.5 text-[10px] text-muted-foreground">
              {p}
            </span>
          ))}
          {node.providers.length > 4 && (
            <span className="text-[10px] text-muted-foreground">+{node.providers.length - 4}</span>
          )}
        </div>
      )}

      {git && (
        <p className="text-[10px] text-muted-foreground font-mono">
          {git.local_sha} · {git.branch} {git.up_to_date === "yes" ? "· up to date" : "· behind"}
        </p>
      )}
    </div>
  );
}

function ProviderRow({
  name,
  stats,
}: {
  name: string;
  stats: ProviderStats["providers"][string];
}) {
  const displayName = name.replace("claude/claude-", "claude/").replace("openrouter/", "openrouter/");
  const lastFiveBoxes = Array.from({ length: 5 }, (_, i) => {
    const run = (stats as unknown as { last_5_runs?: Array<{ success: boolean }> }).last_5_runs?.[i];
    if (!run) return null;
    return run.success;
  });

  return (
    <div className="flex items-center gap-3 py-2 border-b border-border/20 last:border-0">
      <div className="flex-1 min-w-0">
        <p className="text-sm text-foreground truncate">{displayName}</p>
        <p className="text-xs text-muted-foreground">
          {stats.total_runs} runs · avg {Math.round(stats.avg_duration_s)}s
        </p>
      </div>
      <div className="flex gap-0.5">
        {lastFiveBoxes.map((success, i) => (
          <span
            key={i}
            className={`inline-block w-3 h-3 rounded-sm ${
              success === null
                ? "bg-muted/30"
                : success
                  ? "bg-emerald-400/70"
                  : "bg-red-400/70"
            }`}
            title={success === null ? "no data" : success ? "success" : "failure"}
          />
        ))}
      </div>
      <div className="text-right w-16 shrink-0">
        <p className={`text-sm font-medium tabular-nums ${healthColor(stats.last_5_rate, stats.blocked)}`}>
          {stats.blocked ? "BLOCKED" : `${Math.round(stats.last_5_rate * 100)}%`}
        </p>
        <p className="text-[10px] text-muted-foreground">{Math.round(stats.selection_probability * 100)}% sel</p>
      </div>
    </div>
  );
}

// ── Main dashboard ─────────────────────────────────────────────────────────────

function PipelineDashboardContent() {
  const [nodes, setNodes] = useState<NetworkNode[]>([]);
  const [activeTasks, setActiveTasks] = useState<ActivityEvent[]>([]);
  const [recentActivity, setRecentActivity] = useState<ActivityEvent[]>([]);
  const [providerStats, setProviderStats] = useState<ProviderStats | null>(null);
  const [taskSummary, setTaskSummary] = useState<TaskSummary | null>(null);
  const [pendingQueue, setPendingQueue] = useState<PendingTask[]>([]);
  const [dailySummary, setDailySummary] = useState<DailySummary | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");

  const load = useCallback(async () => {
    try {
      const [nodesData, activeData, activityData, provStats, pendingData, runningData, pendingQueueData, dailySummaryData] = await Promise.allSettled([
        fetchJson<NetworkNode[]>("/api/federation/nodes"),
        fetchJson<ActivityEvent[]>("/api/agent/tasks/active"),
        fetchJson<ActivityEvent[]>("/api/agent/tasks/activity?limit=50"),
        fetchJson<ProviderStats>("/api/providers/stats"),
        fetchJson<{ total?: number }>("/api/agent/tasks?status=pending&limit=1"),
        fetchJson<{ total?: number }>("/api/agent/tasks?status=running&limit=1"),
        fetchJson<{ tasks?: PendingTask[]; total?: number }>("/api/agent/tasks?status=pending&limit=20"),
        fetchJson<DailySummary>("/api/agent/usage/daily-summary"),
      ]);

      if (nodesData.status === "fulfilled") setNodes(nodesData.value);
      if (activeData.status === "fulfilled") setActiveTasks(Array.isArray(activeData.value) ? activeData.value : []);
      if (activityData.status === "fulfilled") setRecentActivity(Array.isArray(activityData.value) ? activityData.value : []);
      if (provStats.status === "fulfilled") setProviderStats(provStats.value);
      if (pendingQueueData.status === "fulfilled") setPendingQueue(pendingQueueData.value.tasks ?? []);
      if (dailySummaryData.status === "fulfilled") setDailySummary(dailySummaryData.value);

      const pendingCount = pendingData.status === "fulfilled" ? (pendingData.value.total ?? 0) : 0;
      const runningCount = runningData.status === "fulfilled" ? (runningData.value.total ?? 0) : 0;
      setTaskSummary({
        total: pendingCount + runningCount,
        pending: pendingCount,
        running: Math.max(runningCount, activeTasks.length),
        completed: 0,
        failed: 0,
      });

      setLastRefresh(new Date());
      setStatus("ok");
    } catch {
      setStatus("error");
    }
  }, [activeTasks.length]);

  // Initial load
  useEffect(() => {
    void load();
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-refresh every 8 seconds
  const loadRef = useRef(load);
  loadRef.current = load;
  useEffect(() => {
    const timer = window.setInterval(() => void loadRef.current(), 8_000);
    return () => window.clearInterval(timer);
  }, []);

  const onlineNodes = nodes.filter((n) => n.status === "online");
  const recentCompleted = recentActivity.filter((e) => e.event_type === "completed").length;
  const recentFailed = recentActivity.filter((e) => e.event_type === "failed" || e.event_type === "timeout").length;

  return (
    <main className="min-h-screen px-4 pb-8 pt-6 sm:px-6 lg:px-8">
      <div className="mx-auto w-full max-w-7xl space-y-5">

        {/* Header */}
        <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 sm:p-7 space-y-3">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Live view</p>
              <h1 className="text-3xl md:text-4xl font-light tracking-tight">What Is Happening Now</h1>
              <p className="max-w-2xl text-sm text-muted-foreground sm:text-base">
                Nodes claiming tasks, providers executing, ideas advancing through stages — the network is alive.
              </p>
            </div>
            {lastRefresh && (
              <p className="text-xs text-muted-foreground shrink-0 tabular-nums pt-1">
                Updated {elapsed(lastRefresh.toISOString())}
              </p>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href="/tasks" className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200">
              Work Cards
            </Link>
            <Link href="/nodes" className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200">
              Nodes
            </Link>
            <Link href="/ideas" className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200">
              Ideas
            </Link>
            <Link href="/flow" className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200">
              Progress
            </Link>
          </div>
        </section>

        {/* Summary stats */}
        <section className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {[
            { label: "Nodes online", value: onlineNodes.length, total: nodes.length, accent: onlineNodes.length > 0 },
            { label: "Tasks executing", value: activeTasks.length, total: null, accent: activeTasks.length > 0 },
            { label: "Tasks pending", value: taskSummary?.pending ?? "—", total: null, accent: false },
            { label: "Completed (stream)", value: recentCompleted, total: null, accent: recentCompleted > 0 },
            { label: "Failed (stream)", value: recentFailed, total: null, accent: false, warn: recentFailed > 0 },
          ].map((s) => (
            <div key={s.label} className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 space-y-1">
              <p className="text-xs text-muted-foreground">{s.label}</p>
              <p className={`text-2xl font-light tabular-nums ${s.warn ? "text-red-400" : s.accent ? "text-primary" : "text-foreground"}`}>
                {s.value}
                {s.total !== null && <span className="text-sm text-muted-foreground">/{s.total}</span>}
              </p>
            </div>
          ))}
        </section>

        {/* Active tasks */}
        {activeTasks.length > 0 && (
          <section className="rounded-2xl border border-amber-500/30 bg-gradient-to-b from-amber-500/5 to-card/20 p-5 space-y-3">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2.5 w-2.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400/60" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-amber-400" />
              </span>
              <h2 className="text-lg font-medium">Executing Right Now</h2>
              <span className="text-sm text-muted-foreground">({activeTasks.length})</span>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {activeTasks.map((task) => {
                const ideaId = String(task.data?.idea_id ?? "");
                const taskType = String(task.data?.task_type ?? task.event_type ?? "working");
                return (
                  <Link
                    key={task.task_id}
                    href={`/tasks/${encodeURIComponent(task.task_id)}`}
                    className="rounded-xl border border-amber-500/20 bg-card/60 p-4 space-y-2 hover:border-amber-500/40 transition-all duration-200"
                  >
                    <div className="flex items-start gap-2">
                      <span className="relative flex h-2 w-2 mt-1.5 shrink-0">
                        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400/50" />
                        <span className="relative inline-flex h-2 w-2 rounded-full bg-amber-400" />
                      </span>
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-foreground line-clamp-1">
                          {taskType}{ideaId ? `: ${ideaId.replace(/-/g, " ")}` : ""}
                        </p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {task.node_name || "node"} · {task.provider || "agent"} · {elapsed(task.timestamp)}
                        </p>
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>
          </section>
        )}

        <div className="grid gap-5 lg:grid-cols-2">
          {/* Nodes */}
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-medium">Nodes</h2>
              <Link href="/nodes" className="text-xs text-muted-foreground hover:text-foreground transition-colors">
                View all →
              </Link>
            </div>
            {status === "loading" && (
              <div className="rounded-2xl border border-border/30 bg-card/30 p-8 text-center">
                <p className="text-sm text-muted-foreground">Loading nodes…</p>
              </div>
            )}
            {nodes.length === 0 && status === "ok" && (
              <div className="rounded-2xl border border-border/30 bg-card/30 p-8 text-center">
                <p className="text-sm text-muted-foreground">No nodes registered.</p>
              </div>
            )}
            <div className="space-y-3">
              {nodes.map((node) => (
                <NodeCard key={node.node_id} node={node} />
              ))}
            </div>
          </section>

          {/* Provider health */}
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-medium">Provider Health</h2>
              {providerStats && (
                <span className="text-xs text-muted-foreground">
                  {providerStats.summary.healthy_providers}/{providerStats.summary.total_providers} healthy
                </span>
              )}
            </div>
            {providerStats && providerStats.alerts.length > 0 && (
              <div className="rounded-xl border border-red-500/30 bg-red-500/5 px-4 py-3 space-y-1">
                {providerStats.alerts.map((alert) => (
                  <p key={alert.provider + alert.metric} className="text-xs text-red-300">
                    ⚠ {alert.message}
                  </p>
                ))}
              </div>
            )}
            <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 px-4 py-2">
              {status === "loading" && (
                <p className="py-4 text-sm text-muted-foreground text-center">Loading provider stats…</p>
              )}
              {providerStats && Object.entries(providerStats.providers).map(([name, stats]) => (
                <ProviderRow key={name} name={name} stats={stats} />
              ))}
              {providerStats && Object.keys(providerStats.providers).length === 0 && (
                <p className="py-4 text-sm text-muted-foreground text-center">No provider data yet.</p>
              )}
            </div>
          </section>
        </div>

        {/* Pending queue */}
        {pendingQueue.length > 0 && (
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-medium">Pending Queue</h2>
              <Link href="/tasks" className="text-xs text-muted-foreground hover:text-foreground transition-colors">
                All tasks →
              </Link>
            </div>
            <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 space-y-2">
              {pendingQueue.slice(0, 10).map((task) => (
                <div key={task.id} className="flex items-start gap-3 py-2 border-b border-border/20 last:border-0">
                  <span className="inline-block w-2 h-2 mt-1.5 rounded-full bg-muted-foreground/40 shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 mb-0.5">
                      <Link
                        href={`/tasks/${encodeURIComponent(task.id)}`}
                        className="text-xs font-mono text-muted-foreground hover:text-foreground transition-colors"
                      >
                        {task.id.slice(0, 12)}
                      </Link>
                      {task.task_type && (
                        <span className="text-[10px] rounded bg-muted/60 px-1.5 py-0.5 text-muted-foreground">
                          {task.task_type}
                        </span>
                      )}
                    </div>
                    {task.direction && (
                      <p className="text-xs text-muted-foreground line-clamp-1">{task.direction}</p>
                    )}
                  </div>
                  {task.created_at && (
                    <span className="text-[10px] text-muted-foreground/60 shrink-0 tabular-nums">
                      {elapsed(task.created_at)}
                    </span>
                  )}
                </div>
              ))}
              {(taskSummary?.pending ?? 0) > 10 && (
                <p className="text-xs text-muted-foreground text-center pt-2">
                  + {(taskSummary?.pending ?? 0) - 10} more pending —{" "}
                  <Link href="/tasks" className="underline hover:text-foreground">view all</Link>
                </p>
              )}
            </div>
          </section>
        )}

        {/* Daily summary — task execution health */}
        {dailySummary && (
          <section className="space-y-3">
            <h2 className="text-lg font-medium">Execution Health (24h)</h2>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {dailySummary.host_runner && (
                <>
                  <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 space-y-1">
                    <p className="text-xs text-muted-foreground">Total runs</p>
                    <p className="text-2xl font-light tabular-nums">{dailySummary.host_runner.total_runs}</p>
                  </div>
                  <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 space-y-1">
                    <p className="text-xs text-muted-foreground">Completed</p>
                    <p className="text-2xl font-light tabular-nums text-emerald-400">{dailySummary.host_runner.completed_runs}</p>
                  </div>
                  <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 space-y-1">
                    <p className="text-xs text-muted-foreground">Failed</p>
                    <p className={`text-2xl font-light tabular-nums ${dailySummary.host_runner.failed_runs > 0 ? "text-red-400" : "text-foreground"}`}>
                      {dailySummary.host_runner.failed_runs}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 space-y-1">
                    <p className="text-xs text-muted-foreground">Success rate</p>
                    {(() => {
                      const total = dailySummary.host_runner!.total_runs;
                      const rate = total > 0 ? Math.round((dailySummary.host_runner!.completed_runs / total) * 100) : 0;
                      return (
                        <p className={`text-2xl font-light tabular-nums ${rate >= 70 ? "text-emerald-400" : rate >= 40 ? "text-yellow-400" : "text-red-400"}`}>
                          {rate}%
                        </p>
                      );
                    })()}
                  </div>
                </>
              )}
            </div>

            {/* Task type breakdown */}
            {dailySummary.host_runner && Object.keys(dailySummary.host_runner.by_task_type).length > 0 && (
              <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 space-y-2">
                <p className="text-sm font-medium">By task type</p>
                <div className="grid gap-2 sm:grid-cols-2">
                  {Object.entries(dailySummary.host_runner.by_task_type).slice(0, 8).map(([taskType, counts]) => {
                    const completed = Number(counts.completed ?? 0);
                    const failed = Number(counts.failed ?? 0);
                    const total = completed + failed + Number(counts.running ?? 0) + Number(counts.pending ?? 0);
                    return (
                      <div key={taskType} className="flex items-center gap-3 text-sm">
                        <span className="text-muted-foreground w-16 truncate text-xs">{taskType}</span>
                        <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
                          {total > 0 && (
                            <div
                              className="h-full bg-emerald-500/60 rounded-full"
                              style={{ width: `${Math.round((completed / total) * 100)}%` }}
                            />
                          )}
                        </div>
                        <span className="text-xs text-muted-foreground tabular-nums w-12 text-right">
                          {completed}/{total}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Friction signals */}
            {dailySummary.friction && dailySummary.friction.open_events > 0 && (
              <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-4 space-y-2">
                <div className="flex items-center gap-2">
                  <span className="text-amber-400 text-sm">⚠</span>
                  <p className="text-sm font-medium">Friction: {dailySummary.friction.open_events} open events</p>
                </div>
                {dailySummary.friction.top_block_types.slice(0, 3).map((block) => (
                  <div key={block.key} className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span className="w-2 h-2 rounded-full bg-amber-400/60 shrink-0" />
                    <span className="flex-1">{block.key}</span>
                    <span className="tabular-nums">{block.count}×</span>
                  </div>
                ))}
                <Link href="/friction" className="text-xs text-amber-600 dark:text-amber-400 hover:underline">
                  View friction details →
                </Link>
              </div>
            )}
          </section>
        )}

        {/* Activity stream */}
        <section className="space-y-3">
          <h2 className="text-lg font-medium">Activity Stream</h2>
          <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 space-y-1.5 max-h-96 overflow-y-auto">
            {status === "loading" && (
              <p className="text-sm text-muted-foreground text-center py-4">Loading activity…</p>
            )}
            {recentActivity.length === 0 && status === "ok" && (
              <p className="text-sm text-muted-foreground text-center py-4">No recent activity.</p>
            )}
            {[...recentActivity].reverse().map((event, i) => {
              const ideaId = String(event.data?.idea_id ?? "");
              const taskType = String(event.data?.task_type ?? "");
              return (
                <div key={event.id ?? event.timestamp + String(i)} className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span className={`inline-flex h-1.5 w-1.5 rounded-full shrink-0 ${eventColor(event.event_type)}`} />
                  <Link
                    href={`/tasks/${encodeURIComponent(event.task_id)}`}
                    className="hover:text-foreground transition-colors min-w-0 truncate max-w-[200px]"
                  >
                    {ideaId
                      ? <span>{taskType ? `${taskType}: ` : ""}{ideaId.replace(/-/g, " ")}</span>
                      : <span className="font-mono">{event.task_id.slice(0, 8)}</span>
                    }
                  </Link>
                  <span className="shrink-0">{event.event_type}</span>
                  {event.node_name && <span className="shrink-0 text-muted-foreground/60">on {event.node_name}</span>}
                  {event.provider && <span className="shrink-0 text-muted-foreground/60">via {event.provider}</span>}
                  {typeof event.data?.duration_s === "number" && (
                    <span className="shrink-0 text-muted-foreground/50">
                      {event.data.duration_s < 60
                        ? `${Math.round(event.data.duration_s)}s`
                        : `${Math.floor(event.data.duration_s / 60)}m ${Math.round(event.data.duration_s % 60)}s`}
                    </span>
                  )}
                  <span className="ml-auto tabular-nums shrink-0">{new Date(event.timestamp).toLocaleTimeString()}</span>
                </div>
              );
            })}
          </div>
        </section>

        {/* Footer nav */}
        <nav className="py-6 text-center space-y-2 border-t border-border/20" aria-label="Where to go next">
          <p className="text-xs text-muted-foreground/80 uppercase tracking-wider">Where to go next</p>
          <div className="flex flex-wrap justify-center gap-4 text-sm">
            <Link href="/nodes" className="text-amber-600 dark:text-amber-400 hover:underline">Nodes</Link>
            <Link href="/tasks" className="text-amber-600 dark:text-amber-400 hover:underline">Work Cards</Link>
            <Link href="/flow" className="text-amber-600 dark:text-amber-400 hover:underline">Flow</Link>
            <Link href="/friction" className="text-amber-600 dark:text-amber-400 hover:underline">Friction</Link>
          </div>
        </nav>

      </div>
    </main>
  );
}

export default function PipelinePage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen px-4 pb-8 pt-6 sm:px-6 lg:px-8">
          <div className="mx-auto w-full max-w-7xl">
            <p className="text-muted-foreground">Loading pipeline…</p>
          </div>
        </main>
      }
    >
      <PipelineDashboardContent />
    </Suspense>
  );
}
