"use client";

import Link from "next/link";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import { useLiveRefresh } from "@/lib/live_refresh";

import { EvidenceTrail } from "./EvidenceTrail";
import { TasksListSection } from "./TasksListSection";
import type { AgentTask, RuntimeEvent, TaskListResponse, TaskLogResponse } from "./types";
import {
  asRecord,
  DEFAULT_PAGE_SIZE,
  describeTaskStatus,
  EVENTS_LIMIT,
  EVENTS_TIMEOUT_MS,
  fetchWithTimeout,
  MAX_PAGE_SIZE,
  parsePositiveInt,
} from "./utils";

function toNumber(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value.trim());
    if (Number.isFinite(parsed)) return parsed;
  }
  return 0;
}

type IdeasLookupResponse = {
  ideas?: Array<{
    id?: string;
    name?: string;
  }>;
};

type ActivityEvent = {
  task_id: string;
  node_id: string;
  node_name: string;
  provider: string;
  event_type: string;
  data: Record<string, unknown>;
  timestamp: string;
};

function elapsed(timestamp: string): string {
  const ms = Date.now() - new Date(timestamp).getTime();
  if (!Number.isFinite(ms) || ms < 0) return "just now";
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s elapsed`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ${s % 60}s elapsed`;
  return `${Math.floor(m / 60)}h ${m % 60}m elapsed`;
}

function TasksPageContent() {
  const searchParams = useSearchParams();
  const [rows, setRows] = useState<AgentTask[]>([]);
  const [totalTasks, setTotalTasks] = useState<number>(0);
  const [activeTasks, setActiveTasks] = useState<ActivityEvent[]>([]);
  const [recentActivity, setRecentActivity] = useState<ActivityEvent[]>([]);
  const [selectedTask, setSelectedTask] = useState<AgentTask | null>(null);
  const [selectedTaskLog, setSelectedTaskLog] = useState<string>("");
  const [selectedTaskEvents, setSelectedTaskEvents] = useState<RuntimeEvent[]>([]);
  const [selectedTaskEventsWarning, setSelectedTaskEventsWarning] = useState<string | null>(null);
  const [ideaNamesById, setIdeaNamesById] = useState<Record<string, string>>({});
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  const statusFilter = useMemo(() => (searchParams.get("status") || "").trim(), [searchParams]);
  const typeFilter = useMemo(() => (searchParams.get("task_type") || "").trim(), [searchParams]);
  const taskIdFilter = useMemo(() => (searchParams.get("task_id") || "").trim(), [searchParams]);
  const pageSize = useMemo(
    () => Math.max(1, Math.min(parsePositiveInt(searchParams.get("page_size"), DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE)),
    [searchParams],
  );
  const page = useMemo(() => parsePositiveInt(searchParams.get("page"), 1), [searchParams]);
  const offset = useMemo(() => (page - 1) * pageSize, [page, pageSize]);

  const loadRows = useCallback(async () => {
    setStatus((prev) => (prev === "ok" ? "ok" : "loading"));
    setError(null);
    try {
      const params = new URLSearchParams({
        limit: String(pageSize),
        offset: String(offset),
      });
      if (statusFilter) params.set("status", statusFilter);
      if (typeFilter) params.set("task_type", typeFilter);
      const [tasksResponse, ideasResponse, activeResponse, activityResponse] = await Promise.all([
        fetchWithTimeout(`/api/agent/tasks?${params.toString()}`),
        fetchWithTimeout("/api/ideas?limit=500"),
        fetchWithTimeout("/api/agent/tasks/active").catch(() => null),
        fetchWithTimeout("/api/agent/tasks/activity?limit=30").catch(() => null),
      ]);
      const json = (await tasksResponse.json()) as TaskListResponse;
      if (!tasksResponse.ok) throw new Error(JSON.stringify(json));
      const taskRows = Array.isArray(json.tasks)
        ? json.tasks
        : Array.isArray(json.items)
          ? json.items
          : Array.isArray(json)
            ? json
            : [];
      setRows(taskRows);
      const responseTotal = Number.isFinite(Number(json.total)) ? Number(json.total) : taskRows.length;
      setTotalTasks(Math.max(taskRows.length, responseTotal));

      if (ideasResponse.ok) {
        const ideasPayload = (await ideasResponse.json()) as IdeasLookupResponse;
        const names = (ideasPayload.ideas || []).reduce<Record<string, string>>((acc, row) => {
          const id = String(row.id || "").trim();
          const name = String(row.name || "").trim();
          if (id && name) acc[id] = name;
          return acc;
        }, {});
        setIdeaNamesById(names);
      } else {
        setIdeaNamesById({});
      }

      // Active tasks and recent activity
      if (activeResponse && activeResponse.ok) {
        const activePayload = (await activeResponse.json()) as ActivityEvent[];
        setActiveTasks(Array.isArray(activePayload) ? activePayload : []);
      } else {
        setActiveTasks([]);
      }
      if (activityResponse && activityResponse.ok) {
        const activityPayload = (await activityResponse.json()) as ActivityEvent[];
        setRecentActivity(Array.isArray(activityPayload) ? activityPayload : []);
      } else {
        setRecentActivity([]);
      }

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
  }, [offset, pageSize, statusFilter, taskIdFilter, typeFilter]);

  useLiveRefresh(loadRows);

  // Auto-refresh every 10 seconds for live task visibility
  const loadRowsRef = useRef(loadRows);
  loadRowsRef.current = loadRows;
  useEffect(() => {
    const timer = window.setInterval(() => {
      void loadRowsRef.current();
    }, 10_000);
    return () => window.clearInterval(timer);
  }, []);

  const filteredRows = useMemo(() => {
    return rows.filter((row) => {
      if (taskIdFilter && row.id !== taskIdFilter) return false;
      return true;
    });
  }, [rows, taskIdFilter]);

  const pageStart = totalTasks > 0 ? offset + 1 : 0;
  const pageEnd = totalTasks > 0 ? offset + filteredRows.length : 0;
  const hasPrevious = page > 1;
  const hasNext = pageEnd < totalTasks;
  const previousHref = `/tasks?page=${Math.max(1, page - 1)}&page_size=${pageSize}${statusFilter ? `&status=${encodeURIComponent(statusFilter)}` : ""}${typeFilter ? `&task_type=${encodeURIComponent(typeFilter)}` : ""}`;
  const nextHref = `/tasks?page=${page + 1}&page_size=${pageSize}${statusFilter ? `&status=${encodeURIComponent(statusFilter)}` : ""}${typeFilter ? `&task_type=${encodeURIComponent(typeFilter)}` : ""}`;

  const selectedContext = useMemo(() => asRecord(selectedTask?.context), [selectedTask]);
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
    return [...map.entries()].map(([ideaId, source]) => ({
      ideaId,
      ideaName: ideaNamesById[ideaId] || undefined,
      source,
    }));
  }, [ideaNamesById, selectedContext, selectedTaskEvents]);
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
        reviewPassFail: String(metadata.review_pass_fail || "").trim(),
        verifiedAssertions: String(metadata.verified_assertions || "").trim(),
        infrastructureCostUsd: toNumber(metadata.infrastructure_cost_usd),
        externalProviderCostUsd: toNumber(metadata.external_provider_cost_usd),
        totalCostUsd: toNumber(metadata.total_cost_usd),
      };
    });
  }, [selectedTaskEvents]);

  const acceptanceProof = useMemo(() => {
    let infrastructureCostUsd = 0;
    let externalProviderCostUsd = 0;
    let totalCostUsd = 0;
    for (const row of evidenceEvents) {
      if (row.trackingKind !== "agent_tool_call") continue;
      infrastructureCostUsd += row.infrastructureCostUsd;
      externalProviderCostUsd += row.externalProviderCostUsd;
      totalCostUsd += row.totalCostUsd;
    }
    const completionRow = evidenceEvents.find((row) => row.trackingKind === "agent_task_completion");
    const reviewPassFail = completionRow?.reviewPassFail || "";
    const verifiedAssertions = completionRow?.verifiedAssertions || "";
    const reviewAccepted = reviewPassFail === "PASS" ? true : reviewPassFail === "FAIL" ? false : null;
    return {
      reviewPassFail,
      verifiedAssertions,
      reviewAccepted,
      infrastructureCostUsd: Number(infrastructureCostUsd.toFixed(6)),
      externalProviderCostUsd: Number(externalProviderCostUsd.toFixed(6)),
      totalCostUsd: Number(totalCostUsd.toFixed(6)),
    };
  }, [evidenceEvents]);

  const readyCount = useMemo(
    () => filteredRows.filter((row) => ["pending", "queued"].includes(row.status)).length,
    [filteredRows],
  );
  const activeCount = useMemo(
    () => filteredRows.filter((row) => ["running", "claimed", "in_progress"].includes(row.status)).length,
    [filteredRows],
  );
  const blockedCount = useMemo(
    () => filteredRows.filter((row) => row.status === "failed" || row.status === "needs_decision").length,
    [filteredRows],
  );
  const finishedCount = useMemo(
    () => filteredRows.filter((row) => row.status === "completed").length,
    [filteredRows],
  );
  const selectedSummary = taskIdFilter
    ? selectedTask
      ? describeTaskStatus(selectedTask.status)
      : status === "loading"
        ? "Loading selected work card…"
        : "The selected work card is unavailable right now."
    : "Open a work card to see details and keep it up to date.";

  return (
    <main className="min-h-screen px-4 pb-8 pt-6 sm:px-6 lg:px-8">
      <div className="mx-auto w-full max-w-7xl space-y-4">
        <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 sm:p-7 space-y-3">
          <p className="text-sm text-muted-foreground">Work view</p>
          <h1 className="text-3xl md:text-4xl font-light tracking-tight">Work That Is Moving</h1>
          <p className="max-w-3xl text-sm text-muted-foreground sm:text-base">
            See what is active, what is blocked, what finished recently, and open one work card when you need to update it.
          </p>
          <p className="text-xs text-muted-foreground">
            {statusFilter || typeFilter || taskIdFilter ? "Showing a filtered work view." : "Showing active and past work cards."}
          </p>
          <div className="flex flex-wrap gap-2">
            <Link href="/today" className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200">
              Today
            </Link>
            <Link href="/ideas" className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200">
              Ideas
            </Link>
            <Link href="/flow" className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200">
              Progress
            </Link>
            <Link href="/demo" className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200">
              Demo
            </Link>
          </div>
        </section>

        <section className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3 lg:grid-cols-5">
          <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
            <p className="text-muted-foreground">Work cards in view</p>
            <p className="text-2xl font-light text-primary">{filteredRows.length}</p>
          </div>
          <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
            <p className="text-muted-foreground">Ready to start</p>
            <p className="text-2xl font-light text-primary">{readyCount}</p>
          </div>
          <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
            <p className="text-muted-foreground">In progress</p>
            <p className="text-2xl font-light text-primary">{activeCount}</p>
          </div>
          <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
            <p className="text-muted-foreground">Needs attention</p>
            <p className="text-2xl font-light text-primary">{blockedCount}</p>
          </div>
          <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
            <p className="text-muted-foreground">Finished</p>
            <p className="text-2xl font-light text-primary">{finishedCount}</p>
          </div>
        </section>

        {activeTasks.length > 0 && (
          <section className="rounded-2xl border border-amber-500/30 bg-gradient-to-b from-amber-500/5 to-card/30 p-5 space-y-3">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2.5 w-2.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400/60" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-amber-400" />
              </span>
              <h2 className="text-lg font-medium">Active Now</h2>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {activeTasks.map((task) => (
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
                    <span className="text-sm font-medium text-foreground line-clamp-2">
                      {String(task.data?.task_type || task.event_type || "Working")}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Node: {task.node_name || "unknown"} | Provider: {task.provider || "unknown"} | {elapsed(task.timestamp)}
                  </p>
                  <p className="text-xs text-amber-500/80">Watch live →</p>
                </Link>
              ))}
            </div>
          </section>
        )}

        {recentActivity.length > 0 && !taskIdFilter && (
          <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3">
            <h2 className="text-lg font-medium">Recent Activity</h2>
            <div className="space-y-1.5 max-h-48 overflow-y-auto">
              {recentActivity.slice().reverse().map((event, i) => (
                <div key={event.timestamp + i} className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span className={`inline-flex h-1.5 w-1.5 rounded-full shrink-0 ${
                    event.event_type === "completed" ? "bg-green-400" :
                    event.event_type === "failed" || event.event_type === "timeout" ? "bg-red-400" :
                    event.event_type === "executing" ? "bg-amber-400" :
                    "bg-muted-foreground/40"
                  }`} />
                  <Link
                    href={`/tasks/${encodeURIComponent(event.task_id)}`}
                    className="hover:text-foreground transition-colors"
                  >
                    <span className="font-mono">{event.task_id.slice(0, 8)}</span>
                  </Link>
                  <span>{event.event_type}</span>
                  {event.node_name && <span>on {event.node_name}</span>}
                  {event.provider && <span>via {event.provider}</span>}
                  <span className="ml-auto tabular-nums">{new Date(event.timestamp).toLocaleTimeString()}</span>
                </div>
              ))}
            </div>
          </section>
        )}

        {taskIdFilter ? (
          <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-2">
            <h2 className="text-xl font-medium">Selected Work Card</h2>
            <p className="text-sm text-muted-foreground">{selectedSummary}</p>
          </section>
        ) : null}

        {status === "loading" && <p className="text-muted-foreground">Loading work cards…</p>}
        {status === "error" && <p className="text-destructive">Error: {error}</p>}

        {status === "ok" && (
          <>
            <TasksListSection
              filteredRows={filteredRows}
              ideaNamesById={ideaNamesById}
              pageStart={pageStart}
              pageEnd={pageEnd}
              totalTasks={totalTasks}
              page={page}
              statusFilter={statusFilter}
              typeFilter={typeFilter}
              taskIdFilter={taskIdFilter}
              hasPrevious={hasPrevious}
              hasNext={hasNext}
              previousHref={previousHref}
              nextHref={nextHref}
            />

            {taskIdFilter ? (
              <EvidenceTrail
                taskIdFilter={taskIdFilter}
                selectedTask={selectedTask}
                selectedTaskLog={selectedTaskLog}
                selectedTaskEventsWarning={selectedTaskEventsWarning}
                selectedContext={selectedContext}
                evidenceIdeas={evidenceIdeas}
                evidenceEvents={evidenceEvents}
                acceptanceProof={acceptanceProof}
                onTaskUpdated={loadRows}
              />
            ) : null}
          </>
        )}
      </div>
    </main>
  );
}

export default function TasksPage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen px-4 pb-8 pt-6 sm:px-6 lg:px-8">
          <div className="mx-auto w-full max-w-7xl">
            <p className="text-muted-foreground">Loading work cards…</p>
          </div>
        </main>
      }
    >
      <TasksPageContent />
    </Suspense>
  );
}
