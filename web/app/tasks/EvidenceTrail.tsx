"use client";

import Link from "next/link";
import type { AgentTask, EvidenceEventRow, EvidenceIdeaRow } from "./types";
import { TaskQuickUpdate } from "./TaskQuickUpdate";
import {
  describeTaskStatus,
  formatTime,
  humanizeTaskStatus,
  humanizeTaskType,
  tailLines,
  toInt,
} from "./utils";

type EvidenceTrailProps = {
  taskIdFilter: string;
  selectedTask: AgentTask | null;
  selectedTaskLog: string;
  selectedTaskEventsWarning: string | null;
  selectedContext: Record<string, unknown>;
  evidenceIdeas: EvidenceIdeaRow[];
  evidenceEvents: EvidenceEventRow[];
  acceptanceProof: {
    reviewPassFail: string;
    verifiedAssertions: string;
    reviewAccepted: boolean | null;
    infrastructureCostUsd: number;
    externalProviderCostUsd: number;
    totalCostUsd: number;
  };
  onTaskUpdated: () => Promise<void> | void;
};

function latestActivitySummary(events: EvidenceEventRow[]): string {
  const latest = events[0];
  if (!latest) return "No recent activity is visible for this work card yet.";
  if (latest.finalStatus) {
    return `Latest recorded result: ${humanizeTaskStatus(latest.finalStatus)}.`;
  }
  if (latest.trackingKind === "agent_tool_call") {
    return `Latest recorded update happened at ${formatTime(latest.recordedAt)}.`;
  }
  return `Latest recorded update happened at ${formatTime(latest.recordedAt)}.`;
}

function reviewSummary(acceptanceProof: EvidenceTrailProps["acceptanceProof"]): string {
  if (acceptanceProof.reviewAccepted === true) return "Recent review passed.";
  if (acceptanceProof.reviewAccepted === false) return "Recent review did not pass yet.";
  return "No review result is recorded yet.";
}

export function EvidenceTrail({
  taskIdFilter,
  selectedTask,
  selectedTaskLog,
  selectedTaskEventsWarning,
  selectedContext,
  evidenceIdeas,
  evidenceEvents,
  acceptanceProof,
  onTaskUpdated,
}: EvidenceTrailProps) {
  const failureHits = toInt(selectedContext.failure_hits);
  const retryCount = toInt(selectedContext.retry_count);
  const retryHint = String(selectedContext.retry_hint || "").trim();
  const lastFailure = String(selectedContext.last_failure_output || "").trim();

  return (
    <section className="rounded-2xl border border-border/70 bg-card/60 p-4 shadow-sm space-y-4 text-sm">
      <h2 className="font-semibold">Work Details</h2>
      {selectedTask ? (
        <>
          <div className="space-y-1">
            <p className="font-medium">
              {humanizeTaskType(selectedTask.task_type)} | {humanizeTaskStatus(selectedTask.status)}
            </p>
            <p className="text-muted-foreground">{describeTaskStatus(selectedTask.status)}</p>
            <p className="text-muted-foreground">
              Started {formatTime(selectedTask.created_at)} | Last updated {formatTime(selectedTask.updated_at)}
            </p>
            {selectedTask.current_step ? (
              <p className="text-muted-foreground">What is happening now: {selectedTask.current_step}</p>
            ) : null}
            {selectedTask.output ? (
              <p className="text-muted-foreground">Latest outcome note: {selectedTask.output}</p>
            ) : null}
          </div>

          <TaskQuickUpdate
            taskId={taskIdFilter}
            initialStatus={selectedTask.status || "pending"}
            initialCurrentStep={selectedTask.current_step || ""}
            initialOutput={selectedTask.output || ""}
            onUpdated={onTaskUpdated}
          />

          <div className="rounded-lg border border-border/70 bg-background/35 p-3 space-y-2">
            <p className="font-medium">What Connects To This Work</p>
            {evidenceIdeas.length === 0 ? (
              <p className="text-muted-foreground">This work card is not linked to an idea yet.</p>
            ) : (
              <ul className="space-y-1">
                {evidenceIdeas.map((row) => (
                  <li key={row.ideaId} className="text-muted-foreground">
                    <Link
                      href={`/ideas/${encodeURIComponent(row.ideaId)}`}
                      className="underline hover:text-foreground"
                      title={`Idea ID: ${row.ideaId}`}
                    >
                      {row.ideaName || "Linked idea"}
                    </Link>
                    {" "}|{" "}
                    <Link
                      href={`/flow?idea_id=${encodeURIComponent(row.ideaId)}`}
                      className="underline hover:text-foreground"
                      title={`Idea ID: ${row.ideaId}`}
                    >
                      Open progress
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="rounded-lg border border-border/70 bg-background/35 p-3 space-y-2">
            <p className="font-medium">What The System Has Seen</p>
            <p className="text-muted-foreground">{latestActivitySummary(evidenceEvents)}</p>
            <p className="text-muted-foreground">{reviewSummary(acceptanceProof)}</p>
            {selectedTaskEventsWarning ? (
              <p className="text-muted-foreground">Detailed activity is unavailable right now.</p>
            ) : null}
            {failureHits || retryCount ? (
              <p className="text-muted-foreground">
                This work has hit {failureHits || 0} recent failure signal{failureHits === 1 ? "" : "s"} and {retryCount || 0} retr{retryCount === 1 ? "y" : "ies"}.
              </p>
            ) : null}
            {lastFailure ? <p className="text-muted-foreground">Latest blocker note: {lastFailure}</p> : null}
            {retryHint ? <p className="text-muted-foreground">Suggested retry note: {retryHint}</p> : null}
          </div>

          <details className="rounded-lg border border-border/70 bg-background/35 p-3">
            <summary className="cursor-pointer font-medium">Behind the scenes</summary>
            <div className="mt-3 space-y-3 text-muted-foreground">
              <p>
                Internal state <code>{selectedTask.status}</code> | work type <code>{selectedTask.task_type}</code> | model <code>{selectedTask.model || "-"}</code>
              </p>
              <p>
                claimed_by <code>{selectedTask.claimed_by || "-"}</code> | task id <code>{taskIdFilter}</code>
              </p>
              <div>
                <p className="mb-1">Runtime events</p>
                {evidenceEvents.length === 0 ? (
                  <p>No runtime events found.</p>
                ) : (
                  <ul className="space-y-1">
                    {evidenceEvents.slice(0, 20).map((row) => (
                      <li key={row.id}>
                        <code>{row.id}</code> | {formatTime(row.recordedAt)} | <code>{row.endpoint}</code> | status <code>{row.statusCode}</code>
                        {row.trackingKind ? <> | kind <code>{row.trackingKind}</code></> : null}
                        {row.finalStatus ? <> | final <code>{row.finalStatus}</code></> : null}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div>
                <p className="mb-1">Review and cost record</p>
                <p>
                  review_pass_fail <code>{acceptanceProof.reviewPassFail || "-"}</code> | review_accepted{" "}
                  <code>
                    {acceptanceProof.reviewAccepted === null
                      ? "-"
                      : acceptanceProof.reviewAccepted
                        ? "true"
                        : "false"}
                  </code>
                </p>
                <p>
                  verified_assertions <code>{acceptanceProof.verifiedAssertions || "-"}</code>
                </p>
                <p>
                  infrastructure_cost_usd <code>{acceptanceProof.infrastructureCostUsd.toFixed(6)}</code> | external_provider_cost_usd{" "}
                  <code>{acceptanceProof.externalProviderCostUsd.toFixed(6)}</code> | total_cost_usd <code>{acceptanceProof.totalCostUsd.toFixed(6)}</code>
                </p>
              </div>
              <div>
                <p className="mb-1">Task log tail</p>
                <pre className="rounded bg-muted/40 p-2 overflow-auto whitespace-pre-wrap break-words">
                  {selectedTaskLog ? tailLines(selectedTaskLog, 40) : "(task log unavailable)"}
                </pre>
              </div>
            </div>
          </details>
        </>
      ) : (
        <p className="text-muted-foreground">The selected work card could not be loaded right now.</p>
      )}
    </section>
  );
}
