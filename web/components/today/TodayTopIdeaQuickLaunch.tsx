"use client";

import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";

type TodayTopIdeaQuickLaunchProps = {
  ideaId: string;
  ideaName: string;
};

type LaunchState = "idle" | "creating" | "starting" | "running" | "created" | "error";

function defaultDirection(ideaName: string): string {
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
  const [launchState, setLaunchState] = useState<LaunchState>("idle");
  const [createdTaskId, setCreatedTaskId] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  async function launchTopIdeaTask() {
    setLaunchState("creating");
    setErrorMessage("");
    setCreatedTaskId("");

    try {
      const createResponse = await fetch("/api/agent/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task_type: "impl",
          direction: defaultDirection(ideaName),
          context: {
            idea_id: ideaId,
            idea_name: ideaName,
            created_from: "today_top_idea_quick_launch",
            launch_mode: "one_click_create_and_execute",
          },
        }),
      });

      if (!createResponse.ok) {
        throw new Error(await readErrorMessage(createResponse));
      }

      const createPayload = (await createResponse.json()) as { id?: string };
      const taskId = String(createPayload.id || "").trim();
      if (!taskId) throw new Error("Task was created but response did not include task id.");
      setCreatedTaskId(taskId);

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
        return;
      }

      setLaunchState("running");
    } catch (error) {
      setLaunchState("error");
      setErrorMessage(String(error));
    }
  }

  return (
    <section className="rounded-xl border p-4 space-y-2">
      <h2 className="text-lg font-semibold">Launch Top Idea Now</h2>
      <p className="text-sm text-muted-foreground">
        One click will create a build task for <span className="font-medium text-foreground">{ideaName}</span> and try to start execution immediately.
      </p>
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
    </section>
  );
}
