"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getApiBase } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────────────

type PipelineTask = {
  id: string;
  status: string;
  task_type: string;
  direction: string;
  created_at?: string;
};

type HealthResponse = {
  status: string;
  uptime_human: string;
  version: string;
  started_at: string;
};

type RemoteOpsState = {
  health: HealthResponse | null;
  pendingTasks: PipelineTask[];
  pendingTotal: number;
  activeCount: number;
  status: "idle" | "loading" | "error";
  error: string | null;
  runningMessage: string | null;
};

// ── Helpers ────────────────────────────────────────────────────────────────────

function relTs(iso: string | undefined): string {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  return `${Math.floor(mins / 60)}h ago`;
}

// ── Panel ──────────────────────────────────────────────────────────────────────

export function RemoteControlPanel() {
  const API = getApiBase();

  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [pendingTasks, setPendingTasks] = useState<PipelineTask[]>([]);
  const [pendingTotal, setPendingTotal] = useState(0);
  const [activeCount, setActiveCount] = useState(0);
  const [status, setStatus] = useState<RemoteOpsState["status"]>("idle");
  const [error, setError] = useState<string | null>(null);
  const [runningMessage, setRunningMessage] = useState<string | null>(null);

  // Controls
  const [executeToken, setExecuteToken] = useState("");
  const [executor, setExecutor] = useState("openclaw");
  const [taskType, setTaskType] = useState("impl");
  const [modelOverride, setModelOverride] = useState("");
  const [forcePaid, setForcePaid] = useState(false);
  const [runAsPrThread, setRunAsPrThread] = useState(false);
  const [autoMergePr, setAutoMergePr] = useState(false);
  const [direction, setDirection] = useState("");

  const authHeaders = useCallback(() => {
    const h: Record<string, string> = { "Content-Type": "application/json" };
    const t = executeToken.trim();
    if (t) h["X-Agent-Execute-Token"] = t;
    return h;
  }, [executeToken]);

  const refresh = useCallback(async () => {
    try {
      const [healthRes, pendingRes, pipelineRes] = await Promise.allSettled([
        fetch(`${API}/api/health`, { cache: "no-store" }),
        fetch(`${API}/api/agent/tasks?status=pending&limit=20`, { cache: "no-store" }),
        fetch(`${API}/api/agent/pipeline-status`, { cache: "no-store" }),
      ]);

      if (healthRes.status === "fulfilled" && healthRes.value.ok) {
        setHealth(await healthRes.value.json() as HealthResponse);
      }
      if (pendingRes.status === "fulfilled" && pendingRes.value.ok) {
        const data = await pendingRes.value.json() as { tasks: PipelineTask[]; total: number };
        setPendingTasks(data.tasks ?? []);
        setPendingTotal(data.total ?? 0);
      }
      if (pipelineRes.status === "fulfilled" && pipelineRes.value.ok) {
        const data = await pipelineRes.value.json() as { running?: PipelineTask[] };
        setActiveCount(data.running?.length ?? 0);
      }
    } catch {
      // silently ignore
    }
  }, [API]);

  useEffect(() => {
    void refresh();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const refreshRef = useRef(refresh);
  refreshRef.current = refresh;
  useEffect(() => {
    const t = window.setInterval(() => void refreshRef.current(), 15_000);
    return () => window.clearInterval(t);
  }, []);

  const runTask = useCallback(async (taskId: string) => {
    setStatus("loading");
    setError(null);
    setRunningMessage(null);
    try {
      const res = await fetch(`${API}/api/agent/tasks/${taskId}/run`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ executor, task_type: taskType, model_override: modelOverride || undefined, force_paid: forcePaid }),
      });
      const data = await res.json() as { ok: boolean; task_id?: string; reason?: string };
      if (!res.ok || !data.ok) throw new Error(data.reason ?? `HTTP ${res.status}`);
      setRunningMessage(`Running task ${data.task_id ?? taskId}`);
      setStatus("idle");
      setTimeout(() => void refresh(), 2000);
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
      setStatus("error");
    }
  }, [API, authHeaders, executor, taskType, modelOverride, forcePaid, refresh]);

  const onCreate = useCallback(async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!direction.trim()) return;
    setStatus("loading");
    setError(null);
    setRunningMessage(null);
    try {
      const res = await fetch(`${API}/api/agent/tasks`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({
          direction,
          task_type: taskType,
          executor,
          model_override: modelOverride || undefined,
          force_paid: forcePaid,
          run_as_pr_thread: runAsPrThread,
          auto_merge_pr: autoMergePr,
        }),
      });
      const data = await res.json() as { ok?: boolean; task_id?: string; id?: string; reason?: string };
      if (!res.ok) throw new Error(data.reason ?? `HTTP ${res.status}`);
      const newId = data.task_id ?? data.id;
      setRunningMessage(`Created task ${newId ?? "(unknown)"}`);
      setDirection("");
      setStatus("idle");
      setTimeout(() => void refresh(), 2000);
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
      setStatus("error");
    }
  }, [API, authHeaders, direction, taskType, executor, modelOverride, forcePaid, runAsPrThread, autoMergePr, refresh]);

  const runPickUp = useCallback(async () => {
    setStatus("loading");
    setError(null);
    setRunningMessage(null);
    try {
      const res = await fetch(`${API}/api/agent/tasks/pick-up`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ executor, task_type: taskType, model_override: modelOverride || undefined, force_paid: forcePaid }),
      });
      const data = await res.json() as { ok: boolean; task_id?: string; picked?: boolean; reason?: string };
      if (!res.ok || !data.ok) throw new Error(data.reason ?? `HTTP ${res.status}`);
      if (data.picked) {
        setRunningMessage(`Picked up and running task ${data.task_id ?? ""}`);
      } else {
        setRunningMessage("No pending tasks to pick up.");
      }
      setStatus("idle");
      setTimeout(() => void refresh(), 2000);
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
      setStatus("error");
    }
  }, [API, authHeaders, executor, taskType, modelOverride, forcePaid, refresh]);

  const tokenProvided = executeToken.trim().length > 0;

  return (
    <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-6 text-sm">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Remote Control</h2>
        {health && (
          <span className="text-xs text-muted-foreground">
            API {health.status} · up {health.uptime_human}
          </span>
        )}
      </div>

      {!tokenProvided && (
        <p className="text-xs text-amber-500">
          Execute token not set — provide one below if AGENT_EXECUTE_TOKEN is configured on the API.
        </p>
      )}

      {/* Queue summary */}
      <div className="flex gap-4 text-xs text-muted-foreground">
        <span>Pending: <strong className="text-foreground">{pendingTotal}</strong></span>
        <span>Running: <strong className="text-amber-400">{activeCount}</strong></span>
      </div>

      {/* Controls */}
      <div className="grid gap-3 md:grid-cols-2">
        <label>
          Execute token (optional)
          <Input
            value={executeToken}
            onChange={(e) => setExecuteToken(e.target.value)}
            placeholder="AGENT_EXECUTE_TOKEN value"
            className="mt-1"
          />
        </label>
        <label>
          Executor
          <Input
            value={executor}
            onChange={(e) => setExecutor(e.target.value)}
            placeholder="openclaw | cursor | claude"
            className="mt-1"
          />
        </label>
        <label>
          Task type
          <Input
            value={taskType}
            onChange={(e) => setTaskType(e.target.value)}
            placeholder="impl | spec | test | review"
            className="mt-1"
          />
        </label>
        <label>
          Model override (optional)
          <Input
            value={modelOverride}
            onChange={(e) => setModelOverride(e.target.value)}
            placeholder="openrouter/free | gpt-4.1-mini"
            className="mt-1"
          />
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={forcePaid} onChange={(e) => setForcePaid(e.target.checked)} />
          Force paid provider
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={runAsPrThread} onChange={(e) => setRunAsPrThread(e.target.checked)} />
          Run as PR thread
        </label>
        <label className="flex items-center gap-2 md:col-span-2">
          <input type="checkbox" checked={autoMergePr} onChange={(e) => setAutoMergePr(e.target.checked)} />
          Auto-merge PR when checks pass
        </label>
      </div>

      {/* Create new task */}
      <form className="space-y-2" onSubmit={onCreate}>
        <label className="block">
          New task direction
          <textarea
            value={direction}
            onChange={(e) => setDirection(e.target.value)}
            className="mt-1 min-h-20 w-full rounded border bg-background px-3 py-2 text-sm"
            placeholder="Describe what to implement, fix, or review…"
          />
        </label>
        <div className="flex gap-2 flex-wrap">
          <Button type="submit" disabled={status === "loading" || !direction.trim()}>
            Create + Run
          </Button>
          <Button type="button" variant="outline" onClick={runPickUp} disabled={status === "loading"}>
            Pick up oldest pending
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={refresh} disabled={status === "loading"}>
            Refresh
          </Button>
        </div>
      </form>

      {status === "error" && error && (
        <p className="text-xs text-destructive">Error: {error}</p>
      )}
      {runningMessage && (
        <p className="text-xs text-muted-foreground">{runningMessage}</p>
      )}

      {/* Pending task queue */}
      {pendingTasks.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-muted-foreground">
            Pending Queue ({pendingTasks.length} shown of {pendingTotal})
          </h3>
          <ul className="space-y-2 max-h-80 overflow-y-auto">
            {pendingTasks.map((task) => (
              <li
                key={task.id}
                className="rounded-xl border border-border/20 bg-background/40 p-3 space-y-1"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-mono text-xs text-muted-foreground">{task.id.slice(0, 16)}…</p>
                    <p className="text-xs font-medium text-foreground">{task.task_type}</p>
                    {task.direction && (
                      <p className="text-xs text-muted-foreground line-clamp-2 mt-0.5">{task.direction}</p>
                    )}
                    {task.created_at && (
                      <p className="text-[10px] text-muted-foreground/60 mt-0.5">{relTs(task.created_at)}</p>
                    )}
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void runTask(task.id)}
                    disabled={status === "loading"}
                    className="shrink-0 text-xs"
                  >
                    Run
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
