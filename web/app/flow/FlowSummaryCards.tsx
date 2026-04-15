import type { FlowItem, FlowResponse } from "./types";

type Props = {
  filteredItems: FlowItem[];
  flow: FlowResponse;
};

export function FlowSummaryCards({ filteredItems, flow }: Props) {
  const plannedCount = filteredItems.filter((row) => row.spec.sensed).length;
  const workCount = filteredItems.filter((row) => row.process.sensed).length;
  const proofCount = filteredItems.filter((row) => row.implementation.sensed || row.validation.sensed).length;
  const fullStoryCount = filteredItems.filter(
    (row) => row.spec.sensed && row.process.sensed && row.implementation.sensed && row.validation.sensed,
  ).length;

  return (
    <section className="grid grid-cols-2 gap-6 text-sm md:grid-cols-3 lg:grid-cols-6">
      <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6">
        <p className="text-muted-foreground">Ideas in view</p>
        <p className="text-lg font-semibold">{filteredItems.length}</p>
      </div>
      <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6">
        <p className="text-muted-foreground">Ideas with a plan</p>
        <p className="text-lg font-semibold">{plannedCount}</p>
      </div>
      <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6">
        <p className="text-muted-foreground">Ideas with work linked</p>
        <p className="text-lg font-semibold">{workCount}</p>
      </div>
      <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6">
        <p className="text-muted-foreground">Ideas with proof visible</p>
        <p className="text-lg font-semibold">{proofCount}</p>
      </div>
      <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6">
        <p className="text-muted-foreground">Full story visible</p>
        <p className="text-lg font-semibold">{fullStoryCount}</p>
      </div>
      <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6">
        <p className="text-muted-foreground">Needs help now</p>
        <p className="text-lg font-semibold">{flow.summary.blocked_ideas}</p>
      </div>
    </section>
  );
}
