"use client";

import { FormEvent, useCallback, useState } from "react";
import Link from "next/link";
import { getApiBase } from "@/lib/api";
import { useLiveRefresh } from "@/lib/live_refresh";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const API_URL = getApiBase();

type HealthResponse = {
  status: string;
  uptime_human: string;
  uptime_seconds: number;
  version: string;
  timestamp: string;
  started_at: string;
};

type DeployContract = {
  result?: string;
  repository?: string;
  branch?: string;
  api_base?: string;
  web_base?: string;
  failing_checks?: string[];
  warnings?: string[];
  checks?: Array<{ name?: string; ok?: boolean; status_code?: number; error?: string }>;
};

type PipelineTask = {
  id: string;
  status: string;
  task_type: string;
  direction: string;
  created_at?: string;
  updated_at?: string;
};

type PipelineStatus = {
  running: PipelineTask[];
  pending: PipelineTask[];
};

type PendingTaskList = {
  tasks: PipelineTask[];
  total: number;
};

type RemoteActionResponse = {
  ok: boolean;
  task_id?: string;
  picked?: boolean;
  task?: PipelineTask;
  reason?: string;
  detail?: string;
};

type HealthProxyResponse = {
  api?: HealthResponse;
  web?: {
    status: string;
    uptime_human: string;
    uptime_seconds: number;
    started_at: string;
    updated_at?: string;
  };
  checked_at?: string;
  error?: string;
};

async function readResponseBody(response: Response): Promise<unknown> {
  const text = await response.text();
  const trimmed = text.trim();
  if (!trimmed) return null;
  if (!trimmed.startsWith("{") && !trimmed.startsWith("[")) return text;
  try {
    return JSON.parse(trimmed);
  } catch {
    return text;
  }
}

function pickErrorMessage(payload: unknown): string | null {
  if (typeof payload === "string") return payload;
  if (!payload || typeof payload !== "object") return null;
  const obj = payload as Record<string, unknown>;
  const candidates = [
    obj.detail,
    obj.error,
    obj.reason,
    obj.message,
    obj.task_id,
    obj.detail_message,
  ];
  for (const value of candidates) {
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
      return String(value);
    }
  }
  return null;
}

function toErrorMessage(payload: unknown, status: number): string {
  return pickErrorMessage(payload) ?? `Request failed with status ${status}`;
}

function toText(error: unknown): string {
  if (typeof error === "string") return error;
  if (error && typeof error === "object" && "message" in (error as Record<string, unknown>)) {
    return String((error as Record<string, unknown>).message);
  }
  return String(error);
}

function formatTs(value?: string): string {
  if (!value) return "unknown";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString();
}

export default function RemoteOpsPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [proxy, setProxy] = useState<HealthProxyResponse | null>(null);
  const [deploy, setDeploy] = useState<DeployContract | null>(null);
  const [pipeline, setPipeline] = useState<PipelineStatus | null>(null);
  const [pending, setPending] = useState<PendingTaskList | null>(null);
  const [runningMessage, setRunningMessage] = useState<string | null>(null);

  const [direction, setDirection] = useState("");
  const [taskType, setTaskType] = useState("impl");
  const [executor, setExecutor] = useState("openclaw");
  const [modelOverride, setModelOverride] = useState("");
  const [forcePaid, setForcePaid] = useState(false);
  const [runAsPrThread, setRunAsPrThread] = useState(false);
  const [autoMergePr, setAutoMergePr] = useState(false);
  const [waitPublic, setWaitPublic] = useState(false);
  const [executeToken, setExecuteToken] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const tokenProvided = executeToken.trim().length > 0;

  const authHeaders = useCallback(
    () => {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      const token = executeToken.trim();
      if (token) {
        headers["X-Agent-Execute-Token"] = token;
      }
      return headers;
    },
    [executeToken],
  );

  const runRemoteSync = useCallback(async () => {
    setStatus((prev) => (prev === "idle" ? "loading" : prev));
    setError(null);
    try {
      const [healthRes, proxyRes, deployRes, pipelineRes, pendingRes] = await Promise.all([
        fetch(`${API_URL}/api/health`, { cache: "no-store" }),
        fetch("/api/health-proxy", { cache: "no-store" }),
        fetch(`${API_URL}/api/gates/public-deploy-contract`, { cache: "no-store" }),
        fetch(`${API_URL}/api/agent/pipeline-status`, { cache: "no-store" }),
        fetch(`${API_URL}/api/agent/tasks?status=pending&limit=20`, { cache: "no-store" }),
      ]);

      const [healthJson, proxyJson, deployJson, pipelineJson, pendingJson] = await Promise.all([
        readResponseBody(healthRes),
        readResponseBody(proxyRes),
        readResponseBody(deployRes),
        readResponseBody(pipelineRes),
        readResponseBody(pendingRes),
      ]);

      if (!healthRes.ok) throw new Error(toErrorMessage(healthJson, healthRes.status));
      if (!deployRes.ok) throw new Error(toErrorMessage(deployJson, deployRes.status));
      if (!pipelineRes.ok) throw new Error(toErrorMessage(pipelineJson, pipelineRes.status));
      if (!pendingRes.ok) throw new Error(toErrorMessage(pendingJson, pendingRes.status));
      if (!proxyRes.ok) {
        const hasApiHealth =
          typeof proxyJson === "object" &&
          proxyJson !== null &&
          Object.prototype.hasOwnProperty.call(proxyJson, "api");
        if (!hasApiHealth) {
          throw new Error(toErrorMessage(proxyJson, proxyRes.status));
        }
      }

      setHealth(healthJson as HealthResponse);
      setProxy(proxyJson as HealthProxyResponse);
      setDeploy(deployJson as DeployContract);
      setPipeline(
        pipelineJson as PipelineStatus & {
          attention?: Record<string, unknown>;
        },
      );
      setPending(pendingJson as PendingTaskList);
      setStatus("idle");
      setRunningMessage(`Last refresh: ${new Date().toLocaleString()}`);
    } catch (err) {
      setStatus("error");
      setError(summarizeExecutionError(err));
    }
  }, []);

  const summarizeExecutionError = (err: unknown): string => {
    const message = toText(err);
    const lower = message.toLowerCase();
    if (lower.includes("forbidden") || lower.includes("403")) {
      return `${message}. If execute is denied, provide the same X-Agent-Execute-Token used by AGENT_EXECUTE_TOKEN.`;
    }
    return message;
  };

  useLiveRefresh(runRemoteSync);

  const runPickUp = useCallback(async () => {
    setStatus("loading");
    setError(null);
    try {
      const params = new URLSearchParams();
      if (taskType) params.set("task_type", taskType);
      if (forcePaid) params.set("force_paid_providers", "true");
      const query = params.toString();

      const res = await fetch(
        `${API_URL}/api/agent/tasks/pickup-and-execute${query ? `?${query}` : ""}`,
        {
          method: "POST",
          headers: authHeaders(),
          cache: "no-store",
        },
      );
      const actionJson = (await readResponseBody(res)) as RemoteActionResponse | null;
      if (!res.ok || !actionJson || !actionJson.ok) {
        throw new Error(toErrorMessage(actionJson, res.status));
      }
      if (actionJson.task?.id) {
        setRunningMessage(`Picked up and started: ${actionJson.task.id}`);
      } else if (actionJson.task_id) {
        setRunningMessage(`Picked up and started: ${actionJson.task_id}`);
      } else {
        setRunningMessage("Pickup request accepted.");
      }
      setStatus("idle");
      await runRemoteSync();
    } catch (err) {
      setStatus("error");
      setError(summarizeExecutionError(err));
    }
  }, [authHeaders, forcePaid, taskType, runRemoteSync]);

  const runTask = useCallback(
    async (taskId: string) => {
      setStatus("loading");
      setError(null);
      try {
        const params = new URLSearchParams();
        if (forcePaid) params.set("force_paid_providers", "true");
        const query = params.toString();

        const res = await fetch(
          `${API_URL}/api/agent/tasks/${encodeURIComponent(taskId)}/execute${query ? `?${query}` : ""}`,
          {
            method: "POST",
            headers: authHeaders(),
            cache: "no-store",
          },
        );
        const json = (await readResponseBody(res)) as { task_id?: string; ok?: boolean } | null;
        if (!res.ok || !(json?.ok ?? true)) {
          throw new Error(toErrorMessage(json, res.status));
        }
        setRunningMessage(`Started execution for ${taskId}`);
        setStatus("idle");
        await runRemoteSync();
      } catch (err) {
        setStatus("error");
        setError(summarizeExecutionError(err));
      }
    },
    [authHeaders, forcePaid, runRemoteSync],
  );

  async function onCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus("loading");
    setError(null);
    try {
      const trimmed = direction.trim();
      if (!trimmed) {
        throw new Error("Direction is required.");
      }
      const context: Record<string, string | boolean> = {
        executor,
      };
      if (forcePaid) context.force_paid_providers = true;
      if (modelOverride.trim()) context.model_override = modelOverride.trim();
      if (runAsPrThread) {
        context.execution_mode = "pr";
        context.create_pr = true;
      }
      if (autoMergePr) context.auto_merge_pr = true;
      if (waitPublic) context.wait_public = true;

      const res = await fetch(`${API_URL}/api/agent/tasks`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          direction: trimmed,
          task_type: taskType,
          context,
        }),
        cache: "no-store",
      });
      const json = (await readResponseBody(res)) as {
        id?: string;
        error?: string;
        detail?: string;
        direction?: string;
      } | null;
      if (!res.ok) {
        throw new Error(toErrorMessage(json, res.status));
      }
      if (!json) {
        throw new Error("Create task response was empty");
      }
      if (!json.id) throw new Error("Task id missing in response");
      setDirection("");
      setModelOverride("");
      setRunAsPrThread(false);
      setAutoMergePr(false);
      setWaitPublic(false);
      setRunningMessage(`Created task ${json.id}`);
      setStatus("idle");
      await runTask(json.id);
    } catch (err) {
      setStatus("error");
      setError(summarizeExecutionError(err));
    }
  }

  const pendingRows = pending?.tasks ?? [];
  const pendingTotal = pending?.total ?? 0;
  const active = pipeline?.running ?? [];
  const pendingCount = pipeline?.pending?.length ?? 0;

  return (
    <main className="min-h-screen p-8 max-w-6xl mx-auto space-y-6">
      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Coherence Network
        </Link>
        <Link href="/agent" className="text-muted-foreground hover:text-foreground">
          Agent
        </Link>
        <Link href="/tasks" className="text-muted-foreground hover:text-foreground">
          Tasks
        </Link>
        <Link href="/remote-ops" className="text-muted-foreground hover:text-foreground">
          Remote Ops
        </Link>
        <Link href="/gates" className="text-muted-foreground hover:text-foreground">
          Gates
        </Link>
        <a
          href={`${API_URL}/docs`}
          className="text-muted-foreground hover:text-foreground"
          target="_blank"
          rel="noopener noreferrer"
        >
          API Docs
        </a>
      </div>

      <section className="space-y-3 border rounded-md p-4">
        <h1 className="text-2xl font-bold">Remote Ops</h1>
        <p className="text-muted-foreground">
          Work from anywhere: verify Railway deploy status, monitor queue, and dispatch Codex on the deployed API.
        </p>
        <p className="text-xs text-muted-foreground">
          Current API target: <span className="font-mono">{API_URL}</span>
        </p>
        {tokenProvided ? (
          <p className="text-xs text-muted-foreground">Execute token is provided for execute endpoints.</p>
        ) : (
          <p className="text-xs text-destructive">
            Execute token is not set. If execution is protected, enter AGENT_EXECUTE_TOKEN before running.
          </p>
        )}
      </section>

      <section className="space-y-3 border rounded-md p-4">
        <h2 className="text-lg font-semibold">Deployment + Uptime</h2>
        <div className="grid gap-3 md:grid-cols-2">
          <div className="rounded border p-3">
            <h3 className="text-sm font-medium">API</h3>
            {health ? (
              <ul className="text-sm text-muted-foreground space-y-1">
                <li>Status: {health.status}</li>
                <li>Version: {health.version}</li>
                <li>Uptime: {health.uptime_human}</li>
                <li>Started: {formatTs(health.started_at)}</li>
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">Loading API health…</p>
            )}
          </div>
          <div className="rounded border p-3">
            <h3 className="text-sm font-medium">Web</h3>
            {proxy?.web ? (
              <ul className="text-sm text-muted-foreground space-y-1">
                <li>Status: {proxy.web.status}</li>
                <li>Uptime: {proxy.web.uptime_human}</li>
                <li>Checked: {formatTs(proxy.checked_at)}</li>
                <li>Updated SHA: {proxy.web.updated_at || "unknown"}</li>
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">Loading web proxy…</p>
            )}
          </div>
          <div className="rounded border p-3 md:col-span-2">
            <h3 className="text-sm font-medium">Public deploy contract</h3>
            {deploy ? (
              <pre className="text-xs bg-muted p-2 rounded overflow-auto">
                {JSON.stringify(deploy, null, 2)}
              </pre>
            ) : (
              <p className="text-sm text-muted-foreground">Loading deploy check…</p>
            )}
          </div>
        </div>
      </section>

      <section className="space-y-4 border rounded-md p-4">
        <h2 className="text-lg font-semibold">Controls</h2>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="text-sm">
            Execute token (optional)
            <Input
              value={executeToken}
              onChange={(e) => setExecuteToken(e.target.value)}
              placeholder="Only required if AGENT_EXECUTE_TOKEN is set"
            />
          </label>
          <label className="text-sm">
            Executor
            <Input
              value={executor}
              onChange={(e) => setExecutor(e.target.value)}
              placeholder="openclaw (or clawwork) | cursor | claude"
            />
          </label>
          <label className="text-sm">
            Task type
            <Input
              value={taskType}
              onChange={(e) => setTaskType(e.target.value)}
              placeholder="impl | spec | test | review | heal"
            />
          </label>
          <label className="text-sm">
            Model override (optional)
            <Input
              value={modelOverride}
              onChange={(e) => setModelOverride(e.target.value)}
              placeholder="openrouter/free | gpt-4.1-mini | gpt-5.3-codex-spark"
            />
          </label>
          <label className="text-sm md:col-span-2 flex items-center gap-2">
            <input
              type="checkbox"
              checked={forcePaid}
              onChange={(e) => setForcePaid(e.target.checked)}
            />
            Force paid provider override
          </label>
          <label className="text-sm md:col-span-2 flex items-center gap-2">
            <input
              type="checkbox"
              checked={runAsPrThread}
              onChange={(e) => setRunAsPrThread(e.target.checked)}
            />
            Run as Codex thread (create PR)
          </label>
          <label className="text-sm md:col-span-2 flex items-center gap-2">
            <input
              type="checkbox"
              checked={autoMergePr}
              onChange={(e) => setAutoMergePr(e.target.checked)}
            />
            Auto-merge PR when checks are ready
          </label>
          <label className="text-sm md:col-span-2 flex items-center gap-2">
            <input
              type="checkbox"
              checked={waitPublic}
              onChange={(e) => setWaitPublic(e.target.checked)}
            />
            Wait for public deploy validation before completion
          </label>
        </div>

        <form className="space-y-2" onSubmit={onCreate}>
          <label className="text-sm">
            New task direction
            <textarea
              value={direction}
              onChange={(e) => setDirection(e.target.value)}
              className="mt-1 min-h-24 w-full rounded border bg-background px-3 py-2 text-sm"
              placeholder="Add implementation for x, bug fix y, etc."
            />
          </label>
          <div className="flex gap-2">
            <Button type="submit" disabled={status === "loading"}>
              Create + Run Now
            </Button>
            <Button type="button" variant="outline" onClick={runPickUp} disabled={status === "loading"}>
              Pick up oldest pending and run
            </Button>
          </div>
        </form>

        {status === "error" && <p className="text-destructive">Error: {error}</p>}
        {runningMessage && <p className="text-sm text-muted-foreground">{runningMessage}</p>}
      </section>

      <section className="space-y-3 border rounded-md p-4">
        <h2 className="text-lg font-semibold">Queue / Pipeline</h2>
        <p className="text-sm text-muted-foreground">
          Running: {active.length} | pending (latest page): {pendingCount} | total pending: {pendingTotal}
        </p>
        {pendingRows.length === 0 ? (
          <p className="text-sm text-muted-foreground">No pending tasks in this window.</p>
        ) : (
          <ul className="space-y-2">
            {pendingRows.map((task) => (
              <li key={task.id} className="rounded border p-3">
                <div className="flex flex-wrap justify-between gap-2">
                  <span className="font-medium text-sm break-all">{task.id}</span>
                  <span className="text-xs text-muted-foreground">{task.task_type}</span>
                </div>
                <p className="text-sm text-muted-foreground mt-1">{task.direction}</p>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => void runTask(task.id)}
                  disabled={status === "loading"}
                  className="mt-2"
                >
                  Run now
                </Button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
