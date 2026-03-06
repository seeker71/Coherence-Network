"use client";

import Link from "next/link";
import type { AgentTask, EvidenceEventRow, EvidenceIdeaRow } from "./types";
import { formatTime, tailLines, toInt } from "./utils";

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
};

export function EvidenceTrail({
  taskIdFilter,
  selectedTask,
  selectedTaskLog,
  selectedTaskEventsWarning,
  selectedContext,
  evidenceIdeas,
  evidenceEvents,
  acceptanceProof,
}: EvidenceTrailProps) {
  const failureHits = toInt(selectedContext.failure_hits);
  const retryCount = toInt(selectedContext.retry_count);
  const retryHint = String(selectedContext.retry_hint || "").trim();
  const lastFailure = String(selectedContext.last_failure_output || "").trim();

  return (
    <section className="rounded-2xl border border-border/70 bg-card/60 p-4 shadow-sm space-y-3 text-sm">
      <h2 className="font-semibold">Evidence Trail</h2>
      {selectedTask ? (
        <>
          <p className="text-muted-foreground">
            status <code>{selectedTask.status}</code> | task_type <code>{selectedTask.task_type}</code> | model{" "}
            <code>{selectedTask.model || "-"}</code>
          </p>
          <p className="text-muted-foreground">
            created {formatTime(selectedTask.created_at)} | updated {formatTime(selectedTask.updated_at)} | claimed_by{" "}
            <code>{selectedTask.claimed_by || "-"}</code>
          </p>
          {selectedTask.current_step ? (
            <p className="text-muted-foreground">
              current_step <code>{selectedTask.current_step}</code>
            </p>
          ) : null}
          {Array.isArray(selectedContext.runner_recent_activity) &&
          selectedContext.runner_recent_activity.length > 0 ? (
            <div className="space-y-1">
              <p className="text-muted-foreground">recent activity</p>
              <ul className="list-disc list-inside text-muted-foreground">
                {(selectedContext.runner_recent_activity as { step?: string }[]).map((a, i) => (
                  <li key={i}>{a.step ?? "—"}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <div>
            <p className="text-muted-foreground mb-1">output</p>
            <pre className="rounded bg-muted/40 p-2 overflow-auto whitespace-pre-wrap break-words">
              {selectedTask.output || "(empty)"}
            </pre>
          </div>

          <div className="space-y-1">
            <p className="text-muted-foreground">retry/failure telemetry</p>
            <p>
              failure_hits <code>{failureHits ?? "-"}</code> | retry_count <code>{retryCount ?? "-"}</code>
            </p>
            {lastFailure ? (
              <p className="text-muted-foreground">
                last_failure_output <code>{lastFailure}</code>
              </p>
            ) : null}
            {retryHint ? (
              <p className="text-muted-foreground">
                retry_hint <code>{retryHint}</code>
              </p>
            ) : null}
          </div>

          <div className="space-y-1">
            <p className="text-muted-foreground">linked ideas</p>
            {evidenceIdeas.length === 0 ? (
              <p className="text-muted-foreground">No idea linkage found for this task.</p>
            ) : (
              <ul className="space-y-1">
                {evidenceIdeas.map((row) => (
                  <li key={row.ideaId}>
                    <Link href={`/ideas/${encodeURIComponent(row.ideaId)}`} className="underline hover:text-foreground">
                      {row.ideaId}
                    </Link>{" "}
                    <span className="text-muted-foreground">({row.source})</span>{" "}
                    |{" "}
                    <Link href={`/flow?idea_id=${encodeURIComponent(row.ideaId)}`} className="underline hover:text-foreground">
                      flow
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="space-y-1">
            <p className="text-muted-foreground">runtime events for this task</p>
            {selectedTaskEventsWarning ? (
              <p className="text-muted-foreground">
                runtime events unavailable: <code>{selectedTaskEventsWarning}</code>
              </p>
            ) : null}
            {evidenceEvents.length === 0 ? (
              <p className="text-muted-foreground">No runtime events found.</p>
            ) : (
              <ul className="space-y-1">
                {evidenceEvents.slice(0, 20).map((row) => (
                  <li key={row.id}>
                    <code>{row.id}</code> | {formatTime(row.recordedAt)} | <code>{row.endpoint}</code> | status{" "}
                    <code>{row.statusCode}</code>
                    {row.trackingKind ? (
                      <>
                        {" "}
                        | kind <code>{row.trackingKind}</code>
                      </>
                    ) : null}
                    {row.finalStatus ? (
                      <>
                        {" "}
                        | final <code>{row.finalStatus}</code>
                      </>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="space-y-1">
            <p className="text-muted-foreground">MVP acceptance proof</p>
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
            <p className="text-muted-foreground">
              verified_assertions <code>{acceptanceProof.verifiedAssertions || "-"}</code>
            </p>
            <p className="text-muted-foreground">
              infrastructure_cost_usd <code>{acceptanceProof.infrastructureCostUsd.toFixed(6)}</code> | external_provider_cost_usd{" "}
              <code>{acceptanceProof.externalProviderCostUsd.toFixed(6)}</code> | total_cost_usd{" "}
              <code>{acceptanceProof.totalCostUsd.toFixed(6)}</code>
            </p>
          </div>

          <div>
            <p className="text-muted-foreground mb-1">task log tail (proof)</p>
            <pre className="rounded bg-muted/40 p-2 overflow-auto whitespace-pre-wrap break-words">
              {selectedTaskLog ? tailLines(selectedTaskLog, 40) : "(task log unavailable)"}
            </pre>
          </div>
        </>
      ) : (
        <p className="text-muted-foreground">Task details unavailable for <code>{taskIdFilter}</code>.</p>
      )}
    </section>
  );
}
