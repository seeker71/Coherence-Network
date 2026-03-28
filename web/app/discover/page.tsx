"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

import { getApiBase } from "@/lib/api";
import { useLiveRefresh } from "@/lib/live_refresh";

const API_URL = getApiBase();

type AxisKey =
  | "curiosity"
  | "serendipity"
  | "depth"
  | "coherence_affinity"
  | "recency";

const AXIS_LABELS: Record<AxisKey, { title: string; low: string; high: string }> = {
  curiosity: {
    title: "Curiosity",
    low: "Familiar",
    high: "Novel",
  },
  serendipity: {
    title: "Serendipity",
    low: "Close to what you already touch",
    high: "Surprising angles",
  },
  depth: {
    title: "Depth",
    low: "Overview",
    high: "Dense and connected",
  },
  coherence_affinity: {
    title: "Coherence",
    low: "Raw / contested",
    high: "Consensus-rich",
  },
  recency: {
    title: "Recency",
    low: "Timeless",
    high: "Fresh activity",
  },
};

type ResonanceIdea = {
  idea: {
    id: string;
    name: string;
    description?: string;
    free_energy_score?: number;
  };
  resonance_score: number;
  axis_profile: Record<string, number>;
};

type DiscoverResponse = {
  requested_axes: Record<string, number>;
  ideas: ResonanceIdea[];
};

const DEFAULT_AXES: Record<AxisKey, number> = {
  curiosity: 0.55,
  serendipity: 0.5,
  depth: 0.45,
  coherence_affinity: 0.5,
  recency: 0.65,
};

function pct(n: number) {
  return Math.round(n * 100);
}

export default function DiscoverPage() {
  const [axes, setAxes] = useState<Record<AxisKey, number>>(DEFAULT_AXES);
  const [contributorId, setContributorId] = useState("");
  const [data, setData] = useState<DiscoverResponse | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "ok" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const debounceFirst = useRef(true);

  const runDiscover = useCallback(async () => {
    setStatus("loading");
    setError(null);
    try {
      const body: Record<string, unknown> = {
        axes,
        limit: 24,
        include_internal: false,
        include_graph: true,
      };
      const trimmed = contributorId.trim();
      if (trimmed) body.contributor_id = trimmed;

      const res = await fetch(`${API_URL}/api/discovery/resonance`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        cache: "no-store",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = (await res.json()) as DiscoverResponse;
      setData(json);
      setStatus("ok");
    } catch (e) {
      setError(String(e));
      setStatus("error");
    }
  }, [axes, contributorId]);

  useEffect(() => {
    const delay = debounceFirst.current ? 0 : 320;
    debounceFirst.current = false;
    const t = window.setTimeout(() => {
      void runDiscover();
    }, delay);
    return () => window.clearTimeout(t);
  }, [axes, contributorId, runDiscover]);

  useLiveRefresh(() => runDiscover(), { runOnMount: false });

  function setAxis(key: AxisKey, value: number) {
    setAxes((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <main className="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8 py-8 space-y-10">
      <header className="space-y-2">
        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground/80">
          Tunable discovery
        </p>
        <h1 className="text-3xl font-bold tracking-tight">Discover by resonance</h1>
        <p className="text-muted-foreground leading-relaxed max-w-2xl">
          Tune how you want to explore — not what to search for. The network surfaces ideas
          that match your current mental state: curiosity, serendipity, depth, coherence,
          and freshness.
        </p>
      </header>

      <section
        className="rounded-2xl border border-border/40 bg-card/40 p-6 space-y-6"
        aria-label="Resonance controls"
      >
        {(Object.keys(AXIS_LABELS) as AxisKey[]).map((key) => (
          <div key={key} className="space-y-2">
            <div className="flex justify-between gap-4 text-sm">
              <span className="font-medium text-foreground">{AXIS_LABELS[key].title}</span>
              <span className="text-muted-foreground tabular-nums">{pct(axes[key])}%</span>
            </div>
            <input
              type="range"
              min={0}
              max={100}
              value={pct(axes[key])}
              onChange={(e) => setAxis(key, Number(e.target.value) / 100)}
              className="w-full accent-primary h-2 rounded-lg cursor-pointer"
              aria-label={AXIS_LABELS[key].title}
            />
            <div className="flex justify-between text-[11px] text-muted-foreground/90">
              <span>{AXIS_LABELS[key].low}</span>
              <span>{AXIS_LABELS[key].high}</span>
            </div>
          </div>
        ))}

        <div className="space-y-2">
          <label htmlFor="contributor-id" className="text-sm font-medium">
            Contributor ID (optional)
          </label>
          <input
            id="contributor-id"
            type="text"
            placeholder="Serendipity uses your recent idea keywords when set"
            value={contributorId}
            onChange={(e) => setContributorId(e.target.value)}
            className="w-full rounded-lg border border-border/60 bg-background px-3 py-2 text-sm"
          />
        </div>

        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => void runDiscover()}
            className="rounded-full bg-primary px-5 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 transition-opacity"
          >
            Refresh matches
          </button>
          <Link
            href="/ideas"
            className="rounded-full border border-border/60 px-5 py-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
          >
            Browse all ideas
          </Link>
        </div>
      </section>

      <section aria-live="polite">
        {status === "loading" && (
          <p className="text-sm text-muted-foreground">Finding resonant ideas…</p>
        )}
        {error && (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        )}
        {data && data.ideas.length === 0 && status === "ok" && (
          <p className="text-sm text-muted-foreground">No ideas in the portfolio yet.</p>
        )}
        {data && data.ideas.length > 0 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold">What resonates now</h2>
            <ul className="space-y-3">
              {data.ideas.map((row, idx) => (
                <li
                  key={row.idea.id}
                  className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 animate-fade-in-up"
                  style={{ animationDelay: `${idx * 0.04}s` }}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <Link
                        href={`/ideas/${encodeURIComponent(row.idea.id)}`}
                        className="text-base font-medium hover:text-primary transition-colors"
                      >
                        {row.idea.name}
                      </Link>
                      <p className="mt-1 text-xs text-muted-foreground line-clamp-2">
                        {(row.idea.description || "").slice(0, 220)}
                        {(row.idea.description || "").length > 220 ? "…" : ""}
                      </p>
                      <p className="mt-2 text-xs text-muted-foreground">
                        Resonance {(row.resonance_score * 100).toFixed(1)}% · Energy{" "}
                        {row.idea.free_energy_score != null
                          ? row.idea.free_energy_score.toFixed(1)
                          : "—"}
                      </p>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
    </main>
  );
}
