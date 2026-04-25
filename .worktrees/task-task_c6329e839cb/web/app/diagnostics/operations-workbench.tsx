"use client";

import Link from "next/link";
import { useDeferredValue, useEffect, useState, useTransition } from "react";

type RunnerRow = {
  runner_id: string;
  status: string;
  active_task_id?: string | null;
  host?: string | null;
  version?: string | null;
  is_stale?: boolean;
};

type TaskRow = {
  id: string;
  status: string;
  task_type: string;
  direction: string;
  updated_at?: string | null;
  claimed_by?: string | null;
};

type TaskLogPayload = {
  task_id: string;
  log: string;
  command?: string | null;
  output?: string | null;
  log_source?: string | null;
};

type OperationsWorkbenchProps = {
  apiBase: string;
  initialTasks: TaskRow[];
  initialRunners: RunnerRow[];
};

function formatStamp(value: string | null | undefined): string {
  if (!value) return "n/a";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function statusTone(status: string): string {
  const normalized = status.trim().toLowerCase();
  if (normalized === "completed" || normalized === "idle") return "text-emerald-700";
  if (normalized === "failed" || normalized === "timed_out") return "text-red-700";
  if (normalized === "needs_decision" || normalized === "degraded") return "text-amber-700";
  return "text-blue-700";
}

export function OperationsWorkbench({
  apiBase,
  initialTasks,
  initialRunners,
}: OperationsWorkbenchProps) {
  const [isPending, startTransition] = useTransition();
  const [tasks, setTasks] = useState<TaskRow[]>(initialTasks);
  const [runners, setRunners] = useState<RunnerRow[]>(initialRunners);
  const [taskStatusFilter, setTaskStatusFilter] = useState("all");
  const [taskSearch, setTaskSearch] = useState("");
  const [runnerSearch, setRunnerSearch] = useState("");
  const [selectedTaskId, setSelectedTaskId] = useState(initialTasks[0]?.id ?? "");
  const [logPayload, setLogPayload] = useState<TaskLogPayload | null>(null);
  const [logError, setLogError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<string | null>(null);
  const deferredTaskSearch = useDeferredValue(taskSearch);
  const deferredRunnerSearch = useDeferredValue(runnerSearch);

  useEffect(() => {
    if (!selectedTaskId && tasks[0]?.id) {
      setSelectedTaskId(tasks[0].id);
    }
  }, [selectedTaskId, tasks]);

  useEffect(() => {
    let cancelled = false;

    async function refresh() {
      const taskParams = new URLSearchParams({ limit: "100" });
      if (taskStatusFilter !== "all") {
        taskParams.set("status", taskStatusFilter);
      }
      const [tasksResponse, runnersResponse] = await Promise.all([
        fetch(`${apiBase}/api/agent/tasks?${taskParams.toString()}`, { cache: "no-store" }),
        fetch(`${apiBase}/api/agent/runners?include_stale=true&limit=100`, { cache: "no-store" }),
      ]);
      if (cancelled) return;
      if (tasksResponse.ok) {
        const payload = (await tasksResponse.json()) as { tasks?: TaskRow[] };
        setTasks(Array.isArray(payload.tasks) ? payload.tasks : []);
      }
      if (runnersResponse.ok) {
        const payload = (await runnersResponse.json()) as { runners?: RunnerRow[] };
        setRunners(Array.isArray(payload.runners) ? payload.runners : []);
      }
      setLastRefresh(new Date().toISOString());
    }

    startTransition(() => {
      void refresh();
    });

    return () => {
      cancelled = true;
    };
  }, [apiBase, taskStatusFilter]);

  useEffect(() => {
    if (!selectedTaskId) {
      setLogPayload(null);
      return;
    }
    let cancelled = false;

    async function loadLog() {
      const response = await fetch(
        `${apiBase}/api/agent/tasks/${encodeURIComponent(selectedTaskId)}/log`,
        { cache: "no-store" },
      );
      if (cancelled) return;
      if (!response.ok) {
        setLogError(`Task log request failed with HTTP ${response.status}`);
        return;
      }
      const payload = (await response.json()) as TaskLogPayload;
      setLogPayload(payload);
      setLogError(null);
    }

    void loadLog();
    const interval = window.setInterval(() => {
      void loadLog();
    }, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [apiBase, selectedTaskId]);

  const visibleTasks = tasks.filter((task) => {
    const haystack = `${task.id} ${task.direction} ${task.status} ${task.task_type} ${task.claimed_by ?? ""}`.toLowerCase();
    return haystack.includes(deferredTaskSearch.trim().toLowerCase());
  });
  const visibleRunners = runners.filter((runner) => {
    const haystack = `${runner.runner_id} ${runner.host ?? ""} ${runner.status} ${runner.active_task_id ?? ""}`.toLowerCase();
    return haystack.includes(deferredRunnerSearch.trim().toLowerCase());
  });

  return (
    <section className="grid gap-6 lg:grid-cols-[0.95fr_1.05fr]">
      <div className="border rounded-2xl p-5 space-y-4">
        <div>
          <h2 className="text-xl font-semibold">Operations Workbench</h2>
          <p className="text-sm text-muted-foreground">
            Filter the fleet, drill into live work, and keep a task log open while the runner is moving.
          </p>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <label className="space-y-2 text-sm">
            <span className="font-medium">Task status</span>
            <select
              value={taskStatusFilter}
              onChange={(event) => setTaskStatusFilter(event.target.value)}
              className="w-full rounded-xl border bg-background px-3 py-2"
            >
              <option value="all">all</option>
              <option value="pending">pending</option>
              <option value="running">running</option>
              <option value="completed">completed</option>
              <option value="failed">failed</option>
              <option value="timed_out">timed_out</option>
              <option value="needs_decision">needs_decision</option>
            </select>
          </label>
          <label className="space-y-2 text-sm">
            <span className="font-medium">Task search</span>
            <input
              value={taskSearch}
              onChange={(event) => setTaskSearch(event.target.value)}
              className="w-full rounded-xl border bg-background px-3 py-2"
              placeholder="task id, direction, status"
            />
          </label>
        </div>
        <div className="space-y-3">
          {visibleTasks.slice(0, 12).map((task) => (
            <button
              key={task.id}
              type="button"
              onClick={() => setSelectedTaskId(task.id)}
              className={`w-full rounded-xl border p-3 text-left transition-colors ${
                selectedTaskId === task.id ? "border-primary bg-primary/5" : "hover:border-foreground/40"
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <span className="font-mono text-xs break-all">{task.id}</span>
                <span className={`text-sm font-medium ${statusTone(task.status)}`}>{task.status}</span>
              </div>
              <div className="mt-1 text-sm">{task.direction}</div>
              <div className="mt-1 text-xs text-muted-foreground">
                {task.task_type} • {task.claimed_by || "unclaimed"} • {formatStamp(task.updated_at)}
              </div>
            </button>
          ))}
          {visibleTasks.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No tasks match the current filters.
            </p>
          ) : null}
        </div>
      </div>

      <div className="border rounded-2xl p-5 space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold">Runner And Log Drilldown</h2>
            <p className="text-sm text-muted-foreground">
              Polls the selected task log every 3 seconds and keeps runner context nearby.
            </p>
          </div>
          <div className="text-xs text-muted-foreground">
            {isPending ? "refreshing…" : lastRefresh ? `refreshed ${formatStamp(lastRefresh)}` : "live"}
          </div>
        </div>
        <label className="space-y-2 text-sm block">
          <span className="font-medium">Runner search</span>
          <input
            value={runnerSearch}
            onChange={(event) => setRunnerSearch(event.target.value)}
            className="w-full rounded-xl border bg-background px-3 py-2"
            placeholder="runner id, host, active task"
          />
        </label>
        <div className="grid gap-3 md:grid-cols-2">
          {visibleRunners.slice(0, 8).map((runner) => (
            <div key={runner.runner_id} className="rounded-xl border p-3 text-sm">
              <div className="flex items-center justify-between gap-3">
                <span className="font-medium">{runner.runner_id}</span>
                <span className={statusTone(runner.status)}>{runner.status}</span>
              </div>
              <div className="mt-1 text-muted-foreground">{runner.host || "unknown host"}</div>
              <div className="mt-1 text-xs text-muted-foreground">
                version {runner.version || "unknown"}{runner.is_stale ? " • stale" : ""}
              </div>
              {runner.active_task_id ? (
                <button
                  type="button"
                  onClick={() => setSelectedTaskId(runner.active_task_id || "")}
                  className="mt-2 text-sm text-primary hover:underline"
                >
                  Open active task {runner.active_task_id}
                </button>
              ) : null}
            </div>
          ))}
        </div>
        <div className="rounded-xl border p-4 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-sm text-muted-foreground">Selected task</div>
              <div className="font-mono text-xs break-all">{selectedTaskId || "none"}</div>
            </div>
            {selectedTaskId ? (
              <Link href={`/tasks/${encodeURIComponent(selectedTaskId)}`} className="text-sm text-primary hover:underline">
                Open task detail
              </Link>
            ) : null}
          </div>
          {logError ? <p className="text-sm text-destructive">{logError}</p> : null}
          <div className="text-xs text-muted-foreground">
            {logPayload?.log_source ? `log source: ${logPayload.log_source}` : "Waiting for task selection"}
          </div>
          <pre className="min-h-72 whitespace-pre-wrap rounded-lg bg-muted/40 p-3 text-xs leading-5">
            {logPayload?.log || "Select a task to watch its live log tail here."}
          </pre>
        </div>
      </div>
    </section>
  );
}
