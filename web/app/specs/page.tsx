import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "Specs",
  description: "Browse feature specifications and their implementation status.",
};

type SpecItem = {
  spec_id: string;
  title: string;
  path: string;
  api_path?: string;
};

type InventoryResponse = {
  specs?: {
    source?: string;
    items?: SpecItem[];
  };
};

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

type FlowItem = {
  idea_id: string;
  spec: { spec_ids: string[] };
  process: { task_ids: string[] };
  implementation: { implementation_refs: string[] };
  contributors: { all: string[] };
};

type FlowResponse = {
  items: FlowItem[];
};

type SpecRelations = {
  ideaIds: Set<string>;
  contributorIds: Set<string>;
  taskIds: Set<string>;
  implementationRefs: Set<string>;
};

type SpecsSearchParams = Promise<{
  spec_id?: string | string[];
}>;

function normalizeFilter(value: string | string[] | undefined): string {
  if (Array.isArray(value)) return (value[0] || "").trim();
  return (value || "").trim();
}

function collectSpecRelations(flowItems: FlowItem[]): Map<string, SpecRelations> {
  const map = new Map<string, SpecRelations>();
  for (const item of flowItems) {
    for (const specId of item.spec.spec_ids) {
      if (!map.has(specId)) {
        map.set(specId, {
          ideaIds: new Set<string>(),
          contributorIds: new Set<string>(),
          taskIds: new Set<string>(),
          implementationRefs: new Set<string>(),
        });
      }
      const rel = map.get(specId);
      if (!rel) continue;
      rel.ideaIds.add(item.idea_id);
      for (const contributorId of item.contributors.all) rel.contributorIds.add(contributorId);
      for (const taskId of item.process.task_ids) rel.taskIds.add(taskId);
      for (const ref of item.implementation.implementation_refs) rel.implementationRefs.add(ref);
    }
  }
  return map;
}

function humanizeSource(value: string): string {
  const normalized = value.trim().toLowerCase();
  if (!normalized) return "Unknown";
  if (normalized === "local") return "This workspace";
  if (normalized === "api") return "Live API";
  return value;
}

async function loadSpecs(): Promise<{ source: string; items: SpecItem[]; registry: SpecRegistryEntry[]; flowItems: FlowItem[] }> {
  const API = getApiBase();
  // 86400 seconds = 24 hours — fetch specs and flow data from the last day
  const [inventoryRes, registryRes, flowRes] = await Promise.all([
    fetch(`${API}/api/inventory/system-lineage?runtime_window_seconds=86400`, { cache: "no-store" }),
    fetch(`${API}/api/spec-registry`, { cache: "no-store" }),
    fetch(`${API}/api/inventory/flow?runtime_window_seconds=86400`, { cache: "no-store" }),
  ]);
  if (!inventoryRes.ok || !registryRes.ok || !flowRes.ok) {
    throw new Error(`HTTP ${inventoryRes.status}/${registryRes.status}/${flowRes.status}`);
  }
  const json = (await inventoryRes.json()) as InventoryResponse;
  const registryJson = (await registryRes.json()) as SpecRegistryEntry[];
  const flowJson = (await flowRes.json()) as FlowResponse;
  return {
    source: json.specs?.source ?? "unknown",
    items: (json.specs?.items ?? []).filter((s) => Boolean(s?.spec_id)),
    registry: Array.isArray(registryJson) ? registryJson : [],
    flowItems: Array.isArray(flowJson?.items) ? flowJson.items : [],
  };
}

export default async function SpecsPage({ searchParams }: { searchParams: SpecsSearchParams }) {
  const resolvedSearchParams = await searchParams;
  const specFilter = normalizeFilter(resolvedSearchParams.spec_id);
  const { source, items: specs, registry, flowItems } = await loadSpecs();
  const relationsBySpec = collectSpecRelations(flowItems);
  const filteredSpecs = specFilter ? specs.filter((s) => s.spec_id === specFilter) : specs;
  const filteredRegistry = specFilter ? registry.filter((s) => s.spec_id === specFilter) : registry;

  return (
    <main className="min-h-screen px-4 md:px-8 py-10 max-w-5xl mx-auto space-y-6">
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 sm:p-7 space-y-3">
        <p className="text-sm text-muted-foreground">Specs</p>
        <h1 className="text-3xl md:text-4xl font-light tracking-tight">Feature Specifications</h1>
        <p className="max-w-3xl text-muted-foreground">
          Feature plans with direct links to idea context, delivery workflow, and implementation proof.
        </p>
      </section>
      {specFilter ? (
        <p className="text-sm text-muted-foreground">
          Spec filter active |{" "}
          <Link href="/specs" className="underline hover:text-foreground">
            Clear filter
          </Link>
        </p>
      ) : null}

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3">
        <p className="text-sm text-muted-foreground">
          {filteredSpecs.length} discovered specs from {humanizeSource(source)}
        </p>
        <ul className="space-y-2 text-sm">
          {filteredSpecs.map((s) => {
            const relations = relationsBySpec.get(s.spec_id);
            const ideaIds = relations ? [...relations.ideaIds].sort() : [];
            const contributorIds = relations ? [...relations.contributorIds].sort() : [];
            return (
              <li key={s.spec_id} className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-1">
                <div className="flex justify-between gap-3">
                  <Link
                    href={`/specs/${encodeURIComponent(s.spec_id)}`}
                    className="font-medium underline hover:text-foreground"
                    title={`Spec ID: ${s.spec_id}`}
                  >
                    {s.title}
                  </Link>
                  <a
                    href={s.api_path ?? `/api/spec-registry/${encodeURIComponent(s.spec_id)}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-muted-foreground underline hover:text-foreground"
                    title={`Spec ID: ${s.spec_id}`}
                  >
                    Open API
                  </a>
                </div>
                <p className="text-xs text-muted-foreground">
                  Idea{" "}
                  {ideaIds.length > 0
                    ? ideaIds.map((ideaId, idx) => (
                        <span key={`${s.spec_id}-idea-${ideaId}`}>
                          {idx > 0 ? ", " : ""}
                          <Link
                            href={`/ideas/${encodeURIComponent(ideaId)}`}
                            className="underline hover:text-foreground"
                            title={`Idea ID: ${ideaId}`}
                          >
                            Idea {idx + 1}
                          </Link>
                        </span>
                      ))
                    : (
                      <Link href="/ideas" className="underline hover:text-foreground">
                        missing
                      </Link>
                    )}{" "}
                  | Contributors{" "}
                  {contributorIds.length > 0
                    ? contributorIds.slice(0, 6).map((contributorId, idx) => (
                        <span key={`${s.spec_id}-contributor-${contributorId}`}>
                          {idx > 0 ? ", " : ""}
                          <Link
                            href={`/contributors?contributor_id=${encodeURIComponent(contributorId)}`}
                            className="underline hover:text-foreground"
                            title={`Contributor ID: ${contributorId}`}
                          >
                            Contributor {idx + 1}
                          </Link>
                        </span>
                      ))
                    : (
                      <Link href="/contributors" className="underline hover:text-foreground">
                        missing
                      </Link>
                    )}{" "}
                  |{" "}
                  <Link href={`/flow?spec_id=${encodeURIComponent(s.spec_id)}`} className="underline hover:text-foreground">
                    process
                  </Link>{" "}
                  |{" "}
                  <Link href={`/flow?spec_id=${encodeURIComponent(s.spec_id)}`} className="underline hover:text-foreground">
                    implementation
                  </Link>
                </p>
              </li>
            );
          })}
          {filteredSpecs.length === 0 && <li className="text-muted-foreground">No data available yet. Once the API is running, results will appear here.</li>}
        </ul>
      </section>

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3">
        <p className="text-sm text-muted-foreground">
          {filteredRegistry.length} team-authored specs | create or update via{" "}
          <Link href="/contribute" className="underline hover:text-foreground">
            Contribution Console
          </Link>
        </p>
        <ul className="space-y-2 text-sm">
          {filteredRegistry.map((s) => (
            <li key={s.spec_id} className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-1">
              <div className="flex justify-between gap-3">
                <Link
                  href={`/specs/${encodeURIComponent(s.spec_id)}`}
                  className="font-medium underline hover:text-foreground"
                  title={`Spec ID: ${s.spec_id}`}
                >
                  {s.title}
                </Link>
                <span className="text-muted-foreground">updated {s.updated_at}</span>
              </div>
              <p className="text-muted-foreground">{s.summary}</p>
              {/* ROI values: estimated_roi = potential_value / estimated_cost, actual_roi = actual_value / actual_cost.
                 Values are displayed with 2 decimal places. No threshold filtering is applied here. */}
              <p className="text-xs text-muted-foreground">
                value potential {s.potential_value.toFixed(2)} | value actual {s.actual_value.toFixed(2)} | value_gap{" "}
                {s.value_gap.toFixed(2)} | cost est {s.estimated_cost.toFixed(2)} | cost actual {s.actual_cost.toFixed(2)} | cost_gap{" "}
                {s.cost_gap.toFixed(2)} | roi est {s.estimated_roi.toFixed(2)} | roi actual {s.actual_roi.toFixed(2)}
              </p>
              <p className="text-xs text-muted-foreground">
                Idea{" "}
                {s.idea_id ? (
                  <Link
                    href={`/ideas/${encodeURIComponent(s.idea_id)}`}
                    className="underline hover:text-foreground"
                    title={`Idea ID: ${s.idea_id}`}
                  >
                    Open idea
                  </Link>
                ) : (
                  <Link href="/ideas" className="underline hover:text-foreground">
                    missing
                  </Link>
                )}{" "}
                | Created by{" "}
                {s.created_by_contributor_id ? (
                  <Link
                    href={`/contributors?contributor_id=${encodeURIComponent(s.created_by_contributor_id)}`}
                    className="underline hover:text-foreground"
                    title={`Contributor ID: ${s.created_by_contributor_id}`}
                  >
                    Contributor profile
                  </Link>
                ) : (
                  <Link href="/contributors" className="underline hover:text-foreground">
                    missing
                  </Link>
                )}{" "}
                | Updated by{" "}
                {s.updated_by_contributor_id ? (
                  <Link
                    href={`/contributors?contributor_id=${encodeURIComponent(s.updated_by_contributor_id)}`}
                    className="underline hover:text-foreground"
                    title={`Contributor ID: ${s.updated_by_contributor_id}`}
                  >
                    Contributor profile
                  </Link>
                ) : (
                  <Link href="/contributors" className="underline hover:text-foreground">
                    missing
                  </Link>
                )}{" "}
                |{" "}
                <Link href={`/flow?spec_id=${encodeURIComponent(s.spec_id)}`} className="underline hover:text-foreground">
                  process
                </Link>{" "}
                |{" "}
                <Link href={`/flow?spec_id=${encodeURIComponent(s.spec_id)}`} className="underline hover:text-foreground">
                  implementation
                </Link>
              </p>
              <p className="text-xs text-muted-foreground">
                process_summary {s.process_summary || "-"} | pseudocode_summary {s.pseudocode_summary || "-"} | implementation_summary{" "}
                {s.implementation_summary || "-"}
              </p>
            </li>
          ))}
          {filteredRegistry.length === 0 && (
            <li className="text-muted-foreground">No data available yet. Once the API is running, results will appear here.</li>
          )}
        </ul>
      </section>
    </main>
  );
}
