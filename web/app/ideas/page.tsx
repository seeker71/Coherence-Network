import Link from "next/link";

import { getApiBase } from "@/lib/api";
import { UI_RUNTIME_SUMMARY_WINDOW } from "@/lib/egress";

type IdeaCardItem = {
  idea_id: string;
  title: string;
  subtitle: string;
  state: "none" | "spec" | "implemented" | "validated" | "measured";
  attention_level: "none" | "low" | "medium" | "high";
  attention_score: number;
  value_gap: number;
  measured_roi: number;
  measured_value: number;
  spec_count: number;
  implementation_ref_count: number;
  links: {
    web_detail_path: string;
    web_spec_path?: string | null;
  };
};

type IdeaCardsResponse = {
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
    cursor: string;
    limit: number;
    include_internal_ideas: boolean;
    min_roi: number | null;
    min_value_gap: number | null;
  };
  items: IdeaCardItem[];
};

type IdeaSearchParams = Promise<Record<string, string | string[] | undefined>>;

const DEFAULT_LIMIT = 50;
const MAX_LIMIT = 200;
const FILTER_STATES = ["all", "spec", "implemented", "validated", "measured"] as const;
const ATTENTION_LEVELS = ["all", "none", "low", "medium", "high"] as const;
const SORT_OPTIONS = ["attention_desc", "roi_desc", "gap_desc", "state_desc", "name_asc"] as const;
const VIEW_OPTIONS = ["list", "focus"] as const;

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
  return query ? `/ideas?${query}` : "/ideas";
}

function stateIcon(state: IdeaCardItem["state"]): string {
  switch (state) {
    case "measured":
      return "◒";
    case "validated":
      return "◍";
    case "implemented":
      return "◈";
    case "spec":
      return "◧";
    default:
      return "◌";
  }
}

function stateBadgeClass(state: IdeaCardItem["state"]): string {
  switch (state) {
    case "measured":
      return "bg-emerald-500/20 text-emerald-200 border-emerald-400/30";
    case "validated":
      return "bg-teal-500/20 text-teal-200 border-teal-400/30";
    case "implemented":
      return "bg-sky-500/20 text-sky-200 border-sky-400/30";
    case "spec":
      return "bg-indigo-500/20 text-indigo-200 border-indigo-400/30";
    default:
      return "bg-slate-500/20 text-slate-200 border-slate-400/30";
  }
}

function attentionDotClass(level: IdeaCardItem["attention_level"]): string {
  switch (level) {
    case "high":
      return "bg-rose-300";
    case "medium":
      return "bg-amber-300";
    case "low":
      return "bg-cyan-300";
    default:
      return "bg-emerald-300";
  }
}

function buildSparklinePath(values: number[]): string {
  const points = values.length > 1 ? values : [0, 1, 0.5, 1.2, 0.8, 1.6, 1.9];
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = Math.max(max - min, 0.0001);
  const width = 260;
  const height = 76;

  return points
    .map((value, index) => {
      const x = (index / Math.max(points.length - 1, 1)) * width;
      const y = height - ((value - min) / span) * height;
      return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

async function loadIdeaCards(params: {
  q: string;
  state: string;
  attention: string;
  sort: string;
  cursor: number;
  limit: number;
  minRoi: number | null;
  minValueGap: number | null;
  includeInternalIdeas: boolean;
}): Promise<IdeaCardsResponse> {
  const API = getApiBase();
  const search = new URLSearchParams({
    q: params.q,
    state: params.state,
    attention: params.attention,
    sort: params.sort,
    cursor: String(params.cursor),
    limit: String(params.limit),
    include_internal_ideas: params.includeInternalIdeas ? "true" : "false",
    runtime_window_seconds: String(UI_RUNTIME_SUMMARY_WINDOW),
  });
  if (params.minRoi !== null) search.set("min_roi", String(params.minRoi));
  if (params.minValueGap !== null) search.set("min_value_gap", String(params.minValueGap));

  const response = await fetch(`${API}/api/ideas/cards?${search.toString()}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Failed to load ideas cards (${response.status})`);
  }
  return (await response.json()) as IdeaCardsResponse;
}

export default async function IdeasPage({ searchParams }: { searchParams: IdeaSearchParams }) {
  const resolved = await searchParams;
  const q = readParam(resolved.q);
  const state = parseEnum(readParam(resolved.state, "all"), FILTER_STATES, "all");
  const attention = parseEnum(readParam(resolved.attention, "all"), ATTENTION_LEVELS, "all");
  const sort = parseEnum(readParam(resolved.sort, "attention_desc"), SORT_OPTIONS, "attention_desc");
  const view = parseEnum(readParam(resolved.view, "list"), VIEW_OPTIONS, "list");
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
  if (cursor > 0) currentParams.set("cursor", String(cursor));
  if (limit !== DEFAULT_LIMIT) currentParams.set("limit", String(limit));
  if (minRoi !== null) currentParams.set("min_roi", String(minRoi));
  if (minValueGap !== null) currentParams.set("min_value_gap", String(minValueGap));

  const payload = await loadIdeaCards({
    q,
    state,
    attention,
    sort,
    cursor,
    limit,
    minRoi,
    minValueGap,
    includeInternalIdeas: true,
  });

  const items = payload.items;
  const summary = payload.summary;
  const pagination = payload.pagination;

  const validatedCount =
    Number(summary.state_counts.validated || 0) + Number(summary.state_counts.measured || 0);
  const measuredCount = Number(summary.state_counts.measured || 0);
  const needsAttentionCount = Number(summary.needs_attention || 0);

  const startIndex = Math.min(cursor + 1, Math.max(summary.total, 1));
  const endIndex = Math.min(cursor + pagination.returned, summary.total);

  const focusIdeas = [...items]
    .sort((a, b) => b.attention_score - a.attention_score)
    .slice(0, 3);
  const pulsePath = buildSparklinePath(
    items.slice(0, 7).map((item) => Math.max(item.attention_score, item.value_gap * 0.8, item.measured_roi)),
  );

  const stateCycleNext = FILTER_STATES[(FILTER_STATES.indexOf(state) + 1) % FILTER_STATES.length];
  const sortCycleNext = SORT_OPTIONS[(SORT_OPTIONS.indexOf(sort) + 1) % SORT_OPTIONS.length];
  const viewCycleNext = VIEW_OPTIONS[(VIEW_OPTIONS.indexOf(view) + 1) % VIEW_OPTIONS.length];

  const clearCursor = { cursor: null } as const;

  return (
    <main className="relative min-h-screen overflow-hidden px-4 pb-8 pt-8 sm:px-6 lg:px-10">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_10%_8%,rgba(198,131,78,0.28),transparent_34%),radial-gradient(circle_at_72%_12%,rgba(86,169,188,0.2),transparent_36%),radial-gradient(circle_at_86%_72%,rgba(99,176,154,0.18),transparent_30%),linear-gradient(140deg,#081020_14%,#0e1a2d_56%,#111b2b_100%)]" />
      <div className="mx-auto w-full max-w-[1600px] space-y-4 text-slate-100">
        <section className="space-y-2 px-1 py-2">
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Ideas In Motion</h1>
          <p className="max-w-3xl text-sm text-slate-200/80 sm:text-base">
            A global community bringing ideas to life with care, coherence, and measurable impact.
          </p>
        </section>

        <section className="rounded-[2rem] border border-cyan-200/20 bg-cyan-950/35 p-4 shadow-[0_24px_80px_-34px_rgba(21,170,189,0.6)] backdrop-blur-xl sm:p-6">
          <div className="grid gap-3 xl:grid-cols-[repeat(4,minmax(0,1fr))_1.75fr]">
            <div className="rounded-3xl border border-white/5 bg-slate-900/30 p-5">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-300/80">Ideas in the field</p>
              <p className="mt-1 text-3xl font-semibold">{formatCompactNumber(summary.total)}</p>
            </div>
            <div className="rounded-3xl border border-white/5 bg-slate-900/30 p-5">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-300/80">Validated</p>
              <p className="mt-1 text-3xl font-semibold">{formatCompactNumber(validatedCount)}</p>
            </div>
            <div className="rounded-3xl border border-white/5 bg-slate-900/30 p-5">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-300/80">Actively measured</p>
              <p className="mt-1 text-3xl font-semibold">{formatCompactNumber(measuredCount)}</p>
            </div>
            <div className="rounded-3xl border border-white/5 bg-slate-900/30 p-5">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-300/80">Ready for attention</p>
              <p className="mt-1 text-3xl font-semibold">{formatCompactNumber(needsAttentionCount)}</p>
            </div>
            <div className="rounded-3xl border border-white/5 bg-slate-900/30 p-5">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-300/80">Collective focus this cycle</p>
              <p className="mt-2 text-lg font-semibold text-cyan-100">
                {focusIdeas[0] ? `Lift ${focusIdeas[0].title} from ${focusIdeas[0].state} → measured` : "Lift high-potential ideas from implemented → validated"}
              </p>
            </div>
          </div>
        </section>

        <section className="grid gap-3 lg:grid-cols-[1fr_auto_auto_auto]">
          <form action="/ideas" method="get" className="rounded-3xl border border-cyan-100/20 bg-slate-950/45 px-4 py-3 backdrop-blur-xl">
            <input
              type="text"
              name="q"
              defaultValue={q}
              placeholder="Search ideas, specs, places, owners, or questions..."
              className="w-full bg-transparent text-base text-slate-100 outline-none placeholder:text-slate-400"
            />
            <input type="hidden" name="state" value={state} />
            <input type="hidden" name="attention" value={attention} />
            <input type="hidden" name="sort" value={sort} />
            <input type="hidden" name="view" value={view} />
            <input type="hidden" name="limit" value={String(limit)} />
            {minRoi !== null ? <input type="hidden" name="min_roi" value={String(minRoi)} /> : null}
            {minValueGap !== null ? <input type="hidden" name="min_value_gap" value={String(minValueGap)} /> : null}
          </form>
          <Link
            href={buildHref(currentParams, { state: stateCycleNext, ...clearCursor })}
            className="inline-flex min-w-40 items-center justify-center rounded-3xl border border-cyan-100/20 bg-slate-950/45 px-5 text-lg font-medium text-slate-100 transition hover:border-cyan-200/40 hover:bg-slate-900/60"
          >
            Filters
          </Link>
          <Link
            href={buildHref(currentParams, { sort: sortCycleNext, ...clearCursor })}
            className="inline-flex min-w-40 items-center justify-center rounded-3xl border border-cyan-100/20 bg-slate-950/45 px-5 text-lg font-medium text-slate-100 transition hover:border-cyan-200/40 hover:bg-slate-900/60"
          >
            Sort
          </Link>
          <Link
            href={buildHref(currentParams, { view: viewCycleNext, ...clearCursor })}
            className="inline-flex min-w-40 items-center justify-center rounded-3xl border border-cyan-100/20 bg-slate-950/45 px-5 text-lg font-medium text-slate-100 transition hover:border-cyan-200/40 hover:bg-slate-900/60"
          >
            Views
          </Link>
        </section>

        <section className="rounded-3xl border border-cyan-100/20 bg-slate-950/35 px-3 py-3 backdrop-blur-xl sm:px-5">
          <div className="flex flex-wrap items-center gap-2">
            {[
              { label: "All", href: buildHref(currentParams, { state: "all", attention: "all", min_roi: null, min_value_gap: null, ...clearCursor }), active: state === "all" && attention === "all" && minRoi === null },
              { label: "Spec", href: buildHref(currentParams, { state: "spec", ...clearCursor }), active: state === "spec" },
              { label: "Implemented", href: buildHref(currentParams, { state: "implemented", ...clearCursor }), active: state === "implemented" },
              { label: "Validated", href: buildHref(currentParams, { state: "validated", ...clearCursor }), active: state === "validated" },
              { label: "Measured", href: buildHref(currentParams, { state: "measured", ...clearCursor }), active: state === "measured" },
              { label: "Needs Attention", href: buildHref(currentParams, { attention: "high", ...clearCursor }), active: attention === "high" },
              { label: "ROI > 10", href: buildHref(currentParams, { min_roi: 10, ...clearCursor }), active: minRoi !== null && minRoi >= 10 },
            ].map((chip) => (
              <Link
                key={chip.label}
                href={chip.href}
                className={`inline-flex min-w-28 items-center justify-center rounded-full border px-4 py-2 text-lg font-medium transition ${
                  chip.active
                    ? "border-emerald-300/35 bg-emerald-500/20 text-emerald-100"
                    : "border-cyan-100/20 bg-slate-900/30 text-slate-200 hover:border-cyan-100/45"
                }`}
              >
                {chip.label}
              </Link>
            ))}
            <div className="ml-auto px-2 text-lg text-slate-300">
              {startIndex}-{endIndex} of {formatCompactNumber(summary.total)}
            </div>
          </div>
        </section>

        <section className={view === "focus" ? "space-y-4" : "grid gap-4 xl:grid-cols-[2.1fr_0.95fr]"}>
          <article className="rounded-[1.9rem] border border-cyan-100/20 bg-slate-950/45 p-4 backdrop-blur-xl sm:p-6">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-3xl font-semibold tracking-tight">Active Ideas</h2>
              <div className="flex items-center gap-6 text-xl text-slate-300/90">
                <span>{"∞"} links</span>
                <span>⚡ gap</span>
                <span>↗ roi</span>
                <span>• attention</span>
              </div>
            </div>

            <ul className={view === "focus" ? "grid gap-3 sm:grid-cols-2 xl:grid-cols-3" : "space-y-3"}>
              {items.map((item) => {
                const linksCount = Math.max(item.spec_count, 0) + Math.max(item.implementation_ref_count, 0);
                return (
                  <li
                    key={item.idea_id}
                    className="rounded-3xl border border-cyan-100/20 bg-slate-900/55 p-4 shadow-[0_16px_28px_-26px_rgba(110,220,212,0.95)]"
                  >
                    <div className="flex items-start gap-3">
                      <div className={`mt-1 inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border text-lg ${stateBadgeClass(item.state)}`}>
                        {stateIcon(item.state)}
                      </div>
                      <div className="min-w-0 flex-1">
                        <h3 className="truncate text-2xl font-semibold text-slate-100">{item.title}</h3>
                        <p className="mt-1 line-clamp-2 text-lg text-slate-300/90">
                          {item.subtitle || "No description yet. Add context to unlock better implementation and ROI decisions."}
                        </p>
                      </div>
                    </div>

                    <div className="mt-4 grid grid-cols-4 gap-2 text-right text-lg text-slate-200/90">
                      <div>
                        <p className="text-slate-400">links</p>
                        <p className="font-medium">{formatCompactNumber(linksCount)}</p>
                      </div>
                      <div>
                        <p className="text-slate-400">gap</p>
                        <p className="font-medium">{formatMetric(item.value_gap)}</p>
                      </div>
                      <div>
                        <p className="text-slate-400">roi</p>
                        <p className="font-medium">{formatMetric(item.measured_roi)}</p>
                      </div>
                      <div>
                        <p className="text-slate-400">attention</p>
                        <div className="flex items-center justify-end gap-2">
                          <span className={`inline-block h-3.5 w-3.5 rounded-full ${attentionDotClass(item.attention_level)}`} />
                          <span className="capitalize">{item.attention_level === "none" ? "on track" : item.attention_level}</span>
                        </div>
                      </div>
                    </div>

                    <div className="mt-3 flex items-center justify-between text-lg">
                      <span className="text-slate-400">{item.state}</span>
                      <Link href={item.links.web_detail_path} className="font-medium text-cyan-200 hover:text-cyan-100">
                        Open →
                      </Link>
                    </div>
                  </li>
                );
              })}
              {items.length === 0 ? (
                <li className="rounded-3xl border border-cyan-100/20 bg-slate-900/55 p-6 text-lg text-slate-300">
                  No ideas matched this query yet. Try widening filters or clearing search.
                </li>
              ) : null}
            </ul>

            <div className="mt-4 flex items-center justify-between">
              <Link
                href={buildHref(currentParams, { cursor: Math.max(cursor - limit, 0) })}
                className={`rounded-full border px-4 py-2 text-lg ${cursor > 0 ? "border-cyan-100/35 text-slate-100 hover:bg-slate-800/60" : "pointer-events-none border-slate-700/40 text-slate-500"}`}
              >
                Previous
              </Link>
              <Link
                href={buildHref(currentParams, { cursor: pagination.next_cursor })}
                className={`rounded-full border px-4 py-2 text-lg ${pagination.has_more && pagination.next_cursor ? "border-cyan-100/35 text-slate-100 hover:bg-slate-800/60" : "pointer-events-none border-slate-700/40 text-slate-500"}`}
              >
                Next
              </Link>
            </div>
          </article>

          {view === "focus" ? null : (
            <aside className="space-y-4">
              <section className="rounded-[1.9rem] border border-cyan-100/20 bg-slate-950/45 p-5 backdrop-blur-xl">
                <h2 className="text-3xl font-semibold">Where Attention Helps Most</h2>
                <div className="mt-4 space-y-3">
                  {focusIdeas.map((item) => (
                    <div key={item.idea_id} className="rounded-3xl border border-cyan-100/20 bg-slate-900/60 p-4">
                      <p className="text-2xl font-semibold text-slate-100">{item.title}</p>
                      <p className="mt-1 text-lg text-slate-300/85 line-clamp-2">{item.subtitle || "Expected lift from validation confidence."}</p>
                      <div className="mt-3 flex items-center justify-between text-lg">
                        <p className="font-medium text-emerald-200">+{formatMetric(Math.max(item.value_gap, item.attention_score), 1)} lift</p>
                        <Link href={item.links.web_detail_path} className="text-cyan-200 hover:text-cyan-100">
                          Focus →
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              <section className="rounded-[1.9rem] border border-cyan-100/20 bg-slate-950/45 p-5 backdrop-blur-xl">
                <h2 className="text-3xl font-semibold">Community Pulse</h2>
                <p className="mt-1 text-lg text-slate-300/85">Activity across regions (last 7 days)</p>
                <div className="mt-4 rounded-3xl border border-cyan-100/20 bg-slate-900/60 p-4">
                  <svg viewBox="0 0 260 76" className="h-20 w-full" preserveAspectRatio="none" aria-hidden>
                    <path d={pulsePath} fill="none" stroke="rgba(117,214,204,0.95)" strokeWidth="3" strokeLinecap="round" />
                  </svg>
                  <p className="mt-2 text-lg text-slate-300/85">
                    {formatCompactNumber(summary.total)} regions active • {formatCompactNumber(validatedCount)} validated ideas • {formatCompactNumber(measuredCount)} measured now
                  </p>
                </div>
              </section>
            </aside>
          )}
        </section>

        <section className="rounded-2xl border border-cyan-100/20 bg-slate-950/30 px-4 py-3 text-lg text-slate-300 backdrop-blur-xl">
          State icons: <span className="ml-2">◧ spec</span> <span className="ml-4">◈ implemented</span>{" "}
          <span className="ml-4">◍ validated</span> <span className="ml-4">◒ measured</span>
        </section>
      </div>
    </main>
  );
}
