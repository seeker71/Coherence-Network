import Link from "next/link";

import { formatUsd, humanizeStatus } from "@/lib/humanize";

import type { FlowResponse } from "./types";

type Props = { flow: FlowResponse };

type QueueItem = FlowResponse["unblock_queue"][number];

function stageLabel(value: string): string {
  const normalized = value.trim().toLowerCase();
  if (normalized === "spec") return "Planning";
  if (normalized === "process") return "Work setup";
  if (normalized === "implementation") return "Visible result";
  if (normalized === "validation") return "Proof";
  if (normalized === "contributors") return "People handoff";
  if (normalized === "contributions") return "Measured impact";
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

function stageBadgeColor(value: string): string {
  const normalized = value.trim().toLowerCase();
  if (normalized === "spec") return "bg-blue-500/10 text-blue-500";
  if (normalized === "process") return "bg-amber-500/10 text-amber-500";
  if (normalized === "implementation") return "bg-purple-500/10 text-purple-500";
  if (normalized === "validation") return "bg-cyan-500/10 text-cyan-500";
  if (normalized === "contributors") return "bg-emerald-500/10 text-emerald-500";
  if (normalized === "contributions") return "bg-orange-500/10 text-orange-500";
  return "bg-muted text-muted-foreground";
}

function groupByStage(items: QueueItem[]): Map<string, QueueItem[]> {
  const groups = new Map<string, QueueItem[]>();
  for (const item of items) {
    const key = item.blocking_stage;
    const list = groups.get(key) || [];
    list.push(item);
    groups.set(key, list);
  }
  return groups;
}

export function FlowUnblockQueue({ flow }: Props) {
  const queue = flow.unblock_queue.slice(0, 12);
  const overflow = Math.max(0, flow.unblock_queue.length - 12);
  const grouped = groupByStage(queue);

  return (
    <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3">
      <h2 className="text-xl font-semibold">Best Places To Unstick Progress</h2>
      <p className="text-sm text-muted-foreground">
        Start with the ideas where a small step is most likely to reopen useful progress.
      </p>

      {flow.unblock_queue.length === 0 ? (
        <p className="text-sm text-muted-foreground">No major blockers are visible in this progress view right now.</p>
      ) : (
        <div className="space-y-4">
          {Array.from(grouped.entries()).map(([stage, items]) => (
            <div key={stage} className="space-y-1">
              <div className="flex items-center gap-2 mb-1.5">
                <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${stageBadgeColor(stage)}`}>
                  {stageLabel(stage)}
                </span>
                <span className="text-xs text-muted-foreground">{nextMoveText(stage)}</span>
              </div>
              <div className="rounded-xl border border-border/20 bg-background/40 overflow-hidden">
                <table className="w-full text-sm">
                  <tbody className="divide-y divide-border/10">
                    {items.map((row) => (
                      <tr key={row.task_fingerprint} className="hover:bg-accent/30 transition-colors">
                        <td className="px-3 py-2 font-medium">
                          <Link href={`/flow?idea_id=${encodeURIComponent(row.idea_id)}`} className="hover:underline">
                            {humanIdeaName(row.idea_name || row.idea_id)}
                          </Link>
                        </td>
                        <td className="px-3 py-2 text-xs text-muted-foreground text-right whitespace-nowrap">
                          {formatUsd(row.estimated_unblock_cost)} effort
                        </td>
                        <td className="px-3 py-2 text-xs text-muted-foreground text-right whitespace-nowrap">
                          {formatUsd(row.estimated_unblock_value)} value
                        </td>
                        {row.downstream_blocked.length > 0 ? (
                          <td className="px-3 py-2 text-xs text-muted-foreground text-right whitespace-nowrap">
                            unblocks {row.downstream_blocked.length}
                          </td>
                        ) : (
                          <td className="px-3 py-2" />
                        )}
                        <td className="px-3 py-2 text-right">
                          {row.active_task ? (
                            <Link
                              href={`/tasks?task_id=${encodeURIComponent(row.active_task.id)}`}
                              className="inline-flex items-center gap-1 text-xs text-green-500 hover:underline"
                              title="Work card open"
                            >
                              <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-500" />
                              active
                            </Link>
                          ) : (
                            <span className="inline-block w-1.5 h-1.5 rounded-full bg-muted-foreground/30" title="No work card" />
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
          {overflow > 0 && (
            <p className="text-xs text-muted-foreground">+{overflow} more blocked items not shown</p>
          )}
        </div>
      )}
    </section>
  );
}
