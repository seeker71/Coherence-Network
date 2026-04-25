"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type TaskQuickUpdateProps = {
  taskId: string;
  initialStatus: string;
  initialOutput: string;
  initialCurrentStep: string;
  onUpdated: () => Promise<void> | void;
};

type SaveState = "idle" | "saving" | "saved" | "error";

const STATUS_OPTIONS = [
  { value: "pending", label: "Ready to start" },
  { value: "running", label: "In progress" },
  { value: "completed", label: "Finished" },
  { value: "failed", label: "Blocked" },
  { value: "needs_decision", label: "Waiting for your decision" },
];

export function TaskQuickUpdate({
  taskId,
  initialStatus,
  initialOutput,
  initialCurrentStep,
  onUpdated,
}: TaskQuickUpdateProps) {
  const [status, setStatus] = useState(initialStatus || "pending");
  const [currentStep, setCurrentStep] = useState(initialCurrentStep || "");
  const [output, setOutput] = useState(initialOutput || "");
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    setStatus(initialStatus || "pending");
    setCurrentStep(initialCurrentStep || "");
    setOutput(initialOutput || "");
    setSaveState("idle");
    setErrorMsg("");
  }, [taskId, initialStatus, initialCurrentStep, initialOutput]);

  async function save(nextStatus?: string): Promise<void> {
    setSaveState("saving");
    setErrorMsg("");

    const statusToSave = nextStatus || status;
    const payload = {
      status: statusToSave,
      current_step: currentStep.trim() || null,
      output: output.trim() || null,
    };

    try {
      const response = await fetch(`/api/agent/tasks/${encodeURIComponent(taskId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `HTTP ${response.status}`);
      }

      if (nextStatus) setStatus(nextStatus);
      setSaveState("saved");
      await onUpdated();
    } catch (error) {
      setSaveState("error");
      setErrorMsg(String(error));
    }
  }

  async function quickSet(nextStatus: string): Promise<void> {
    if (nextStatus === "completed" && !output.trim()) {
      setOutput("The work is finished and ready for the next follow-up.");
    }
    if (nextStatus === "running" && !currentStep.trim()) {
      setCurrentStep("Someone is actively moving this forward.");
    }
    if (nextStatus === "failed" && !output.trim()) {
      setOutput("This work is blocked and needs a follow-up decision.");
    }
    await save(nextStatus);
  }

  return (
    <div className="rounded-lg border border-border/70 bg-background/35 p-3 space-y-3">
      <h3 className="font-medium">Update This Work Card</h3>
      <p className="text-muted-foreground">
        Keep the status, current step, and outcome note up to date without leaving this page.
      </p>

      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" onClick={() => void quickSet("running")} disabled={saveState === "saving"}>
          Mark in progress
        </Button>
        <Button type="button" variant="outline" onClick={() => void quickSet("completed")} disabled={saveState === "saving"}>
          Mark finished
        </Button>
        <Button type="button" variant="outline" onClick={() => void quickSet("failed")} disabled={saveState === "saving"}>
          Mark blocked
        </Button>
      </div>

      <label className="block space-y-1 text-sm">
        <span className="text-muted-foreground">Current state</span>
        <select
          className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
          value={status}
          onChange={(event) => {
            setStatus(event.target.value);
            setSaveState("idle");
            setErrorMsg("");
          }}
        >
          {STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>

      <label className="block space-y-1 text-sm">
        <span className="text-muted-foreground">What is happening now</span>
        <Input
          value={currentStep}
          onChange={(event) => {
            setCurrentStep(event.target.value);
            setSaveState("idle");
            setErrorMsg("");
          }}
          placeholder="Example: drafting the short summary for the next review"
        />
      </label>

      <label className="block space-y-1 text-sm">
        <span className="text-muted-foreground">Outcome note</span>
        <textarea
          className="min-h-[84px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
          value={output}
          onChange={(event) => {
            setOutput(event.target.value);
            setSaveState("idle");
            setErrorMsg("");
          }}
          placeholder="Write a short update another person can understand quickly"
        />
      </label>

      <div className="flex items-center gap-3">
        <Button type="button" onClick={() => void save()} disabled={saveState === "saving"}>
          {saveState === "saving" ? "Saving..." : "Save update"}
        </Button>
        {saveState === "saved" ? <span className="text-sm text-green-700">Saved</span> : null}
        {saveState === "error" ? <span className="text-sm text-destructive">Update failed: {errorMsg}</span> : null}
      </div>
    </div>
  );
}
