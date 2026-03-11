"use client";

import { Suspense, useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useLiveRefresh } from "@/lib/live_refresh";
import type { AgentTask, RuntimeEvent, TaskListResponse, TaskLogResponse } from "./types";
import {
  asRecord,
  DEFAULT_PAGE_SIZE,
  EVENTS_LIMIT,
  EVENTS_TIMEOUT_MS,
  fetchWithTimeout,
  MAX_PAGE_SIZE,
  parsePositiveInt,
} from "./utils";
import { EvidenceTrail } from "./EvidenceTrail";
import { TasksListSection } from "./TasksListSection";

function toNumber(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value.trim());
    if (Number.isFinite(parsed)) return parsed;
  }
  return 0;
}

function TasksPageContent() {
  const searchParams = useSearchParams();
  const [rows, setRows] = useState<AgentTask[]>([]);
  const [totalTasks, setTotalTasks] = useState<number>(0);
  const [selectedTask, setSelectedTask] = useState<AgentTask | null>(null);
  const [selectedTaskLog, setSelectedTaskLog] = useState<string>("");
  const [selectedTaskEvents, setSelectedTaskEvents] = useState<RuntimeEvent[]>([]);
  const [selectedTaskEventsWarning, setSelectedTaskEventsWarning] = useState<string | null>(null);
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
      const res = await fetchWithTimeout(`/api/agent/tasks?${params.toString()}`);
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
      const responseTotal = Number.isFinite(Number(json.total)) ? Number(json.total) : taskRows.length;
      setTotalTasks(Math.max(taskRows.length, responseTotal));

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

  return (
    <main className="min-h-screen px-4 pb-8 pt-6 sm:px-6 lg:px-8">
      <div className="mx-auto w-full max-w-7xl space-y-4">
        <section className="space-y-1 px-1">
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Tasks In Motion</h1>
          <p className="max-w-3xl text-sm text-muted-foreground sm:text-base">
            Track work in progress, completed outcomes, and supporting evidence in one place.
          </p>
          <p className="text-xs text-muted-foreground">
            {statusFilter || typeFilter || taskIdFilter ? "Showing filtered tasks." : "Showing active and historical tasks."}
          </p>
        </section>

        <section className="rounded-xl border border-border/70 bg-card/50 px-3 py-3">
          <div className="flex flex-wrap items-center gap-2">
            {[
              { href: "/", label: "Home" },
              { href: "/portfolio", label: "Portfolio" },
              { href: "/gates", label: "Gates" },
              { href: "/flow", label: "Flow" },
              { href: "/agent", label: "Agent" },
              { href: "/contributors", label: "Contributors" },
            ].map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="inline-flex items-center rounded-full border border-border/70 bg-background/55 px-3 py-1.5 text-sm text-muted-foreground transition hover:text-foreground"
              >
                {link.label}
              </Link>
            ))}
          </div>
        </section>

        {status === "loading" && <p className="text-muted-foreground">Loading…</p>}
        {status === "error" && <p className="text-destructive">Error: {error}</p>}

        {status === "ok" && (
          <>
            <TasksListSection
              filteredRows={filteredRows}
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

            {taskIdFilter && (
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
            )}
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
            <p className="text-muted-foreground">Loading tasks…</p>
          </div>
        </main>
      }
    >
      <TasksPageContent />
    </Suspense>
  );
}
