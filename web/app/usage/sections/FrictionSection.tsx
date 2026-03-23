import Link from "next/link";
import type { DailySummary } from "../types";

type FrictionSectionProps = {
  friction: DailySummary["friction"];
};

export function FrictionSection({ friction }: FrictionSectionProps) {
  return (
    <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-2 text-sm">
      <h2 className="text-xl font-semibold">Friction (24h)</h2>
      <p className="text-muted-foreground">total_events {friction.total_events} | open {friction.open_events}</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="rounded-xl border border-border/30 bg-background/40 p-3">
          <p className="font-medium mb-2">Top block types</p>
          <ul className="space-y-1">
            {friction.top_block_types.slice(0, 8).map((row) => (
              <li key={row.key} className="flex justify-between">
                <Link href="/friction" className="underline hover:text-foreground">
                  {row.key}
                </Link>
                <span className="text-muted-foreground">{row.count}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-xl border border-border/30 bg-background/40 p-3">
          <p className="font-medium mb-2">Top stages</p>
          <ul className="space-y-1">
            {friction.top_stages.slice(0, 8).map((row) => (
              <li key={row.key} className="flex justify-between">
                <span>{row.key}</span>
                <span className="text-muted-foreground">{row.count}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <div className="rounded-xl border border-border/30 bg-background/40 p-3">
        <p className="font-medium mb-2">Top entry points</p>
        <ul className="space-y-1">
          {friction.entry_points.slice(0, 8).map((row) => (
            <li key={row.key} className="flex justify-between gap-2">
              <span className="truncate">{row.key}</span>
              <span className="text-muted-foreground">
                events {row.event_count} | {row.status}
              </span>
            </li>
          ))}
          {friction.entry_points.length === 0 ? (
            <li className="text-muted-foreground">No friction entry points in the selected window.</li>
          ) : null}
        </ul>
      </div>
    </section>
  );
}
