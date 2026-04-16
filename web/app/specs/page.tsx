import type { Metadata } from "next";
import Link from "next/link";
import { cookies } from "next/headers";

import { getApiBase } from "@/lib/api";
import { withWorkspaceScope } from "@/lib/workspace";
import { getActiveWorkspaceFromCookie } from "@/lib/workspace-server";
import { createTranslator, type Translator } from "@/lib/i18n";
import { DEFAULT_LOCALE, isSupportedLocale, type LocaleCode } from "@/lib/locales";

export const metadata: Metadata = {
  title: "Specs",
  description: "Browse feature specifications, linked ideas, and implementation proof.",
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

type SpecCard = {
  spec_id: string;
  title: string;
  api_path?: string;
  source_label: string;
  inventoryItem: SpecItem | null;
  registryItem: SpecRegistryEntry | null;
  relations: SpecRelations;
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

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(2);
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return value;
  }
}

async function loadSpecs(workspaceId: string): Promise<{ source: string; items: SpecItem[]; registry: SpecRegistryEntry[]; flowItems: FlowItem[] }> {
  const API = getApiBase();
  const inventoryUrl = withWorkspaceScope(`${API}/api/inventory/system-lineage?runtime_window_seconds=86400`, workspaceId);
  const registryUrl = withWorkspaceScope(`${API}/api/spec-registry`, workspaceId);
  const flowUrl = withWorkspaceScope(`${API}/api/inventory/flow?runtime_window_seconds=86400`, workspaceId);
  const [inventoryRes, registryRes, flowRes] = await Promise.all([
    fetch(inventoryUrl, { cache: "no-store" }),
    fetch(registryUrl, { cache: "no-store" }),
    fetch(flowUrl, { cache: "no-store" }),
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

function buildSpecCards(source: string, specs: SpecItem[], registry: SpecRegistryEntry[], flowItems: FlowItem[]): SpecCard[] {
  const relationsBySpec = collectSpecRelations(flowItems);
  const inventoryById = new Map(specs.map((item) => [item.spec_id, item]));
  const registryById = new Map(registry.map((item) => [item.spec_id, item]));
  const ids = [...new Set([...inventoryById.keys(), ...registryById.keys()])].sort((a, b) => a.localeCompare(b));

  return ids.map((spec_id) => {
    const inventoryItem = inventoryById.get(spec_id) ?? null;
    const registryItem = registryById.get(spec_id) ?? null;
    const relations = relationsBySpec.get(spec_id) ?? {
      ideaIds: new Set<string>(),
      contributorIds: new Set<string>(),
      taskIds: new Set<string>(),
      implementationRefs: new Set<string>(),
    };

    return {
      spec_id,
      title: registryItem?.title || inventoryItem?.title || spec_id,
      api_path: registryItem ? `/api/spec-registry/${encodeURIComponent(spec_id)}` : inventoryItem?.api_path,
      source_label: registryItem && inventoryItem ? `${humanizeSource(source)} + Registry` : registryItem ? "Registry" : humanizeSource(source),
      inventoryItem,
      registryItem,
      relations,
    };
  });
}

function SpecsSummary({ filteredSpecs, t }: { filteredSpecs: SpecCard[]; t: Translator }) {
  const linkedIdeas = new Set(filteredSpecs.flatMap((spec) => [...spec.relations.ideaIds]));
  const contributors = new Set(filteredSpecs.flatMap((spec) => [...spec.relations.contributorIds]));
  const measured = filteredSpecs.filter((spec) => Boolean(spec.registryItem)).length;

  return (
    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4">
        <p className="text-xs uppercase tracking-widest text-muted-foreground">{t("specs.statVisible")}</p>
        <p className="mt-2 text-3xl font-light">{filteredSpecs.length}</p>
      </div>
      <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4">
        <p className="text-xs uppercase tracking-widest text-muted-foreground">{t("specs.statMeasured")}</p>
        <p className="mt-2 text-3xl font-light">{measured}</p>
        <p className="mt-1 text-xs text-muted-foreground">{t("specs.statMeasuredSub")}</p>
      </div>
      <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4">
        <p className="text-xs uppercase tracking-widest text-muted-foreground">{t("specs.statLinkedIdeas")}</p>
        <p className="mt-2 text-3xl font-light">{linkedIdeas.size}</p>
      </div>
      <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4">
        <p className="text-xs uppercase tracking-widest text-muted-foreground">{t("specs.statContributors")}</p>
        <p className="mt-2 text-3xl font-light">{contributors.size}</p>
      </div>
    </section>
  );
}

function LinkList({
  values,
  hrefBuilder,
  fallbackHref,
  fallbackLabel,
}: {
  values: string[];
  hrefBuilder: (value: string) => string;
  fallbackHref: string;
  fallbackLabel: string;
}) {
  if (values.length === 0) {
    return (
      <Link href={fallbackHref} className="underline hover:text-foreground">
        {fallbackLabel}
      </Link>
    );
  }

  return (
    <>
      {values.map((value, idx) => (
        <span key={value}>
          {idx > 0 ? ", " : ""}
          <Link href={hrefBuilder(value)} className="underline hover:text-foreground" title={value}>
            {value}
          </Link>
        </span>
      ))}
    </>
  );
}

export default async function SpecsPage({ searchParams }: { searchParams: SpecsSearchParams }) {
  const resolvedSearchParams = await searchParams;
  const specFilter = normalizeFilter(resolvedSearchParams.spec_id);
  const workspaceId = await getActiveWorkspaceFromCookie();
  const cookieStore = await cookies();
  const cookieLang = cookieStore.get("NEXT_LOCALE")?.value;
  const lang: LocaleCode = isSupportedLocale(cookieLang) ? cookieLang : DEFAULT_LOCALE;
  const t = createTranslator(lang);
  const { source, items: specs, registry, flowItems } = await loadSpecs(workspaceId);
  const specCards = buildSpecCards(source, specs, registry, flowItems);
  const filteredSpecs = specFilter ? specCards.filter((s) => s.spec_id === specFilter) : specCards;
  const filteredRegistry = filteredSpecs.filter((spec) => Boolean(spec.registryItem));

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-6xl mx-auto space-y-8">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">{t("specs.title")}</h1>
        <p className="max-w-3xl leading-relaxed text-muted-foreground">
          Specs are the delivery contracts between ideas, implementation work, and verification. This view shows what the repo can currently discover, what the registry knows, and where the links are still missing.
        </p>
      </div>

      {specFilter ? (
        <p className="text-sm text-muted-foreground">
          Spec filter active for <span className="font-mono">{specFilter}</span> |{" "}
          <Link href="/specs" className="underline hover:text-foreground">
            Clear filter
          </Link>
        </p>
      ) : null}

      <SpecsSummary filteredSpecs={filteredSpecs} t={t} />

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-medium">{t("specs.visibleHeading")}</h2>
            <p className="text-sm text-muted-foreground">
              {filteredSpecs.length} visible specs from {humanizeSource(source)} and the registry.
            </p>
          </div>
          <Link href="/contribute" className="text-sm underline hover:text-foreground">
            Add or update spec metadata
          </Link>
        </div>

        <ul className="space-y-3 text-sm">
          {filteredSpecs.map((spec) => {
            const registryItem = spec.registryItem;
            const ideaIds = [...spec.relations.ideaIds].sort();
            const contributorIds = [...spec.relations.contributorIds].sort();
            const taskCount = spec.relations.taskIds.size;
            const implementationCount = spec.relations.implementationRefs.size;

            return (
              <li key={spec.spec_id} className="rounded-2xl border border-border/20 bg-background/40 p-4 space-y-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        href={`/specs/${encodeURIComponent(spec.spec_id)}`}
                        className="text-base font-medium underline hover:text-foreground"
                        title={`Spec ID: ${spec.spec_id}`}
                      >
                        {spec.title}
                      </Link>
                      <span className="rounded-full border border-border/30 px-2 py-0.5 text-xs text-muted-foreground">
                        {spec.spec_id}
                      </span>
                      <span className="rounded-full border border-border/30 px-2 py-0.5 text-xs text-muted-foreground">
                        {spec.source_label}
                      </span>
                      {registryItem ? (
                        <span className="rounded-full border border-emerald-500/30 px-2 py-0.5 text-xs text-emerald-400">
                          measured
                        </span>
                      ) : (
                        <span className="rounded-full border border-amber-500/30 px-2 py-0.5 text-xs text-amber-400">
                          registry missing
                        </span>
                      )}
                    </div>
                    <p className="text-muted-foreground">
                      {registryItem?.summary || "Discovered from system lineage. Add registry metadata to make this spec measurable and easier to reason about."}
                    </p>
                  </div>

                  <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                    <Link href={`/flow?spec_id=${encodeURIComponent(spec.spec_id)}`} className="underline hover:text-foreground">
                      Process view
                    </Link>
                    <Link href={`/specs/${encodeURIComponent(spec.spec_id)}`} className="underline hover:text-foreground">
                      Spec detail
                    </Link>
                    {spec.api_path ? (
                      <a href={spec.api_path} target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">
                        Open API
                      </a>
                    ) : null}
                  </div>
                </div>

                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <div className="rounded-xl border border-border/20 bg-card/30 p-3">
                    <p className="text-xs uppercase tracking-widest text-muted-foreground">Ideas</p>
                    <p className="mt-2 font-medium">{ideaIds.length}</p>
                  </div>
                  <div className="rounded-xl border border-border/20 bg-card/30 p-3">
                    <p className="text-xs uppercase tracking-widest text-muted-foreground">{t("specs.statContributors")}</p>
                    <p className="mt-2 font-medium">{contributorIds.length}</p>
                  </div>
                  <div className="rounded-xl border border-border/20 bg-card/30 p-3">
                    <p className="text-xs uppercase tracking-widest text-muted-foreground">Tasks</p>
                    <p className="mt-2 font-medium">{taskCount}</p>
                  </div>
                  <div className="rounded-xl border border-border/20 bg-card/30 p-3">
                    <p className="text-xs uppercase tracking-widest text-muted-foreground">Implementation Refs</p>
                    <p className="mt-2 font-medium">{implementationCount}</p>
                  </div>
                </div>

                <div className="space-y-1 text-xs text-muted-foreground">
                  <p>
                    Linked ideas:{" "}
                    <LinkList
                      values={ideaIds}
                      hrefBuilder={(ideaId) => `/ideas/${encodeURIComponent(ideaId)}`}
                      fallbackHref="/ideas"
                      fallbackLabel="none yet"
                    />
                  </p>
                  <p>
                    Contributors:{" "}
                    <LinkList
                      values={contributorIds}
                      hrefBuilder={(contributorId) => `/contributors?contributor_id=${encodeURIComponent(contributorId)}`}
                      fallbackHref="/contributors"
                      fallbackLabel="none yet"
                    />
                  </p>
                  {registryItem ? (
                    <p>
                      ROI est {formatNumber(registryItem.estimated_roi)} | ROI actual {formatNumber(registryItem.actual_roi)} | value gap {formatNumber(registryItem.value_gap)} | updated {formatDate(registryItem.updated_at)}
                    </p>
                  ) : (
                    <p>Registry metrics missing. Link this spec in the registry to expose ROI, gap, and summary data.</p>
                  )}
                </div>
              </li>
            );
          })}

          {filteredSpecs.length === 0 ? (
            <li className="rounded-2xl border border-dashed border-border/30 bg-background/30 p-6 text-sm text-muted-foreground">
              No specs are visible yet. Once lineage or registry data lands, this page will show the linked ideas, contributors, and implementation proof automatically.
            </li>
          ) : null}
        </ul>
      </section>

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3">
        <h2 className="text-lg font-medium">{t("specs.registryCoverage")}</h2>
        <p className="text-sm text-muted-foreground">
          {filteredRegistry.length} of {filteredSpecs.length} visible specs currently have registry metadata attached.
        </p>
        <div className="flex flex-wrap gap-3 text-sm">
          <Link href="/contribute" className="underline hover:text-foreground">
            Open Contribution Console
          </Link>
          <Link href="/flow" className="underline hover:text-foreground">
            Review process coverage
          </Link>
          <Link href="/ideas" className="underline hover:text-foreground">
            Check linked ideas
          </Link>
        </div>
      </section>
    </main>
  );
}
