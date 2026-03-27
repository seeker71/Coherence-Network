"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { getApiBase } from "@/lib/api";

const STORAGE_KEY = "coherence_contributor_id";

type FlowEdge = {
  source: string;
  target: string;
  amount_cc: number;
  kind: string;
  recorded_at?: string;
  hours?: number;
  commitment?: string;
};

type FlowNode = { id: string; label: string; type: string };

type FlowPayload = {
  nodes: FlowNode[];
  edges: FlowEdge[];
};

export default function InvestHistoryPage() {
  const [contributorId, setContributorId] = useState("");
  const [input, setInput] = useState("");
  const [flow, setFlow] = useState<FlowPayload | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const s = localStorage.getItem(STORAGE_KEY);
    if (s) {
      setContributorId(s);
      setInput(s);
    }
  }, []);

  const load = useCallback(async (id: string) => {
    if (!id.trim()) return;
    setLoading(true);
    try {
      const API = getApiBase();
      const res = await fetch(
        `${API}/api/investments/flow?contributor_id=${encodeURIComponent(id.trim())}`,
        { cache: "no-store" },
      );
      if (!res.ok) {
        setFlow(null);
        return;
      }
      const j: FlowPayload = await res.json();
      setFlow(j);
    } catch {
      setFlow(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (contributorId) void load(contributorId);
  }, [contributorId, load]);

  function saveName() {
    const t = input.trim();
    if (!t) return;
    localStorage.setItem(STORAGE_KEY, t);
    setContributorId(t);
  }

  const maxAmt = useMemo(() => {
    if (!flow?.edges?.length) return 1;
    return Math.max(...flow.edges.map((e) => Math.abs(e.amount_cc) || 0), 1);
  }, [flow]);

  return (
    <main className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <header>
        <h1 className="text-3xl font-bold tracking-tight mb-2">Investment history</h1>
        <p className="text-muted-foreground max-w-2xl">
          CC flowing from you toward ideas (and other ledger rows). Bar width scales to the largest
          movement in this window.
        </p>
      </header>

      <section className="rounded-2xl border border-border/30 bg-card/40 p-5 space-y-3">
        <p className="text-sm font-medium">Contributor</p>
        <div className="flex flex-wrap gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && saveName()}
            placeholder="Your contributor name"
            className="flex-1 min-w-[12rem] rounded-xl border border-border/40 bg-background px-3 py-2 text-sm"
          />
          <button
            type="button"
            onClick={saveName}
            className="rounded-xl bg-primary/10 px-4 py-2 text-sm font-medium text-primary"
          >
            Load
          </button>
        </div>
      </section>

      {loading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : flow?.edges ? (
        <div className="space-y-6">
          {flow.nodes.length > 1 ? (
            <div className="rounded-2xl border border-border/20 bg-muted/20 p-4 overflow-x-auto">
              <svg width="100%" height={120} viewBox="0 0 640 120" className="min-w-[520px]">
                <text x={16} y={56} className="fill-foreground text-xs font-medium">
                  You
                </text>
                {flow.nodes
                  .filter((n) => n.type === "idea")
                  .slice(0, 8)
                  .map((n, i) => {
                    const x = 180 + i * 92;
                    return (
                      <g key={n.id}>
                        <rect
                          x={x - 36}
                          y={36}
                          width={72}
                          height={40}
                          rx={8}
                          className="fill-primary/15 stroke-primary/40"
                        />
                        <text x={x} y={60} textAnchor="middle" className="fill-foreground text-[10px]">
                          {n.label.length > 14 ? `${n.label.slice(0, 12)}…` : n.label}
                        </text>
                      </g>
                    );
                  })}
                <line x1={56} y1={56} x2={140} y2={56} className="stroke-border" strokeWidth={1} />
              </svg>
              <p className="text-xs text-muted-foreground mt-2">
                Nodes show ideas you have directed CC or time toward (subset for clarity).
              </p>
            </div>
          ) : null}

          <ul className="space-y-2">
            {flow.edges.map((e, i) => {
              const label = e.target === "_network" ? "Network / other" : e.target;
              const w = Math.min(100, (Math.abs(e.amount_cc) / maxAmt) * 100);
              return (
                <li
                  key={`${e.recorded_at}-${i}`}
                  className="rounded-xl border border-border/30 bg-card/50 px-3 py-2 text-sm"
                >
                  <div className="flex flex-wrap justify-between gap-2">
                    <span className="text-muted-foreground">{e.kind}</span>
                    <span className="text-xs text-muted-foreground">
                      {e.recorded_at ? new Date(e.recorded_at).toLocaleString() : ""}
                    </span>
                  </div>
                  <div className="mt-1 font-medium">
                    → {label}{" "}
                    {e.amount_cc !== 0 ? (
                      <span className="text-primary">{e.amount_cc} CC</span>
                    ) : e.hours ? (
                      <span className="text-amber-600 dark:text-amber-400">
                        {e.hours}h ({e.commitment || "time"})
                      </span>
                    ) : null}
                  </div>
                  <div className="mt-2 h-1.5 rounded-full bg-muted/50 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-primary/50 to-primary"
                      style={{ width: `${w}%` }}
                    />
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      ) : (
        <p className="text-muted-foreground">Enter a contributor name to load flow history.</p>
      )}

      <nav className="text-sm">
        <Link href="/invest" className="text-amber-600 dark:text-amber-400 hover:underline">
          ← Invest
        </Link>
        {" · "}
        <Link href="/invest/portfolio" className="text-amber-600 dark:text-amber-400 hover:underline">
          Portfolio
        </Link>
      </nav>
    </main>
  );
}
