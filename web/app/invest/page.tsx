import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";
import { humanizeManifestationStatus } from "@/lib/humanize";
import { InvestBalanceSection } from "./InvestBalanceSection";

export const metadata: Metadata = {
  title: "Tend the Garden",
  description: "Nurture ideas you believe in. Your attention becomes someone else's growing code.",
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

function computeRoi(idea: IdeaWithScore): number {
  const cost = idea.estimated_cost > 0 ? idea.estimated_cost : 1;
  return idea.value_gap / cost;
}

/** Maps a growth ratio to a garden stage 0–4 */
function growthStage(roi: number): 0 | 1 | 2 | 3 | 4 {
  if (roi >= 15) return 4;
  if (roi >= 7) return 3;
  if (roi >= 3) return 2;
  if (roi >= 1) return 1;
  return 0;
}

const STAGES: { icon: string; label: string }[] = [
  { icon: "🌱", label: "Seed" },
  { icon: "🪴", label: "Sprout" },
  { icon: "🌿", label: "Sapling" },
  { icon: "🌳", label: "Tree" },
  { icon: "🌲", label: "Ancient" },
];

function GrowthProgression({ stage }: { stage: 0 | 1 | 2 | 3 | 4 }) {
  return (
    <div className="flex items-end gap-1" aria-label={`Growth stage: ${STAGES[stage].label}`}>
      {STAGES.map((s, i) => {
        const isActive = i === stage;
        const isPast = i < stage;
        return (
          <div
            key={s.label}
            title={s.label}
            className={[
              "flex flex-col items-center gap-0.5 transition-all duration-300",
              isActive ? "opacity-100 scale-110" : isPast ? "opacity-50" : "opacity-20",
            ].join(" ")}
          >
            <span
              className={[
                "transition-all",
                isActive ? "text-xl" : "text-sm",
              ].join(" ")}
            >
              {s.icon}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function gardenStageLabel(roi: number): string {
  const s = growthStage(roi);
  return STAGES[s].label;
}

function nurtureSentence(estimatedCost: number): string {
  if (estimatedCost <= 0) return "Staking this idea triggers new compute tasks";
  const tasks = Math.max(1, Math.round(10 / Math.max(estimatedCost, 0.01)));
  return `10 CC plants ~${tasks} new task${tasks > 1 ? "s" : ""} into the ground`;
}

function formatCC(value: number): string {
  return `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(
    Number.isFinite(value) ? value : 0
  )} CC`;
}

function proofStageLabel(status: string): { icon: string; label: string } {
  const s = status.trim().toLowerCase();
  if (s === "validated") return { icon: "🍎", label: "Bearing fruit" };
  if (s === "partial") return { icon: "🌸", label: "First blooms" };
  return { icon: "🌱", label: "Still sprouting" };
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

export default async function InvestPage() {
  const ideas = await loadIdeas();

  const sorted = [...ideas].sort((a, b) => computeRoi(b) - computeRoi(a));

  return (
    <main className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <header>
        <h1 className="text-3xl font-bold tracking-tight mb-2">
          Tend the Garden
        </h1>
        <p className="text-muted-foreground max-w-2xl leading-relaxed">
          Every idea here is a living seed. Stake CC to water it — real compute runs, specs
          are written, and code grows. Your attention becomes someone else&apos;s flourishing work.
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
            const stage = growthStage(roi);
            const proof = proofStageLabel(idea.manifestation_status);

            return (
              <div
                key={idea.id}
                className="hover-lift rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 md:p-6 space-y-4"
              >
                {/* Title row */}
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
                        {proof.icon} {proof.label}
                      </span>
                      <span className="text-xs text-muted-foreground/60">
                        {humanizeManifestationStatus(idea.manifestation_status)}
                      </span>
                    </div>
                  </div>
                  <Link
                    href={`/ideas/${encodeURIComponent(idea.id)}`}
                    className="shrink-0 rounded-full bg-primary/10 px-4 py-1.5 text-sm font-medium text-primary transition-colors hover:bg-primary/20"
                  >
                    Water it
                  </Link>
                </div>

                {/* Growth progression visual — the centrepiece */}
                <div className="flex items-center gap-4">
                  <GrowthProgression stage={stage} />
                  <div>
                    <p className="text-sm font-medium text-foreground">
                      {gardenStageLabel(roi)} — {roi.toFixed(1)}× growth potential
                    </p>
                    <p className="text-xs text-muted-foreground/70 mt-0.5">
                      How far this idea can still grow relative to what it needs
                    </p>
                  </div>
                </div>

                {/* Numbers — accessible but secondary */}
                <details className="group">
                  <summary className="cursor-pointer text-xs text-muted-foreground/60 hover:text-muted-foreground transition-colors list-none flex items-center gap-1">
                    <span className="group-open:hidden">▶ Show details</span>
                    <span className="hidden group-open:inline">▼ Hide details</span>
                  </summary>
                  <div className="mt-3 grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm pl-1 border-l-2 border-border/20">
                    <div>
                      <p className="text-xs text-muted-foreground/70">Room to grow</p>
                      <p className="font-medium">{formatCC(idea.value_gap)}</p>
                      <p className="text-xs text-muted-foreground/50">unrealised potential</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground/70">Care needed</p>
                      <p className="text-muted-foreground">{formatCC(idea.estimated_cost)}</p>
                      <p className="text-xs text-muted-foreground/50">estimated nurture cost</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground/70">Growth ratio</p>
                      <p className="font-medium text-primary">{roi.toFixed(1)}×</p>
                      <p className="text-xs text-muted-foreground/50">room ÷ cost</p>
                    </div>
                  </div>
                </details>

                {/* Stake hint */}
                <p className="text-xs text-muted-foreground/60">
                  {nurtureSentence(idea.estimated_cost)}
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
