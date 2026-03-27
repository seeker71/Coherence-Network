"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";

const STORAGE_KEY = "coherence_contributor_id";

type Position = {
  idea_id: string;
  idea_name: string;
  staked_cc: number;
  time_hours_committed: number;
  roi_cc: number;
  current_value_cc: number;
};

type PortfolioPayload = {
  positions: Position[];
  totals?: { staked_cc: number; estimated_mark_value_cc: number };
};

export default function InvestPortfolioPage() {
  const [contributorId, setContributorId] = useState("");
  const [input, setInput] = useState("");
  const [data, setData] = useState<PortfolioPayload | null>(null);
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
        `${API}/api/investments/portfolio?contributor_id=${encodeURIComponent(id.trim())}`,
        { cache: "no-store" },
      );
      if (!res.ok) {
        setData(null);
        return;
      }
      const j: PortfolioPayload = await res.json();
      setData(j);
    } catch {
      setData(null);
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

  return (
    <main className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <header>
        <h1 className="text-3xl font-bold tracking-tight mb-2">Portfolio</h1>
        <p className="text-muted-foreground max-w-2xl">
          Staked CC and estimated mark value per idea (ROI from live portfolio scores).
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
      ) : data?.positions ? (
        <div className="space-y-4">
          {data.totals ? (
            <div className="rounded-2xl border border-primary/20 bg-primary/5 p-4 flex flex-wrap gap-6 text-sm">
              <div>
                <p className="text-muted-foreground">Total staked</p>
                <p className="text-xl font-semibold">{data.totals.staked_cc} CC</p>
              </div>
              <div>
                <p className="text-muted-foreground">Est. mark value</p>
                <p className="text-xl font-semibold">{data.totals.estimated_mark_value_cc} CC</p>
              </div>
            </div>
          ) : null}
          {data.positions.length === 0 ? (
            <p className="text-muted-foreground">No positions yet. Stake from the Invest page.</p>
          ) : (
            <ul className="space-y-3">
              {data.positions.map((p) => (
                <li
                  key={p.idea_id}
                  className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5"
                >
                  <div className="flex flex-wrap justify-between gap-2">
                    <Link
                      href={`/ideas/${encodeURIComponent(p.idea_id)}`}
                      className="font-medium hover:text-primary"
                    >
                      {p.idea_name}
                    </Link>
                    <span className="text-sm text-muted-foreground">ROI × {p.roi_cc.toFixed(3)}</span>
                  </div>
                  <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
                    <div>
                      <p className="text-xs text-muted-foreground">Staked</p>
                      <p>{p.staked_cc} CC</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Est. value</p>
                      <p className="font-medium text-primary">{p.current_value_cc} CC</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Time</p>
                      <p>{p.time_hours_committed > 0 ? `${p.time_hours_committed}h` : "—"}</p>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : (
        <p className="text-muted-foreground">Enter a contributor name to load your portfolio.</p>
      )}

      <nav className="text-sm">
        <Link href="/invest" className="text-amber-600 dark:text-amber-400 hover:underline">
          ← Invest
        </Link>
        {" · "}
        <Link href="/invest/history" className="text-amber-600 dark:text-amber-400 hover:underline">
          History
        </Link>
      </nav>
    </main>
  );
}
