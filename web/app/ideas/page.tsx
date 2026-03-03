import {
  Activity,
  ArrowUpDown,
  BadgeCheck,
  BookOpen,
  ChevronRight,
  Circle,
  Cog,
  LayoutGrid,
  Link2,
  Search,
  SlidersHorizontal,
  Sparkles,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";

import { getApiBase } from "@/lib/api";
import { buildFlowSearchParams } from "@/lib/egress";
import { fetchJsonOrNull } from "@/lib/fetch";

type IdeaWithScore = {
  id: string;
  name: string;
  description: string;
  manifestation_status: string;
  free_energy_score: number;
  value_gap: number;
};

type IdeasResponse = {
  ideas: IdeaWithScore[];
  summary: {
    total_ideas: number;
    validated_ideas: number;
    unvalidated_ideas: number;
    total_potential_value: number;
    total_actual_value: number;
    total_value_gap: number;
  };
};

type ValidationCounts = {
  pass: number;
  fail: number;
  pending: number;
};

type FlowItem = {
  idea_id: string;
  idea_name: string;
  idea_classification?: {
    internal?: boolean;
    actionable?: boolean;
  };
  spec: {
    tracked: boolean;
    count: number;
    spec_ids: string[];
  };
  implementation: {
    tracked: boolean;
    lineage_link_count: number;
    runtime_events_count: number;
    runtime_cost_estimate: number;
  };
  validation: {
    tracked: boolean;
    local: ValidationCounts;
    ci: ValidationCounts;
    deploy: ValidationCounts;
    e2e: ValidationCounts;
  };
  contributions: {
    tracked: boolean;
    measured_value_total: number;
    usage_events_count: number;
  };
  interdependencies: {
    blocked: boolean;
    blocking_stage: string | null;
    unblock_priority_score: number;
  };
  idea_signals: {
    value_gap: number;
    potential_value: number;
    actual_value: number;
    estimated_cost: number;
    confidence: number;
  };
};

type FlowResponse = {
  summary: {
    ideas: number;
    with_spec: number;
    with_implementation: number;
    with_validation: number;
    with_contributions: number;
    blocked_ideas: number;
  };
  items: FlowItem[];
};

type IdeasSearchParams = Promise<{
  page?: string | string[];
  page_size?: string | string[];
  q?: string | string[];
  stage?: string | string[];
  manifestation?: string | string[];
  sort?: string | string[];
  actionable_only?: string | string[];
}>;

type DisplayRow = {
  id: string;
  name: string;
  description: string;
  manifestation: string;
  freeEnergyScore: number | null;
  valueGap: number;
  isInIdeaRegistry: boolean;
  flow: FlowItem;
};

const DEFAULT_PAGE_SIZE = 24;
const MAX_PAGE_SIZE = 100;

export const revalidate = 90;

function parsePositiveInt(raw: string | string[] | undefined, fallback: number): number {
  const value = Array.isArray(raw) ? raw[0] : raw;
  const parsed = Number.parseInt((value || "").trim(), 10);
  if (!Number.isFinite(parsed) || parsed < 1) return fallback;
  return parsed;
}

function parseSingle(raw: string | string[] | undefined, fallback = ""): string {
  const value = Array.isArray(raw) ? raw[0] : raw;
  const text = String(value || "").trim();
  return text || fallback;
}

function parseBool(raw: string | string[] | undefined): boolean {
  const value = parseSingle(raw).toLowerCase();
  return value === "1" || value === "true" || value === "yes" || value === "on";
}

function humanizeMachineText(value: string): string {
  const normalized = value.replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim();
  if (!normalized) return value;
  return normalized
    .split(" ")
    .map((chunk) => chunk.charAt(0).toUpperCase() + chunk.slice(1))
    .join(" ");
}

function formatNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "0";
  return Number(value).toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function inferManifestation(flow: FlowItem): string {
  const hasValidationPass =
    (flow.validation.local.pass || 0) +
      (flow.validation.ci.pass || 0) +
      (flow.validation.deploy.pass || 0) +
      (flow.validation.e2e.pass || 0) >
    0;
  if (flow.validation.tracked && hasValidationPass) return "validated";
  if (flow.implementation.tracked || flow.spec.tracked) return "partial";
  return "none";
}

function isMeasured(flow: FlowItem): boolean {
  return (
    flow.contributions.tracked ||
    flow.contributions.measured_value_total > 0 ||
    flow.implementation.runtime_events_count > 0
  );
}

function stageMatches(stage: string, row: DisplayRow): boolean {
  const flow = row.flow;
  if (!stage || stage === "all") return true;
  if (stage === "needs_spec") return !flow.spec.tracked;
  if (stage === "spec") return flow.spec.tracked;
  if (stage === "implementation") return flow.implementation.tracked;
  if (stage === "validation") return flow.validation.tracked;
  if (stage === "measurement") return isMeasured(flow);
  if (stage === "blocked") return flow.interdependencies.blocked;
  return true;
}

function compareRows(sort: string, a: DisplayRow, b: DisplayRow): number {
  if (sort === "name_asc") return a.name.localeCompare(b.name);
  if (sort === "value_gap_desc") return b.valueGap - a.valueGap;
  if (sort === "roi_desc") return b.flow.contributions.measured_value_total - a.flow.contributions.measured_value_total;
  if (sort === "energy_desc") return (b.freeEnergyScore || 0) - (a.freeEnergyScore || 0);
  return b.flow.interdependencies.unblock_priority_score - a.flow.interdependencies.unblock_priority_score;
}

function buildIdeasHref(input: {
  page: number;
  pageSize: number;
  q: string;
  stage: string;
  manifestation: string;
  sort: string;
  actionableOnly: boolean;
}): string {
  const params = new URLSearchParams();
  params.set("page", String(Math.max(1, input.page)));
  params.set("page_size", String(Math.max(1, Math.min(input.pageSize, MAX_PAGE_SIZE))));
  if (input.q) params.set("q", input.q);
  if (input.stage && input.stage !== "all") params.set("stage", input.stage);
  if (input.manifestation && input.manifestation !== "all") params.set("manifestation", input.manifestation);
  if (input.sort && input.sort !== "priority_desc") params.set("sort", input.sort);
  if (input.actionableOnly) params.set("actionable_only", "1");
  return `/ideas?${params.toString()}`;
}

async function loadIdeas(): Promise<IdeasResponse> {
  const API = getApiBase();
  const params = new URLSearchParams({
    limit: "500",
    offset: "0",
    include_internal: "true",
  });
  const payload = await fetchJsonOrNull<IdeasResponse>(`${API}/api/ideas?${params.toString()}`, {}, 7000);
  return (
    payload || {
      ideas: [],
      summary: {
        total_ideas: 0,
        validated_ideas: 0,
        unvalidated_ideas: 0,
        total_potential_value: 0,
        total_actual_value: 0,
        total_value_gap: 0,
      },
    }
  );
}

async function loadFlow(): Promise<FlowResponse> {
  const API = getApiBase();
  const params = buildFlowSearchParams();
  params.set("include_internal_ideas", "true");
  const payload = await fetchJsonOrNull<FlowResponse>(`${API}/api/inventory/flow?${params.toString()}`, {}, 9000);
  return (
    payload || {
      summary: {
        ideas: 0,
        with_spec: 0,
        with_implementation: 0,
        with_validation: 0,
        with_contributions: 0,
        blocked_ideas: 0,
      },
      items: [],
    }
  );
}

export default async function IdeasPage({ searchParams }: { searchParams: IdeasSearchParams }) {
  const resolved = await searchParams;
  const currentPage = parsePositiveInt(resolved.page, 1);
  const requestedPageSize = parsePositiveInt(resolved.page_size, DEFAULT_PAGE_SIZE);
  const pageSize = Math.max(1, Math.min(requestedPageSize, MAX_PAGE_SIZE));
  const query = parseSingle(resolved.q).toLowerCase();
  const stage = parseSingle(resolved.stage, "all");
  const manifestation = parseSingle(resolved.manifestation, "all").toLowerCase();
  const sort = parseSingle(resolved.sort, "priority_desc");
  const actionableOnly = parseBool(resolved.actionable_only);

  const [ideasData, flowData] = await Promise.all([loadIdeas(), loadFlow()]);
  const byIdeaId = new Map(ideasData.ideas.map((idea) => [idea.id, idea]));

  const merged: DisplayRow[] = flowData.items.map((flowItem) => {
    const idea = byIdeaId.get(flowItem.idea_id);
    const rawName = idea?.name || flowItem.idea_name || flowItem.idea_id;
    const friendlyName = rawName.includes("_") ? humanizeMachineText(rawName) : rawName;
    const rawDescription = idea?.description || "";
    return {
      id: flowItem.idea_id,
      name: friendlyName,
      description: rawDescription,
      manifestation: String(idea?.manifestation_status || inferManifestation(flowItem)).toLowerCase(),
      freeEnergyScore: typeof idea?.free_energy_score === "number" ? idea.free_energy_score : null,
      valueGap: typeof idea?.value_gap === "number" ? idea.value_gap : flowItem.idea_signals.value_gap,
      isInIdeaRegistry: Boolean(idea),
      flow: flowItem,
    };
  });

  const filtered = merged
    .filter((row) => {
      if (actionableOnly && row.flow.idea_classification?.actionable === false) return false;
      if (query) {
        const haystack = `${row.id} ${row.name} ${row.description}`.toLowerCase();
        if (!haystack.includes(query)) return false;
      }
      if (manifestation !== "all" && row.manifestation !== manifestation) return false;
      return stageMatches(stage, row);
    })
    .sort((a, b) => compareRows(sort, a, b));

  const totalFiltered = filtered.length;
  const totalPages = Math.max(1, Math.ceil(totalFiltered / pageSize));
  const clampedPage = Math.min(currentPage, totalPages);
  const startIndex = (clampedPage - 1) * pageSize;
  const pageItems = filtered.slice(startIndex, startIndex + pageSize);
  const pageStart = totalFiltered === 0 ? 0 : startIndex + 1;
  const pageEnd = startIndex + pageItems.length;

  const counted = filtered.reduce(
    (acc, row) => {
      if (row.flow.spec.tracked) acc.spec += 1;
      if (row.flow.implementation.tracked) acc.implementation += 1;
      if (row.flow.validation.tracked) acc.validation += 1;
      if (isMeasured(row.flow)) acc.measured += 1;
      return acc;
    },
    { spec: 0, implementation: 0, validation: 0, measured: 0 },
  );

  const prevHref = buildIdeasHref({
    page: Math.max(1, clampedPage - 1),
    pageSize,
    q: parseSingle(resolved.q),
    stage,
    manifestation,
    sort,
    actionableOnly,
  });
  const nextHref = buildIdeasHref({
    page: clampedPage + 1,
    pageSize,
    q: parseSingle(resolved.q),
    stage,
    manifestation,
    sort,
    actionableOnly,
  });

  return (
    <main className="min-h-screen p-8 max-w-6xl mx-auto space-y-6">
      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Home
        </Link>
        <Link href="/portfolio" className="text-muted-foreground hover:text-foreground">
          Portfolio
        </Link>
        <Link href="/flow" className="text-muted-foreground hover:text-foreground">
          Flow
        </Link>
        <Link href="/specs" className="text-muted-foreground hover:text-foreground">
          Specs
        </Link>
        <Link href="/usage" className="text-muted-foreground hover:text-foreground">
          Usage
        </Link>
      </div>

      <div className="space-y-2">
        <h1 className="text-2xl font-bold">Ideas</h1>
        <p className="text-muted-foreground">
          Unified view of idea stage coverage: spec, implementation, validation, and measurement.
        </p>
      </div>

      <section className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
        <div className="rounded border p-3">
          <p className="text-muted-foreground">Ideas visible</p>
          <p className="text-lg font-semibold">
            {totalFiltered} / {flowData.summary.ideas}
          </p>
        </div>
        <div className="rounded border p-3">
          <p className="text-muted-foreground">With spec</p>
          <p className="text-lg font-semibold">{counted.spec}</p>
        </div>
        <div className="rounded border p-3">
          <p className="text-muted-foreground">Implemented</p>
          <p className="text-lg font-semibold">{counted.implementation}</p>
        </div>
        <div className="rounded border p-3">
          <p className="text-muted-foreground">Validated</p>
          <p className="text-lg font-semibold">{counted.validation}</p>
        </div>
        <div className="rounded border p-3">
          <p className="text-muted-foreground">Measured</p>
          <p className="text-lg font-semibold">{counted.measured}</p>
        </div>
      </section>

      <section className="rounded border p-4 space-y-2 text-sm">
        <p className="font-medium">Manifestation status meanings</p>
        <p className="text-muted-foreground">
          <span className="font-medium text-foreground">none</span>: no material implementation evidence yet.
        </p>
        <p className="text-muted-foreground">
          <span className="font-medium text-foreground">partial</span>: some spec or implementation progress exists, but end-to-end validation is incomplete.
        </p>
        <p className="text-muted-foreground">
          <span className="font-medium text-foreground">validated</span>: validated through passing validation signals and tracked as validated in the idea registry.
        </p>
      </section>

      <section className="rounded border p-4 space-y-3">
        <form className="grid gap-3 md:grid-cols-6" method="GET">
          <input
            type="text"
            name="q"
            defaultValue={parseSingle(resolved.q)}
            placeholder="Search idea name or id"
            className="md:col-span-2 rounded border px-3 py-2 bg-background"
          />
          <select name="stage" defaultValue={stage} className="rounded border px-3 py-2 bg-background">
            <option value="all">All stages</option>
            <option value="needs_spec">Needs spec</option>
            <option value="spec">Has spec</option>
            <option value="implementation">Implemented</option>
            <option value="validation">Validated</option>
            <option value="measurement">Measured</option>
            <option value="blocked">Blocked</option>
          </select>
          <select name="manifestation" defaultValue={manifestation} className="rounded border px-3 py-2 bg-background">
            <option value="all">All manifestation states</option>
            <option value="none">none</option>
            <option value="partial">partial</option>
            <option value="validated">validated</option>
          </select>
          <select name="sort" defaultValue={sort} className="rounded border px-3 py-2 bg-background">
            <option value="priority_desc">Sort by unblock priority</option>
            <option value="value_gap_desc">Sort by value gap</option>
            <option value="roi_desc">Sort by measured ROI</option>
            <option value="energy_desc">Sort by free energy</option>
            <option value="name_asc">Sort by name</option>
          </select>
          <select
            name="page_size"
            defaultValue={String(pageSize)}
            className="rounded border px-3 py-2 bg-background"
          >
            <option value="12">12 / page</option>
            <option value="24">24 / page</option>
            <option value="48">48 / page</option>
            <option value="96">96 / page</option>
          </select>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" name="actionable_only" value="1" defaultChecked={actionableOnly} />
            Actionable only
          </label>
          <div className="flex gap-3 items-center">
            <button type="submit" className="rounded border px-3 py-2 hover:bg-muted">
              Apply
            </button>
            <Link href="/ideas" className="text-muted-foreground hover:text-foreground underline">
              Reset
            </Link>
          </div>
        </form>
      </section>

      <section className="rounded border p-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
          <p>
            Showing {pageStart > 0 ? `${pageStart}-${pageEnd}` : "0"} of {totalFiltered}
            {" | "}page {clampedPage} / {totalPages}
          </p>
          <div className="flex gap-3">
            {clampedPage > 1 ? (
              <Link href={prevHref} className="underline hover:text-foreground">
                Previous
              </Link>
            ) : (
              <span className="opacity-50">Previous</span>
            )}
            {clampedPage < totalPages ? (
              <Link href={nextHref} className="underline hover:text-foreground">
                Next
              </Link>
            ) : (
              <span className="opacity-50">Next</span>
            )}
          </div>
        </div>

        <ul className="space-y-2">
          {pageItems.map((row) => {
            const measured = isMeasured(row.flow);
            return (
              <li key={row.id} className="rounded border p-3 space-y-2">
                <div className="flex flex-wrap justify-between gap-3">
                  {row.isInIdeaRegistry ? (
                    <Link href={`/ideas/${encodeURIComponent(row.id)}`} className="font-medium hover:underline">
                      {row.name}
                    </Link>
                  ) : (
                    <p className="font-medium">{row.name}</p>
                  )}
                  <div className="flex gap-2 text-xs">
                    <span className="rounded border px-2 py-1">{row.manifestation}</span>
                    <span className="rounded border px-2 py-1">{row.flow.interdependencies.blocked ? "blocked" : "ready"}</span>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">{row.id}</p>
                {row.description ? <p className="text-sm">{row.description}</p> : null}
                <p className="text-sm text-muted-foreground">
                  Spec {row.flow.spec.tracked ? "yes" : "no"} | Implementation {row.flow.implementation.tracked ? "yes" : "no"} | Validation{" "}
                  {row.flow.validation.tracked ? "yes" : "no"} | Measurement {measured ? "yes" : "no"}
                </p>
                <p className="text-sm text-muted-foreground">
                  Blocking stage {row.flow.interdependencies.blocking_stage || "none"} | Unblock priority{" "}
                  {formatNumber(row.flow.interdependencies.unblock_priority_score)} | Specs {row.flow.spec.count}
                </p>
                <p className="text-sm text-muted-foreground">
                  Measured ROI {formatNumber(row.flow.contributions.measured_value_total)} | Runtime events{" "}
                  {row.flow.implementation.runtime_events_count} | Value gap {formatNumber(row.valueGap)} | Free energy{" "}
                  {formatNumber(row.freeEnergyScore)}
                </p>
                {!row.isInIdeaRegistry ? (
                  <p className="text-xs text-muted-foreground">
                    This idea is derived from traceability evidence and is not yet represented in the idea registry.
                  </p>
                ) : null}
              </li>
            );
          })}
          {pageItems.length === 0 ? <li className="text-muted-foreground">No ideas found for this filter set.</li> : null}
        </ul>
      </section>
    </main>
  );
}
