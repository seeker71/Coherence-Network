import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";
import { formatUsd, humanizeManifestationStatus } from "@/lib/humanize";
import { InvestBalanceSection } from "./InvestBalanceSection";

export const metadata: Metadata = {
  title: "Invest",
  description: "Nurture ideas you believe in. Your attention becomes someone's working code.",
};

export const revalidate = 90;

type IdeaWithScore = {
  id: string;
  name: string;
  description: string;
  potential_value: number;
  actual_value: number;
  estimated_cost: number;
  actual_cost: number;
  confidence: number;
  manifestation_status: string;
  free_energy_score: number;
  value_gap: number;
};

type IdeaPortfolioResponse = {
  ideas: IdeaWithScore[];
};

/** Map manifestation_status to a garden growth stage label and emoji */
function growthStage(status: string): { label: string; emoji: string; stage: number } {
  const s = status.trim().toLowerCase();
  if (s === "validated") return { label: "Blooming", emoji: "🌸", stage: 4 };
  if (s === "partial") return { label: "Sprouting", emoji: "🌱", stage: 2 };
  if (s === "in_progress" || s === "inprogress") return { label: "Growing", emoji: "🌿", stage: 3 };
  return { label: "Seed", emoji: "🫘", stage: 1 };
}

/** Sprout-to-tree visual: 5 stages rendered as inline SVG plant icons */
function GrowthBar({ roi }: { roi: number }) {
  // Map roi (0–20+) to a 1–5 growth stage
  const stage = Math.min(5, Math.max(1, Math.ceil((roi / 20) * 5)));
  const stages = [
    { label: "🫘", title: "Seed" },
    { label: "🌱", title: "Sprout" },
    { label: "🌿", title: "Sapling" },
    { label: "🌳", title: "Tree" },
    { label: "🌲", title: "Forest" },
  ];

  return (
    <div className="flex items-center gap-1" title={`Growth stage ${stage}/5`} aria-label={`Growth potential: stage ${stage} of 5`}>
      {stages.map((s, i) => (
        <span
          key={s.title}
          className={`text-base leading-none transition-all duration-300 ${
            i < stage ? "opacity-100 scale-100" : "opacity-20 scale-90"
          }`}
          title={s.title}
        >
          {s.label}
        </span>
      ))}
    </div>
  );
}

async function loadIdeas(): Promise<IdeaWithScore[]> {
  try {
    const API = getApiBase();
    const res = await fetch(`${API}/api/ideas?limit=60`, { cache: "no-store" });
    if (!res.ok) return [];
    const data: IdeaPortfolioResponse = await res.json();
    return data.ideas ?? [];
  } catch {
    return [];
  }
}

function computeRoi(idea: IdeaWithScore): number {
  const cost = idea.estimated_cost > 0 ? idea.estimated_cost : 1;
  return idea.value_gap / cost;
}

/** How many compute tasks a nurture action spawns */
function nurtureDescription(cost: number): string {
  if (cost <= 0) return "Nurturing this idea triggers compute tasks";
  const tasks = Math.max(1, Math.round(10 / Math.max(cost, 0.01)));
  return `10 CC of care → ~${tasks} spec task${tasks > 1 ? "s" : ""} sprouted`;
}

/** Secondary numeric details hidden behind a softer label */
function growthPotentialLabel(valueGap: number): string {
  if (valueGap <= 0) return "Untapped";
  if (valueGap < 500) return "Budding";
  if (valueGap < 2000) return "Promising";
  if (valueGap < 5000) return "Abundant";
  return "Exceptional";
}

export default async function InvestPage() {
  const ideas = await loadIdeas();

  const sorted = [...ideas].sort((a, b) => computeRoi(b) - computeRoi(a));

  return (
    <main className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <header>
        <h1 className="text-3xl font-bold tracking-tight mb-2">
          Garden of Ideas
        </h1>
        <p className="text-muted-foreground max-w-2xl leading-relaxed">
          Every idea you nurture grows into real code. Your attention is water —
          direct it toward the seeds you believe in most.
        </p>
      </header>

      <InvestBalanceSection />

      {sorted.length === 0 ? (
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-8 text-center space-y-3">
          <p className="text-4xl">🌱</p>
          <p className="text-lg text-muted-foreground">
            The garden is empty. Plant the first seed.
          </p>
          <Link
            href="/"
            className="inline-block text-primary hover:text-foreground transition-colors underline underline-offset-4"
          >
            Share an idea &rarr;
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {sorted.map((idea) => {
            const roi = computeRoi(idea);
            const { label: stageLabel, emoji: stageEmoji } = growthStage(idea.manifestation_status);
            const potentialLabel = growthPotentialLabel(idea.value_gap);

            return (
              <div
                key={idea.id}
                className="hover-lift rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 md:p-6 space-y-3"
              >
                {/* Header row */}
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <Link
                      href={`/ideas/${encodeURIComponent(idea.id)}`}
                      className="text-lg font-medium hover:text-primary transition-colors duration-300"
                    >
                      {idea.name}
                    </Link>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs rounded-full border border-border/40 px-2.5 py-0.5 bg-muted/30 text-muted-foreground">
                        {stageEmoji} {stageLabel}
                      </span>
                    </div>
                  </div>
                  <Link
                    href={`/ideas/${encodeURIComponent(idea.id)}`}
                    className="shrink-0 rounded-full bg-primary/10 px-4 py-1.5 text-sm font-medium text-primary transition-colors hover:bg-primary/20"
                  >
                    Nurture
                  </Link>
                </div>

                {/* Growth visualization */}
                <div className="space-y-1">
                  <GrowthBar roi={roi} />
                  <p className="text-xs text-muted-foreground/70">
                    Growth potential: <span className="font-medium text-foreground/80">{potentialLabel}</span>
                  </p>
                </div>

                {/* Secondary numeric details — accessible but quieter */}
                <details className="group">
                  <summary className="cursor-pointer text-xs text-muted-foreground/60 hover:text-muted-foreground transition-colors list-none flex items-center gap-1 select-none">
                    <span className="group-open:rotate-90 inline-block transition-transform">›</span>
                    Show metrics
                  </summary>
                  <div className="mt-2 grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
                    <div>
                      <p className="text-xs text-muted-foreground/80">Growth potential</p>
                      <p className="font-medium">{formatUsd(idea.value_gap)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground/80">Nutrients needed</p>
                      <p className="text-muted-foreground">{formatUsd(idea.estimated_cost)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground/80">Bloom rate</p>
                      <p className="font-medium text-primary">{roi.toFixed(1)}x</p>
                    </div>
                  </div>
                </details>

                <p className="text-xs text-muted-foreground/80">
                  {nurtureDescription(idea.estimated_cost)}
                </p>
              </div>
            );
          })}
        </div>
      )}

      {/* Where to go next */}
      <nav className="py-8 text-center space-y-2 border-t border-border/20" aria-label="Where to go next">
        <p className="text-xs text-muted-foreground/80 uppercase tracking-wider">Where to go next</p>
        <div className="flex flex-wrap justify-center gap-4 text-sm">
          <Link href="/ideas" className="text-amber-600 dark:text-amber-400 hover:underline">All ideas</Link>
          <Link href="/contribute" className="text-amber-600 dark:text-amber-400 hover:underline">Contribute</Link>
          <Link href="/resonance" className="text-amber-600 dark:text-amber-400 hover:underline">Resonance</Link>
        </div>
      </nav>
    </main>
  );
}
