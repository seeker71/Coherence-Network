import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";
import {
  formatConfidence,
  formatUsd,
  humanizeManifestationStatus,
} from "@/lib/humanize";

export const metadata: Metadata = {
  title: "Ideas",
  description: "Browse ideas in plain language and choose what looks most worth moving next.",
};

type IdeaQuestion = {
  question: string;
  value_to_whole: number;
  estimated_cost: number;
  answer?: string | null;
  measured_delta?: number | null;
};

type IdeaWithScore = {
  id: string;
  name: string;
  description: string;
  potential_value: number;
  actual_value: number;
  estimated_cost: number;
  actual_cost: number;
  confidence: number;
  resistance_risk: number;
  manifestation_status: string;
  interfaces: string[];
  open_questions: IdeaQuestion[];
  free_energy_score: number;
  value_gap: number;
};

type IdeasResponse = {
  ideas: IdeaWithScore[];
  summary: {
    total_ideas: number;
    unvalidated_ideas: number;
    validated_ideas: number;
    total_potential_value: number;
    total_actual_value: number;
    total_value_gap: number;
  };
};

async function loadIdeas(): Promise<IdeasResponse> {
  const API = getApiBase();
  const res = await fetch(`${API}/api/ideas`, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as IdeasResponse;
}

function stageIndicator(status: string): string {
  const s = status.trim().toLowerCase();
  if (s === "validated") return "\u2705";
  if (s === "partial") return "\uD83D\uDD28";
  return "\uD83D\uDCCB";
}

function whatItNeeds(idea: IdeaWithScore): string {
  const s = idea.manifestation_status.trim().toLowerCase();
  if (s === "validated") return "Proven — ready to scale";
  if (s === "partial") return "Needs more validation";
  if (idea.open_questions && idea.open_questions.some((q) => !q.answer)) return "Has open questions";
  return "Needs a spec";
}

export default async function IdeasPage() {
  const data = await loadIdeas();

  const ideas = [...data.ideas].sort((a, b) => b.free_energy_score - a.free_energy_score);

  return (
    <main className="min-h-screen px-4 md:px-8 py-8 max-w-5xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl md:text-4xl font-light tracking-tight mb-2">
          Ideas
        </h1>
        <p className="text-muted-foreground max-w-2xl leading-relaxed">
          Ideas are living things. They start as a thought, attract attention,
          grow through collaboration, and create real value.
        </p>
      </div>

      <section className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
          <p className="text-sm text-muted-foreground">Total ideas</p>
          <p className="text-2xl font-light text-primary">{data.summary.total_ideas}</p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
          <p className="text-sm text-muted-foreground">Value created</p>
          <p className="text-2xl font-light text-primary">{formatUsd(data.summary.total_actual_value)}</p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
          <p className="text-sm text-muted-foreground">Remaining opportunity</p>
          <p className="text-2xl font-light text-primary">{formatUsd(data.summary.total_value_gap)}</p>
        </div>
      </section>

      <section className="space-y-4">
        <div className="space-y-3">
          {ideas.map((idea, index) => {
            const valueGapPct = idea.potential_value > 0
              ? Math.min(((idea.potential_value - idea.actual_value) / idea.potential_value) * 100, 100)
              : 0;
            return (
              <article
                key={idea.id}
                className="hover-lift rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 md:p-6 space-y-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <Link
                    href={`/ideas/${encodeURIComponent(idea.id)}`}
                    className="text-lg font-medium hover:text-primary transition-colors duration-300"
                  >
                    {index + 1}. {idea.name}
                  </Link>
                  <div className="flex items-center gap-2">
                    <span className="text-sm" title={humanizeManifestationStatus(idea.manifestation_status)}>
                      {stageIndicator(idea.manifestation_status)}
                    </span>
                    <span className="text-xs rounded-full border border-border/40 px-3 py-1 bg-muted/30 text-muted-foreground">
                      {humanizeManifestationStatus(idea.manifestation_status)}
                    </span>
                  </div>
                </div>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {idea.description}
                </p>

                {/* Value gap bar */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>Value realized</span>
                    <span>{formatUsd(idea.actual_value)} / {formatUsd(idea.potential_value)}</span>
                  </div>
                  <div className="h-2 rounded-full bg-muted/40 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-primary/40 to-primary/80 transition-all duration-500"
                      style={{ width: `${Math.max(100 - valueGapPct, 2)}%` }}
                    />
                  </div>
                </div>

                {/* What it needs */}
                <p className="text-xs text-primary/80">
                  {whatItNeeds(idea)}
                </p>

                <div className="flex items-center gap-3">
                  <div className="flex-1 h-1.5 rounded-full bg-muted/40 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-primary/60"
                      style={{ width: `${Math.min(idea.confidence * 100, 100)}%` }}
                    />
                  </div>
                  <span className="text-xs text-muted-foreground whitespace-nowrap">
                    {formatConfidence(idea.confidence)} confidence
                  </span>
                </div>
                <div className="flex flex-wrap gap-4 text-sm">
                  <Link
                    href={`/ideas/${encodeURIComponent(idea.id)}`}
                    className="text-primary hover:text-foreground transition-colors duration-300"
                  >
                    Open idea &rarr;
                  </Link>
                  <Link
                    href={`/flow?idea_id=${encodeURIComponent(idea.id)}`}
                    className="text-muted-foreground hover:text-foreground transition-colors duration-300"
                  >
                    View progress
                  </Link>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      {/* Bottom nudge */}
      <section className="py-8 text-center border-t border-border/20">
        <p className="text-muted-foreground mb-3">Have an idea?</p>
        <Link
          href="/"
          className="text-primary hover:text-foreground transition-colors duration-300 underline underline-offset-4"
        >
          Share it &rarr;
        </Link>
      </section>

      {/* Where to go next */}
      <nav className="py-8 text-center space-y-2" aria-label="Where to go next">
        <p className="text-xs text-muted-foreground/60 uppercase tracking-wider">Where to go next</p>
        <div className="flex flex-wrap justify-center gap-4 text-sm">
          <Link href="/resonance" className="text-muted-foreground hover:text-foreground transition-colors">Resonance</Link>
          <Link href="/invest" className="text-muted-foreground hover:text-foreground transition-colors">Invest</Link>
          <Link href="/contribute" className="text-muted-foreground hover:text-foreground transition-colors">Contribute</Link>
        </div>
      </nav>
    </main>
  );
}
