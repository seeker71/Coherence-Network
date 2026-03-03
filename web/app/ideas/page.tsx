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
import { UI_RUNTIME_SUMMARY_WINDOW } from "@/lib/egress";

type IdeaCardItem = {
  idea_id: string;
  title: string;
  subtitle: string;
  state: "none" | "spec" | "implemented" | "validated" | "measured";
  attention_level: "none" | "low" | "medium" | "high";
  attention_score: number;
  attention_reason?: string | null;
  value_gap: number;
};

type PaginationInfo = {
  total: number;
  limit: number;
  offset: number;
  returned: number;
  has_more: boolean;
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
  pagination?: PaginationInfo;
};

type IdeasSearchParams = Promise<{
  page?: string | string[];
  page_size?: string | string[];
}>;

const DEFAULT_PAGE_SIZE = 25;
const MAX_PAGE_SIZE = 100;

export const revalidate = 90;

function parsePositiveInt(raw: string | string[] | undefined, fallback: number): number {
  const value = Array.isArray(raw) ? raw[0] : raw;
  const parsed = Number.parseInt((value || "").trim(), 10);
  if (!Number.isFinite(parsed) || parsed < 1) return fallback;
  return parsed;
}

async function loadIdeas(limit: number, offset: number): Promise<IdeasResponse> {
  const API = getApiBase();
  const params = new URLSearchParams({
    limit: String(Math.max(1, Math.min(limit, MAX_PAGE_SIZE))),
    offset: String(Math.max(0, offset)),
  });
  const res = await fetch(`${API}/api/ideas?${params.toString()}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as IdeasResponse;
}

export default async function IdeasPage({ searchParams }: { searchParams: IdeasSearchParams }) {
  const resolved = await searchParams;
  const requestedPageSize = parsePositiveInt(resolved.page_size, DEFAULT_PAGE_SIZE);
  const pageSize = Math.max(1, Math.min(requestedPageSize, MAX_PAGE_SIZE));
  const requestedPage = parsePositiveInt(resolved.page, 1);
  const offset = (requestedPage - 1) * pageSize;

  const data = await loadIdeas(pageSize, offset);
  const ideas = [...data.ideas].sort((a, b) => b.free_energy_score - a.free_energy_score);
  const pagination = data.pagination;
  const currentPage = Math.max(1, Math.floor((pagination?.offset ?? offset) / (pagination?.limit || pageSize)) + 1);
  const hasPrevious = currentPage > 1;
  const hasNext = Boolean(pagination?.has_more) || ideas.length >= pageSize;
  const pageStart = (pagination?.offset ?? offset) + 1;
  const pageEnd = (pagination?.offset ?? offset) + ideas.length;

  const prevHref = hasPrevious
    ? `/ideas?page=${currentPage - 1}&page_size=${pagination?.limit || pageSize}`
    : "/ideas";
  const nextHref = `/ideas?page=${currentPage + 1}&page_size=${pagination?.limit || pageSize}`;

  return (
    <main className="min-h-screen px-4 pb-8 pt-6 sm:px-6 lg:px-8">
      <div className="mx-auto w-full max-w-7xl space-y-4">
        <section className="space-y-1 px-1">
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Ideas In Motion</h1>
          <p className="max-w-3xl text-sm text-muted-foreground sm:text-base">
            A global community bringing ideas to life with care, coherence, and measurable impact.
          </p>
          <p className="text-xs uppercase tracking-[0.12em] text-muted-foreground">
            {scope === "all" ? "Showing all ideas (including system/internal)." : "Showing contributor-actionable ideas."}
          </p>
        </section>

      <h1 className="text-2xl font-bold">Ideas</h1>
      <p className="text-muted-foreground">Paginated `GET /api/ideas` with direct links to full idea detail.</p>

      <section className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
        <div className="rounded border p-3">
          <p className="text-muted-foreground">Total ideas</p>
          <p className="text-lg font-semibold">{data.summary.total_ideas}</p>
        </div>
        <div className="rounded border p-3">
          <p className="text-muted-foreground">Actual value</p>
          <p className="text-lg font-semibold">{data.summary.total_actual_value}</p>
        </div>
        <div className="rounded border p-3">
          <p className="text-muted-foreground">Value gap</p>
          <p className="text-lg font-semibold">{data.summary.total_value_gap}</p>
        </div>
      </section>

      <section className="rounded border p-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
          <p>
            Showing {ideas.length > 0 ? `${pageStart}-${pageEnd}` : "0"} of {pagination?.total ?? data.summary.total_ideas}
            {" | "}
            page {currentPage}
          </p>
          <div className="flex gap-3">
            {hasPrevious ? (
              <Link href={prevHref} className="underline hover:text-foreground">
                Previous
              </Link>
            ) : (
              <span className="opacity-50">Previous</span>
            )}
            {hasNext ? (
              <Link href={nextHref} className="underline hover:text-foreground">
                Next
              </Link>
            ) : (
              <span className="opacity-50">Next</span>
            )}
          </div>
        </div>

        <ul className="space-y-2">
          {ideas.map((idea) => (
            <li key={idea.id} className="rounded border p-3 space-y-1">
              <div className="flex justify-between gap-3">
                <Link href={`/ideas/${encodeURIComponent(idea.id)}`} className="font-medium hover:underline">
                  {idea.name}
                </Link>
                <span className="text-muted-foreground">{idea.manifestation_status}</span>
              </div>
              <p className="text-sm text-muted-foreground">{idea.id}</p>
              <p className="text-sm">{idea.description}</p>
              <p className="text-sm text-muted-foreground">
                free_energy {idea.free_energy_score.toFixed(2)} | value_gap {idea.value_gap.toFixed(2)} | cost_est {idea.estimated_cost}
              </p>
            </li>
          ))}
          {ideas.length === 0 ? <li className="text-muted-foreground">No ideas found for this page.</li> : null}
        </ul>
      </section>
    </main>
  );
}
