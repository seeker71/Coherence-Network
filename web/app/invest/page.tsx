import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";
import { formatUsd, humanizeManifestationStatus } from "@/lib/humanize";
import { InvestBalanceSection } from "./InvestBalanceSection";

export const metadata: Metadata = {
  title: "Invest",
  description: "Direct compute toward ideas you believe in.",
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

function stageIcon(status: string): string {
  const s = status.trim().toLowerCase();
  if (s === "validated") return "\u2705";
  if (s === "partial") return "\uD83D\uDD28";
  return "\uD83D\uDCCB";
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

function roiBarWidth(roi: number): number {
  // Cap the visual at 20x for display purposes
  return Math.min((roi / 20) * 100, 100);
}

function stakeDescription(cost: number): string {
  if (cost <= 0) return "Stake triggers compute tasks";
  const tasks = Math.max(1, Math.round(10 / Math.max(cost, 0.01)));
  return `10 CC = ~${tasks} spec task${tasks > 1 ? "s" : ""} created`;
}

export default async function InvestPage() {
  const ideas = await loadIdeas();

  const sorted = [...ideas].sort((a, b) => computeRoi(b) - computeRoi(a));

  return (
    <main className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <header>
        <h1 className="text-3xl font-bold tracking-tight mb-2">
          Invest
        </h1>
        <p className="text-muted-foreground max-w-2xl leading-relaxed">
          When you invest in an idea, real compute runs against it. Your attention
          becomes someone else&apos;s working code.
        </p>
      </header>

      <InvestBalanceSection />

      {sorted.length === 0 ? (
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-8 text-center space-y-3">
          <p className="text-lg text-muted-foreground">
            No ideas yet. Be the first to share one.
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
            return (
              <div
                key={idea.id}
                className="hover-lift rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 md:p-6 space-y-3"
              >
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
                        {stageIcon(idea.manifestation_status)} {humanizeManifestationStatus(idea.manifestation_status)}
                      </span>
                    </div>
                  </div>
                  <Link
                    href={`/ideas/${encodeURIComponent(idea.id)}`}
                    className="shrink-0 rounded-full bg-primary/10 px-4 py-1.5 text-sm font-medium text-primary transition-colors hover:bg-primary/20"
                  >
                    Stake
                  </Link>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
                  <div>
                    <p className="text-xs text-muted-foreground/80">Value gap</p>
                    <p className="font-medium">{formatUsd(idea.value_gap)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground/80">Est. cost</p>
                    <p className="text-muted-foreground">{formatUsd(idea.estimated_cost)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground/80">ROI</p>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-1.5 rounded-full bg-muted/40 overflow-hidden max-w-[80px]">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-primary/40 to-primary/80"
                          style={{ width: `${roiBarWidth(roi)}%` }}
                        />
                      </div>
                      <span className="font-medium text-primary">{roi.toFixed(1)}x</span>
                    </div>
                  </div>
                </div>

                <p className="text-xs text-muted-foreground/80">
                  {stakeDescription(idea.estimated_cost)}
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
