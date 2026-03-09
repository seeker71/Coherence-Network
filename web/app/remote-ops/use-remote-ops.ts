"use client";

import { FormEvent, useCallback, useState } from "react";
import { getApiBase } from "@/lib/api";
import { useLiveRefresh } from "@/lib/live_refresh";
import type {
  DeployContract,
  HealthProxyResponse,
  HealthResponse,
  PendingTaskList,
  PipelineStatus,
  RemoteActionResponse,
} from "./types";
import { readResponseBody, toErrorMessage, toText } from "./utils";

const API_URL = getApiBase();

function summarizeExecutionError(err: unknown): string {
  const message = toText(err);
  const lower = message.toLowerCase();
  if (lower.includes("forbidden") || lower.includes("403")) {
    return `${message}. If execute is denied, provide the same X-Agent-Execute-Token used by AGENT_EXECUTE_TOKEN.`;
  }
  return message;
}

export function useRemoteOps() {
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

  const onCreate = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
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
    },
    [
      direction,
      executor,
      forcePaid,
      modelOverride,
      runAsPrThread,
      autoMergePr,
      waitPublic,
      taskType,
      runTask,
    ],
  );

  return {
    API_URL,
    health,
    proxy,
    deploy,
    pipeline,
    pending,
    runningMessage,
    direction,
    setDirection,
    taskType,
    setTaskType,
    executor,
    setExecutor,
    modelOverride,
    setModelOverride,
    forcePaid,
    setForcePaid,
    runAsPrThread,
    setRunAsPrThread,
    autoMergePr,
    setAutoMergePr,
    waitPublic,
    setWaitPublic,
    executeToken,
    setExecuteToken,
    status,
    error,
    tokenProvided,
    runRemoteSync,
    runPickUp,
    runTask,
    onCreate,
  };
}
