import {
  Activity,
  ArrowUpDown,
  BadgeCheck,
  ChevronDown,
  ChevronRight,
  Circle,
  Cog,
  GitBranch,
  Link2,
  Search,
  Sparkles,
  TrendingUp,
  Unlink2,
  type LucideIcon,
} from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "Specs",
  description: "Browse feature specifications and their implementation status.",
};

type SpecCardState = "unlinked" | "linked" | "in_progress" | "implemented" | "measured";
type SpecAttentionLevel = "none" | "low" | "medium" | "high";

type SpecCardItem = {
  spec_id: string;
  title: string;
  summary: string;
  state: SpecCardState;
  attention_level: SpecAttentionLevel;
  attention_score: number;
  attention_reason?: string | null;
  value_gap: number;
  actual_roi: number;
  estimated_roi: number;
  potential_value: number;
  actual_value: number;
  estimated_cost: number;
  actual_cost: number;
  links_count: number;
  idea_id?: string | null;
  created_by_contributor_id?: string | null;
  updated_by_contributor_id?: string | null;
  updated_at: string;
  links: {
    web_detail_path: string;
    web_idea_path?: string | null;
    api_path: string;
  };
};

type SpecCardsResponse = {
  summary: {
    total: number;
    returned: number;
    state_counts: Record<string, number>;
    attention_counts: Record<string, number>;
    needs_attention: number;
  };
  pagination: {
    cursor: string;
    next_cursor: string | null;
    limit: number;
    returned: number;
    has_more: boolean;
  };
  query: {
    q: string;
    state: string;
    attention: string;
    sort: string;
    cursor: number;
    limit: number;
    linked: string;
    min_roi: number | null;
    min_value_gap: number | null;
  };
  items: SpecCardItem[];
};

type SpecsSearchParams = Promise<Record<string, string | string[] | undefined>>;

const DEFAULT_LIMIT = 50;
const MAX_LIMIT = 200;
const FILTER_STATES = ["all", "unlinked", "linked", "in_progress", "implemented", "measured"] as const;
const ATTENTION_LEVELS = ["all", "none", "low", "medium", "high"] as const;
const SORT_OPTIONS = ["attention_desc", "roi_desc", "gap_desc", "state_desc", "updated_desc", "name_asc"] as const;
const VIEW_OPTIONS = ["list", "focus"] as const;
const LINKED_OPTIONS = ["all", "linked", "unlinked"] as const;
const LIMIT_OPTIONS = [25, 50, 100, 200] as const;

const SORT_LABEL: Record<(typeof SORT_OPTIONS)[number], string> = {
  attention_desc: "attention (high to low)",
  roi_desc: "ROI (high to low)",
  gap_desc: "value gap (high to low)",
  state_desc: "state progress",
  updated_desc: "updated (newest first)",
  name_asc: "name (A to Z)",
};

const STATE_FILTER_LABEL: Record<(typeof FILTER_STATES)[number], string> = {
  all: "All states",
  unlinked: "Unlinked",
  linked: "Linked",
  in_progress: "In progress",
  implemented: "Implemented",
  measured: "Measured",
};

const ATTENTION_FILTER_LABEL: Record<(typeof ATTENTION_LEVELS)[number], string> = {
  all: "All attention levels",
  none: "On track",
  low: "Low",
  medium: "Medium",
  high: "High",
};

const VIEW_LABEL: Record<(typeof VIEW_OPTIONS)[number], string> = {
  list: "List + side insights",
  focus: "Focus list only",
};

const LINKED_LABEL: Record<(typeof LINKED_OPTIONS)[number], string> = {
  all: "All specs",
  linked: "Linked to ideas",
  unlinked: "Unlinked specs",
};

const STATE_META: Record<SpecCardState, { label: string; icon: LucideIcon; tone: string; subtleTone: string }> = {
  unlinked: {
    label: "unlinked",
    icon: Unlink2,
    tone: "border-destructive/45 text-destructive bg-destructive/10",
    subtleTone: "text-destructive",
  },
  linked: {
    label: "linked",
    icon: Link2,
    tone: "border-chart-5/45 text-chart-5 bg-chart-5/10",
    subtleTone: "text-chart-5",
  },
  in_progress: {
    label: "in progress",
    icon: GitBranch,
    tone: "border-chart-3/45 text-chart-3 bg-chart-3/10",
    subtleTone: "text-chart-3",
  },
  implemented: {
    label: "implemented",
    icon: Cog,
    tone: "border-chart-4/45 text-chart-4 bg-chart-4/10",
    subtleTone: "text-chart-4",
  },
  measured: {
    label: "measured",
    icon: BadgeCheck,
    tone: "border-chart-2/45 text-chart-2 bg-chart-2/10",
    subtleTone: "text-chart-2",
  },
};

const ATTENTION_META: Record<SpecAttentionLevel, { label: string; dot: string }> = {
  none: { label: "on track", dot: "bg-chart-2" },
  low: { label: "low", dot: "bg-chart-5" },
  medium: { label: "medium", dot: "bg-chart-3" },
  high: { label: "high", dot: "bg-destructive" },
};

export const revalidate = 30;

function readParam(value: string | string[] | undefined, fallback = ""): string {
  if (Array.isArray(value)) return String(value[0] || fallback);
  return String(value || fallback);
}

function parseCursor(value: string): number {
  const parsed = Number.parseInt(value.trim(), 10);
  if (!Number.isFinite(parsed) || parsed < 0) return 0;
  return parsed;
}

function parseLimit(value: string): number {
  const parsed = Number.parseInt(value.trim(), 10);
  if (!Number.isFinite(parsed) || parsed < 1) return DEFAULT_LIMIT;
  return Math.max(1, Math.min(parsed, MAX_LIMIT));
}

function parseEnum<T extends readonly string[]>(value: string, allowed: T, fallback: T[number]): T[number] {
  return (allowed as readonly string[]).includes(value) ? (value as T[number]) : fallback;
}

function parseOptionalNumber(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number.parseFloat(trimmed);
  if (!Number.isFinite(parsed)) return null;
  return parsed;
}

function formatCompactNumber(value: number): string {
  return new Intl.NumberFormat("en-US").format(Math.max(0, Math.round(value)));
}

function formatMetric(value: number, fractionDigits = 1): string {
  if (!Number.isFinite(value)) return "0.0";
  return value.toFixed(fractionDigits);
}

function formatAttentionReason(value?: string | null): string | null {
  const raw = String(value || "").trim();
  if (!raw) return null;
  const cleaned = raw.replace(/[_:-]+/g, " ").replace(/\s+/g, " ").trim();
  if (!cleaned) return null;
  return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
}

function buildHref(
  base: URLSearchParams,
  updates: Record<string, string | number | null | undefined>,
): string {
  const next = new URLSearchParams(base.toString());
  for (const [key, value] of Object.entries(updates)) {
    if (value === null || value === undefined || String(value).trim() === "") {
      next.delete(key);
    } else {
      next.set(key, String(value));
    }
  }
  const query = next.toString();
  return query ? `/specs?${query}` : "/specs";
}

function buildSparklinePath(values: number[]): string {
  const points = values.length > 1 ? values : [0.2, 0.45, 0.75, 0.55, 0.95, 1.2, 1.35];
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = Math.max(max - min, 0.0001);
  const width = 260;
  const height = 72;

  return points
    .map((value, index) => {
      const x = (index / Math.max(points.length - 1, 1)) * width;
      const y = height - ((value - min) / span) * height;
      return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

async function loadSpecCards(params: {
  q: string;
  state: string;
  attention: string;
  sort: string;
  cursor: number;
  limit: number;
  linked: string;
  minRoi: number | null;
  minValueGap: number | null;
}): Promise<SpecCardsResponse> {
  const API = getApiBase();
  const search = new URLSearchParams({
    q: params.q,
    state: params.state,
    attention: params.attention,
    sort: params.sort,
    cursor: String(params.cursor),
    limit: String(params.limit),
    linked: params.linked,
  });
  if (params.minRoi !== null) search.set("min_roi", String(params.minRoi));
  if (params.minValueGap !== null) search.set("min_value_gap", String(params.minValueGap));

  const response = await fetch(`${API}/api/spec-registry/cards?${search.toString()}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Failed to load spec cards (${response.status})`);
  }
  return (await response.json()) as SpecCardsResponse;
}

export default async function SpecsPage({ searchParams }: { searchParams: SpecsSearchParams }) {
  const resolved = await searchParams;
  const q = readParam(resolved.q);
  const state = parseEnum(readParam(resolved.state, "all"), FILTER_STATES, "all");
  const attention = parseEnum(readParam(resolved.attention, "all"), ATTENTION_LEVELS, "all");
  const sort = parseEnum(readParam(resolved.sort, "attention_desc"), SORT_OPTIONS, "attention_desc");
  const view = parseEnum(readParam(resolved.view, "list"), VIEW_OPTIONS, "list");
  const linked = parseEnum(readParam(resolved.linked, "all"), LINKED_OPTIONS, "all");
  const cursor = parseCursor(readParam(resolved.cursor, "0"));
  const limit = parseLimit(readParam(resolved.limit, String(DEFAULT_LIMIT)));
  const minRoi = parseOptionalNumber(readParam(resolved.min_roi));
  const minValueGap = parseOptionalNumber(readParam(resolved.min_value_gap));

  const currentParams = new URLSearchParams();
  if (q) currentParams.set("q", q);
  if (state !== "all") currentParams.set("state", state);
  if (attention !== "all") currentParams.set("attention", attention);
  if (sort !== "attention_desc") currentParams.set("sort", sort);
  if (view !== "list") currentParams.set("view", view);
  if (linked !== "all") currentParams.set("linked", linked);
  if (cursor > 0) currentParams.set("cursor", String(cursor));
  if (limit !== DEFAULT_LIMIT) currentParams.set("limit", String(limit));
  if (minRoi !== null) currentParams.set("min_roi", String(minRoi));
  if (minValueGap !== null) currentParams.set("min_value_gap", String(minValueGap));

  const payload = await loadSpecCards({
    q,
    state,
    attention,
    sort,
    cursor,
    limit,
    linked,
    minRoi,
    minValueGap,
  });

  const items = payload.items;
  const summary = payload.summary;
  const pagination = payload.pagination;

  const unlinkedCount = Number(summary.state_counts.unlinked || 0);
  const linkedCount = Math.max(summary.total - unlinkedCount, 0);
  const measuredCount = Number(summary.state_counts.measured || 0);
  const needsAttentionCount = Number(summary.needs_attention || 0);

  const startIndex = summary.total === 0 ? 0 : cursor + 1;
  const endIndex = summary.total === 0 ? 0 : Math.min(cursor + pagination.returned, summary.total);

  const focusSpecs = [...items].sort((a, b) => b.attention_score - a.attention_score).slice(0, 3);
  const pulsePath = buildSparklinePath(items.slice(0, 7).map((item) => Math.max(item.attention_score, item.value_gap, item.actual_roi)));

  const clearCursor = { cursor: null } as const;

  return (
    <main className="min-h-screen px-4 pb-8 pt-6 sm:px-6 lg:px-8">
      <div className="mx-auto w-full max-w-7xl space-y-4">
        <section className="space-y-1 px-1">
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Specs In Motion</h1>
          <p className="max-w-3xl text-sm text-muted-foreground sm:text-base">
            Contributor-written specs moving from draft intent to measurable outcomes.
          </p>
          <p className="text-xs uppercase tracking-[0.12em] text-muted-foreground">
            {linked === "all" ? "Showing all specs in registry." : linked === "linked" ? "Showing specs linked to ideas." : "Showing specs missing idea links."}
          </p>
        </section>

        <section className="rounded-2xl border border-border/70 bg-card/70 p-4 shadow-sm sm:p-5">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-[repeat(4,minmax(0,1fr))_1.8fr]">
            <div className="rounded-xl border border-border/70 bg-background/45 p-4">
              <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Specs in registry</p>
              <p className="mt-1 text-2xl font-semibold">{formatCompactNumber(summary.total)}</p>
            </div>
            <div className="rounded-xl border border-border/70 bg-background/45 p-4">
              <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Linked to ideas</p>
              <p className="mt-1 text-2xl font-semibold">{formatCompactNumber(linkedCount)}</p>
            </div>
            <div className="rounded-xl border border-border/70 bg-background/45 p-4">
              <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Measured</p>
              <p className="mt-1 text-2xl font-semibold">{formatCompactNumber(measuredCount)}</p>
            </div>
            <div className="rounded-xl border border-border/70 bg-background/45 p-4">
              <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Needs attention</p>
              <p className="mt-1 text-2xl font-semibold">{formatCompactNumber(needsAttentionCount)}</p>
            </div>
            <div className="rounded-xl border border-border/70 bg-background/45 p-4">
              <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Collective focus</p>
              <p className="mt-2 text-sm font-medium text-foreground sm:text-base">
                {focusSpecs[0]
                  ? `Resolve ${focusSpecs[0].title} gaps with linked ownership and implementation clarity.`
                  : "Lift under-specified specs toward measurable outcomes."}
              </p>
            </div>
          </div>
        </section>

        <section className="rounded-2xl border border-border/70 bg-card/60 p-4 shadow-sm sm:p-5">
          <form action="/specs" method="get" className="space-y-3">
            <div className="flex items-center gap-2 rounded-xl border border-border/70 bg-background/50 px-3 py-3">
              <Search className="h-4 w-4 text-muted-foreground" aria-hidden />
              <input
                type="text"
                name="q"
                defaultValue={q}
                placeholder="Search specs, ideas, contributors, or implementation notes"
                className="w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
              />
              <button
                type="submit"
                className="rounded-lg border border-border/70 bg-background/70 px-3 py-1.5 text-sm font-medium hover:bg-muted/60"
              >
                Apply
              </button>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <label className="space-y-1.5 rounded-xl border border-border/70 bg-background/45 px-3 py-2.5">
                <span className="block text-[11px] uppercase tracking-[0.12em] text-muted-foreground">State</span>
                <select
                  name="state"
                  defaultValue={state}
                  className="w-full rounded-md border border-border/70 bg-background/90 px-2.5 py-1.5 text-sm"
                >
                  {FILTER_STATES.map((stateOption) => (
                    <option key={stateOption} value={stateOption}>
                      {STATE_FILTER_LABEL[stateOption]}
                    </option>
                  ))}
                </select>
              </label>

              <label className="space-y-1.5 rounded-xl border border-border/70 bg-background/45 px-3 py-2.5">
                <span className="block text-[11px] uppercase tracking-[0.12em] text-muted-foreground">Attention</span>
                <select
                  name="attention"
                  defaultValue={attention}
                  className="w-full rounded-md border border-border/70 bg-background/90 px-2.5 py-1.5 text-sm"
                >
                  {ATTENTION_LEVELS.map((attentionOption) => (
                    <option key={attentionOption} value={attentionOption}>
                      {ATTENTION_FILTER_LABEL[attentionOption]}
                    </option>
                  ))}
                </select>
              </label>

              <label className="space-y-1.5 rounded-xl border border-border/70 bg-background/45 px-3 py-2.5">
                <span className="block text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
                  Sort (table header)
                </span>
                <select
                  name="sort"
                  defaultValue={sort}
                  className="w-full rounded-md border border-border/70 bg-background/90 px-2.5 py-1.5 text-sm"
                >
                  {SORT_OPTIONS.map((sortOption) => (
                    <option key={sortOption} value={sortOption}>
                      {SORT_LABEL[sortOption]}
                    </option>
                  ))}
                </select>
              </label>

              <label className="space-y-1.5 rounded-xl border border-border/70 bg-background/45 px-3 py-2.5">
                <span className="block text-[11px] uppercase tracking-[0.12em] text-muted-foreground">View</span>
                <select
                  name="view"
                  defaultValue={view}
                  className="w-full rounded-md border border-border/70 bg-background/90 px-2.5 py-1.5 text-sm"
                >
                  {VIEW_OPTIONS.map((viewOption) => (
                    <option key={viewOption} value={viewOption}>
                      {VIEW_LABEL[viewOption]}
                    </option>
                  ))}
                </select>
              </label>

              <label className="space-y-1.5 rounded-xl border border-border/70 bg-background/45 px-3 py-2.5">
                <span className="block text-[11px] uppercase tracking-[0.12em] text-muted-foreground">Link status</span>
                <select
                  name="linked"
                  defaultValue={linked}
                  className="w-full rounded-md border border-border/70 bg-background/90 px-2.5 py-1.5 text-sm"
                >
                  {LINKED_OPTIONS.map((linkedOption) => (
                    <option key={linkedOption} value={linkedOption}>
                      {LINKED_LABEL[linkedOption]}
                    </option>
                  ))}
                </select>
              </label>

              <label className="space-y-1.5 rounded-xl border border-border/70 bg-background/45 px-3 py-2.5">
                <span className="block text-[11px] uppercase tracking-[0.12em] text-muted-foreground">Rows per page</span>
                <select
                  name="limit"
                  defaultValue={String(limit)}
                  className="w-full rounded-md border border-border/70 bg-background/90 px-2.5 py-1.5 text-sm"
                >
                  {LIMIT_OPTIONS.map((pageLimit) => (
                    <option key={pageLimit} value={String(pageLimit)}>
                      {pageLimit}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <label className="space-y-1.5 rounded-xl border border-border/70 bg-background/45 px-3 py-2.5">
                <span className="block text-[11px] uppercase tracking-[0.12em] text-muted-foreground">Min ROI</span>
                <input
                  type="number"
                  step="0.1"
                  name="min_roi"
                  defaultValue={minRoi ?? ""}
                  placeholder="Any"
                  className="w-full rounded-md border border-border/70 bg-background/90 px-2.5 py-1.5 text-sm"
                />
              </label>
              <label className="space-y-1.5 rounded-xl border border-border/70 bg-background/45 px-3 py-2.5">
                <span className="block text-[11px] uppercase tracking-[0.12em] text-muted-foreground">Min Value Gap</span>
                <input
                  type="number"
                  step="0.1"
                  name="min_value_gap"
                  defaultValue={minValueGap ?? ""}
                  placeholder="Any"
                  className="w-full rounded-md border border-border/70 bg-background/90 px-2.5 py-1.5 text-sm"
                />
              </label>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs text-muted-foreground">
                State, link status, and attention narrow results. Click table headers to sort; this dropdown is a fallback. View only changes layout.
              </p>
              <div className="flex items-center gap-2">
                <button
                  type="submit"
                  className="rounded-lg border border-border/70 bg-background/70 px-3 py-1.5 text-sm font-medium hover:bg-muted/60"
                >
                  Apply filters
                </button>
                <Link
                  href="/specs"
                  className="rounded-lg border border-border/70 bg-background/70 px-3 py-1.5 text-sm font-medium text-muted-foreground hover:bg-muted/60 hover:text-foreground"
                >
                  Reset
                </Link>
              </div>
            </div>
          </form>
        </section>

        <section className="rounded-xl border border-border/70 bg-card/50 px-3 py-3">
          <div className="flex flex-wrap items-center gap-2">
            {[
              {
                label: "All",
                href: buildHref(currentParams, {
                  state: "all",
                  attention: "all",
                  linked: "all",
                  min_roi: null,
                  min_value_gap: null,
                  ...clearCursor,
                }),
                active: state === "all" && attention === "all" && linked === "all" && minRoi === null && minValueGap === null,
              },
              { label: "Linked Ideas", href: buildHref(currentParams, { linked: "linked", ...clearCursor }), active: linked === "linked" },
              { label: "Unlinked", href: buildHref(currentParams, { linked: "unlinked", ...clearCursor }), active: linked === "unlinked" },
              {
                label: "In Progress",
                href: buildHref(currentParams, { state: "in_progress", ...clearCursor }),
                active: state === "in_progress",
              },
              {
                label: "Implemented",
                href: buildHref(currentParams, { state: "implemented", ...clearCursor }),
                active: state === "implemented",
              },
              {
                label: "Measured",
                href: buildHref(currentParams, { state: "measured", ...clearCursor }),
                active: state === "measured",
              },
              {
                label: "Needs Attention",
                href: buildHref(currentParams, { attention: "high", ...clearCursor }),
                active: attention === "high",
              },
              {
                label: "ROI > 5",
                href: buildHref(currentParams, { min_roi: 5, ...clearCursor }),
                active: minRoi !== null && minRoi >= 5,
              },
              {
                label: "Gap > 5",
                href: buildHref(currentParams, { min_value_gap: 5, ...clearCursor }),
                active: minValueGap !== null && minValueGap >= 5,
              },
            ].map((chip) => (
              <Link
                key={chip.label}
                href={chip.href}
                className={`inline-flex items-center rounded-full border px-3 py-1.5 text-sm transition ${
                  chip.active
                    ? "border-primary/50 bg-primary/15 text-primary"
                    : "border-border/70 bg-background/55 text-muted-foreground hover:text-foreground"
                }`}
              >
                {chip.label}
              </Link>
            ))}

            <div className="ml-auto flex flex-wrap items-center gap-2">
              {LIMIT_OPTIONS.map((pageLimit) => (
                <Link
                  key={pageLimit}
                  href={buildHref(currentParams, { limit: pageLimit, ...clearCursor })}
                  className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs transition ${
                    limit === pageLimit
                      ? "border-primary/50 bg-primary/15 text-primary"
                      : "border-border/70 text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {pageLimit}
                </Link>
              ))}
              <span className="text-xs text-muted-foreground">
                {startIndex}-{endIndex} of {formatCompactNumber(summary.total)}
              </span>
            </div>
          </div>
        </section>

        <section className={view === "focus" ? "space-y-4" : "grid gap-4 xl:grid-cols-[2fr_1fr]"}>
          <article className="rounded-2xl border border-border/70 bg-card/60 p-4 sm:p-5">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-xl font-semibold tracking-tight">Active Specs</h2>
              <p className="text-xs text-muted-foreground">sorted by {SORT_LABEL[sort]}</p>
            </div>
            <div className="sticky top-[56px] z-30 mb-3 hidden grid-cols-[minmax(0,1fr)_128px_76px_76px_120px] items-center rounded-lg border border-border/70 bg-background/95 px-3 py-2 text-xs text-muted-foreground shadow-sm backdrop-blur-sm md:grid">
              <Link
                href={buildHref(currentParams, { sort: "name_asc", ...clearCursor })}
                className={`inline-flex items-center gap-1.5 transition ${
                  sort === "name_asc" ? "font-semibold text-primary" : "hover:text-foreground"
                }`}
                aria-label="Sort by spec name"
              >
                <Circle className="h-3.5 w-3.5" aria-hidden />
                spec
                <ArrowUpDown className="h-3.5 w-3.5" aria-hidden />
              </Link>
              <span className="inline-flex items-center justify-end gap-1" title="Links column is not sortable yet.">
                <Link2 className="h-3.5 w-3.5" aria-hidden />
                links
              </span>
              <Link
                href={buildHref(currentParams, { sort: "gap_desc", ...clearCursor })}
                className={`inline-flex items-center justify-end gap-1 transition ${
                  sort === "gap_desc" ? "font-semibold text-primary" : "hover:text-foreground"
                }`}
                aria-label="Sort by value gap"
              >
                <Sparkles className="h-3.5 w-3.5" aria-hidden />
                gap
                <ArrowUpDown className="h-3.5 w-3.5" aria-hidden />
              </Link>
              <Link
                href={buildHref(currentParams, { sort: "roi_desc", ...clearCursor })}
                className={`inline-flex items-center justify-end gap-1 transition ${
                  sort === "roi_desc" ? "font-semibold text-primary" : "hover:text-foreground"
                }`}
                aria-label="Sort by ROI"
              >
                <TrendingUp className="h-3.5 w-3.5" aria-hidden />
                roi
                <ArrowUpDown className="h-3.5 w-3.5" aria-hidden />
              </Link>
              <Link
                href={buildHref(currentParams, { sort: "attention_desc", ...clearCursor })}
                className={`inline-flex items-center justify-end gap-1 transition ${
                  sort === "attention_desc" ? "font-semibold text-primary" : "hover:text-foreground"
                }`}
                aria-label="Sort by attention"
              >
                <Activity className="h-3.5 w-3.5" aria-hidden />
                attention
                <ArrowUpDown className="h-3.5 w-3.5" aria-hidden />
              </Link>
            </div>
            <div className="sticky top-[56px] z-30 mb-2 flex items-center justify-between gap-2 rounded-lg border border-border/70 bg-background/95 px-2.5 py-1.5 text-[11px] text-muted-foreground shadow-sm backdrop-blur-sm md:hidden">
              <span className="inline-flex items-center gap-1">
                <Link2 className="h-3 w-3" aria-hidden />
                links
              </span>
              <span className="inline-flex items-center gap-1">
                <Sparkles className="h-3 w-3" aria-hidden />
                gap
              </span>
              <span className="inline-flex items-center gap-1">
                <TrendingUp className="h-3 w-3" aria-hidden />
                roi
              </span>
              <span className="inline-flex items-center gap-1">
                <Activity className="h-3 w-3" aria-hidden />
                attention
              </span>
            </div>
            <div className="mb-2 flex flex-wrap items-center gap-1.5 md:hidden">
              {[
                { label: "spec", value: "name_asc" },
                { label: "gap", value: "gap_desc" },
                { label: "roi", value: "roi_desc" },
                { label: "attention", value: "attention_desc" },
              ].map((option) => (
                <Link
                  key={option.value}
                  href={buildHref(currentParams, { sort: option.value, ...clearCursor })}
                  className={`inline-flex items-center gap-1 rounded-full border px-2 py-1 text-[11px] transition ${
                    sort === option.value
                      ? "border-primary/50 bg-primary/15 text-primary"
                      : "border-border/70 text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {option.label}
                </Link>
              ))}
            </div>

            <ul className="space-y-2.5">
              {items.map((item) => {
                const stateMeta = STATE_META[item.state];
                const attentionMeta = ATTENTION_META[item.attention_level];
                const StateIcon = stateMeta.icon;
                const reason = formatAttentionReason(item.attention_reason);
                const linkTargets = [
                  { label: "Spec detail", href: item.links.web_detail_path },
                  ...(item.links.web_idea_path ? [{ label: "Idea", href: item.links.web_idea_path }] : []),
                  ...(item.created_by_contributor_id
                    ? [
                        {
                          label: "Created by",
                          href: `/contributors?contributor_id=${encodeURIComponent(item.created_by_contributor_id)}`,
                        },
                      ]
                    : []),
                  ...(item.updated_by_contributor_id
                    ? [
                        {
                          label: "Updated by",
                          href: `/contributors?contributor_id=${encodeURIComponent(item.updated_by_contributor_id)}`,
                        },
                      ]
                    : []),
                  { label: "API record", href: item.links.api_path },
                ];
                const linksCount = linkTargets.length;

                return (
                  <li key={item.spec_id} className="rounded-xl border border-border/70 bg-background/45 p-2.5 shadow-sm sm:p-3.5">
                    <div className="grid gap-2.5 md:grid-cols-[minmax(0,1fr)_128px_76px_76px_120px] md:items-center">
                      <div className="min-w-0">
                        <div className="flex items-start gap-3">
                          <span
                            title={stateMeta.label}
                            className={`mt-0.5 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border ${stateMeta.tone}`}
                          >
                            <StateIcon className="h-4 w-4" aria-hidden />
                          </span>
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <h3 className="truncate text-base font-semibold">
                                <Link href={item.links.web_detail_path} className="underline-offset-2 hover:underline">
                                  {item.title}
                                </Link>
                              </h3>
                              <span className="text-xs text-muted-foreground">{item.spec_id}</span>
                              {item.links.web_idea_path ? (
                                <Link
                                  href={item.links.web_idea_path}
                                  className="text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
                                >
                                  idea
                                </Link>
                              ) : null}
                            </div>
                            <p className="mt-0.5 line-clamp-2 text-sm text-muted-foreground md:line-clamp-1">
                              {item.summary || "No summary provided yet. Add process context and implementation notes to improve execution quality."}
                            </p>
                            {reason ? <p className="mt-0.5 text-xs text-muted-foreground">{reason}</p> : null}
                          </div>
                        </div>
                      </div>

                      <div className="hidden justify-end md:flex">
                        <details className="group relative">
                          <summary className="inline-flex list-none cursor-pointer items-center gap-1 rounded-md border border-border/70 bg-background/70 px-2 py-1 text-xs text-foreground transition hover:bg-muted/50 [&::-webkit-details-marker]:hidden">
                            {formatCompactNumber(linksCount)} links
                            <ChevronDown className="h-3 w-3 transition group-open:rotate-180" aria-hidden />
                          </summary>
                          <div className="absolute right-0 top-full z-30 mt-1 w-44 rounded-md border border-border/70 bg-popover p-1 shadow-md">
                            {linkTargets.map((target) => (
                              <Link
                                key={`${item.spec_id}-${target.label}`}
                                href={target.href}
                                className="block rounded px-2 py-1.5 text-xs text-foreground hover:bg-muted/60"
                              >
                                {target.label}
                              </Link>
                            ))}
                          </div>
                        </details>
                      </div>
                      <div className="hidden text-right text-sm font-medium tabular-nums text-foreground md:block">
                        {formatMetric(item.value_gap)}
                      </div>
                      <div className="hidden text-right text-sm font-medium tabular-nums text-foreground md:block">
                        {formatMetric(item.actual_roi)}
                      </div>
                      <div className="hidden items-center justify-end gap-2 text-sm text-muted-foreground md:flex">
                        <span className={`inline-block h-2.5 w-2.5 rounded-full ${attentionMeta.dot}`} />
                        {attentionMeta.label}
                      </div>

                      <div className="grid grid-cols-2 gap-2 text-xs md:hidden">
                        <div className="rounded-lg border border-border/60 bg-muted/30 px-2 py-1.5">
                          <p className="text-muted-foreground">links</p>
                          <p className="tabular-nums text-foreground">{formatCompactNumber(linksCount)}</p>
                        </div>
                        <div className="rounded-lg border border-border/60 bg-muted/30 px-2 py-1.5">
                          <p className="text-muted-foreground">gap</p>
                          <p className="tabular-nums text-foreground">{formatMetric(item.value_gap)}</p>
                        </div>
                        <div className="rounded-lg border border-border/60 bg-muted/30 px-2 py-1.5">
                          <p className="text-muted-foreground">roi</p>
                          <p className="tabular-nums text-foreground">{formatMetric(item.actual_roi)}</p>
                        </div>
                        <div className="rounded-lg border border-border/60 bg-muted/30 px-2 py-1.5">
                          <p className="text-muted-foreground">value</p>
                          <p className="tabular-nums text-foreground">{formatMetric(item.actual_value)}</p>
                        </div>
                      </div>
                      <div className="space-y-1.5 md:hidden">
                        <details className="group relative">
                          <summary className="inline-flex list-none cursor-pointer items-center gap-1 rounded-md border border-border/70 bg-background/70 px-2 py-1 text-xs text-foreground transition hover:bg-muted/50 [&::-webkit-details-marker]:hidden">
                            Links
                            <ChevronDown className="h-3 w-3 transition group-open:rotate-180" aria-hidden />
                          </summary>
                          <div className="absolute left-0 top-full z-30 mt-1 w-44 rounded-md border border-border/70 bg-popover p-1 shadow-md">
                            {linkTargets.map((target) => (
                              <Link
                                key={`${item.spec_id}-mobile-${target.label}`}
                                href={target.href}
                                className="block rounded px-2 py-1.5 text-xs text-foreground hover:bg-muted/60"
                              >
                                {target.label}
                              </Link>
                            ))}
                          </div>
                        </details>
                        <div className="inline-flex items-center gap-2 text-xs text-muted-foreground">
                          <span className={`inline-block h-2 w-2 rounded-full ${attentionMeta.dot}`} />
                          {attentionMeta.label}
                        </div>
                      </div>
                    </div>
                  </li>
                );
              })}
              {items.length === 0 ? (
                <li className="rounded-xl border border-border/70 bg-background/45 p-6 text-sm text-muted-foreground">
                  No specs matched this query yet. Try widening filters or clearing search.
                </li>
              ) : null}
            </ul>

            <div className="mt-4 flex items-center justify-between gap-3">
              <Link
                href={buildHref(currentParams, { cursor: Math.max(cursor - limit, 0) })}
                className={`rounded-full border px-4 py-2 text-sm ${
                  cursor > 0
                    ? "border-border/70 text-foreground hover:bg-muted/50"
                    : "pointer-events-none border-border/40 text-muted-foreground/50"
                }`}
              >
                Previous
              </Link>
              <span className="text-xs text-muted-foreground">
                showing {formatCompactNumber(pagination.returned)} of {formatCompactNumber(summary.total)}
              </span>
              <Link
                href={buildHref(currentParams, { cursor: pagination.next_cursor })}
                className={`rounded-full border px-4 py-2 text-sm ${
                  pagination.has_more && pagination.next_cursor
                    ? "border-border/70 text-foreground hover:bg-muted/50"
                    : "pointer-events-none border-border/40 text-muted-foreground/50"
                }`}
              >
                Next
              </Link>
            </div>
          </article>

          {view === "focus" ? null : (
            <aside className="space-y-4">
              <section className="rounded-2xl border border-border/70 bg-card/60 p-5">
                <h2 className="text-lg font-semibold">Where Spec Attention Helps Most</h2>
                <div className="mt-3 space-y-3">
                  {focusSpecs.map((item) => {
                    const lift = Math.max(item.value_gap, item.attention_score);
                    return (
                      <div key={item.spec_id} className="rounded-xl border border-border/70 bg-background/45 p-3">
                        <p className="text-base font-semibold">{item.title}</p>
                        <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
                          {item.summary || "Expected lift from clearer implementation and contributor ownership."}
                        </p>
                        <div className="mt-2 flex items-center justify-between text-sm">
                          <p className="font-medium text-primary">+{formatMetric(lift)} potential lift</p>
                          <Link
                            href={item.links.web_detail_path}
                            className="inline-flex items-center gap-1 text-foreground underline-offset-2 hover:underline"
                          >
                            Focus
                            <ChevronRight className="h-3.5 w-3.5" aria-hidden />
                          </Link>
                        </div>
                      </div>
                    );
                  })}
                  {focusSpecs.length === 0 ? (
                    <p className="rounded-xl border border-border/70 bg-background/45 p-3 text-sm text-muted-foreground">
                      No focus specs yet. Try removing filters.
                    </p>
                  ) : null}
                </div>
              </section>

              <section className="rounded-2xl border border-border/70 bg-card/60 p-5">
                <h2 className="text-lg font-semibold">Registry Pulse</h2>
                <p className="mt-1 text-sm text-muted-foreground">Activity trend from current spec feed</p>
                <div className="mt-3 rounded-xl border border-border/70 bg-background/45 p-3">
                  <svg viewBox="0 0 260 72" className="h-20 w-full" preserveAspectRatio="none" aria-hidden>
                    <path d={pulsePath} fill="none" stroke="hsl(var(--primary))" strokeWidth="2.5" strokeLinecap="round" />
                  </svg>
                  <p className="mt-2 text-xs text-muted-foreground">
                    {formatCompactNumber(summary.total)} specs • {formatCompactNumber(linkedCount)} linked •{" "}
                    {formatCompactNumber(measuredCount)} measured
                  </p>
                </div>
              </section>
            </aside>
          )}
        </section>

        <section className="rounded-xl border border-border/70 bg-card/50 px-4 py-3 text-xs text-muted-foreground">
          <div className="flex flex-wrap items-center gap-4">
            {Object.entries(STATE_META).map(([key, meta]) => {
              const Icon = meta.icon;
              return (
                <span key={key} className="inline-flex items-center gap-1.5">
                  <Icon className={`h-3.5 w-3.5 ${meta.subtleTone}`} aria-hidden />
                  {meta.label}
                </span>
              );
            })}
          </div>
        </section>
      </div>
    </main>
  );
}
