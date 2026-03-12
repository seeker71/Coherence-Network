import type { FlowItem, FlowResponse } from "./types";

type Props = {
  filteredItems: FlowItem[];
  flow: FlowResponse;
};

export function FlowSummaryCards({ filteredItems, flow }: Props) {
  const plannedCount = filteredItems.filter((row) => row.spec.tracked).length;
  const workCount = filteredItems.filter((row) => row.process.tracked).length;
  const proofCount = filteredItems.filter((row) => row.implementation.tracked || row.validation.tracked).length;
  const fullStoryCount = filteredItems.filter(
    (row) => row.spec.tracked && row.process.tracked && row.implementation.tracked && row.validation.tracked,
  ).length;

  return (
    <section className="grid grid-cols-2 gap-3 text-sm md:grid-cols-3 lg:grid-cols-6">
      <div className="rounded border p-3">
        <p className="text-muted-foreground">Ideas in view</p>
        <p className="text-lg font-semibold">{filteredItems.length}</p>
      </div>
      <div className="rounded border p-3">
        <p className="text-muted-foreground">Ideas with a plan</p>
        <p className="text-lg font-semibold">{plannedCount}</p>
      </div>
      <div className="rounded border p-3">
        <p className="text-muted-foreground">Ideas with work linked</p>
        <p className="text-lg font-semibold">{workCount}</p>
      </div>
      <div className="rounded border p-3">
        <p className="text-muted-foreground">Ideas with proof visible</p>
        <p className="text-lg font-semibold">{proofCount}</p>
      </div>
      <div className="rounded border p-3">
        <p className="text-muted-foreground">Full story visible</p>
        <p className="text-lg font-semibold">{fullStoryCount}</p>
      </div>
      <div className="rounded border p-3">
        <p className="text-muted-foreground">Needs help now</p>
        <p className="text-lg font-semibold">{flow.summary.blocked_ideas}</p>
      </div>
    </section>
  );
}
