import Link from "next/link";
import type { FlowResponse } from "./types";

type Props = { flow: FlowResponse };

export function FlowUnblockQueue({ flow }: Props) {
  const queue = flow.unblock_queue.slice(0, 12);

  return (
    <section className="rounded border p-4 space-y-2">
      <h2 className="font-semibold">Unblock Priority Queue</h2>
      <p className="text-sm text-muted-foreground">
        Ordered by estimated unlock value per cost. Work top-down to unblock more downstream tasks.
      </p>
      <ul className="space-y-2 text-sm">
        {queue.map((row) => (
          <li key={row.task_fingerprint} className="rounded border p-2 space-y-1">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Link href={`/flow?idea_id=${encodeURIComponent(row.idea_id)}`} className="font-medium underline hover:text-foreground">
                {row.idea_name}
              </Link>
              <span className="text-xs text-muted-foreground">
                stage {row.blocking_stage} | priority {row.unblock_priority_score.toFixed(2)}
              </span>
            </div>
            <p className="text-muted-foreground">
              cost {row.estimated_unblock_cost.toFixed(2)} | unlock value {row.estimated_unblock_value.toFixed(2)} |
              blocked {row.downstream_blocked.length > 0 ? row.downstream_blocked.join(", ") : "none"}
            </p>
            {row.active_task ? (
              <p className="text-muted-foreground">
                active task{" "}
                <Link href={`/tasks?task_id=${encodeURIComponent(row.active_task.id)}`} className="underline hover:text-foreground">
                  {row.active_task.id}
                </Link>{" "}
                ({row.active_task.status})
              </p>
            ) : (
              <p className="text-muted-foreground">ready to create as <code>{row.task_type}</code> task</p>
            )}
          </li>
        ))}
        {flow.unblock_queue.length === 0 && (
          <li className="text-muted-foreground">No blockers detected in current flow scope.</li>
        )}
      </ul>
    </section>
  );
}
