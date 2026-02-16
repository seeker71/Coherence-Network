import Link from "next/link";

import { getApiBase } from "@/lib/api";

type RuntimeIdeaRow = {
  idea_id: string;
  event_count: number;
  total_runtime_ms: number;
  average_runtime_ms: number;
  runtime_cost_estimate: number;
  by_source: Record<string, number>;
};

type RuntimeSummaryResponse = {
  window_seconds: number;
  ideas: RuntimeIdeaRow[];
};

type FrictionReportRow = {
  key: string;
  count: number;
  energy_loss: number;
  cost_of_delay?: number;
};

type FrictionReport = {
  window_days: number;
  total_events: number;
  open_events: number;
  total_energy_loss: number;
  total_cost_of_delay: number;
  top_block_types: FrictionReportRow[];
  top_stages: FrictionReportRow[];
};

async function loadUsage(): Promise<{ runtime: RuntimeSummaryResponse; friction: FrictionReport }> {
  const API = getApiBase();
  const [rtRes, frRes] = await Promise.all([
    fetch(`${API}/api/runtime/ideas/summary?seconds=86400`, { cache: "no-store" }),
    fetch(`${API}/api/friction/report?window_days=7`, { cache: "no-store" }),
  ]);
  if (!rtRes.ok) throw new Error(`runtime HTTP ${rtRes.status}`);
  if (!frRes.ok) throw new Error(`friction HTTP ${frRes.status}`);
  return {
    runtime: (await rtRes.json()) as RuntimeSummaryResponse,
    friction: (await frRes.json()) as FrictionReport,
  };
}

export default async function UsagePage() {
  const { runtime, friction } = await loadUsage();
  const ideas = [...runtime.ideas].sort((a, b) => b.runtime_cost_estimate - a.runtime_cost_estimate).slice(0, 20);

  return (
    <main className="min-h-screen p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Home
        </Link>
        <Link href="/portfolio" className="text-muted-foreground hover:text-foreground">
          Portfolio
        </Link>
        <Link href="/ideas" className="text-muted-foreground hover:text-foreground">
          Ideas
        </Link>
        <Link href="/specs" className="text-muted-foreground hover:text-foreground">
          Specs
        </Link>
        <Link href="/flow" className="text-muted-foreground hover:text-foreground">
          Flow
        </Link>
        <Link href="/contributors" className="text-muted-foreground hover:text-foreground">
          Contributors
        </Link>
        <Link href="/contributions" className="text-muted-foreground hover:text-foreground">
          Contributions
        </Link>
        <Link href="/assets" className="text-muted-foreground hover:text-foreground">
          Assets
        </Link>
        <Link href="/tasks" className="text-muted-foreground hover:text-foreground">
          Tasks
        </Link>
        <Link href="/gates" className="text-muted-foreground hover:text-foreground">
          Gates
        </Link>
      </div>

      <h1 className="text-2xl font-bold">Usage</h1>
      <p className="text-muted-foreground">Runtime telemetry + friction summary (machine data rendered for humans).</p>

      <section className="rounded border p-4 space-y-2 text-sm">
        <h2 className="font-semibold">Friction (7d)</h2>
        <p className="text-muted-foreground">
          total_events {friction.total_events} | open {friction.open_events} | energy_loss {friction.total_energy_loss}
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="rounded border p-3">
            <p className="font-medium mb-2">Top block types</p>
            <ul className="space-y-1">
              {friction.top_block_types.slice(0, 8).map((r) => (
                <li key={r.key} className="flex justify-between">
                  <Link href="/friction" className="underline hover:text-foreground">
                    {r.key}
                  </Link>
                  <span className="text-muted-foreground">{r.count}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded border p-3">
            <p className="font-medium mb-2">Top stages</p>
            <ul className="space-y-1">
              {friction.top_stages.slice(0, 8).map((r) => (
                <li key={r.key} className="flex justify-between">
                  <span>{r.key}</span>
                  <span className="text-muted-foreground">{r.count}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <section className="rounded border p-4 space-y-2 text-sm">
        <h2 className="font-semibold">Runtime Cost by Idea (24h)</h2>
        <p className="text-muted-foreground">window_seconds {runtime.window_seconds}</p>
        <ul className="space-y-2">
              {ideas.map((row) => (
                <li key={row.idea_id} className="flex justify-between rounded border p-2">
              <Link href={`/ideas/${encodeURIComponent(row.idea_id)}`} className="underline hover:text-foreground">
                {row.idea_id}
              </Link>
              <span className="text-muted-foreground">
                events {row.event_count} | runtime {row.total_runtime_ms.toFixed(2)}ms | cost ${row.runtime_cost_estimate.toFixed(6)}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
