"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type ControlsSectionProps = {
  executeToken: string;
  setExecuteToken: (v: string) => void;
  executor: string;
  setExecutor: (v: string) => void;
  taskType: string;
  setTaskType: (v: string) => void;
  modelOverride: string;
  setModelOverride: (v: string) => void;
  forcePaid: boolean;
  setForcePaid: (v: boolean) => void;
  runAsPrThread: boolean;
  setRunAsPrThread: (v: boolean) => void;
  autoMergePr: boolean;
  setAutoMergePr: (v: boolean) => void;
  waitPublic: boolean;
  setWaitPublic: (v: boolean) => void;
  direction: string;
  setDirection: (v: string) => void;
  status: "idle" | "loading" | "error";
  error: string | null;
  runningMessage: string | null;
  onCreate: (e: React.FormEvent<HTMLFormElement>) => void;
  runPickUp: () => void;
};

export function ControlsSection(props: ControlsSectionProps) {
  const {
    executeToken,
    setExecuteToken,
    executor,
    setExecutor,
    taskType,
    setTaskType,
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
    direction,
    setDirection,
    status,
    error,
    runningMessage,
    onCreate,
    runPickUp,
  } = props;

  return (
    <section className="space-y-4 border rounded-md p-4">
      <h2 className="text-lg font-semibold">Controls</h2>
      <div className="grid gap-3 md:grid-cols-2">
        <label className="text-sm">
          Execute token (optional)
          <Input
            value={executeToken}
            onChange={(e) => setExecuteToken(e.target.value)}
            placeholder="Only required if AGENT_EXECUTE_TOKEN is set"
          />
        </label>
        <label className="text-sm">
          Executor
          <Input
            value={executor}
            onChange={(e) => setExecutor(e.target.value)}
            placeholder="openclaw (or clawwork) | cursor | claude"
          />
        </label>
        <label className="text-sm">
          Task type
          <Input
            value={taskType}
            onChange={(e) => setTaskType(e.target.value)}
            placeholder="impl | spec | test | review | heal"
          />
        </label>
        <label className="text-sm">
          Model override (optional)
          <Input
            value={modelOverride}
            onChange={(e) => setModelOverride(e.target.value)}
            placeholder="openrouter/free | gpt-4.1-mini | gpt-5.3-codex-spark"
          />
        </label>
        <label className="text-sm md:col-span-2 flex items-center gap-2">
          <input
            type="checkbox"
            checked={forcePaid}
            onChange={(e) => setForcePaid(e.target.checked)}
          />
          Force paid provider override
        </label>
        <label className="text-sm md:col-span-2 flex items-center gap-2">
          <input
            type="checkbox"
            checked={runAsPrThread}
            onChange={(e) => setRunAsPrThread(e.target.checked)}
          />
          Run as Codex thread (create PR)
        </label>
        <label className="text-sm md:col-span-2 flex items-center gap-2">
          <input
            type="checkbox"
            checked={autoMergePr}
            onChange={(e) => setAutoMergePr(e.target.checked)}
          />
          Auto-merge PR when checks are ready
        </label>
        <label className="text-sm md:col-span-2 flex items-center gap-2">
          <input
            type="checkbox"
            checked={waitPublic}
            onChange={(e) => setWaitPublic(e.target.checked)}
          />
          Wait for public deploy validation before completion
        </label>
      </div>

      <form className="space-y-2" onSubmit={onCreate}>
        <label className="text-sm">
          New task direction
          <textarea
            value={direction}
            onChange={(e) => setDirection(e.target.value)}
            className="mt-1 min-h-24 w-full rounded border bg-background px-3 py-2 text-sm"
            placeholder="Add implementation for x, bug fix y, etc."
          />
        </label>
        <div className="flex gap-2">
          <Button type="submit" disabled={status === "loading"}>
            Create + Run Now
          </Button>
          <Button type="button" variant="outline" onClick={runPickUp} disabled={status === "loading"}>
            Pick up oldest pending and run
          </Button>
        </div>
      </form>

      {status === "error" && <p className="text-destructive">Error: {error}</p>}
      {runningMessage && <p className="text-sm text-muted-foreground">{runningMessage}</p>}
    </section>
  );
}
