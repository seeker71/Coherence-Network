import type { Metadata } from "next";
import Link from "next/link";

import { FlowItemCard } from "./FlowItemCard";
import { FlowSummaryCards } from "./FlowSummaryCards";
import { FlowTopContributors } from "./FlowTopContributors";
import { FlowUnblockQueue } from "./FlowUnblockQueue";
import { loadData, loadDataForIdea } from "./load-flow-data";
import type { FlowSearchParams } from "./types";
import { normalizeFilter } from "./utils";

export const metadata: Metadata = {
  title: "Progress",
  description: "See how ideas move from planning to work to visible proof.",
};

export default async function FlowPage({ searchParams }: { searchParams: FlowSearchParams }) {
  const resolvedSearchParams = await searchParams;
  const ideaFilter = normalizeFilter(resolvedSearchParams.idea_id);
  const specFilter = normalizeFilter(resolvedSearchParams.spec_id);
  const contributorFilter = normalizeFilter(resolvedSearchParams.contributor_id);

  const { flow, contributors, contributions } = ideaFilter ? await loadDataForIdea(ideaFilter) : await loadData();
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
    <main className="min-h-screen p-8 max-w-6xl mx-auto space-y-6">
      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Home
        </Link>
        <Link href="/today" className="text-muted-foreground hover:text-foreground">
          Today
        </Link>
        <Link href="/ideas" className="text-muted-foreground hover:text-foreground">
          Ideas
        </Link>
        <Link href="/demo" className="text-muted-foreground hover:text-foreground">
          Demo
        </Link>
        <Link href="/tasks" className="text-muted-foreground hover:text-foreground">
          Work
        </Link>
      </div>

      <section className="rounded-2xl border border-border/70 bg-card/60 p-5 sm:p-7 space-y-3">
        <p className="text-sm text-muted-foreground">Progress view</p>
        <h1 className="text-3xl font-semibold tracking-tight">How Ideas Are Moving</h1>
        <p className="max-w-3xl text-muted-foreground">
          See what is planned, what work is moving, what proof is visible, and where progress is getting stuck.
        </p>
        <div className="flex flex-wrap gap-2 text-sm">
          <span className="rounded border px-3 py-1.5">Plan</span>
          <span className="rounded border px-3 py-1.5">Work</span>
          <span className="rounded border px-3 py-1.5">Proof</span>
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
          <article className="rounded border p-4 text-sm text-muted-foreground">
            No progress stories match the current filters.
          </article>
        ) : null}
      </section>
    </main>
  );
}
