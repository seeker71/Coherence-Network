import type { DailySummary } from "../types";

type QualityAwarenessSectionProps = {
  qualityAwareness: DailySummary["quality_awareness"];
};

export function QualityAwarenessSection({ qualityAwareness }: QualityAwarenessSectionProps) {
  const summary = qualityAwareness.summary;
  return (
    <section className="rounded-2xl border border-border/70 bg-card/60 p-4 shadow-sm space-y-2 text-sm">
      <h2 className="font-semibold">Code Quality Awareness (Guidance)</h2>
      <p className="text-muted-foreground">
        intent {qualityAwareness.intent_focus.join(", ")} | severity {summary.severity} | risk score {summary.risk_score}{" "}
        | status {qualityAwareness.status}
      </p>
      <p className="text-muted-foreground">
        modules {summary.python_module_count} | runtime files {summary.runtime_file_count} | layer violations{" "}
        {summary.layer_violations} | very large modules {summary.very_large_modules} | long functions{" "}
        {summary.long_functions}
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="rounded-xl border border-border/70 bg-background/45 p-3">
          <p className="font-medium mb-2">Hotspots</p>
          <ul className="space-y-1">
            {qualityAwareness.hotspots.slice(0, 6).map((row, idx) => (
              <li key={`${row.path}:${row.kind}:${idx}`} className="flex flex-col">
                <span>
                  {row.path} [{row.kind}]
                </span>
                <span className="text-muted-foreground text-xs">
                  {row.function ? `fn ${row.function} | ` : ""}
                  {row.line_count ? `lines ${row.line_count} | ` : ""}
                  {row.line ? `line ${row.line} | ` : ""}
                  {row.detail}
                </span>
              </li>
            ))}
            {qualityAwareness.hotspots.length === 0 ? (
              <li className="text-muted-foreground">No current maintainability hotspots in this window.</li>
            ) : null}
          </ul>
        </div>
        <div className="rounded-xl border border-border/70 bg-background/45 p-3">
          <p className="font-medium mb-2">Guidance</p>
          <ul className="space-y-1">
            {qualityAwareness.guidance.map((row) => (
              <li key={row} className="text-muted-foreground">
                {row}
              </li>
            ))}
            {qualityAwareness.guidance.length === 0 ? (
              <li className="text-muted-foreground">No quality guidance available yet.</li>
            ) : null}
          </ul>
        </div>
      </div>
      <div className="rounded-xl border border-border/70 bg-background/45 p-3">
        <p className="font-medium mb-2">Recommended self-improvement tasks</p>
        <ul className="space-y-1">
          {qualityAwareness.recommended_tasks.slice(0, 3).map((task) => (
            <li key={task.task_id || task.title} className="flex justify-between gap-2">
              <span className="truncate">{task.title || task.task_id}</span>
              <span className="text-muted-foreground">
                priority {task.priority} | roi {task.roi_estimate.toFixed(2)}
              </span>
            </li>
          ))}
          {qualityAwareness.recommended_tasks.length === 0 ? (
            <li className="text-muted-foreground">No recommended quality tasks available.</li>
          ) : null}
        </ul>
      </div>
    </section>
  );
}
