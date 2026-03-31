"use client";

import { Button } from "@/components/ui/button";
import type { PipelineTask } from "./types";

type QueuePipelineSectionProps = {
  pendingRows: PipelineTask[];
  pendingTotal: number;
  pendingCount: number;
  activeCount: number;
  runTask: (taskId: string) => void;
  status: "idle" | "loading" | "error";
};

export function QueuePipelineSection({
  pendingRows,
  pendingTotal,
  pendingCount,
  activeCount,
  runTask,
  status,
}: QueuePipelineSectionProps) {
  return (
    <section className="space-y-3 border rounded-md p-4">
      <h2 className="text-lg font-semibold">Queue / Pipeline</h2>
      <p className="text-sm text-muted-foreground">
        Running: {activeCount} | pending (latest page): {pendingCount} | total pending: {pendingTotal}
      </p>
      {pendingRows.length === 0 ? (
        <p className="text-sm text-muted-foreground">No pending tasks in this window.</p>
      ) : (
        <ul className="space-y-2">
          {pendingRows.map((task) => (
            <li key={task.id} className="rounded border p-3">
              <div className="flex flex-wrap justify-between gap-2">
                <span className="font-medium text-sm break-all">{task.id}</span>
                <span className="text-xs text-muted-foreground">{task.task_type}</span>
              </div>
              <p className="text-sm text-muted-foreground mt-1">{task.direction}</p>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => void runTask(task.id)}
                disabled={status === "loading"}
                className="mt-2"
              >
                Run now
              </Button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
