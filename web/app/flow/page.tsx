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
  title: "Flow",
  description: "Visual system flow: ideas to specs to implementations to runtime usage.",
};

export default async function FlowPage({ searchParams }: { searchParams: FlowSearchParams }) {
  const resolvedSearchParams = await searchParams;
  const ideaFilter = normalizeFilter(resolvedSearchParams.idea_id);
  const specFilter = normalizeFilter(resolvedSearchParams.spec_id);
  const contributorFilter = normalizeFilter(resolvedSearchParams.contributor_id);

  const { flow, contributors, contributions } = ideaFilter ? await loadDataForIdea(ideaFilter) : await loadData();
  const contributorsById = new Map(contributors.map((c) => [c.id, c]));
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
        <Link href="/portfolio" className="text-muted-foreground hover:text-foreground">
          Portfolio
        </Link>
        <Link href="/ideas" className="text-muted-foreground hover:text-foreground">
          Ideas
        </Link>
        <Link href="/specs" className="text-muted-foreground hover:text-foreground">
          Specs
        </Link>
        <Link href="/usage" className="text-muted-foreground hover:text-foreground">
          Usage
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

      <h1 className="text-2xl font-bold">Flow</h1>
      <p className="text-muted-foreground">
        Follow each idea from plan to implementation to validation, with contribution visibility at each step.
      </p>
      {(ideaFilter || specFilter || contributorFilter) && (
        <p className="text-sm text-muted-foreground">
          Filters active:
          {ideaFilter ? (
            <>
              {" "}idea selected
            </>
          ) : null}
          {specFilter ? (
            <>
              {" "}spec selected
            </>
          ) : null}
          {contributorFilter ? (
            <>
              {" "}contributor selected
            </>
          ) : null}
          {" | "}
          <Link href="/flow" className="underline hover:text-foreground">
            Clear filters
          </Link>
        </p>
      )}

      <FlowSummaryCards
        filteredItems={filteredItems}
        flow={flow}
        contributorsLength={contributors.length}
        contributionsLength={contributions.length}
      />

      <FlowTopContributors rows={topContributorsRowsList} />

      <FlowUnblockQueue flow={flow} />

      <section className="space-y-4">
        {filteredItems.map((item) => (
          <FlowItemCard key={item.idea_id} item={item} />
        ))}
        {filteredItems.length === 0 && (
          <article className="rounded border p-4 text-sm text-muted-foreground">
            No flow rows match current filters.
          </article>
        )}
      </section>
    </main>
  );
}
