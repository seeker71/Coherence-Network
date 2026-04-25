import Link from "next/link";
import type { WebViewPerformanceRow } from "../types";

type ViewPerformanceSectionProps = {
  viewRows: WebViewPerformanceRow[];
};

export function ViewPerformanceSection({ viewRows }: ViewPerformanceSectionProps) {
  return (
    <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-2 text-sm">
      <h2 className="text-xl font-semibold">Full View Render + API Cost</h2>
      <p className="text-muted-foreground">
        Measured after data is loaded (`web_view_complete` beacon): render time and summed API runtime/cost per route.
      </p>
      <ul className="space-y-2">
        {viewRows.map((row) => (
          <li
            key={row.route}
            className="rounded-lg border border-border/30 bg-background/40 p-2 flex flex-wrap justify-between gap-2"
          >
            <Link href={row.route} className="underline hover:text-foreground">
              {row.route}
            </Link>
            <span className="text-muted-foreground">
              views {row.views} | p50 {row.p50_render_ms.toFixed(1)}ms | p95 {row.p95_render_ms.toFixed(1)}ms | api
              calls {row.average_api_call_count.toFixed(1)} | api runtime {row.average_api_runtime_ms.toFixed(1)}ms |
              api cost ${row.average_api_runtime_cost_estimate.toFixed(6)}
            </span>
          </li>
        ))}
        {viewRows.length === 0 ? (
          <li className="text-muted-foreground">
            No full-view telemetry yet. Visit pages and refresh this screen.
          </li>
        ) : null}
      </ul>
    </section>
  );
}
