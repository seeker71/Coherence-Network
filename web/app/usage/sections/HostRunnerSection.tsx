import type { DailySummary } from "../types";

type HostRunnerSectionProps = {
  dailySummary: DailySummary;
  workerFailedRaw: number;
  workerFailedRecoverable: number;
  workerFailedActive: number;
  recoveryStreakTarget: number;
  hostTaskTypeRows: [string, Record<string, number>][];
};

export function HostRunnerSection({
  dailySummary,
  workerFailedRaw,
  workerFailedRecoverable,
  workerFailedActive,
  recoveryStreakTarget,
  hostTaskTypeRows,
}: HostRunnerSectionProps) {
  const toolUsage = dailySummary.tool_usage ?? { worker_events: 0 };
  return (
    <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-2 text-sm">
      <h2 className="text-xl font-semibold">Host Runner (24h)</h2>
      <p className="text-muted-foreground">
        runs {dailySummary.host_runner.total_runs} | failed {dailySummary.host_runner.failed_runs} | completed{" "}
        {dailySummary.host_runner.completed_runs} | tool events {toolUsage.worker_events} | tool failures(raw){" "}
        {workerFailedRaw} | recoverable {workerFailedRecoverable} | active {workerFailedActive} | recovery streak target{" "}
        {recoveryStreakTarget}x
      </p>
      <ul className="space-y-2">
        {hostTaskTypeRows.map(([taskType, counts]) => (
          <li
            key={taskType}
            className="rounded-lg border border-border/30 bg-background/40 p-2 flex flex-wrap justify-between gap-2"
          >
            <span className="font-medium">{taskType}</span>
            <span className="text-muted-foreground">
              total {Number(counts.total || 0)} | completed {Number(counts.completed || 0)} | failed{" "}
              {Number(counts.failed || 0)}
            </span>
          </li>
        ))}
        {hostTaskTypeRows.length === 0 ? (
          <li className="text-muted-foreground">No host-runner task-type data yet.</li>
        ) : null}
      </ul>
      {dailySummary.contract_gaps.length > 0 ? (
        <div className="rounded-xl border border-border/30 bg-background/40 p-3">
          <p className="font-medium mb-1">Telemetry Contract Gaps</p>
          <ul className="list-disc pl-5 space-y-1 text-muted-foreground">
            {dailySummary.contract_gaps.map((gap) => (
              <li key={gap}>{gap}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
