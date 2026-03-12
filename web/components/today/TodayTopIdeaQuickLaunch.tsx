"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { humanizeStatus } from "@/lib/humanize";

type TodayTopIdeaQuickLaunchProps = {
  ideaId: string;
  ideaName: string;
};

type LaunchState = "idle" | "creating" | "starting" | "running" | "created" | "error";
type TaskType = "impl" | "review" | "spec";
type UpdateState = "idle" | "saving" | "saved" | "error";
type CreatedTaskSnapshot = {
  id: string;
  status: string;
  task_type: string;
  direction: string;
  current_step?: string | null;
  output?: string | null;
  updated_at?: string | null;
};
type RuntimeEvent = {
  id: string;
  endpoint: string;
  status_code: number;
  recorded_at?: string | null;
  metadata?: Record<string, unknown> | null;
};
type TaskActivityRow = {
  id: string;
  recordedAt: string;
  title: string;
  detail: string;
};
type NextActionRecommendation = {
  title: string;
  detail: string;
  href: string;
  cta: string;
};

const LATEST_TODAY_TASK_STORAGE_KEY = "coherence.today.latest_task_id";
const ACTIVITY_LIMIT = 5;

function directionForType(taskType: TaskType, ideaName: string): string {
  if (taskType === "review") {
    return `Review current progress for ${ideaName}. Report confidence, key risks, and one clear next action to improve MVP readiness.`;
  }
  if (taskType === "spec") {
    return `Define the next one-week plan for ${ideaName} with measurable outcomes and evidence to collect before implementation.`;
  }
  return `Deliver the next highest-value milestone for ${ideaName}. Focus on visible MVP progress and record what changed for users.`;
}

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string; error?: string; message?: string };
    return String(payload.detail || payload.error || payload.message || `HTTP ${response.status}`);
  } catch {
    const text = await response.text();
    return String(text || `HTTP ${response.status}`);
  }
}

function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  return value as Record<string, unknown>;
}

function humanizeWords(value: string): string {
  const normalized = value.trim().toLowerCase();
  if (!normalized) return "Unknown";
  return normalized
    .split("_")
    .map((word) => `${word.slice(0, 1).toUpperCase()}${word.slice(1)}`)
    .join(" ");
}

function formatEventTime(value?: string | null): string {
  if (!value) return "Time unavailable";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Time unavailable";
  return parsed.toLocaleString();
}

function activityRowFromEvent(event: RuntimeEvent): TaskActivityRow {
  const metadata = asRecord(event.metadata);
  const trackingKind = String(metadata.tracking_kind || "").trim();
  const lifecycleEvent = String(metadata.lifecycle_event || "").trim();
  const taskStatus = String(metadata.task_status || "").trim();
  const reason = String(metadata.reason || metadata.error || "").trim();
  const finalStatus = String(metadata.task_final_status || "").trim();
  const reviewPassFail = String(metadata.review_pass_fail || "").trim().toUpperCase();
  const verifiedAssertions = String(metadata.verified_assertions || "").trim();

  if (trackingKind === "agent_task_completion") {
    const reviewSuffix = reviewPassFail ? ` Review ${reviewPassFail}.` : "";
    const verifiedSuffix = verifiedAssertions ? ` Verified: ${verifiedAssertions}.` : "";
    return {
      id: event.id,
      recordedAt: formatEventTime(event.recorded_at),
      title: `${humanizeStatus(finalStatus || "completed")} result recorded`,
      detail: `${humanizeWords(trackingKind)} via ${event.endpoint}.${reviewSuffix}${verifiedSuffix}`.trim(),
    };
  }

  if (trackingKind === "agent_task_lifecycle") {
    return {
      id: event.id,
      recordedAt: formatEventTime(event.recorded_at),
      title: `${humanizeWords(lifecycleEvent || "lifecycle")} (${humanizeStatus(taskStatus || "pending")})`,
      detail: reason ? reason : `${humanizeWords(trackingKind)} at ${event.endpoint}.`,
    };
  }

  return {
    id: event.id,
    recordedAt: formatEventTime(event.recorded_at),
    title: `${humanizeWords(trackingKind || "activity")} at ${event.endpoint}`,
    detail: `Status code ${event.status_code}.`,
  };
}

function deriveNextAction(
  task: CreatedTaskSnapshot,
  activityRows: TaskActivityRow[],
): NextActionRecommendation {
  const latestActivity = activityRows[0];
  const latestDetail = latestActivity?.detail || "";
  const currentStep = String(task.current_step || "").trim();
  const latestOutcome = String(task.output || "").trim();
  const taskHref = `/tasks?task_id=${encodeURIComponent(task.id)}`;

  if (task.status === "failed") {
    return {
      title: "Resolve the blocker before restarting work",
      detail: latestOutcome || latestDetail || "This task is blocked or failed and needs a human decision on how to continue.",
      href: taskHref,
      cta: "Review blocker",
    };
  }

  if (task.status === "completed") {
    return {
      title: "Review the result and choose the follow-up task",
      detail: latestOutcome || latestDetail || "This task is complete. Confirm the outcome and decide what should happen next.",
      href: taskHref,
      cta: "Review result",
    };
  }

  if (task.status === "running") {
    return {
      title: "Check whether execution is still making progress",
      detail: currentStep || latestDetail || "This task is in progress. Confirm it is advancing and update status if it has stalled.",
      href: taskHref,
      cta: "Inspect progress",
    };
  }

  if (task.status === "needs_decision") {
    return {
      title: "Make the decision this task is waiting on",
      detail: latestOutcome || latestDetail || "Execution is paused pending a human choice.",
      href: taskHref,
      cta: "Open decision",
    };
  }

  return {
    title: "Start or re-start this task now",
    detail: latestDetail || "The task exists, but it is not actively moving. Re-open it and decide whether to execute or update it.",
    href: taskHref,
    cta: "Open task",
  };
}

export default function TodayTopIdeaQuickLaunch({
  ideaId,
  ideaName,
}: TodayTopIdeaQuickLaunchProps) {
  const [taskType, setTaskType] = useState<TaskType>("impl");
  const [launchState, setLaunchState] = useState<LaunchState>("idle");
  const [createdTaskId, setCreatedTaskId] = useState("");
  const [createdTask, setCreatedTask] = useState<CreatedTaskSnapshot | null>(null);
  const [activityRows, setActivityRows] = useState<TaskActivityRow[]>([]);
  const [updateState, setUpdateState] = useState<UpdateState>("idle");
  const [updateMessage, setUpdateMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  const nextAction = createdTask ? deriveNextAction(createdTask, activityRows) : null;

  function persistLatestTaskId(taskId: string): void {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(LATEST_TODAY_TASK_STORAGE_KEY, taskId);
  }

  function clearLatestTaskId(): void {
    if (typeof window === "undefined") return;
    window.localStorage.removeItem(LATEST_TODAY_TASK_STORAGE_KEY);
  }

  async function refreshCreatedTask(taskId: string): Promise<void> {
    const taskResponse = await fetch(`/api/agent/tasks/${encodeURIComponent(taskId)}`, { cache: "no-store" });
    if (!taskResponse.ok) throw new Error(await readErrorMessage(taskResponse));
    const payload = (await taskResponse.json()) as CreatedTaskSnapshot;

    let timeline: TaskActivityRow[] = [];
    try {
      const eventsResponse = await fetch(`/api/runtime/events?limit=80`, { cache: "no-store" });
      if (eventsResponse.ok) {
        const eventsPayload = (await eventsResponse.json()) as RuntimeEvent[];
        if (Array.isArray(eventsPayload)) {
          timeline = eventsPayload
            .filter((event) => {
              const metadata = asRecord(event.metadata);
              return String(metadata.task_id || "").trim() === taskId;
            })
            .sort((a, b) => {
              const aTime = new Date(String(a.recorded_at || "")).getTime();
              const bTime = new Date(String(b.recorded_at || "")).getTime();
              return (Number.isFinite(bTime) ? bTime : 0) - (Number.isFinite(aTime) ? aTime : 0);
            })
            .slice(0, ACTIVITY_LIMIT)
            .map(activityRowFromEvent);
        }
      }
    } catch {
      timeline = [];
    }

    setCreatedTaskId(taskId);
    setCreatedTask(payload);
    setActivityRows(timeline);
  }

  async function quickUpdateCreatedTask(nextStatus: "running" | "completed" | "failed"): Promise<void> {
    if (!createdTaskId) return;

    setUpdateState("saving");
    setUpdateMessage("");
    try {
      const payload: { status: string; current_step?: string | null; output?: string | null } = {
        status: nextStatus,
      };
      if (nextStatus === "running") payload.current_step = "Actively progressing from Today quick launch.";
      if (nextStatus === "completed") payload.output = "Completed and confirmed from Today quick launch.";
      if (nextStatus === "failed") payload.output = "Blocked and flagged from Today quick launch; follow-up decision needed.";

      const response = await fetch(`/api/agent/tasks/${encodeURIComponent(createdTaskId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(await readErrorMessage(response));

      await refreshCreatedTask(createdTaskId);
      setUpdateState("saved");
      setUpdateMessage(`Task marked ${humanizeStatus(nextStatus)}.`);
    } catch (error) {
      setUpdateState("error");
      setUpdateMessage(String(error));
    }
  }

  async function launchTopIdeaTask() {
    setLaunchState("creating");
    setErrorMessage("");
    setCreatedTaskId("");
    setCreatedTask(null);
    setActivityRows([]);
    setUpdateState("idle");
    setUpdateMessage("");

    try {
      const createResponse = await fetch("/api/agent/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task_type: taskType,
          direction: directionForType(taskType, ideaName),
          context: {
            idea_id: ideaId,
            idea_name: ideaName,
            created_from: "today_top_idea_quick_launch",
            launch_mode: "one_click_create_and_execute",
            launch_task_type: taskType,
          },
        }),
      });

      if (!createResponse.ok) {
        throw new Error(await readErrorMessage(createResponse));
      }

      const createPayload = (await createResponse.json()) as { id?: string };
      const taskId = String(createPayload.id || "").trim();
      if (!taskId) throw new Error("Task was created but response did not include task id.");
      persistLatestTaskId(taskId);
      setCreatedTaskId(taskId);
      await refreshCreatedTask(taskId);

      setLaunchState("starting");
      const executeResponse = await fetch(`/api/agent/tasks/${encodeURIComponent(taskId)}/execute`, {
        method: "POST",
      });

      if (!executeResponse.ok) {
        const executeError = await readErrorMessage(executeResponse);
        setLaunchState("created");
        setErrorMessage(
          `Task created, but auto-start was blocked: ${executeError}. You can start it from Remote Ops with an execute token.`,
        );
        await refreshCreatedTask(taskId);
        return;
      }

      setLaunchState("running");
      await refreshCreatedTask(taskId);
    } catch (error) {
      setLaunchState("error");
      setErrorMessage(String(error));
    }
  }

  useEffect(() => {
    const storedTaskId =
      typeof window === "undefined" ? "" : window.localStorage.getItem(LATEST_TODAY_TASK_STORAGE_KEY) || "";
    const taskId = storedTaskId.trim();
    if (!taskId) return;

    let cancelled = false;
    void (async () => {
      try {
        await refreshCreatedTask(taskId);
      } catch {
        if (!cancelled) {
          clearLatestTaskId();
          setActivityRows([]);
          setUpdateState("idle");
          setUpdateMessage("");
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="rounded-xl border p-4 space-y-2">
      <h2 className="text-lg font-semibold">Launch Top Idea Now</h2>
      <p className="text-sm text-muted-foreground">
        One click will create a task for <span className="font-medium text-foreground">{ideaName}</span> and try to start execution immediately.
      </p>
      <label className="block space-y-1 text-sm">
        <span className="text-muted-foreground">Task type</span>
        <select
          className="h-10 rounded-md border border-input bg-background px-3 text-sm"
          value={taskType}
          onChange={(event) => {
            setTaskType(event.target.value as TaskType);
            setLaunchState("idle");
            setErrorMessage("");
            setUpdateState("idle");
            setUpdateMessage("");
          }}
        >
          <option value="impl">Build next outcome</option>
          <option value="review">Quality review</option>
          <option value="spec">Plan next step</option>
        </select>
      </label>
      <div className="flex flex-wrap items-center gap-3">
        <Button
          type="button"
          onClick={launchTopIdeaTask}
          disabled={launchState === "creating" || launchState === "starting"}
        >
          {launchState === "creating" ? "Creating task..." : launchState === "starting" ? "Starting execution..." : "Create + Start"}
        </Button>
        <Link
          href={`/ideas/${encodeURIComponent(ideaId)}`}
          className="text-sm underline text-muted-foreground hover:text-foreground"
          title={`Idea ID: ${ideaId}`}
        >
          Review idea
        </Link>
      </div>

      {launchState === "running" && createdTaskId ? (
        <p className="text-sm text-green-700">
          Task is running.{" "}
          <Link href={`/tasks?task_id=${encodeURIComponent(createdTaskId)}`} className="underline">
            Open task
          </Link>
          .
        </p>
      ) : null}

      {launchState === "created" && createdTaskId ? (
        <p className="text-sm text-amber-700">
          Task created.{" "}
          <Link href={`/tasks?task_id=${encodeURIComponent(createdTaskId)}`} className="underline">
            Open task
          </Link>{" "}
          or{" "}
          <Link href="/remote-ops" className="underline">
            start from Remote Ops
          </Link>
          .
        </p>
      ) : null}

      {errorMessage ? (
        <p className="text-sm text-destructive">Launch failed: {errorMessage}</p>
      ) : null}

      {createdTask ? (
        <section className="rounded-lg border border-border/70 bg-background/35 p-3 space-y-2">
          <p className="text-sm font-medium">Latest launched task</p>
          {nextAction ? (
            <div className="rounded-md border border-border/60 bg-background/60 px-3 py-2 space-y-1">
              <p className="text-sm font-medium">What should I do next?</p>
              <p className="text-sm text-muted-foreground">{nextAction.title}</p>
              <p className="text-sm text-muted-foreground">{nextAction.detail}</p>
              <Link href={nextAction.href} className="text-sm underline">
                {nextAction.cta}
              </Link>
            </div>
          ) : null}
          <p className="text-sm text-muted-foreground">
            {humanizeStatus(createdTask.status)} {createdTask.task_type} task
            {" · "}
            <Link href={`/tasks?task_id=${encodeURIComponent(createdTask.id)}`} className="underline">
              Open task
            </Link>
          </p>
          <p className="text-sm text-muted-foreground">{createdTask.direction}</p>
          {createdTask.current_step ? (
            <p className="text-sm text-muted-foreground">Current step: {createdTask.current_step}</p>
          ) : null}
          {createdTask.output ? (
            <p className="text-sm text-muted-foreground">Latest outcome: {createdTask.output}</p>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" onClick={() => void quickUpdateCreatedTask("running")} disabled={updateState === "saving"}>
              Mark running
            </Button>
            <Button type="button" variant="outline" onClick={() => void quickUpdateCreatedTask("completed")} disabled={updateState === "saving"}>
              Mark completed
            </Button>
            <Button type="button" variant="outline" onClick={() => void quickUpdateCreatedTask("failed")} disabled={updateState === "saving"}>
              Mark failed
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setUpdateState("idle");
                setUpdateMessage("");
                void refreshCreatedTask(createdTask.id);
              }}
              disabled={updateState === "saving"}
            >
              Refresh
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                clearLatestTaskId();
                setCreatedTaskId("");
                setCreatedTask(null);
                setActivityRows([]);
                setLaunchState("idle");
                setUpdateState("idle");
                setUpdateMessage("");
                setErrorMessage("");
              }}
              disabled={updateState === "saving"}
            >
              Clear
            </Button>
          </div>
          {updateState === "saving" ? <p className="text-sm text-muted-foreground">Saving update…</p> : null}
          {updateState === "saved" && updateMessage ? <p className="text-sm text-green-700">{updateMessage}</p> : null}
          {updateState === "error" && updateMessage ? <p className="text-sm text-destructive">Update failed: {updateMessage}</p> : null}
          <div className="space-y-2 pt-1">
            <p className="text-sm font-medium">Recent activity</p>
            {activityRows.length === 0 ? (
              <p className="text-sm text-muted-foreground">No task activity recorded yet.</p>
            ) : (
              <ul className="space-y-2">
                {activityRows.map((row) => (
                  <li key={row.id} className="rounded-md border border-border/60 bg-background/60 px-3 py-2">
                    <p className="text-sm font-medium">{row.title}</p>
                    <p className="text-xs text-muted-foreground">{row.recordedAt}</p>
                    <p className="text-sm text-muted-foreground">{row.detail}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      ) : null}
    </section>
  );
}
