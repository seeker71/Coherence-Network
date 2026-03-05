import type { DailySummaryAttentionRow, DailySummaryTopTool } from "../types";

type TopToolsAttentionSectionProps = {
  topTools: DailySummaryTopTool[];
  topAttentionRows: DailySummaryAttentionRow[];
  recoveryStreakTarget: number;
};

export function TopToolsAttentionSection({
  topTools,
  topAttentionRows,
  recoveryStreakTarget,
}: TopToolsAttentionSectionProps) {
  return (
    <section className="rounded-2xl border border-border/70 bg-card/60 p-4 shadow-sm space-y-2 text-sm">
      <h2 className="font-semibold">Top Tool Usage + Attention (24h)</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="rounded-xl border border-border/70 bg-background/45 p-3">
          <p className="font-medium mb-2">Top tools</p>
          <ul className="space-y-1">
            {topTools.map((tool) => (
              <li key={tool.tool} className="flex justify-between">
                <span>{tool.tool}</span>
                <span className="text-muted-foreground">
                  events {tool.events} | failed(active) {tool.active_failed ?? tool.failed} | raw {tool.failed} | streak{" "}
                  {tool.recent_success_streak ?? 0}/{tool.success_streak_target ?? recoveryStreakTarget}
                  {tool.failure_recovered ? " | recovered" : ""}
                </span>
              </li>
            ))}
            {topTools.length === 0 ? (
              <li className="text-muted-foreground">No worker tool events in window.</li>
            ) : null}
          </ul>
        </div>
        <div className="rounded-xl border border-border/70 bg-background/45 p-3">
          <p className="font-medium mb-2">Top attention areas</p>
          <ul className="space-y-1">
            {topAttentionRows.map((row) => (
              <li key={row.endpoint} className="flex justify-between gap-2">
                <span className="truncate">{row.endpoint}</span>
                <span className="text-muted-foreground">
                  score {row.attention_score.toFixed(1)} | events {row.events} | streak{" "}
                  {row.recent_success_streak ?? 0}/{row.success_streak_target ?? recoveryStreakTarget}
                  {row.failure_recovered ? " | recovered" : ""}
                </span>
              </li>
            ))}
            {topAttentionRows.length === 0 ? (
              <li className="text-muted-foreground">No attention rows in window.</li>
            ) : null}
          </ul>
        </div>
      </div>
    </section>
  );
}
