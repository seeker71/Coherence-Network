import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "Coherence Score",
  description:
    "Real-time coherence score dashboard with signal breakdown and contributing factors.",
};

type SignalDetail = {
  score: number;
  weight: number;
  details: Record<string, unknown>;
};

type CoherenceScoreResponse = {
  score: number;
  signals: Record<string, SignalDetail>;
  signals_with_data: number;
  total_signals: number;
  computed_at: string;
};

const SIGNAL_COLORS: Record<string, { bar: string; text: string; bg: string }> = {
  task_completion: {
    bar: "bg-blue-500",
    text: "text-blue-300",
    bg: "from-blue-500/5 to-transparent",
  },
  spec_coverage: {
    bar: "bg-purple-500",
    text: "text-purple-300",
    bg: "from-purple-500/5 to-transparent",
  },
  contribution_activity: {
    bar: "bg-emerald-500",
    text: "text-emerald-300",
    bg: "from-emerald-500/5 to-transparent",
  },
  runtime_health: {
    bar: "bg-amber-500",
    text: "text-amber-300",
    bg: "from-amber-500/5 to-transparent",
  },
  value_realization: {
    bar: "bg-rose-500",
    text: "text-rose-300",
    bg: "from-rose-500/5 to-transparent",
  },
};

function getSignalColor(name: string) {
  return (
    SIGNAL_COLORS[name] ?? {
      bar: "bg-teal-500",
      text: "text-teal-300",
      bg: "from-teal-500/5 to-transparent",
    }
  );
}

function scoreColor(score: number): {
  text: string;
  bg: string;
  border: string;
  glow: string;
} {
  if (score >= 0.7) {
    return {
      text: "text-emerald-400",
      bg: "from-emerald-500/10 to-emerald-500/5",
      border: "border-emerald-500/30",
      glow: "shadow-emerald-500/20",
    };
  }
  if (score >= 0.4) {
    return {
      text: "text-amber-400",
      bg: "from-amber-500/10 to-amber-500/5",
      border: "border-amber-500/30",
      glow: "shadow-amber-500/20",
    };
  }
  return {
    text: "text-red-400",
    bg: "from-red-500/10 to-red-500/5",
    border: "border-red-500/30",
    glow: "shadow-red-500/20",
  };
}

function humanizeSignalName(name: string): string {
  return name
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

async function loadCoherence(): Promise<CoherenceScoreResponse | null> {
  try {
    const API = getApiBase();
    const res = await fetch(`${API}/api/coherence/score`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as CoherenceScoreResponse;
  } catch {
    return null;
  }
}

export default async function CoherencePage() {
  const data = await loadCoherence();

  const score = data?.score ?? 0;
  const scorePercent = Math.round(score * 100);
  const color = scoreColor(score);
  const signalEntries = data
    ? Object.entries(data.signals).sort(
        ([, a], [, b]) => b.weight - a.weight,
      )
    : [];

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-5xl mx-auto space-y-8">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">
          Coherence Score
        </h1>
        <p className="max-w-3xl text-muted-foreground leading-relaxed">
          The aggregate coherence score measures how well the network is
          functioning across task completion, spec coverage, contributions,
          runtime health, and value realization.
        </p>
      </header>

      {data ? (
        <>
          {/* Big score display */}
          <section
            className={`rounded-3xl border ${color.border} bg-gradient-to-b ${color.bg} p-8 text-center space-y-4 shadow-lg ${color.glow}`}
          >
            <p className="text-xs uppercase tracking-widest text-muted-foreground">
              Coherence Score
            </p>
            <p className={`text-7xl font-extralight ${color.text}`}>
              {score.toFixed(2)}
            </p>
            <p className="text-sm text-muted-foreground">
              {scorePercent}% coherent across {data.total_signals} signals (
              {data.signals_with_data} with real data)
            </p>
            <p className="text-xs text-muted-foreground">
              Computed at {data.computed_at}
            </p>
          </section>

          {/* Signal breakdown */}
          <section className="space-y-4">
            <h2 className="text-lg font-medium">Signal Breakdown</h2>
            <p className="text-sm text-muted-foreground">
              Each signal contributes to the overall coherence score with its
              own weight and measured value.
            </p>
            <div className="grid gap-4 sm:grid-cols-2">
              {signalEntries.map(([name, signal]) => {
                const sc = getSignalColor(name);
                const percent = Math.round(signal.score * 100);
                const weightPercent = Math.round(signal.weight * 100);
                return (
                  <div
                    key={name}
                    className={`rounded-2xl border border-border/30 bg-gradient-to-br ${sc.bg} p-5 space-y-3`}
                  >
                    <div className="flex items-center justify-between">
                      <h3 className={`text-sm font-medium ${sc.text}`}>
                        {humanizeSignalName(name)}
                      </h3>
                      <span className={`text-2xl font-light ${sc.text}`}>
                        {percent}%
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Weight: {weightPercent}%
                    </p>
                    <div className="h-2 w-full rounded-full bg-background/40 overflow-hidden">
                      <div
                        className={`h-full rounded-full ${sc.bar} transition-all duration-700`}
                        style={{ width: `${percent}%` }}
                      />
                    </div>
                    {Object.keys(signal.details).length > 0 ? (
                      <div className="space-y-0.5 text-xs text-muted-foreground">
                        {Object.entries(signal.details)
                          .slice(0, 4)
                          .map(([key, val]) => (
                            <p key={key}>
                              {key.replace(/_/g, " ")}:{" "}
                              <span className="text-foreground">
                                {typeof val === "number"
                                  ? val.toFixed(2)
                                  : String(val)}
                              </span>
                            </p>
                          ))}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </section>

          {/* Contributing factors */}
          <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3">
            <h2 className="text-lg font-medium">Contributing Factors</h2>
            <div className="space-y-2 text-sm text-muted-foreground">
              <p>
                The coherence score is computed from real system data -- not
                estimates. Each signal pulls from actual task completion rates,
                spec registry coverage, contribution ledger activity, runtime
                health checks, and value gap measurements.
              </p>
              <p>
                Signals without real data fall back to a neutral 0.5, so the
                score improves as more data flows through the system.
              </p>
            </div>
          </section>
        </>
      ) : (
        <section className="rounded-2xl border border-dashed border-border/30 bg-background/30 p-8 text-center space-y-3">
          <p className="text-muted-foreground">
            Coherence score data is not available yet. The score will appear once
            system signals are being computed.
          </p>
          <div className="flex flex-wrap justify-center gap-4 text-sm">
            <Link href="/vitality" className="text-emerald-400 hover:underline">
              Vitality
            </Link>
            <Link href="/specs" className="text-purple-400 hover:underline">
              Specs
            </Link>
          </div>
        </section>
      )}

      {/* Navigation */}
      <nav
        className="py-8 text-center space-y-2 border-t border-border/20"
        aria-label="Related pages"
      >
        <p className="text-xs text-muted-foreground/80 uppercase tracking-wider">
          Explore more
        </p>
        <div className="flex flex-wrap justify-center gap-4 text-sm">
          <Link href="/vitality" className="text-emerald-400 hover:underline">
            Vitality
          </Link>
          <Link href="/cc" className="text-amber-400 hover:underline">
            CC Economics
          </Link>
          <Link href="/specs" className="text-purple-400 hover:underline">
            Specs
          </Link>
          <Link href="/activity" className="text-blue-400 hover:underline">
            Activity
          </Link>
        </div>
      </nav>
    </main>
  );
}
