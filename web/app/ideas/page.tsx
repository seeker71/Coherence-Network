import type { Metadata } from "next";
import Link from "next/link";
import { cookies } from "next/headers";

import { getApiBase } from "@/lib/api";
import {
  formatUsd,
} from "@/lib/humanize";
import IdeasListView from "@/components/ideas/IdeasListView";
import { withWorkspaceScope } from "@/lib/workspace";
import { getActiveWorkspaceFromCookie } from "@/lib/workspace-server";
import { createTranslator } from "@/lib/i18n";
import { DEFAULT_LOCALE, isSupportedLocale, type LocaleCode } from "@/lib/locales";
import type { IdeaQuestion, IdeaWithScore } from "@/lib/types";

export const metadata: Metadata = {
  title: "Ideas",
  description: "Browse ideas in plain language and choose what looks most worth moving next.",
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

const PILLAR_ORDER = [
  "realization",
  "pipeline",
  "economics",
  "surfaces",
  "network",
  "foundation",
] as const;

type PillarName = (typeof PILLAR_ORDER)[number];

const PILLAR_KEY: Record<PillarName, string> = {
  realization: "ideas.pillarRealization",
  pipeline: "ideas.pillarPipeline",
  economics: "ideas.pillarEconomics",
  surfaces: "ideas.pillarSurfaces",
  network: "ideas.pillarNetwork",
  foundation: "ideas.pillarFoundation",
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

const AUTO_ADVANCE_TRIGGERS: Array<{
  taskType: string;
  movesTo: StageName;
  detailKey: string;
}> = [
  { taskType: "spec", movesTo: "specced", detailKey: "ideas.trigger.spec" },
  { taskType: "impl", movesTo: "implementing", detailKey: "ideas.trigger.impl" },
  { taskType: "test", movesTo: "testing", detailKey: "ideas.trigger.test" },
  { taskType: "review", movesTo: "reviewing", detailKey: "ideas.trigger.review" },
];

async function loadIdeas(curatedOnly: boolean, workspaceId: string, lang: LocaleCode): Promise<IdeasResponse> {
  const API = getApiBase();
  const langParam = lang === DEFAULT_LOCALE ? "" : `&lang=${lang}`;
  const qs = curatedOnly ? `?curated_only=true&limit=50${langParam}` : `?limit=500${langParam}`;
  const url = withWorkspaceScope(`${API}/api/ideas${qs}`, workspaceId);
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as IdeasResponse;
}

function groupByPillar(ideas: IdeaWithScore[]): Record<string, IdeaWithScore[]> {
  const groups: Record<string, IdeaWithScore[]> = {};
  for (const p of PILLAR_ORDER) groups[p] = [];
  const unknown: IdeaWithScore[] = [];
  for (const i of ideas) {
    const p = (i.pillar ?? "").toLowerCase();
    if (p && p in groups) groups[p].push(i);
    else unknown.push(i);
  }
  if (unknown.length) groups["_unknown"] = unknown;
  for (const k of Object.keys(groups)) {
    groups[k].sort((a, b) => b.free_energy_score - a.free_energy_score);
  }
  return groups;
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

async function loadProgressDashboard(ideas: IdeaWithScore[], workspaceId: string): Promise<ProgressDashboard> {
  const API = getApiBase();
  const url = withWorkspaceScope(`${API}/api/ideas/progress`, workspaceId);
  const res = await fetch(url, { cache: "no-store" });
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

type SearchParams = { all?: string };

export default async function IdeasPage({
  searchParams,
}: {
  searchParams?: Promise<SearchParams>;
}) {
  const params = (await searchParams) ?? {};
  const showAll = params.all === "1" || params.all === "true";
  const workspaceId = await getActiveWorkspaceFromCookie();
  const cookieStore = await cookies();
  const cookieLang = cookieStore.get("NEXT_LOCALE")?.value;
  const lang: LocaleCode = isSupportedLocale(cookieLang) ? cookieLang : DEFAULT_LOCALE;
  const t = createTranslator(lang);
  const data = await loadIdeas(!showAll, workspaceId, lang);
  const progress = await loadProgressDashboard(data.ideas, workspaceId);

  const allIdeas = data.ideas;
  const roots = getRootIdeas([...allIdeas]);
  const grouped = !showAll ? groupByPillar(allIdeas) : null;
  const completionPct = Math.round(Math.max(0, Math.min(progress.completion_pct, 1)) * 100);

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-5xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight mb-2">
          {t("ideas.title")}
        </h1>
        <p className="text-muted-foreground max-w-2xl leading-relaxed">
          {t("ideas.lede")}
        </p>
      </div>

      <section className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
          <p className="text-sm text-muted-foreground">{t("ideas.statTotal")}</p>
          <p className="text-2xl font-light text-primary">{data.summary.total_ideas}</p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
          <p className="text-sm text-muted-foreground">{t("ideas.statValue")}</p>
          <p className="text-2xl font-light text-primary">{formatUsd(data.summary.total_actual_value)}</p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
          <p className="text-sm text-muted-foreground">{t("ideas.statGap")}</p>
          <p className="text-2xl font-light text-primary">{formatUsd(data.summary.total_value_gap)}</p>
        </div>
      </section>

      <section className="space-y-4" aria-labelledby="ideas-list-heading">
        <div className="space-y-2">
          <h2 id="ideas-list-heading" className="text-xl font-semibold tracking-tight">
            {showAll ? t("ideas.sectionAll") : t("ideas.sectionPortfolio")}
          </h2>
          <p className="text-sm text-muted-foreground max-w-2xl leading-relaxed">
            {showAll ? t("ideas.sectionAllLede") : t("ideas.sectionPortfolioLede")}
          </p>
        </div>
        {allIdeas.length === 0 ? (
          <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-8 text-center space-y-3">
            <p className="text-lg text-muted-foreground">{t("ideas.empty")}</p>
            <Link
              href="/"
              className="inline-block text-primary hover:text-foreground transition-colors underline underline-offset-4"
            >
              {t("ideas.shareArrow")}
            </Link>
          </div>
        ) : showAll ? (
          <IdeasListView ideas={roots} />
        ) : grouped ? (
          <div className="space-y-8">
            {PILLAR_ORDER.map((pillar) => {
              const bucket = grouped[pillar] ?? [];
              if (bucket.length === 0) return null;
              return (
                <div key={pillar} className="space-y-3">
                  <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground/90 border-b border-border/30 pb-2">
                    {t(PILLAR_KEY[pillar])}
                  </h3>
                  <IdeasListView ideas={bucket} />
                </div>
              );
            })}
            {grouped["_unknown"] && grouped["_unknown"].length > 0 && (
              <div className="space-y-3">
                <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground/90 border-b border-border/30 pb-2">
                  {t("ideas.other")}
                </h3>
                <IdeasListView ideas={grouped["_unknown"]} />
              </div>
            )}
          </div>
        ) : null}
        <div className="pt-2">
          <Link
            href={showAll ? "/ideas" : "/ideas?all=1"}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors underline underline-offset-4"
          >
            {showAll ? t("ideas.toggleShowCurated") : t("ideas.toggleShowAll")}
          </Link>
        </div>
      </section>

      {/* Lifecycle dashboard — collapsible, default closed */}
      <details className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30">
        <summary className="cursor-pointer p-5 md:p-6 text-sm font-medium text-foreground hover:text-primary transition-colors select-none">
          {t("ideas.lifecycleDetails", { pct: completionPct })}
        </summary>
        <div className="px-5 md:px-6 pb-5 md:pb-6 space-y-5">
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>{t("ideas.portfolioCompletion")}</span>
              <span>{t("ideas.percentComplete", { pct: completionPct })}</span>
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
              <h3 className="text-sm font-medium text-foreground">{t("ideas.stageTransitions")}</h3>
              <ol className="space-y-2 text-sm">
                {STAGE_ORDER.map((stage, idx) => {
                  const next = STAGE_ORDER[idx + 1];
                  const bucket = progress.by_stage[stage] ?? emptyStageBucket();
                  return (
                    <li key={stage} className="flex items-center justify-between gap-2">
                      <span className="text-foreground">
                        {t(`ideas.stage.${stage}`)}
                        {next ? ` -> ${t(`ideas.stage.${next}`)}` : ` ${t("ideas.terminal")}`}
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
              <h3 className="text-sm font-medium text-foreground">{t("ideas.autoAdvanceTriggers")}</h3>
              <ul className="space-y-2 text-sm">
                {AUTO_ADVANCE_TRIGGERS.map((trigger) => (
                  <li key={trigger.taskType} className="space-y-1">
                    <p className="text-foreground">
                      <span className="font-medium">{trigger.taskType}</span>
                      {" "}
                      {t("ideas.taskArrow")}{" "}<span className="text-primary">{t(`ideas.stage.${trigger.movesTo}`)}</span>
                    </p>
                    <p className="text-xs text-muted-foreground">{t(trigger.detailKey)}</p>
                  </li>
                ))}
              </ul>
            </article>
          </div>

          <div className="space-y-3">
            <h3 className="text-sm font-medium text-foreground">{t("ideas.progressByPhase")}</h3>
            <ul className="space-y-2">
              {STAGE_ORDER.map((stage) => {
                const bucket = progress.by_stage[stage] ?? emptyStageBucket();
                const pct = progress.total_ideas > 0
                  ? Math.round((bucket.count / progress.total_ideas) * 100)
                  : 0;
                return (
                  <li key={stage} className="space-y-1.5">
                    <div className="flex items-center justify-between text-xs text-foreground">
                      <span>{t(`ideas.stage.${stage}`)}</span>
                      <span>{t("ideas.ideasCountPct", { count: bucket.count, pct })}</span>
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
              {t("ideas.snapshot", { time: new Date(progress.snapshot_at).toLocaleString(lang) })}
            </p>
          </div>
        </div>
      </details>

      {/* Bottom nudge */}
      <section className="py-8 text-center border-t border-border/20">
        <p className="text-muted-foreground mb-3">{t("ideas.haveIdea")}</p>
        <Link
          href="/"
          className="text-primary hover:text-foreground transition-colors duration-300 underline underline-offset-4"
        >
          {t("ideas.shareIt")}
        </Link>
      </section>

      {/* Where to go next */}
      <nav className="py-8 text-center space-y-2 border-t border-border/20" aria-label={t("ideas.whereNext")}>
        <p className="text-xs text-muted-foreground/80 uppercase tracking-wider">{t("ideas.whereNext")}</p>
        <div className="flex flex-wrap justify-center gap-4 text-sm">
          <Link href="/resonance" className="text-amber-600 dark:text-amber-400 hover:underline">{t("nav.resonance")}</Link>
          <Link href="/invest" className="text-amber-600 dark:text-amber-400 hover:underline">{t("nav.invest")}</Link>
          <Link href="/contribute" className="text-amber-600 dark:text-amber-400 hover:underline">{t("nav.contribute")}</Link>
        </div>
      </nav>
    </main>
  );
}
