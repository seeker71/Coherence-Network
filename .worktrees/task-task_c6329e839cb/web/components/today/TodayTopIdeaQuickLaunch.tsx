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
type FollowUpState = "idle" | "saving" | "saved" | "error";
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
  context?: Record<string, unknown> | null;
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
type TaskNoteSnapshot = {
  text: string;
  savedAt: string;
  kind: string;
};

const LATEST_TODAY_TASK_STORAGE_KEY = "coherence.today.latest_task_id";
const TODAY_TASK_NOTE_KEY = "today_user_note";
const TODAY_TASK_NOTE_AT_KEY = "today_user_note_at";
const TODAY_TASK_NOTE_KIND_KEY = "today_user_note_kind";
const ACTIVITY_LIMIT = 5;

function directionForType(taskType: TaskType, ideaName: string): string {
  if (taskType === "review") {
    return `Check the current progress for ${ideaName}. Say what is clear, what feels risky, and the one next step that matters most.`;
  }
  if (taskType === "spec") {
    return `Turn ${ideaName} into a short plan for the next week with a clear outcome and a simple way to tell if it worked.`;
  }
  return `Move ${ideaName} forward in a way a first-time user can see. Say what changed and what should happen next.`;
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

function clipText(value: string, maxLength = 260): string {
  const normalized = value.replace(/\s+/g, " ").trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, Math.max(0, maxLength - 1)).trimEnd()}…`;
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
      title: `${humanizeStatus(finalStatus || "completed")} result saved`,
      detail: (`The latest result was recorded.${reviewSuffix}${verifiedSuffix}`).trim(),
    };
  }

  if (trackingKind === "agent_task_lifecycle") {
    return {
      id: event.id,
      recordedAt: formatEventTime(event.recorded_at),
      title: humanizeWords(lifecycleEvent || `status ${taskStatus || "pending"}`),
      detail: reason ? reason : `This work card moved to ${humanizeStatus(taskStatus || "pending")}.`,
    };
  }

  return {
    id: event.id,
    recordedAt: formatEventTime(event.recorded_at),
    title: "Update recorded",
    detail: "A recent system update was saved for this work card.",
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
      detail: latestOutcome || latestDetail || "This work is blocked and needs a human decision on how to continue.",
      href: taskHref,
      cta: "Review blocker",
    };
  }

  if (task.status === "completed") {
    return {
      title: "Review the result and choose the next step",
      detail: latestOutcome || latestDetail || "This work is complete. Confirm the outcome and decide what should happen next.",
      href: taskHref,
      cta: "Review result",
    };
  }

  if (task.status === "running") {
    return {
      title: "Check that this work is still moving",
      detail: currentStep || latestDetail || "This work card is in progress. Confirm it is still moving and update it if it has stalled.",
      href: taskHref,
      cta: "Inspect progress",
    };
  }

  if (task.status === "needs_decision") {
    return {
      title: "Make the choice this work is waiting on",
      detail: latestOutcome || latestDetail || "This work is paused until someone chooses how to continue.",
      href: taskHref,
      cta: "Open decision",
    };
  }

  return {
    title: "Open this work card and decide what to do next",
    detail: latestDetail || "This work card exists, but it is not moving right now. Open it and decide whether to restart it or update it.",
    href: taskHref,
    cta: "Open work card",
  };
}

function readTaskNote(task: CreatedTaskSnapshot): TaskNoteSnapshot | null {
  const context = asRecord(task.context);
  const text = String(context[TODAY_TASK_NOTE_KEY] || "").trim();
  if (!text) return null;
  return {
    text,
    savedAt: formatEventTime(String(context[TODAY_TASK_NOTE_AT_KEY] || task.updated_at || "")),
    kind: String(context[TODAY_TASK_NOTE_KIND_KEY] || "note").trim() || "note",
  };
}

function taskNoteKind(task: CreatedTaskSnapshot): string {
  if (task.status === "needs_decision") return "decision";
  if (task.status === "completed" || task.status === "failed") return "outcome";
  return "instruction";
}

function taskNoteHelper(task: CreatedTaskSnapshot): string {
  if (task.status === "needs_decision") {
    return "Answer the open question here. Saving will move the work forward again.";
  }
  if (task.status === "completed" || task.status === "failed") {
    return "Leave a short note so the next person understands what happened.";
  }
  return "Leave a short note about what to do next or what changed.";
}

function taskNotePlaceholder(task: CreatedTaskSnapshot): string {
  if (task.status === "needs_decision") return "Example: continue with the local demo flow and write down the main blocker in plain language.";
  if (task.status === "completed") return "Example: the main flow now works; next step is making the summary easier to understand.";
  if (task.status === "failed") return "Example: blocked on missing sample data; restore that first, then try again.";
  return "Example: focus on the short user summary first and keep the wording simple.";
}

function taskNoteButtonLabel(task: CreatedTaskSnapshot): string {
  if (task.status === "needs_decision") return "Send answer";
  if (task.status === "completed" || task.status === "failed") return "Save note";
  return "Save note";
}

function followUpTaskType(task: CreatedTaskSnapshot): TaskType {
  if (task.status === "failed" || task.status === "needs_decision") return "review";
  if (task.task_type === "spec") return "impl";
  if (task.task_type === "review") return "impl";
  if (task.status === "completed") return "impl";
  return "review";
}

function followUpButtonLabel(task: CreatedTaskSnapshot): string {
  const nextType = followUpTaskType(task);
  if (nextType === "impl") return "Create the next build step";
  if (nextType === "spec") return "Create the next planning step";
  return "Create the next check-in";
}

function workCardTypeLabel(taskType: string): string {
  if (taskType === "impl") return "build step";
  if (taskType === "review") return "check-in";
  if (taskType === "spec") return "plan";
  return "work card";
}

function noteKindLabel(kind: string): string {
  if (kind === "decision") return "answer";
  if (kind === "follow-up context") return "context";
  return "note";
}

function carryForwardContext(
  task: CreatedTaskSnapshot,
  activityRows: TaskActivityRow[],
  latestTaskNote: TaskNoteSnapshot | null,
): string {
  return clipText(
    latestTaskNote?.text ||
      String(task.output || "").trim() ||
      String(task.current_step || "").trim() ||
      activityRows[0]?.detail ||
      task.direction,
    320,
  );
}

function buildFollowUpDirection(
  task: CreatedTaskSnapshot,
  activityRows: TaskActivityRow[],
  latestTaskNote: TaskNoteSnapshot | null,
  ideaName: string,
): string {
  const nextType = followUpTaskType(task);
  const carryForward = carryForwardContext(task, activityRows, latestTaskNote);

  if (nextType === "review") {
    return `Review the latest context for ${ideaName} and decide the most useful next move. Focus on one clear blocker, risk, or unresolved choice. Carry forward this context: ${carryForward}`;
  }

  if (nextType === "spec") {
    return `Turn the latest context for ${ideaName} into a clear next plan. Keep the result specific enough that the next build step is obvious. Carry forward this context: ${carryForward}`;
  }

  return `Deliver the next highest-value outcome for ${ideaName} using the latest confirmed context. Build the smallest visible improvement that keeps the first version moving. Carry forward this context: ${carryForward}`;
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
  const [followUpState, setFollowUpState] = useState<FollowUpState>("idle");
  const [followUpMessage, setFollowUpMessage] = useState("");
  const [followUpTaskId, setFollowUpTaskId] = useState("");
  const [noteDraft, setNoteDraft] = useState("");
  const [noteState, setNoteState] = useState<UpdateState>("idle");
  const [noteMessage, setNoteMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  const nextAction = createdTask ? deriveNextAction(createdTask, activityRows) : null;
  const latestTaskNote = createdTask ? readTaskNote(createdTask) : null;
  const isMutating = updateState === "saving" || noteState === "saving" || followUpState === "saving";

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
      if (nextStatus === "running") payload.current_step = "Actively moving from the Today page.";
      if (nextStatus === "completed") payload.output = "Marked done from the Today page.";
      if (nextStatus === "failed") payload.output = "Marked stuck from the Today page; a follow-up choice is needed.";

      const response = await fetch(`/api/agent/tasks/${encodeURIComponent(createdTaskId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(await readErrorMessage(response));

      await refreshCreatedTask(createdTaskId);
      setUpdateState("saved");
      setUpdateMessage(`Work card marked ${humanizeStatus(nextStatus)}.`);
    } catch (error) {
      setUpdateState("error");
      setUpdateMessage(String(error));
    }
  }

  async function saveTaskNote(): Promise<void> {
    if (!createdTask) return;
    const trimmedNote = noteDraft.trim();
    if (!trimmedNote) {
      setNoteState("error");
      setNoteMessage("Enter a short note before saving.");
      return;
    }

    const noteKind = taskNoteKind(createdTask);
    const payload: {
      context: Record<string, string>;
      decision?: string;
    } = {
      context: {
        [TODAY_TASK_NOTE_KEY]: trimmedNote,
        [TODAY_TASK_NOTE_AT_KEY]: new Date().toISOString(),
        [TODAY_TASK_NOTE_KIND_KEY]: noteKind,
      },
    };

    if (createdTask.status === "needs_decision") {
      payload.decision = trimmedNote;
    }

    setNoteState("saving");
    setNoteMessage("");
    try {
      const response = await fetch(`/api/agent/tasks/${encodeURIComponent(createdTask.id)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(await readErrorMessage(response));

      await refreshCreatedTask(createdTask.id);
      setNoteDraft("");
      setNoteState("saved");
      setNoteMessage(
        createdTask.status === "needs_decision" ? "Answer saved and work can continue." : "Note saved to this work card.",
      );
    } catch (error) {
      setNoteState("error");
      setNoteMessage(String(error));
    }
  }

  async function createFollowUpTask(): Promise<void> {
    if (!createdTask) return;

    setFollowUpState("saving");
    setFollowUpMessage("");
    setFollowUpTaskId("");

    const nextType = followUpTaskType(createdTask);
    const carryForward = carryForwardContext(createdTask, activityRows, latestTaskNote);
    const direction = buildFollowUpDirection(createdTask, activityRows, latestTaskNote, ideaName);

    try {
      const response = await fetch("/api/agent/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task_type: nextType,
          direction,
          context: {
            idea_id: ideaId,
            idea_name: ideaName,
            created_from: "today_follow_up_task",
            parent_task_id: createdTask.id,
            parent_task_type: createdTask.task_type,
            parent_task_status: createdTask.status,
            parent_task_direction: clipText(createdTask.direction, 240),
            parent_task_note: latestTaskNote?.text || "",
            parent_task_output: clipText(String(createdTask.output || ""), 240),
            parent_task_current_step: clipText(String(createdTask.current_step || ""), 240),
            parent_task_latest_activity: activityRows[0]?.detail || "",
            [TODAY_TASK_NOTE_KEY]: carryForward,
            [TODAY_TASK_NOTE_AT_KEY]: new Date().toISOString(),
            [TODAY_TASK_NOTE_KIND_KEY]: "follow-up context",
          },
        }),
      });

      if (!response.ok) {
        throw new Error(await readErrorMessage(response));
      }

      const payload = (await response.json()) as { id?: string };
      const taskId = String(payload.id || "").trim();
      if (!taskId) throw new Error("The next step was created but the response did not include its id.");

      persistLatestTaskId(taskId);
      setFollowUpTaskId(taskId);
      await refreshCreatedTask(taskId);
      setFollowUpState("saved");
      setFollowUpMessage(`The next ${workCardTypeLabel(nextType)} is ready and is now the current work card.`);
      setLaunchState("created");
      setNoteDraft("");
      setNoteState("idle");
      setNoteMessage("");
    } catch (error) {
      setFollowUpState("error");
      setFollowUpMessage(String(error));
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
    setFollowUpState("idle");
    setFollowUpMessage("");
    setFollowUpTaskId("");
    setNoteDraft("");
    setNoteState("idle");
    setNoteMessage("");

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
      if (!taskId) throw new Error("The work card was created but the response did not include its id.");
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
          `The work card was created, but it could not start automatically: ${executeError}. You can still open it now or continue from Remote Ops if you use manual controls.`,
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
      <h2 className="text-lg font-semibold">Start Moving This Idea</h2>
      <p className="text-sm text-muted-foreground">
        This creates a work card for <span className="font-medium text-foreground">{ideaName}</span> and, when possible,
        starts it right away.
      </p>
      <label className="block space-y-1 text-sm">
        <span className="text-muted-foreground">What kind of help do you want?</span>
        <select
          className="h-10 rounded-md border border-input bg-background px-3 text-sm"
          value={taskType}
          onChange={(event) => {
            setTaskType(event.target.value as TaskType);
            setLaunchState("idle");
            setErrorMessage("");
            setUpdateState("idle");
            setUpdateMessage("");
            setFollowUpState("idle");
            setFollowUpMessage("");
            setFollowUpTaskId("");
            setNoteState("idle");
            setNoteMessage("");
          }}
        >
          <option value="impl">Build something</option>
          <option value="review">Check progress</option>
          <option value="spec">Write a plan</option>
        </select>
      </label>
      <div className="flex flex-wrap items-center gap-3">
        <Button
          type="button"
          onClick={launchTopIdeaTask}
          disabled={launchState === "creating" || launchState === "starting"}
        >
          {launchState === "creating"
            ? "Creating work card..."
            : launchState === "starting"
              ? "Starting work..."
              : "Start this work"}
        </Button>
        <Link
          href={`/ideas/${encodeURIComponent(ideaId)}`}
          className="text-sm underline text-muted-foreground hover:text-foreground"
          title={`Idea ID: ${ideaId}`}
        >
          Read idea
        </Link>
      </div>

      {launchState === "running" && createdTaskId ? (
        <p className="text-sm text-green-700">
          Work is running.{" "}
          <Link href={`/tasks?task_id=${encodeURIComponent(createdTaskId)}`} className="underline">
            Open work card
          </Link>
          .
        </p>
      ) : null}

      {launchState === "created" && createdTaskId ? (
        <p className="text-sm text-amber-700">
          Work card ready.{" "}
          <Link href={`/tasks?task_id=${encodeURIComponent(createdTaskId)}`} className="underline">
            Open work card
          </Link>{" "}
          or{" "}
          <Link href="/remote-ops" className="underline">
            continue from Remote Ops
          </Link>
          .
        </p>
      ) : null}

      {errorMessage ? (
        <p className="text-sm text-destructive">Could not start this work: {errorMessage}</p>
      ) : null}

      {createdTask ? (
        <section className="rounded-lg border border-border/70 bg-background/35 p-3 space-y-2">
          <p className="text-sm font-medium">Current work card</p>
          {nextAction ? (
            <div className="rounded-md border border-border/60 bg-background/60 px-3 py-2 space-y-1">
              <p className="text-sm font-medium">What should happen next?</p>
              <p className="text-sm text-muted-foreground">{nextAction.title}</p>
              <p className="text-sm text-muted-foreground">{nextAction.detail}</p>
              <Link href={nextAction.href} className="text-sm underline">
                {nextAction.cta}
              </Link>
            </div>
          ) : null}
          <p className="text-sm text-muted-foreground">
            {humanizeStatus(createdTask.status)} {workCardTypeLabel(createdTask.task_type)}
            {" · "}
            <Link href={`/tasks?task_id=${encodeURIComponent(createdTask.id)}`} className="underline">
              Open work card
            </Link>
          </p>
          <p className="text-sm text-muted-foreground">{createdTask.direction}</p>
          {createdTask.current_step ? (
            <p className="text-sm text-muted-foreground">Current focus: {createdTask.current_step}</p>
          ) : null}
          {createdTask.output ? (
            <p className="text-sm text-muted-foreground">Latest result: {createdTask.output}</p>
          ) : null}
          <div className="rounded-md border border-border/60 bg-background/60 px-3 py-3 space-y-2">
            <p className="text-sm font-medium">Create the next step</p>
            <p className="text-sm text-muted-foreground">
              Turn what you already know into the next work card without retyping everything.
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <Button type="button" variant="outline" onClick={() => void createFollowUpTask()} disabled={isMutating}>
                {followUpButtonLabel(createdTask)}
              </Button>
              <Link
                href={`/ideas/${encodeURIComponent(ideaId)}`}
                className="text-sm underline text-muted-foreground hover:text-foreground"
              >
                Turn idea into plans
              </Link>
            </div>
            {followUpState === "saving" ? <p className="text-sm text-muted-foreground">Creating the next step…</p> : null}
            {followUpState === "saved" && followUpMessage ? (
              <p className="text-sm text-green-700">
                {followUpMessage}{" "}
                {followUpTaskId ? (
                  <Link href={`/tasks?task_id=${encodeURIComponent(followUpTaskId)}`} className="underline">
                    Open it
                  </Link>
                ) : null}
              </p>
            ) : null}
            {followUpState === "error" && followUpMessage ? (
              <p className="text-sm text-destructive">Could not create the next step: {followUpMessage}</p>
            ) : null}
          </div>
          <div className="rounded-md border border-border/60 bg-background/60 px-3 py-3 space-y-2">
            <p className="text-sm font-medium">Add a short note</p>
            <p className="text-sm text-muted-foreground">{taskNoteHelper(createdTask)}</p>
            <textarea
              className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              rows={3}
              value={noteDraft}
              onChange={(event) => {
                setNoteDraft(event.target.value);
                if (noteState !== "idle") {
                  setNoteState("idle");
                  setNoteMessage("");
                }
              }}
              placeholder={taskNotePlaceholder(createdTask)}
            />
            <div className="flex flex-wrap items-center gap-2">
              <Button type="button" variant="outline" onClick={() => void saveTaskNote()} disabled={isMutating}>
                {taskNoteButtonLabel(createdTask)}
              </Button>
              {latestTaskNote ? (
                <p className="text-sm text-muted-foreground">
                  Latest {noteKindLabel(latestTaskNote.kind)} saved: {latestTaskNote.savedAt}
                </p>
              ) : null}
            </div>
            {noteState === "saving" ? <p className="text-sm text-muted-foreground">Saving note…</p> : null}
            {noteState === "saved" && noteMessage ? <p className="text-sm text-green-700">{noteMessage}</p> : null}
            {noteState === "error" && noteMessage ? <p className="text-sm text-destructive">Could not save the note: {noteMessage}</p> : null}
            {latestTaskNote ? <p className="text-sm text-muted-foreground">{latestTaskNote.text}</p> : null}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" onClick={() => void quickUpdateCreatedTask("running")} disabled={isMutating}>
              Working on it
            </Button>
            <Button type="button" variant="outline" onClick={() => void quickUpdateCreatedTask("completed")} disabled={isMutating}>
              Done
            </Button>
            <Button type="button" variant="outline" onClick={() => void quickUpdateCreatedTask("failed")} disabled={isMutating}>
              Stuck
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setUpdateState("idle");
                setUpdateMessage("");
                void refreshCreatedTask(createdTask.id);
              }}
              disabled={isMutating}
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
                setFollowUpState("idle");
                setFollowUpMessage("");
                setFollowUpTaskId("");
                setNoteDraft("");
                setNoteState("idle");
                setNoteMessage("");
                setErrorMessage("");
              }}
              disabled={isMutating}
            >
              Forget this card
            </Button>
          </div>
          {updateState === "saving" ? <p className="text-sm text-muted-foreground">Saving update…</p> : null}
          {updateState === "saved" && updateMessage ? <p className="text-sm text-green-700">{updateMessage}</p> : null}
          {updateState === "error" && updateMessage ? <p className="text-sm text-destructive">Could not save the update: {updateMessage}</p> : null}
          <div className="space-y-2 pt-1">
            <p className="text-sm font-medium">Recent changes</p>
            {activityRows.length === 0 ? (
              <p className="text-sm text-muted-foreground">No recent changes yet.</p>
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
