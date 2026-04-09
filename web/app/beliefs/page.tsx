import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "Beliefs",
  description:
    "Belief profiles and worldview distribution across the Coherence Network.",
};

type WorldviewAxisStat = {
  axis: string;
  avg_weight: number;
};

type BeliefROI = {
  contributors_with_profiles: number;
  contributors_total: number;
  profile_adoption_rate: number;
  top_worldview_axes: WorldviewAxisStat[];
  avg_resonance_match_rate: number;
  concept_resonances_total: number;
  spec_ref: string;
};

const AXIS_COLORS: Record<string, { bar: string; text: string; bg: string }> = {
  scientific: {
    bar: "bg-blue-500",
    text: "text-blue-300",
    bg: "from-blue-500/5 to-transparent",
  },
  spiritual: {
    bar: "bg-violet-500",
    text: "text-violet-300",
    bg: "from-violet-500/5 to-transparent",
  },
  pragmatic: {
    bar: "bg-amber-500",
    text: "text-amber-300",
    bg: "from-amber-500/5 to-transparent",
  },
  holistic: {
    bar: "bg-emerald-500",
    text: "text-emerald-300",
    bg: "from-emerald-500/5 to-transparent",
  },
  relational: {
    bar: "bg-pink-500",
    text: "text-pink-300",
    bg: "from-pink-500/5 to-transparent",
  },
  systemic: {
    bar: "bg-teal-500",
    text: "text-teal-300",
    bg: "from-teal-500/5 to-transparent",
  },
};

function getAxisColor(axis: string) {
  return (
    AXIS_COLORS[axis] ?? {
      bar: "bg-muted-foreground",
      text: "text-muted-foreground",
      bg: "from-muted/5 to-transparent",
    }
  );
}

async function loadBeliefROI(): Promise<BeliefROI | null> {
  try {
    const API = getApiBase();
    const res = await fetch(`${API}/api/beliefs/roi`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as BeliefROI;
  } catch {
    return null;
  }
}

export default async function BeliefsPage() {
  const data = await loadBeliefROI();

  const adoptionPercent = data
    ? Math.round(data.profile_adoption_rate * 100)
    : 0;
  const avgMatchPercent = data
    ? Math.round(data.avg_resonance_match_rate * 100)
    : 0;

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-5xl mx-auto space-y-8">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">
          Belief Profiles
        </h1>
        <p className="max-w-3xl text-muted-foreground leading-relaxed">
          Every contributor has a worldview expressed across six axes. These
          belief profiles power resonance matching -- connecting people to
          ideas and peers that align with how they see the world.
        </p>
        <div className="flex flex-wrap gap-2">
          <Link
            href="/discover"
            className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200"
          >
            Discover
          </Link>
          <Link
            href="/peers"
            className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200"
          >
            Peers
          </Link>
        </div>
      </header>

      {data ? (
        <>
          {/* Network stats */}
          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4">
              <p className="text-xs uppercase tracking-widest text-muted-foreground">
                Contributors with Profiles
              </p>
              <p className="mt-2 text-3xl font-light">
                {data.contributors_with_profiles}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                of {data.contributors_total} total
              </p>
            </div>
            <div className="rounded-2xl border border-emerald-500/20 bg-gradient-to-b from-emerald-500/5 to-card/30 p-4">
              <p className="text-xs uppercase tracking-widest text-emerald-400">
                Adoption Rate
              </p>
              <p className="mt-2 text-3xl font-light text-emerald-300">
                {adoptionPercent}%
              </p>
            </div>
            <div className="rounded-2xl border border-purple-500/20 bg-gradient-to-b from-purple-500/5 to-card/30 p-4">
              <p className="text-xs uppercase tracking-widest text-purple-400">
                Avg Match Rate
              </p>
              <p className="mt-2 text-3xl font-light text-purple-300">
                {avgMatchPercent}%
              </p>
            </div>
            <div className="rounded-2xl border border-amber-500/20 bg-gradient-to-b from-amber-500/5 to-card/30 p-4">
              <p className="text-xs uppercase tracking-widest text-amber-400">
                Concept Resonances
              </p>
              <p className="mt-2 text-3xl font-light text-amber-300">
                {data.concept_resonances_total}
              </p>
            </div>
          </section>

          {/* Worldview distribution */}
          <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-5">
            <div className="space-y-1">
              <h2 className="text-lg font-medium">
                Network Worldview Distribution
              </h2>
              <p className="text-sm text-muted-foreground">
                Average weight across each worldview axis for all contributors
                with belief profiles.
              </p>
            </div>

            {data.top_worldview_axes.length > 0 ? (
              <div className="space-y-4">
                {data.top_worldview_axes.map((axis) => {
                  const ac = getAxisColor(axis.axis);
                  const percent = Math.round(axis.avg_weight * 100);
                  return (
                    <div
                      key={axis.axis}
                      className={`rounded-xl border border-border/20 bg-gradient-to-br ${ac.bg} p-4 space-y-2`}
                    >
                      <div className="flex items-center justify-between">
                        <h3
                          className={`text-sm font-medium capitalize ${ac.text}`}
                        >
                          {axis.axis}
                        </h3>
                        <span className={`text-lg font-light ${ac.text}`}>
                          {percent}%
                        </span>
                      </div>
                      <div className="h-2 w-full rounded-full bg-background/40 overflow-hidden">
                        <div
                          className={`h-full rounded-full ${ac.bar} transition-all duration-700`}
                          style={{ width: `${percent}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                No worldview axes data available yet.
              </p>
            )}
          </section>

          {/* Explanation */}
          <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3">
            <h2 className="text-lg font-medium">How Belief Profiles Work</h2>
            <div className="space-y-2 text-sm text-muted-foreground">
              <p>
                Each contributor&apos;s worldview is represented across six axes:
                scientific, spiritual, pragmatic, holistic, relational, and
                systemic. These weights are normalized between 0.0 and 1.0.
              </p>
              <p>
                When combined with interest tags and concept resonances, belief
                profiles enable the network to compute structural resonance
                between contributors and ideas -- surfacing connections that
                matter.
              </p>
              <p>
                The result is a network where people discover ideas that align
                with their worldview, and peers who share their way of thinking.
              </p>
            </div>
          </section>
        </>
      ) : (
        <section className="rounded-2xl border border-dashed border-border/30 bg-background/30 p-8 text-center space-y-3">
          <p className="text-muted-foreground">
            Belief profile data is not available yet. Profiles will appear as
            contributors set their worldview preferences.
          </p>
          <div className="flex flex-wrap justify-center gap-4 text-sm">
            <Link href="/discover" className="text-purple-400 hover:underline">
              Discover
            </Link>
            <Link href="/peers" className="text-emerald-400 hover:underline">
              Peers
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
          <Link href="/discover" className="text-purple-400 hover:underline">
            Discover
          </Link>
          <Link href="/peers" className="text-emerald-400 hover:underline">
            Peers
          </Link>
          <Link href="/resonance" className="text-blue-400 hover:underline">
            Resonance
          </Link>
          <Link href="/vitality" className="text-amber-400 hover:underline">
            Vitality
          </Link>
        </div>
      </nav>
    </main>
  );
}
