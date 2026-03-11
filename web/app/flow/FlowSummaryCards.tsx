import type { FlowItem, FlowResponse } from "./types";

type Props = {
  filteredItems: FlowItem[];
  flow: FlowResponse;
  contributorsLength: number;
  contributionsLength: number;
};

export function FlowSummaryCards({ filteredItems, flow, contributorsLength, contributionsLength }: Props) {
  const flowCompleteCount = filteredItems.filter(
    (row) => row.spec.tracked && row.process.tracked && row.implementation.tracked && row.validation.tracked
  ).length;

  return (
    <section className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
      <div className="rounded border p-3">
        <p className="text-muted-foreground">Ideas tracked</p>
        <p className="text-lg font-semibold">{filteredItems.length}</p>
      </div>
      <div className="rounded border p-3">
        <p className="text-muted-foreground">Flow complete (spec+process+impl+validation)</p>
        <p className="text-lg font-semibold">{flowCompleteCount}</p>
      </div>
      <div className="rounded border p-3">
        <p className="text-muted-foreground">Contributors in team records</p>
        <p className="text-lg font-semibold">{contributorsLength}</p>
      </div>
      <div className="rounded border p-3">
        <p className="text-muted-foreground">Contributions in team records</p>
        <p className="text-lg font-semibold">{contributionsLength}</p>
      </div>
      <div className="rounded border p-3">
        <p className="text-muted-foreground">Blocked ideas</p>
        <p className="text-lg font-semibold">{flow.summary.blocked_ideas}</p>
      </div>
      <div className="rounded border p-3">
        <p className="text-muted-foreground">Unblock queue items</p>
        <p className="text-lg font-semibold">{flow.summary.queue_items}</p>
      </div>
    </section>
  );
}
