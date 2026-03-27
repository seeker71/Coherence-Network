import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";
import {
  formatConfidence,
  formatUsd,
  humanizeManifestationStatus,
} from "@/lib/humanize";
import { IdeaCopyLink } from "@/components/idea_share";

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

function stageIndicator(status: string): { emoji: string; label: string } {
  const s = status.trim().toLowerCase();
  if (s === "validated") return { emoji: "\u2705", label: "Complete" };
  if (s === "partial") return { emoji: "\uD83D\uDD28", label: "In progress" };
  return { emoji: "\uD83D\uDCCB", label: "Not started" };
}

function whatItNeeds(idea: IdeaWithScore): string {
  const s = idea.manifestation_status.trim().toLowerCase();
  if (s === "validated") return "Proven — ready to scale";
  if (s === "partial") return "Needs more validation";
  if (idea.open_questions && idea.open_questions.some((q) => !q.answer)) return "Has open questions";
  return "Needs a spec";
}

function hierarchyRoleLabel(idea: IdeaWithScore): string | null {
  const t = (idea.idea_type ?? "").toLowerCase();
  if (t === "super") return "Super-idea";
  if (t === "child") return "Child idea";
  return null;
}

function getChildrenForParent(
  parentId: string,
  allIdeas: IdeaWithScore[],
  byId: Map<string, IdeaWithScore>,
): IdeaWithScore[] {
  const linked = allIdeas.filter((i) => i.parent_idea_id === parentId);
  const parent = byId.get(parentId);
  const childOrder = parent?.child_idea_ids ?? [];
  if (childOrder.length === 0) {
    return [...linked].sort((a, b) => b.free_energy_score - a.free_energy_score);
  }
  const seen = new Set<string>();
  const ordered: IdeaWithScore[] = [];
  for (const id of childOrder) {
    const idea = byId.get(id);
    if (idea && idea.parent_idea_id === parentId && linked.some((x) => x.id === id)) {
      ordered.push(idea);
      seen.add(id);
    }
  }
  const extras = linked
    .filter((i) => !seen.has(i.id))
    .sort((a, b) => b.free_energy_score - a.free_energy_score);
  return [...ordered, ...extras];
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

function IdeaHierarchySubtree({
  idea,
  depth,
  rank,
  allIdeas,
  byId,
}: {
  idea: IdeaWithScore;
  depth: number;
  rank?: number;
  allIdeas: IdeaWithScore[];
  byId: Map<string, IdeaWithScore>;
}) {
  const kids = getChildrenForParent(idea.id, allIdeas, byId);
  const role = hierarchyRoleLabel(idea);
  const valueGapPct = idea.potential_value > 0
    ? Math.min(((idea.potential_value - idea.actual_value) / idea.potential_value) * 100, 100)
    : 0;
  const titlePrefix = rank !== undefined ? `${rank}. ` : "";

  return (
    <div className={depth > 0 ? "border-l border-border/40 pl-4 ml-1 sm:ml-2" : undefined}>
      <article
        className="hover-lift rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 md:p-6 space-y-3"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Link
            href={`/ideas/${encodeURIComponent(idea.id)}`}
            className="text-lg font-medium hover:text-primary transition-colors duration-300"
          >
            {titlePrefix}
            {idea.name}
          </Link>
          <div className="flex items-center gap-2 flex-wrap justify-end">
            {role ? (
              <span className="text-xs rounded-full border border-primary/30 px-2 py-0.5 bg-primary/10 text-primary/90">
                {role}
              </span>
            ) : null}
            <span className="text-sm" title={humanizeManifestationStatus(idea.manifestation_status)} aria-label={stageIndicator(idea.manifestation_status).label} role="img">
              {stageIndicator(idea.manifestation_status).emoji}
            </span>
            <span className="text-xs rounded-full border border-border/40 px-3 py-1 bg-muted/30 text-muted-foreground">
              {humanizeManifestationStatus(idea.manifestation_status)}
            </span>
          </div>
        </div>
        <p className="text-sm text-foreground/80 leading-relaxed">
          {idea.description}
        </p>

        <div className="space-y-1">
          <div className="flex items-center justify-between text-xs text-foreground/70">
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
        <div className="flex flex-wrap items-center gap-4 text-sm">
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
          <IdeaCopyLink url={`https://coherencycoin.com/ideas/${encodeURIComponent(idea.id)}`} />
        </div>
      </article>
      {kids.length > 0 ? (
        <div className="mt-3 space-y-3">
          {kids.map((child) => (
            <IdeaHierarchySubtree
              key={child.id}
              idea={child}
              depth={depth + 1}
              allIdeas={allIdeas}
              byId={byId}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

export default async function IdeasPage() {
  const data = await loadIdeas();
  const progress = await loadProgressDashboard(data.ideas);

  const allIdeas = data.ideas;
  const byId = new Map(allIdeas.map((i) => [i.id, i]));
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

      <section className="space-y-4" aria-labelledby="ideas-hierarchy-heading">
        <div className="space-y-2">
          <h2 id="ideas-hierarchy-heading" className="text-xl font-semibold tracking-tight">
            Portfolio hierarchy
          </h2>
          <p className="text-sm text-muted-foreground max-w-2xl leading-relaxed">
            Super-ideas group related child ideas; everything else stays at the top level.
            Child ideas nest under their parent when lineage data is present.
          </p>
        </div>
        {roots.length === 0 ? (
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
        <div className="space-y-3">
          {roots.map((idea, index) => (
            <IdeaHierarchySubtree
              key={idea.id}
              idea={idea}
              depth={0}
              rank={index + 1}
              allIdeas={allIdeas}
              byId={byId}
            />
          ))}
        </div>
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
