import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "Portfolio Breath",
  description:
    "Gas/water/ice phase distribution for all super-ideas — see where energy is flowing.",
};

export const revalidate = 120;

type IdeaBreath = {
  idea_id: string;
  name: string;
  rhythm: { gas: number; water: number; ice: number };
  breath_health: number;
  state: string;
  total_specs: number;
};

type BreathOverview = {
  ideas: IdeaBreath[];
  portfolio_rhythm: { gas: number; water: number; ice: number };
  portfolio_breath_health: number;
};

async function loadBreathOverview(): Promise<BreathOverview | null> {
  try {
    const API = getApiBase();
    const res = await fetch(`${API}/api/ideas/breath-overview`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

function stateLabel(state: string): string {
  const map: Record<string, string> = {
    breathing: "Breathing",
    inhaling: "Inhaling",
    exhaling: "Exhaling",
    holding: "Holding",
  };
  return map[state] ?? state;
}

function stateColor(state: string): string {
  const map: Record<string, string> = {
    breathing: "text-emerald-600 dark:text-emerald-400",
    inhaling: "text-sky-600 dark:text-sky-400",
    exhaling: "text-blue-600 dark:text-blue-400",
    holding: "text-amber-600 dark:text-amber-400",
  };
  return map[state] ?? "text-muted-foreground";
}

function PhaseBar({ rhythm }: { rhythm: { gas: number; water: number; ice: number } }) {
  const gasW = Math.max(rhythm.gas * 100, 0);
  const waterW = Math.max(rhythm.water * 100, 0);
  const iceW = Math.max(rhythm.ice * 100, 0);
  return (
    <div className="flex h-3 w-full rounded overflow-hidden bg-muted/30">
      {gasW > 0 && (
        <div
          className="bg-amber-400 dark:bg-amber-500"
          style={{ width: `${gasW}%` }}
          title={`Gas ${gasW.toFixed(0)}%`}
        />
      )}
      {waterW > 0 && (
        <div
          className="bg-sky-400 dark:bg-sky-500"
          style={{ width: `${waterW}%` }}
          title={`Water ${waterW.toFixed(0)}%`}
        />
      )}
      {iceW > 0 && (
        <div
          className="bg-blue-300 dark:bg-blue-400"
          style={{ width: `${iceW}%` }}
          title={`Ice ${iceW.toFixed(0)}%`}
        />
      )}
    </div>
  );
}

export default async function BreathOverviewPage() {
  const data = await loadBreathOverview();

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-5xl mx-auto space-y-8">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Portfolio Breath</h1>
        <p className="text-muted-foreground max-w-2xl">
          Every idea breathes through three phases: gas (exploration), water
          (flowing implementation), and ice (crystallized value). A healthy
          portfolio has all three.
        </p>
      </div>

      {!data ? (
        <p className="py-12 text-center text-muted-foreground">
          Breath overview unavailable. The API may be loading.
        </p>
      ) : (
        <>
          {/* Portfolio summary */}
          <section className="rounded-lg border border-border/40 p-5 space-y-3">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Portfolio Rhythm
            </h2>
            <PhaseBar rhythm={data.portfolio_rhythm} />
            <div className="flex gap-6 text-xs text-muted-foreground">
              <span>
                <span className="inline-block w-2 h-2 rounded-full bg-amber-400 mr-1" />
                Gas {(data.portfolio_rhythm.gas * 100).toFixed(0)}%
              </span>
              <span>
                <span className="inline-block w-2 h-2 rounded-full bg-sky-400 mr-1" />
                Water {(data.portfolio_rhythm.water * 100).toFixed(0)}%
              </span>
              <span>
                <span className="inline-block w-2 h-2 rounded-full bg-blue-300 mr-1" />
                Ice {(data.portfolio_rhythm.ice * 100).toFixed(0)}%
              </span>
            </div>
            <p className="text-sm text-muted-foreground">
              Breath health:{" "}
              <span className="font-mono tabular-nums">
                {(data.portfolio_breath_health * 100).toFixed(0)}%
              </span>
            </p>
          </section>

          {/* Per-idea cards */}
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {data.ideas.map((idea) => (
              <Link
                key={idea.idea_id}
                href={`/ideas/${encodeURIComponent(idea.idea_id)}`}
                className="block rounded-lg border border-border/40 p-4 hover:border-amber-500/40 transition-colors space-y-2"
              >
                <h3 className="font-semibold text-sm leading-tight truncate">
                  {idea.name}
                </h3>
                <PhaseBar rhythm={idea.rhythm} />
                <div className="flex items-center justify-between text-xs">
                  <span className={stateColor(idea.state)}>
                    {stateLabel(idea.state)}
                  </span>
                  <span className="text-muted-foreground tabular-nums">
                    {idea.total_specs} specs
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">
                  Health:{" "}
                  <span className="font-mono tabular-nums">
                    {(idea.breath_health * 100).toFixed(0)}%
                  </span>
                </p>
              </Link>
            ))}
          </section>
        </>
      )}

      <nav
        className="pt-8 text-center border-t border-border/20"
        aria-label="Navigation"
      >
        <div className="flex flex-wrap justify-center gap-4 text-sm">
          <Link
            href="/ideas"
            className="text-amber-600 dark:text-amber-400 hover:underline"
          >
            All Ideas
          </Link>
          <Link
            href="/"
            className="text-amber-600 dark:text-amber-400 hover:underline"
          >
            Home
          </Link>
        </div>
      </nav>
    </main>
  );
}
