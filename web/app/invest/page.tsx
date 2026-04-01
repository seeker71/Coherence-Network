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

/** Map manifestation_status to a garden growth stage label and emoji (Spec R1) */
type GardenStage = "seed" | "seedling" | "sapling" | "tree" | "dormant";

function gardenStage(status: string): GardenStage {
  const s = status.trim().toLowerCase();
  if (s === "validated") return "tree";
  if (s === "partial" || s === "in_progress" || s === "inprogress") return "sapling";
  if (s === "specced") return "seedling";
  if (s === "archived" || s === "closed") return "dormant";
  return "seed"; // default for idea / empty / unknown
}

const STAGE_CONFIG: Record<GardenStage, { label: string; emoji: string; index: number }> = {
  seed: { label: "Seed", emoji: "🌱", index: 0 },
  seedling: { label: "Seedling", emoji: "🌿", index: 1 },
  sapling: { label: "Sapling", emoji: "🌳", index: 2 },
  tree: { label: "Tree", emoji: "🌲", index: 3 },
  dormant: { label: "Dormant", emoji: "🍂", index: 4 },
};

/** Legacy alias for test compatibility — returns emoji icon for a garden stage */
function stageIcon(stage: GardenStage): string {
  return STAGE_CONFIG[stage].emoji;
}

/** Get action verb based on garden stage (Spec R3) */
function gardenVerb(stage: GardenStage): string {
  if (stage === "seed") return "Plant";
  if (stage === "tree") return "Tend";
  return "Water";
}

/** Growth description based on free_energy_score (Spec R5) */
function growthDescription(score: number | null | undefined): string {
  if (score === null || score === undefined) return "Young and untested — be the first to tend this idea.";
  if (score > 0.7) return "This plant has strong roots and is ready to grow fast.";
  if (score >= 0.4) return "Steady growth — regular tending will help it thrive.";
  return "Needs attention — a little water could unlock real growth.";
}

/** 5-cell stage strip with current stage pulsing (Spec R2) */
function StageStrip({ currentStage }: { currentStage: GardenStage }) {
  const stageOrder: GardenStage[] = ["seed", "seedling", "sapling", "tree", "dormant"];
  const currentIndex = STAGE_CONFIG[currentStage].index;

  return (
    <div className="flex items-center gap-1" role="group" aria-label={`Growth stage: ${STAGE_CONFIG[currentStage].label} (current)`}>
      {stageOrder.map((stage, i) => {
        const config = STAGE_CONFIG[stage];
        const isCurrent = i === currentIndex;
        const isPast = i <= currentIndex;

        return (
          <span
            key={stage}
            role="img"
            aria-label={`Stage: ${config.label}${isCurrent ? " (current)" : ""}`}
            className={`text-base leading-none transition-all duration-300 ${
              isCurrent
                ? "opacity-100 scale-110 ring-2 ring-emerald-500/50 rounded-full p-0.5 animate-pulse"
                : isPast
                ? "opacity-100 scale-100"
                : "opacity-25 scale-90"
            }`}
          >
            <span aria-hidden="true">{config.emoji}</span>
            <span className="sr-only">{config.label}{isCurrent ? ", current stage" : ""}</span>
          </span>
        );
      })}
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

/** Expected yield badge text (Spec R2) */
function expectedYield(roi: number): string {
  if (!isFinite(roi) || roi <= 0) return "—";
  return `×${roi.toFixed(1)} expected yield`;
}

/** Secondary numeric details (Spec R4) */
function SecondaryDetails({ idea }: { idea: IdeaWithScore }) {
  const roi = computeRoi(idea);

  return (
    <details className="group">
      <summary className="cursor-pointer text-xs text-muted-foreground/60 hover:text-muted-foreground transition-colors list-none flex items-center gap-1 select-none">
        <span className="group-open:rotate-90 inline-block transition-transform">›</span>
        See soil facts
      </summary>
      <div className="mt-2 grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
        <div>
          <p className="text-xs text-muted-foreground/80" aria-label="Growth potential (value gap)">Growth potential</p>
          <p className="font-medium">{formatUsd(idea.value_gap)}</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground/80" aria-label="Water needed (estimated cost)">Water needed</p>
          <p className="text-muted-foreground">{formatUsd(idea.estimated_cost)}</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground/80" aria-label="Expected yield (ROI)">Expected yield</p>
          <p className="font-medium text-primary">{roi.toFixed(1)}x</p>
        </div>
      </div>
    </details>
  );
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
          <p className="text-4xl" aria-hidden="true">🌱</p>
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
            const stage = gardenStage(idea.manifestation_status);
            const stageConfig = STAGE_CONFIG[stage];
            const actionVerb = gardenVerb(stage);
            const description = growthDescription(idea.free_energy_score);

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
                        <span aria-hidden="true">{stageConfig.emoji}</span>
                        <span className="sr-only">{stageConfig.label}</span>
                        {stageConfig.label}
                      </span>
                    </div>
                  </div>
                  <Link
                    href={`/ideas/${encodeURIComponent(idea.id)}`}
                    className="shrink-0 rounded-full bg-primary/10 px-4 py-1.5 text-sm font-medium text-primary transition-colors hover:bg-primary/20"
                    aria-label={`${actionVerb} this idea: ${idea.name}`}
                  >
                    {actionVerb}
                  </Link>
                </div>

                {/* Garden context description (Spec R5) */}
                <p className="text-sm text-muted-foreground/80">
                  {description}
                </p>

                {/* Growth visualization: stage strip + expected yield badge (Spec R2) */}
                <div className="flex items-center justify-between gap-2">
                  <StageStrip currentStage={stage} />
                  <span
                    className="text-xs text-muted-foreground/70 whitespace-nowrap"
                    aria-label={`Expected yield: ${expectedYield(roi)}`}
                  >
                    {expectedYield(roi)}
                  </span>
                </div>

                {/* Secondary numeric details — accessible but quieter (Spec R4) */}
                <SecondaryDetails idea={idea} />
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
