import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "Graph balance — Self-equilibrium",
  description:
    "Split signals, orphan merge hints, and idea energy concentration for dynamic graph health.",
};

type BalancePayload = {
  split_signals: Array<{
    node_id: string;
    name: string;
    node_type: string;
    child_count: number;
    reason: string;
    suggested_action: string;
  }>;
  merge_suggestions: Array<{
    node_ids: string[];
    names: string[];
    component_size: number;
    reason: string;
    suggested_action: string;
  }>;
  entropy: {
    total_ideas: number;
    top3_energy_share: number;
    concentration_alert: boolean;
    shannon_entropy_normalized: number;
    neglected_branches: Array<{
      idea_id: string;
      name: string;
      energy: number;
      value_gap: number;
      roi_cc: number;
      reason: string;
    }>;
  };
  parameters: { max_children: number; concentration_threshold: number };
};

async function loadBalance(): Promise<BalancePayload | null> {
  try {
    const api = getApiBase();
    const res = await fetch(`${api}/api/graph/balance`, { next: { revalidate: 60 } });
    if (!res.ok) return null;
    return (await res.json()) as BalancePayload;
  } catch {
    return null;
  }
}

export default async function GraphBalancePage() {
  const data = await loadBalance();

  return (
    <div className="mx-auto max-w-4xl px-4 py-10 text-muted-foreground">
      <p className="mb-2 text-sm text-muted-foreground/80">
        <Link href="/graph" className="text-primary hover:underline">
          Graph
        </Link>
        {" / "}
        <span>Balance</span>
      </p>
      <h1 className="mb-2 text-2xl font-semibold tracking-tight text-foreground">
        Fractal self-balance
      </h1>
      <p className="mb-8 max-w-2xl text-sm leading-relaxed">
        Dynamic equilibrium signals: split overloaded parents, merge orphan clusters, and
        surface neglected ideas when energy concentrates on a few branches.
      </p>

      {!data && (
        <p className="rounded-md border border-border bg-muted/30 px-4 py-3 text-sm">
          Unable to load balance report. Check API connectivity and{" "}
          <code className="text-xs">NEXT_PUBLIC_API_URL</code>.
        </p>
      )}

      {data && (
        <div className="space-y-8">
          <section className="rounded-lg border border-border bg-card/40 p-4">
            <h2 className="mb-2 text-lg font-medium text-foreground">Parameters</h2>
            <p className="text-sm">
              max_children ≥ {data.parameters.max_children} triggers split · concentration
              threshold {data.parameters.concentration_threshold}
            </p>
          </section>

          <section className="rounded-lg border border-border bg-card/40 p-4">
            <h2 className="mb-2 text-lg font-medium text-foreground">Entropy</h2>
            <ul className="list-inside list-disc space-y-1 text-sm">
              <li>Ideas: {data.entropy.total_ideas}</li>
              <li>Top-3 energy share: {(data.entropy.top3_energy_share * 100).toFixed(1)}%</li>
              <li>
                Diversity (Shannon, normalized):{" "}
                {(data.entropy.shannon_entropy_normalized * 100).toFixed(0)}%
              </li>
              <li>
                Concentration alert:{" "}
                <span className={data.entropy.concentration_alert ? "text-amber-400" : ""}>
                  {data.entropy.concentration_alert ? "yes" : "no"}
                </span>
              </li>
            </ul>
            {data.entropy.neglected_branches.length > 0 && (
              <div className="mt-4">
                <h3 className="mb-2 text-sm font-medium text-foreground">Neglected branches</h3>
                <ul className="space-y-2 text-sm">
                  {data.entropy.neglected_branches.slice(0, 12).map((n) => (
                    <li key={n.idea_id} className="rounded border border-border/60 px-3 py-2">
                      <span className="font-medium text-foreground">{n.name}</span> —{" "}
                      <span className="text-muted-foreground">gap {n.value_gap.toFixed(2)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>

          <section className="rounded-lg border border-border bg-card/40 p-4">
            <h2 className="mb-2 text-lg font-medium text-foreground">Split signals</h2>
            {data.split_signals.length === 0 ? (
              <p className="text-sm text-muted-foreground">None — fan-out within limits.</p>
            ) : (
              <ul className="space-y-3 text-sm">
                {data.split_signals.map((s) => (
                  <li key={s.node_id} className="rounded border border-amber-500/30 bg-amber-500/5 px-3 py-2">
                    <strong className="text-foreground">{s.name}</strong> ({s.child_count}{" "}
                    children)
                    <p className="mt-1 text-muted-foreground">{s.suggested_action}</p>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="rounded-lg border border-border bg-card/40 p-4">
            <h2 className="mb-2 text-lg font-medium text-foreground">Merge suggestions</h2>
            {data.merge_suggestions.length === 0 ? (
              <p className="text-sm text-muted-foreground">No orphan clusters detected.</p>
            ) : (
              <ul className="space-y-3 text-sm">
                {data.merge_suggestions.map((m, idx) => (
                  <li key={idx} className="rounded border border-cyan-500/30 bg-cyan-500/5 px-3 py-2">
                    <span className="text-foreground">{m.names.join(" · ")}</span>
                    <p className="mt-1 text-muted-foreground">{m.suggested_action}</p>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
