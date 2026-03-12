"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";

type IdeaTaskQuickCreateProps = {
  ideaId: string;
  ideaName: string;
  unansweredQuestions: string[];
};

type TaskType = "impl" | "review" | "spec";
type CreateState = "idle" | "saving" | "saved" | "error";

function baseDirectionForType(taskType: TaskType, ideaName: string): string {
  if (taskType === "impl") {
    return `Move ${ideaName} forward in a way a first-time user can see. Say what changed and what should happen next.`;
  }
  if (taskType === "review") {
    return `Check the current progress for ${ideaName}. Say what is clear, what is risky, and the one next step that matters most.`;
  }
  return `Turn ${ideaName} into a short plan for the next week with a clear outcome and a simple way to tell if it worked.`;
}

export default function IdeaTaskQuickCreate({
  ideaId,
  ideaName,
  unansweredQuestions,
}: IdeaTaskQuickCreateProps) {
  const [taskType, setTaskType] = useState<TaskType>("impl");
  const [direction, setDirection] = useState(baseDirectionForType("impl", ideaName));
  const [createState, setCreateState] = useState<CreateState>("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [createdTaskId, setCreatedTaskId] = useState("");

  const topQuestion = useMemo(() => {
    return unansweredQuestions.find((q) => q.trim().length > 0) || "";
  }, [unansweredQuestions]);

  async function createTask() {
    const cleanedDirection = direction.trim();
    if (!cleanedDirection) {
      setCreateState("error");
      setErrorMsg("Add one clear next step before creating a work card.");
      return;
    }

    setCreateState("saving");
    setErrorMsg("");
    setCreatedTaskId("");

    try {
      const response = await fetch("/api/agent/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task_type: taskType,
          direction: cleanedDirection,
          context: {
            idea_id: ideaId,
            idea_name: ideaName,
            created_from: "idea_detail_quick_create",
          },
        }),
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `HTTP ${response.status}`);
      }

      const payload = (await response.json()) as { id?: string };
      const taskId = String(payload.id || "").trim();
      if (!taskId) throw new Error("The work card was created but the response did not include its id.");

      setCreatedTaskId(taskId);
      setCreateState("saved");
    } catch (error) {
      setCreateState("error");
      setErrorMsg(String(error));
    }
  }

  function applyTaskType(nextTaskType: TaskType) {
    setTaskType(nextTaskType);
    setDirection(baseDirectionForType(nextTaskType, ideaName));
    setCreateState("idle");
    setErrorMsg("");
    setCreatedTaskId("");
  }

  function useTopQuestion() {
    if (!topQuestion) return;
    const base = baseDirectionForType(taskType, ideaName);
    setDirection(`${base} Prioritize this open question: ${topQuestion}`);
    setCreateState("idle");
    setErrorMsg("");
    setCreatedTaskId("");
  }

  return (
    <section className="rounded border p-4 space-y-3">
      <h2 className="font-semibold">Start A Piece Of Work</h2>
      <p className="text-sm text-muted-foreground">
        Create a work card from this idea without leaving the page. This is a good place to capture the next small step.
      </p>

      <label className="space-y-1 text-sm">
        <span className="text-muted-foreground">What kind of help do you want?</span>
        <select
          className="h-10 rounded-md border border-input bg-background px-3 text-sm"
          value={taskType}
          onChange={(event) => applyTaskType(event.target.value as TaskType)}
        >
          <option value="impl">Build something</option>
          <option value="review">Check progress</option>
          <option value="spec">Write a plan</option>
        </select>
      </label>

      <label className="space-y-1 text-sm block">
        <span className="text-muted-foreground">What should happen next?</span>
        <textarea
          className="min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
          value={direction}
          onChange={(event) => {
            setDirection(event.target.value);
            setCreateState("idle");
            setErrorMsg("");
            setCreatedTaskId("");
          }}
          placeholder="Describe the next clear step in plain language"
        />
      </label>

      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={createTask} disabled={createState === "saving"}>
          {createState === "saving" ? "Creating..." : "Create Work Card"}
        </Button>
        {topQuestion ? (
          <button
            type="button"
            className="text-sm underline text-muted-foreground hover:text-foreground"
            onClick={useTopQuestion}
          >
            Use the top unanswered question
          </button>
        ) : null}
      </div>

      {createState === "saved" && createdTaskId ? (
        <p className="text-sm text-green-700">
          Work card created. <Link href={`/tasks?task_id=${encodeURIComponent(createdTaskId)}`} className="underline">Open it</Link>.
        </p>
      ) : null}
      {createState === "error" ? (
        <p className="text-sm text-destructive">Could not create the work card: {errorMsg}</p>
      ) : null}
    </section>
  );
}
