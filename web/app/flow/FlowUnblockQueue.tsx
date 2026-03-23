import Link from "next/link";

import { formatUsd, humanizeStatus } from "@/lib/humanize";

import type { FlowResponse } from "./types";

type Props = { flow: FlowResponse };

function stageLabel(value: string): string {
  const normalized = value.trim().toLowerCase();
  if (normalized === "spec") return "planning";
  if (normalized === "process") return "work setup";
  if (normalized === "implementation") return "visible result";
  if (normalized === "validation") return "proof";
  if (normalized === "contributors") return "people handoff";
  if (normalized === "contributions") return "measured impact";
  return humanizeStatus(value);
}

function humanIdeaName(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return "Untitled idea";
  if (/[_-]/.test(trimmed) && !trimmed.includes(" ")) {
    return trimmed
      .split(/[_-]+/)
      .filter(Boolean)
      .map((word) => `${word.slice(0, 1).toUpperCase()}${word.slice(1)}`)
      .join(" ");
  }
  return trimmed;
}

function countLabel(value: number, singular: string, plural = `${singular}s`): string {
  return `${value} ${value === 1 ? singular : plural}`;
}

function nextMoveText(blockingStage: string): string {
  const normalized = blockingStage.trim().toLowerCase();
  if (normalized === "spec") return "Write the first clear plan so the work can start.";
  if (normalized === "process") return "Open or update the next work card so the plan turns into action.";
  if (normalized === "implementation") return "Show one visible result so people can see real progress.";
  if (normalized === "validation") return "Capture proof that the recent work really works.";
  if (normalized === "contributors") return "Make ownership clear so someone can pick this up quickly.";
  if (normalized === "contributions") return "Record what changed so the result becomes measurable.";
  return "Choose the next small step that gets this idea moving again.";
}

export function FlowUnblockQueue({ flow }: Props) {
  const queue = flow.unblock_queue.slice(0, 12);

  return (
    <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3">
      <h2 className="text-xl font-semibold">Best Places To Unstick Progress</h2>
      <p className="text-sm text-muted-foreground">
        Start with the ideas where a small step is most likely to reopen useful progress.
      </p>
      <ul className="space-y-2 text-sm">
        {queue.map((row) => (
          <li key={row.task_fingerprint} className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Link href={`/flow?idea_id=${encodeURIComponent(row.idea_id)}`} className="font-medium underline hover:text-foreground">
                {humanIdeaName(row.idea_name || row.idea_id)}
              </Link>
              <span className="text-xs text-muted-foreground">Stuck around {stageLabel(row.blocking_stage)}</span>
            </div>
            <p className="text-muted-foreground">
              Fixing this could reopen {countLabel(row.downstream_blocked.length, "later step")}.
            </p>
            <p className="text-muted-foreground">Suggested next move: {nextMoveText(row.blocking_stage)}</p>
            <p className="text-muted-foreground">
              Likely effort {formatUsd(row.estimated_unblock_cost)} | Possible value unlocked {formatUsd(row.estimated_unblock_value)}
            </p>
            {row.active_task ? (
              <p className="text-muted-foreground">
                A work card is already open for this. {" "}
                <Link href={`/tasks?task_id=${encodeURIComponent(row.active_task.id)}`} className="underline hover:text-foreground">
                  Open current work card
                </Link>
                .
              </p>
            ) : (
              <p className="text-muted-foreground">No work card is open for this yet. Start from the idea page or today page when you are ready.</p>
            )}
          </li>
        ))}
        {flow.unblock_queue.length === 0 ? (
          <li className="text-muted-foreground">No major blockers are visible in this progress view right now.</li>
        ) : null}
      </ul>
    </section>
  );
}
