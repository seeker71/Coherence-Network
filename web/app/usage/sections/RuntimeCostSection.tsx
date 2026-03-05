import Link from "next/link";
import type { RuntimeIdeaRow, RuntimeSummaryResponse } from "../types";

type RuntimeCostSectionProps = {
  ideas: RuntimeIdeaRow[];
  runtime: RuntimeSummaryResponse;
  page: number;
  hasPrevious: boolean;
  hasNext: boolean;
  previousHref: string;
  nextHref: string;
};

export function RuntimeCostSection({
  ideas,
  runtime,
  page,
  hasPrevious,
  hasNext,
  previousHref,
  nextHref,
}: RuntimeCostSectionProps) {
  return (
    <section className="rounded-2xl border border-border/70 bg-card/60 p-4 shadow-sm space-y-2 text-sm">
      <h2 className="font-semibold">Runtime Cost by Idea</h2>
      <p className="text-muted-foreground">window_seconds {runtime.window_seconds} | page {page}</p>
      <div className="flex gap-3 text-muted-foreground">
        {hasPrevious ? (
          <Link href={previousHref} className="underline hover:text-foreground">
            Previous
          </Link>
        ) : (
          <span className="opacity-50">Previous</span>
        )}
        {hasNext ? (
          <Link href={nextHref} className="underline hover:text-foreground">
            Next
          </Link>
        ) : (
          <span className="opacity-50">Next</span>
        )}
      </div>
      <ul className="space-y-2">
        {ideas.map((row) => (
          <li key={row.idea_id} className="flex justify-between rounded-lg border border-border/70 bg-background/45 p-2">
            <Link href={`/ideas/${encodeURIComponent(row.idea_id)}`} className="underline hover:text-foreground">
              {row.idea_id}
            </Link>
            <span className="text-muted-foreground">
              events {row.event_count} | runtime {row.total_runtime_ms.toFixed(2)}ms | cost $
              {row.runtime_cost_estimate.toFixed(6)}
            </span>
          </li>
        ))}
        {ideas.length === 0 ? (
          <li className="text-muted-foreground">No runtime usage found for this page.</li>
        ) : null}
      </ul>
    </section>
  );
}
