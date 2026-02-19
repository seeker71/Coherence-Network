"use client";

import { Suspense, useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useLiveRefresh } from "@/lib/live_refresh";

const REQUEST_TIMEOUT_MS = 12000;
const EVENTS_TIMEOUT_MS = 8000;
const EVENTS_LIMIT = 500;

type AgentTask = {
  id: string;
  status: string;
  task_type: string;
  direction: string;
  model?: string;
  output?: string | null;
  current_step?: string | null;
  context?: Record<string, unknown> | null;
  claimed_by?: string | null;
  created_at?: string;
  updated_at?: string;
};

type RuntimeEvent = {
  id: string;
  recorded_at?: string;
  endpoint: string;
  method?: string;
  status_code: number;
  idea_id?: string | null;
  origin_idea_id?: string | null;
  metadata?: Record<string, unknown> | null;
};

type TaskListResponse = {
  tasks?: AgentTask[];
  items?: AgentTask[];
};

type TaskLogResponse = {
  task_id: string;
  log?: string;
};

function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  return value as Record<string, unknown>;
}

function toInt(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return Math.trunc(value);
  if (typeof value === "string" && value.trim()) {
    const parsed = Number.parseInt(value.trim(), 10);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function formatTime(value?: string): string {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

function tailLines(value: string, maxLines: number): string {
  const rows = value.split("\n");
  return rows.slice(Math.max(0, rows.length - maxLines)).join("\n");
}

async function fetchWithTimeout(input: string, init: RequestInit = {}, timeoutMs = REQUEST_TIMEOUT_MS): Promise<Response> {
  const controller = new AbortController();
  let timeout: ReturnType<typeof setTimeout> | null = null;
  const timeoutPromise = new Promise<Response>((_, reject) => {
    timeout = setTimeout(() => {
      controller.abort(new DOMException("Request timed out", "TimeoutError"));
      reject(new Error(`Request timed out after ${timeoutMs}ms`));
    }, timeoutMs);
  });

  const fetchPromise = fetch(input, {
    ...init,
    signal: controller.signal,
    cache: init.cache ?? "no-store",
  });

  try {
    return await Promise.race([fetchPromise, timeoutPromise]);
  } finally {
    if (timeout) clearTimeout(timeout);
  }
}

function TasksPageContent() {
  const searchParams = useSearchParams();
  const [rows, setRows] = useState<AgentTask[]>([]);
  const [selectedTask, setSelectedTask] = useState<AgentTask | null>(null);
  const [selectedTaskLog, setSelectedTaskLog] = useState<string>("");
  const [selectedTaskEvents, setSelectedTaskEvents] = useState<RuntimeEvent[]>([]);
  const [selectedTaskEventsWarning, setSelectedTaskEventsWarning] = useState<string | null>(null);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  const statusFilter = useMemo(() => (searchParams.get("status") || "").trim(), [searchParams]);
  const typeFilter = useMemo(() => (searchParams.get("task_type") || "").trim(), [searchParams]);
  const taskIdFilter = useMemo(() => (searchParams.get("task_id") || "").trim(), [searchParams]);

  const loadRows = useCallback(async () => {
    setStatus((prev) => (prev === "ok" ? "ok" : "loading"));
    setError(null);
    try {
      const res = await fetchWithTimeout("/api/agent/tasks");
      const json = (await res.json()) as TaskListResponse;
      if (!res.ok) throw new Error(JSON.stringify(json));
      const taskRows = Array.isArray(json.tasks)
        ? json.tasks
        : Array.isArray(json.items)
          ? json.items
          : Array.isArray(json)
            ? json
            : [];
      setRows(taskRows);

      if (!taskIdFilter) {
        setSelectedTask(null);
        setSelectedTaskLog("");
        setSelectedTaskEvents([]);
        setSelectedTaskEventsWarning(null);
      } else {
        const [taskResult, logResult, eventsResult] = await Promise.allSettled([
          fetchWithTimeout(`/api/agent/tasks/${encodeURIComponent(taskIdFilter)}`),
          fetchWithTimeout(`/api/agent/tasks/${encodeURIComponent(taskIdFilter)}/log`),
          fetchWithTimeout(`/api/runtime/events?limit=${EVENTS_LIMIT}`, {}, EVENTS_TIMEOUT_MS),
        ]);

        if (taskResult.status === "fulfilled" && taskResult.value.ok) {
          const taskPayload = (await taskResult.value.json()) as AgentTask;
          setSelectedTask(taskPayload ?? null);
        } else {
          setSelectedTask(null);
        }

        if (logResult.status === "fulfilled" && logResult.value.ok) {
          const logPayload = (await logResult.value.json()) as TaskLogResponse;
          setSelectedTaskLog(String(logPayload.log || ""));
        } else {
          setSelectedTaskLog("");
        }

        if (eventsResult.status === "fulfilled") {
          if (eventsResult.value.ok) {
            const eventsPayload = (await eventsResult.value.json()) as RuntimeEvent[] | { items?: RuntimeEvent[] };
            const eventsRows = Array.isArray(eventsPayload)
              ? eventsPayload
              : Array.isArray(eventsPayload.items)
                ? eventsPayload.items
                : [];
            const filtered = Array.isArray(eventsRows)
              ? eventsRows
                  .filter((event) => {
                    const metadata = asRecord(event.metadata);
                    return String(metadata.task_id || "").trim() === taskIdFilter;
                  })
                  .sort((a, b) => {
                    const aTs = new Date(String(a.recorded_at || "")).getTime();
                    const bTs = new Date(String(b.recorded_at || "")).getTime();
                    return (Number.isFinite(bTs) ? bTs : 0) - (Number.isFinite(aTs) ? aTs : 0);
                  })
              : [];
            setSelectedTaskEvents(filtered);
            setSelectedTaskEventsWarning(null);
          } else {
            setSelectedTaskEvents([]);
            setSelectedTaskEventsWarning(`HTTP ${eventsResult.value.status}`);
          }
        } else {
          setSelectedTaskEvents([]);
          setSelectedTaskEventsWarning(String(eventsResult.reason || "runtime events unavailable"));
        }
      }

      setStatus("ok");
    } catch (e) {
      setStatus("error");
      setError(String(e));
    }
  }, [taskIdFilter]);

  useLiveRefresh(loadRows);

  const filteredRows = useMemo(() => {
    return rows.filter((row) => {
      if (statusFilter && row.status !== statusFilter) return false;
      if (typeFilter && row.task_type !== typeFilter) return false;
      if (taskIdFilter && row.id !== taskIdFilter) return false;
      return true;
    });
  }, [rows, statusFilter, typeFilter, taskIdFilter]);

  const selectedContext = useMemo(() => asRecord(selectedTask?.context), [selectedTask]);
  const failureHits = toInt(selectedContext.failure_hits);
  const retryCount = toInt(selectedContext.retry_count);
  const retryHint = String(selectedContext.retry_hint || "").trim();
  const lastFailure = String(selectedContext.last_failure_output || "").trim();

  const evidenceIdeas = useMemo(() => {
    const map = new Map<string, string>();
    const fromContext = String(selectedContext.idea_id || "").trim();
    if (fromContext) map.set(fromContext, "task context");
    for (const event of selectedTaskEvents) {
      const ideaId = String(event.idea_id || "").trim();
      const originIdeaId = String(event.origin_idea_id || "").trim();
      if (ideaId && !map.has(ideaId)) map.set(ideaId, "runtime idea_id");
      if (originIdeaId && !map.has(originIdeaId)) map.set(originIdeaId, "runtime origin_idea_id");
    }
    return [...map.entries()].map(([ideaId, source]) => ({ ideaId, source }));
  }, [selectedContext, selectedTaskEvents]);

  const evidenceEvents = useMemo(() => {
    return selectedTaskEvents.map((event) => {
      const metadata = asRecord(event.metadata);
      return {
        id: event.id,
        recordedAt: event.recorded_at,
        endpoint: event.endpoint,
        statusCode: event.status_code,
        trackingKind: String(metadata.tracking_kind || "").trim(),
        finalStatus: String(metadata.task_final_status || "").trim(),
      };
    });
  }, [selectedTaskEvents]);

  return (
    <main className="min-h-screen p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Home
        </Link>
        <Link href="/portfolio" className="text-muted-foreground hover:text-foreground">
          Portfolio
        </Link>
        <Link href="/gates" className="text-muted-foreground hover:text-foreground">
          Gates
        </Link>
        <Link href="/flow" className="text-muted-foreground hover:text-foreground">
          Flow
        </Link>
        <Link href="/agent" className="text-muted-foreground hover:text-foreground">
          Agent
        </Link>
        <Link href="/contributors" className="text-muted-foreground hover:text-foreground">
          Contributors
        </Link>
      </div>
      <h1 className="text-2xl font-bold">Tasks</h1>
      <p className="text-muted-foreground">
        Human interface for `GET /api/agent/tasks`.
        {statusFilter ? (
          <>
            {" "}
            status <code>{statusFilter}</code>.
          </>
        ) : null}
        {typeFilter ? (
          <>
            {" "}
            task type <code>{typeFilter}</code>.
          </>
        ) : null}
        {taskIdFilter ? (
          <>
            {" "}
            task id <code>{taskIdFilter}</code>.
          </>
        ) : null}
      </p>

      {status === "loading" && <p className="text-muted-foreground">Loading…</p>}
      {status === "error" && <p className="text-destructive">Error: {error}</p>}

      {status === "ok" && (
        <>
          <section className="rounded border p-4 space-y-3">
            <p className="text-sm text-muted-foreground">
              Total: {filteredRows.length}
              {(statusFilter || typeFilter || taskIdFilter) ? (
                <>
                  {" "}
                  |{" "}
                  <Link href="/tasks" className="underline hover:text-foreground">
                    Clear filters
                  </Link>
                </>
              ) : null}
            </p>
            <ul className="space-y-2 text-sm">
              {filteredRows.slice(0, 50).map((t) => (
                <li key={t.id} className="rounded border p-2 space-y-1">
                  <div className="flex justify-between gap-3">
                    <span className="font-medium">
                      <Link href={`/tasks?task_id=${encodeURIComponent(t.id)}`} className="underline hover:text-foreground">
                        {t.id}
                      </Link>
                    </span>
                    <span className="text-muted-foreground text-right">
                      <Link href={`/tasks?task_type=${encodeURIComponent(t.task_type)}`} className="underline hover:text-foreground">
                        {t.task_type}
                      </Link>{" "}
                      |{" "}
                      <Link href={`/tasks?status=${encodeURIComponent(t.status)}`} className="underline hover:text-foreground">
                        {t.status}
                      </Link>
                    </span>
                  </div>
                  <div className="text-muted-foreground">{t.direction}</div>
                </li>
              ))}
            </ul>
          </section>

          {taskIdFilter && (
            <section className="rounded border p-4 space-y-3 text-sm">
              <h2 className="font-semibold">Evidence Trail</h2>
              {selectedTask ? (
                <>
                  <p className="text-muted-foreground">
                    status <code>{selectedTask.status}</code> | task_type <code>{selectedTask.task_type}</code> | model{" "}
                    <code>{selectedTask.model || "-"}</code>
                  </p>
                  <p className="text-muted-foreground">
                    created {formatTime(selectedTask.created_at)} | updated {formatTime(selectedTask.updated_at)} | claimed_by{" "}
                    <code>{selectedTask.claimed_by || "-"}</code>
                  </p>
                  {selectedTask.current_step ? (
                    <p className="text-muted-foreground">
                      current_step <code>{selectedTask.current_step}</code>
                    </p>
                  ) : null}
                  <div>
                    <p className="text-muted-foreground mb-1">output</p>
                    <pre className="rounded bg-muted/40 p-2 overflow-auto whitespace-pre-wrap break-words">
                      {selectedTask.output || "(empty)"}
                    </pre>
                  </div>

                  <div className="space-y-1">
                    <p className="text-muted-foreground">retry/failure telemetry</p>
                    <p>
                      failure_hits <code>{failureHits ?? "-"}</code> | retry_count <code>{retryCount ?? "-"}</code>
                    </p>
                    {lastFailure ? (
                      <p className="text-muted-foreground">
                        last_failure_output <code>{lastFailure}</code>
                      </p>
                    ) : null}
                    {retryHint ? (
                      <p className="text-muted-foreground">
                        retry_hint <code>{retryHint}</code>
                      </p>
                    ) : null}
                  </div>

                  <div className="space-y-1">
                    <p className="text-muted-foreground">linked ideas</p>
                    {evidenceIdeas.length === 0 ? (
                      <p className="text-muted-foreground">No idea linkage found for this task.</p>
                    ) : (
                      <ul className="space-y-1">
                        {evidenceIdeas.map((row) => (
                          <li key={row.ideaId}>
                            <Link href={`/ideas/${encodeURIComponent(row.ideaId)}`} className="underline hover:text-foreground">
                              {row.ideaId}
                            </Link>{" "}
                            <span className="text-muted-foreground">({row.source})</span>{" "}
                            |{" "}
                            <Link href={`/flow?idea_id=${encodeURIComponent(row.ideaId)}`} className="underline hover:text-foreground">
                              flow
                            </Link>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>

                  <div className="space-y-1">
                    <p className="text-muted-foreground">runtime events for this task</p>
                    {selectedTaskEventsWarning ? (
                      <p className="text-muted-foreground">
                        runtime events unavailable: <code>{selectedTaskEventsWarning}</code>
                      </p>
                    ) : null}
                    {evidenceEvents.length === 0 ? (
                      <p className="text-muted-foreground">No runtime events found.</p>
                    ) : (
                      <ul className="space-y-1">
                        {evidenceEvents.slice(0, 20).map((row) => (
                          <li key={row.id}>
                            <code>{row.id}</code> | {formatTime(row.recordedAt)} | <code>{row.endpoint}</code> | status{" "}
                            <code>{row.statusCode}</code>
                            {row.trackingKind ? (
                              <>
                                {" "}
                                | kind <code>{row.trackingKind}</code>
                              </>
                            ) : null}
                            {row.finalStatus ? (
                              <>
                                {" "}
                                | final <code>{row.finalStatus}</code>
                              </>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>

                  <div>
                    <p className="text-muted-foreground mb-1">task log tail (proof)</p>
                    <pre className="rounded bg-muted/40 p-2 overflow-auto whitespace-pre-wrap break-words">
                      {selectedTaskLog ? tailLines(selectedTaskLog, 40) : "(task log unavailable)"}
                    </pre>
                  </div>
                </>
              ) : (
                <p className="text-muted-foreground">Task details unavailable for <code>{taskIdFilter}</code>.</p>
              )}
            </section>
          )}
        </>
      )}
    </main>
  );
}

export default function TasksPage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen p-8 max-w-5xl mx-auto">
          <p className="text-muted-foreground">Loading tasks…</p>
        </main>
      }
    >
      <TasksPageContent />
    </Suspense>
  );
}
