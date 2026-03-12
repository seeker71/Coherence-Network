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

const LATEST_TODAY_TASK_STORAGE_KEY = "coherence.today.latest_task_id";

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

export default function TodayTopIdeaQuickLaunch({
  ideaId,
  ideaName,
}: TodayTopIdeaQuickLaunchProps) {
  const [taskType, setTaskType] = useState<TaskType>("impl");
  const [launchState, setLaunchState] = useState<LaunchState>("idle");
  const [createdTaskId, setCreatedTaskId] = useState("");
  const [createdTask, setCreatedTask] = useState<CreatedTaskSnapshot | null>(null);
  const [updateState, setUpdateState] = useState<UpdateState>("idle");
  const [updateMessage, setUpdateMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  function persistLatestTaskId(taskId: string): void {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(LATEST_TODAY_TASK_STORAGE_KEY, taskId);
  }

  function clearLatestTaskId(): void {
    if (typeof window === "undefined") return;
    window.localStorage.removeItem(LATEST_TODAY_TASK_STORAGE_KEY);
  }

  async function refreshCreatedTask(taskId: string): Promise<void> {
    const response = await fetch(`/api/agent/tasks/${encodeURIComponent(taskId)}`, { cache: "no-store" });
    if (!response.ok) throw new Error(await readErrorMessage(response));
    const payload = (await response.json()) as CreatedTaskSnapshot;
    setCreatedTaskId(taskId);
    setCreatedTask(payload);
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
        const response = await fetch(`/api/agent/tasks/${encodeURIComponent(taskId)}`, { cache: "no-store" });
        if (!response.ok) {
          if (!cancelled) clearLatestTaskId();
          return;
        }
        const payload = (await response.json()) as CreatedTaskSnapshot;
        if (cancelled) return;
        setCreatedTaskId(taskId);
        setCreatedTask(payload);
      } catch {
        if (!cancelled) {
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
        </section>
      ) : null}
    </section>
  );
}
