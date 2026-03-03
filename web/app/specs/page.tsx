import Link from "next/link";

import { getApiBase } from "@/lib/api";

type SpecRegistryEntry = {
  spec_id: string;
  title: string;
  summary: string;
  potential_value: number;
  actual_value: number;
  estimated_cost: number;
  actual_cost: number;
  value_gap: number;
  cost_gap: number;
  estimated_roi: number;
  actual_roi: number;
  idea_id?: string | null;
  process_summary?: string | null;
  pseudocode_summary?: string | null;
  implementation_summary?: string | null;
  created_by_contributor_id?: string | null;
  updated_by_contributor_id?: string | null;
  updated_at: string;
};

type SpecsSearchParams = Promise<{
  spec_id?: string | string[];
  page?: string | string[];
  page_size?: string | string[];
}>;

const DEFAULT_PAGE_SIZE = 25;
const MAX_PAGE_SIZE = 100;

export const revalidate = 90;

function normalizeValue(raw: string | string[] | undefined): string {
  if (Array.isArray(raw)) return (raw[0] || "").trim();
  return (raw || "").trim();
}

function parsePositiveInt(raw: string | string[] | undefined, fallback: number): number {
  const value = normalizeValue(raw);
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed < 1) return fallback;
  return parsed;
}

async function loadSpecPage(limit: number, offset: number): Promise<{ items: SpecRegistryEntry[]; total: number }> {
  const API = getApiBase();
  const params = new URLSearchParams({
    limit: String(Math.max(1, Math.min(limit, MAX_PAGE_SIZE))),
    offset: String(Math.max(0, offset)),
  });
  const response = await fetch(`${API}/api/spec-registry?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  const totalHeader = Number.parseInt(response.headers.get("x-total-count") || "0", 10);
  const items = (await response.json()) as SpecRegistryEntry[];
  return {
    items: Array.isArray(items) ? items : [],
    total: Number.isFinite(totalHeader) ? Math.max(0, totalHeader) : Array.isArray(items) ? items.length : 0,
  };
}

async function loadSingleSpec(specId: string): Promise<SpecRegistryEntry | null> {
  const API = getApiBase();
  const response = await fetch(`${API}/api/spec-registry/${encodeURIComponent(specId)}`);
  if (response.status === 404) return null;
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return (await response.json()) as SpecRegistryEntry;
}

function paginationHref(page: number, pageSize: number): string {
  const safePage = Math.max(1, page);
  return `/specs?page=${safePage}&page_size=${pageSize}`;
}

export default async function SpecsPage({ searchParams }: { searchParams: SpecsSearchParams }) {
  const resolved = await searchParams;
  const specFilter = normalizeValue(resolved.spec_id);
  const requestedPageSize = parsePositiveInt(resolved.page_size, DEFAULT_PAGE_SIZE);
  const pageSize = Math.max(1, Math.min(requestedPageSize, MAX_PAGE_SIZE));
  const requestedPage = parsePositiveInt(resolved.page, 1);
  const offset = (requestedPage - 1) * pageSize;

  let items: SpecRegistryEntry[] = [];
  let total = 0;

  if (specFilter) {
    const single = await loadSingleSpec(specFilter);
    if (single) {
      items = [single];
      total = 1;
    }
  } else {
    const paged = await loadSpecPage(pageSize, offset);
    items = paged.items;
    total = paged.total;
  }

  const currentPage = specFilter ? 1 : requestedPage;
  const pageStart = specFilter ? (items.length > 0 ? 1 : 0) : offset + (items.length > 0 ? 1 : 0);
  const pageEnd = specFilter ? items.length : offset + items.length;
  const hasPrevious = !specFilter && currentPage > 1;
  const hasNext = !specFilter && pageEnd < total;

  return (
    <main className="min-h-screen p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Home
        </Link>
        <Link href="/portfolio" className="text-muted-foreground hover:text-foreground">
          Portfolio
        </Link>
        <Link href="/contribute" className="text-muted-foreground hover:text-foreground">
          Contribute
        </Link>
        <Link href="/ideas" className="text-muted-foreground hover:text-foreground">
          Ideas
        </Link>
        <Link href="/usage" className="text-muted-foreground hover:text-foreground">
          Usage
        </Link>
        <Link href="/flow" className="text-muted-foreground hover:text-foreground">
          Flow
        </Link>
        <Link href="/contributors" className="text-muted-foreground hover:text-foreground">
          Contributors
        </Link>
        <Link href="/contributions" className="text-muted-foreground hover:text-foreground">
          Contributions
        </Link>
        <Link href="/assets" className="text-muted-foreground hover:text-foreground">
          Assets
        </Link>
        <Link href="/tasks" className="text-muted-foreground hover:text-foreground">
          Tasks
        </Link>
        <Link href="/gates" className="text-muted-foreground hover:text-foreground">
          Gates
        </Link>
      </div>

      <h1 className="text-2xl font-bold">Specs</h1>
      <p className="text-muted-foreground">Paginated registry view with direct links to spec detail, idea context, and contributor ownership.</p>
      {specFilter ? (
        <p className="text-sm text-muted-foreground">
          Filter spec <code>{specFilter}</code> |{" "}
          <Link href="/specs" className="underline hover:text-foreground">
            Clear filter
          </Link>
        </p>
      ) : null}

      <section className="rounded border p-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
          <p>
            Showing {items.length > 0 ? `${pageStart}-${pageEnd}` : "0"} of {total}
            {specFilter ? "" : ` | page ${currentPage}`}
          </p>
          {!specFilter ? (
            <div className="flex gap-3">
              {hasPrevious ? (
                <Link href={paginationHref(currentPage - 1, pageSize)} className="underline hover:text-foreground">
                  Previous
                </Link>
              ) : (
                <span className="opacity-50">Previous</span>
              )}
              {hasNext ? (
                <Link href={paginationHref(currentPage + 1, pageSize)} className="underline hover:text-foreground">
                  Next
                </Link>
              ) : (
                <span className="opacity-50">Next</span>
              )}
            </div>
          ) : null}
        </div>

        <ul className="space-y-2 text-sm">
          {items.map((spec) => (
            <li key={spec.spec_id} className="rounded border p-3 space-y-1">
              <div className="flex justify-between gap-3">
                <Link href={`/specs/${encodeURIComponent(spec.spec_id)}`} className="font-medium underline hover:text-foreground">
                  Spec {spec.spec_id}
                </Link>
                <span className="text-muted-foreground">updated {spec.updated_at}</span>
              </div>
              <p>{spec.title}</p>
              <p className="text-muted-foreground">{spec.summary}</p>
              <p className="text-xs text-muted-foreground">
                value potential {spec.potential_value.toFixed(2)} | value actual {spec.actual_value.toFixed(2)} | value_gap {spec.value_gap.toFixed(2)}
                {" | "}
                cost est {spec.estimated_cost.toFixed(2)} | cost actual {spec.actual_cost.toFixed(2)} | cost_gap {spec.cost_gap.toFixed(2)}
              </p>
              <p className="text-xs text-muted-foreground">
                idea{" "}
                {spec.idea_id ? (
                  <Link href={`/ideas/${encodeURIComponent(spec.idea_id)}`} className="underline hover:text-foreground">
                    {spec.idea_id}
                  </Link>
                ) : (
                  <Link href="/ideas" className="underline hover:text-foreground">
                    missing
                  </Link>
                )}
                {" | "}
                created_by{" "}
                {spec.created_by_contributor_id ? (
                  <Link
                    href={`/contributors?contributor_id=${encodeURIComponent(spec.created_by_contributor_id)}`}
                    className="underline hover:text-foreground"
                  >
                    {spec.created_by_contributor_id}
                  </Link>
                ) : (
                  <Link href="/contributors" className="underline hover:text-foreground">
                    missing
                  </Link>
                )}
                {" | "}
                updated_by{" "}
                {spec.updated_by_contributor_id ? (
                  <Link
                    href={`/contributors?contributor_id=${encodeURIComponent(spec.updated_by_contributor_id)}`}
                    className="underline hover:text-foreground"
                  >
                    {spec.updated_by_contributor_id}
                  </Link>
                ) : (
                  <Link href="/contributors" className="underline hover:text-foreground">
                    missing
                  </Link>
                )}
                {" | "}
                <Link href={`/specs/${encodeURIComponent(spec.spec_id)}`} className="underline hover:text-foreground">
                  full detail
                </Link>
              </p>
            </li>
          ))}
          {items.length === 0 ? (
            <li className="text-muted-foreground">
              {specFilter ? "Spec not found in registry." : "No specs found for this page."}
            </li>
          ) : null}
        </ul>
      </section>
    </main>
  );
}
