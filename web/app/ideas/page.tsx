import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";
import {
  formatUsd,
} from "@/lib/humanize";
import IdeasListView from "@/components/ideas/IdeasListView";

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
  stage?: string;
  interfaces: string[];
  open_questions: IdeaQuestion[];
  free_energy_score: number;
  value_gap: number;
  /** Spec 117 — hierarchy (optional for backward compat) */
  idea_type?: string;
  parent_idea_id?: string | null;
  child_idea_ids?: string[];
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

type StageBucket = {
  count: number;
  idea_ids: string[];
};

type ProgressDashboard = {
  total_ideas: number;
  completion_pct: number;
  by_stage: Record<string, StageBucket>;
  snapshot_at: string;
};

const STAGE_ORDER = [
  "none",
  "specced",
  "implementing",
  "testing",
  "reviewing",
  "complete",
] as const;

type StageName = (typeof STAGE_ORDER)[number];

const STAGE_LABEL: Record<StageName, string> = {
  none: "Backlog",
  specced: "Specced",
  implementing: "Implementing",
  testing: "Testing",
  reviewing: "Reviewing",
  complete: "Complete",
};

const AUTO_ADVANCE_TRIGGERS: Array<{
  taskType: string;
  movesTo: StageName;
  detail: string;
}> = [
  { taskType: "spec", movesTo: "specced", detail: "Task completion moves from backlog to specced." },
  { taskType: "impl", movesTo: "implementing", detail: "Task completion starts active implementation." },
  { taskType: "test", movesTo: "testing", detail: "Task completion moves work into verification." },
  { taskType: "review", movesTo: "reviewing", detail: "Task completion pushes to review readiness." },
];

async function loadIdeas(): Promise<IdeasResponse> {
  const API = getApiBase();
  const res = await fetch(`${API}/api/ideas`, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as IdeasResponse;
}

function emptyStageBucket(): StageBucket {
  return { count: 0, idea_ids: [] };
}

function buildFallbackProgress(ideas: IdeaWithScore[]): ProgressDashboard {
  const byStage: Record<string, StageBucket> = {};
  for (const stage of STAGE_ORDER) {
    byStage[stage] = emptyStageBucket();
  }
  for (const idea of ideas) {
    const stage = (idea.stage ?? "none").toLowerCase();
    if (!(stage in byStage)) {
      continue;
    }
    byStage[stage].count += 1;
    byStage[stage].idea_ids.push(idea.id);
  }
  const totalIdeas = ideas.length;
  const completionPct = totalIdeas > 0 ? byStage.complete.count / totalIdeas : 0;
  return {
    total_ideas: totalIdeas,
    completion_pct: completionPct,
    by_stage: byStage,
    snapshot_at: new Date().toISOString(),
  };
}

async function loadProgressDashboard(ideas: IdeaWithScore[]): Promise<ProgressDashboard> {
  const API = getApiBase();
  const res = await fetch(`${API}/api/ideas/progress`, { cache: "no-store" });
  if (!res.ok) {
    return buildFallbackProgress(ideas);
  }
  const payload = (await res.json()) as ProgressDashboard;
  const byStage: Record<string, StageBucket> = {};
  for (const stage of STAGE_ORDER) {
    byStage[stage] = payload.by_stage[stage] ?? emptyStageBucket();
  }
  return {
    total_ideas: payload.total_ideas,
    completion_pct: payload.completion_pct,
    by_stage: byStage,
    snapshot_at: payload.snapshot_at,
  };
}

function getRootIdeas(allIdeas: IdeaWithScore[]): IdeaWithScore[] {
  const byId = new Map(allIdeas.map((i) => [i.id, i]));
  return allIdeas
    .filter((i) => {
      if (!i.parent_idea_id) return true;
      return !byId.has(i.parent_idea_id);
    })
    .sort((a, b) => b.free_energy_score - a.free_energy_score);
}

export default async function IdeasPage() {
  const data = await loadIdeas();
  const progress = await loadProgressDashboard(data.ideas);

  const allIdeas = data.ideas;
  const roots = getRootIdeas([...allIdeas]);
  const completionPct = Math.round(Math.max(0, Math.min(progress.completion_pct, 1)) * 100);

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-5xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight mb-2">
          Ideas
        </h1>
        <p className="text-muted-foreground max-w-2xl leading-relaxed">
          Ideas are living things. They start as a thought, attract attention,
          grow through collaboration, and create real value.
        </p>
      </div>

      <section className="grid grid-cols-1 sm:grid-cols-3 gap-6">
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

      <section className="space-y-4" aria-labelledby="ideas-list-heading">
        <div className="space-y-2">
          <h2 id="ideas-list-heading" className="text-xl font-semibold tracking-tight">
            Portfolio
          </h2>
          <p className="text-sm text-muted-foreground max-w-2xl leading-relaxed">
            Switch between Cards and Table views. Toggle Expert mode in the header for IDs and raw data.
          </p>
        </div>
        {allIdeas.length === 0 ? (
          <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-8 text-center space-y-3">
            <p className="text-lg text-muted-foreground">No ideas yet. Be the first to share one.</p>
            <Link
              href="/"
              className="inline-block text-primary hover:text-foreground transition-colors underline underline-offset-4"
            >
              Share an idea &rarr;
            </Link>
          </div>
        ) : (
          <IdeasListView ideas={roots} />
        )}
      </section>

      {/* Lifecycle dashboard — collapsible, default closed */}
      <details className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30">
        <summary className="cursor-pointer p-5 md:p-6 text-sm font-medium text-foreground hover:text-primary transition-colors select-none">
          Show lifecycle details ({completionPct}% complete)
        </summary>
        <div className="px-5 md:px-6 pb-5 md:pb-6 space-y-5">
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>Portfolio completion</span>
              <span>{completionPct}% complete</span>
            </div>
            <div className="h-2.5 rounded-full bg-muted/40 overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-primary/50 to-primary/90 transition-all duration-500"
                style={{ width: `${Math.max(completionPct, 2)}%` }}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <article className="rounded-xl border border-border/30 bg-background/40 p-4 space-y-3">
              <h3 className="text-sm font-medium text-foreground">Stage transitions</h3>
              <ol className="space-y-2 text-sm">
                {STAGE_ORDER.map((stage, idx) => {
                  const next = STAGE_ORDER[idx + 1];
                  const bucket = progress.by_stage[stage] ?? emptyStageBucket();
                  return (
                    <li key={stage} className="flex items-center justify-between gap-2">
                      <span className="text-foreground">
                        {STAGE_LABEL[stage]}
                        {next ? ` -> ${STAGE_LABEL[next]}` : " (terminal)"}
                      </span>
                      <span className="text-xs rounded-full border border-border/40 px-2 py-0.5 bg-muted/30 text-foreground">
                        {bucket.count}
                      </span>
                    </li>
                  );
                })}
              </ol>
            </article>

            <article className="rounded-xl border border-border/30 bg-background/40 p-4 space-y-3">
              <h3 className="text-sm font-medium text-foreground">Auto-advancement triggers</h3>
              <ul className="space-y-2 text-sm">
                {AUTO_ADVANCE_TRIGGERS.map((trigger) => (
                  <li key={trigger.taskType} className="space-y-1">
                    <p className="text-foreground">
                      <span className="font-medium">{trigger.taskType}</span>
                      {" "}
                      {"task \u2192 "}<span className="text-primary">{STAGE_LABEL[trigger.movesTo]}</span>
                    </p>
                    <p className="text-xs text-muted-foreground">{trigger.detail}</p>
                  </li>
                ))}
              </ul>
            </article>
          </div>

          <div className="space-y-3">
            <h3 className="text-sm font-medium text-foreground">Progress by phase</h3>
            <ul className="space-y-2">
              {STAGE_ORDER.map((stage) => {
                const bucket = progress.by_stage[stage] ?? emptyStageBucket();
                const pct = progress.total_ideas > 0
                  ? Math.round((bucket.count / progress.total_ideas) * 100)
                  : 0;
                return (
                  <li key={stage} className="space-y-1.5">
                    <div className="flex items-center justify-between text-xs text-foreground">
                      <span>{STAGE_LABEL[stage]}</span>
                      <span>{bucket.count} ideas ({pct}%)</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-muted/40 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-primary/65"
                        style={{ width: `${Math.max(pct, 2)}%` }}
                      />
                    </div>
                  </li>
                );
              })}
            </ul>
            <p className="text-xs text-muted-foreground">
              Snapshot: {new Date(progress.snapshot_at).toLocaleString()}
            </p>
          </div>
        </div>
      </details>

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
      <nav className="py-8 text-center space-y-2 border-t border-border/20" aria-label="Where to go next">
        <p className="text-xs text-muted-foreground/80 uppercase tracking-wider">Where to go next</p>
        <div className="flex flex-wrap justify-center gap-4 text-sm">
          <Link href="/resonance" className="text-amber-600 dark:text-amber-400 hover:underline">Resonance</Link>
          <Link href="/invest" className="text-amber-600 dark:text-amber-400 hover:underline">Invest</Link>
          <Link href="/contribute" className="text-amber-600 dark:text-amber-400 hover:underline">Contribute</Link>
        </div>
      </nav>
    </main>
  );
}
