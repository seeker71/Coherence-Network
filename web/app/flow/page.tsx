import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";
import { FlowItemCard } from "./FlowItemCard";
import { FlowSummaryCards } from "./FlowSummaryCards";
import { FlowTopContributors } from "./FlowTopContributors";
import { FlowUnblockQueue } from "./FlowUnblockQueue";
import { loadData, loadDataForIdea } from "./load-flow-data";
import type { FlowSearchParams } from "./types";
import { normalizeFilter } from "./utils";

type PipelineHealthAlert = {
  provider: string;
  metric: string;
  value: number;
  threshold: number;
  message: string;
};

type PipelineHealthSummary = {
  total_providers: number;
  healthy_providers: number;
  attention_needed: number;
  total_measurements: number;
};

type PipelineHealthResponse = {
  alerts: PipelineHealthAlert[];
  summary: PipelineHealthSummary;
};

async function loadPipelineHealth(): Promise<PipelineHealthResponse | null> {
  try {
    const api = getApiBase();
    const res = await fetch(`${api}/api/providers/stats`, { next: { revalidate: 60 } });
    if (!res.ok) return null;
    return (await res.json()) as PipelineHealthResponse;
  } catch {
    return null;
  }
}

export const metadata: Metadata = {
  title: "Progress",
  description: "See how ideas move from planning to work to visible proof.",
};

export default async function FlowPage({ searchParams }: { searchParams: FlowSearchParams }) {
  const resolvedSearchParams = await searchParams;
  const ideaFilter = normalizeFilter(resolvedSearchParams.idea_id);
  const specFilter = normalizeFilter(resolvedSearchParams.spec_id);
  const contributorFilter = normalizeFilter(resolvedSearchParams.contributor_id);

  const [flowData, pipelineHealth] = await Promise.all([
    ideaFilter ? loadDataForIdea(ideaFilter) : loadData(),
    loadPipelineHealth(),
  ]);
  const { flow, contributors, contributions } = flowData;
  const contributorsById = new Map(contributors.map((contributor) => [contributor.id, contributor]));
  const filteredItems = flow.items.filter((item) => {
    if (specFilter && !item.spec.spec_ids.includes(specFilter)) return false;
    if (contributorFilter && !item.contributors.all.includes(contributorFilter)) return false;
    return true;
  });
  const filteredContributions = contributions.filter((row) => {
    if (contributorFilter && row.contributor_id !== contributorFilter) return false;
    return true;
  });

  const topContributorsRows = [...filteredContributions]
    .reduce<Map<string, number>>((acc, row) => {
      acc.set(row.contributor_id, (acc.get(row.contributor_id) ?? 0) + 1);
      return acc;
    }, new Map())
    .entries();
  const topContributorsRowsList = [...topContributorsRows]
    .map(([contributorId, count]) => ({
      contributorId,
      count,
      name: contributorsById.get(contributorId)?.name ?? contributorId,
    }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 8);

  return (
    <main className="min-h-screen px-4 md:px-8 py-10 max-w-6xl mx-auto space-y-6">
      {pipelineHealth ? (
        <div className="flex items-center gap-2 rounded-lg border border-border/30 bg-card/40 px-4 py-2 text-sm">
          {pipelineHealth.alerts.length > 0 ? (
            <>
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-amber-500" />
              <span className="text-amber-600 dark:text-amber-400">
                {pipelineHealth.summary.attention_needed} provider{pipelineHealth.summary.attention_needed !== 1 ? "s" : ""} need attention
              </span>
              <Link href="/automation" className="ml-auto text-muted-foreground underline hover:text-foreground">
                Details
              </Link>
            </>
          ) : (
            <>
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-green-500" />
              <span className="text-green-600 dark:text-green-400">All providers healthy</span>
              <Link href="/automation" className="ml-auto text-muted-foreground underline hover:text-foreground">
                Details
              </Link>
            </>
          )}
        </div>
      ) : null}

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 sm:p-7 space-y-3">
        <p className="text-sm text-muted-foreground">Progress view</p>
        <h1 className="text-3xl md:text-4xl font-light tracking-tight">How Ideas Are Moving</h1>
        <p className="max-w-3xl text-muted-foreground">
          See what is planned, what work is moving, what proof is visible, and where progress is getting stuck.
        </p>
        <div className="flex flex-wrap gap-2 text-sm">
          <span className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground">Plan</span>
          <span className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground">Work</span>
          <span className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground">Proof</span>
        </div>
      </section>

      {ideaFilter || specFilter || contributorFilter ? (
        <p className="text-sm text-muted-foreground">
          Showing a filtered progress view:
          {ideaFilter ? " one idea" : ""}
          {specFilter ? `${ideaFilter ? "," : ""} one plan` : ""}
          {contributorFilter ? `${ideaFilter || specFilter ? "," : ""} one person` : ""}
          {". "}
          <Link href="/flow" className="underline hover:text-foreground">
            Clear filters
          </Link>
        </p>
      ) : null}

      <FlowSummaryCards filteredItems={filteredItems} flow={flow} />

      <FlowUnblockQueue flow={flow} />

      <FlowTopContributors rows={topContributorsRowsList} />

      <section className="space-y-4">
        {filteredItems.map((item) => (
          <FlowItemCard key={item.idea_id} item={item} />
        ))}
        {filteredItems.length === 0 ? (
          <article className="rounded-xl border border-border/20 bg-background/40 p-4 text-sm text-muted-foreground">
            No data available yet. Once the API is running, results will appear here.
          </article>
        ) : null}
      </section>
    </main>
  );
}
