import Link from "next/link";

import { getApiBase } from "@/lib/api";

type ValidationCounts = {
  pass: number;
  fail: number;
  pending: number;
};

type FlowItem = {
  idea_id: string;
  idea_name: string;
  spec: { tracked: boolean; count: number; spec_ids: string[] };
  process: {
    tracked: boolean;
    evidence_count: number;
    task_ids: string[];
    thread_branches: string[];
    change_intents: string[];
    source_files: string[];
  };
  implementation: {
    tracked: boolean;
    lineage_link_count: number;
    implementation_refs: string[];
    runtime_events_count: number;
    runtime_total_ms: number;
    runtime_cost_estimate: number;
  };
  validation: {
    tracked: boolean;
    local: ValidationCounts;
    ci: ValidationCounts;
    deploy: ValidationCounts;
    e2e: ValidationCounts;
    phase_gate: { pass_count: number; blocked_count: number };
    public_endpoints: string[];
  };
  contributors: {
    tracked: boolean;
    total_unique: number;
    by_role: Record<string, string[]>;
  };
  contributions: {
    tracked: boolean;
    usage_events_count: number;
    measured_value_total: number;
  };
  chain: {
    spec: string;
    process: string;
    implementation: string;
    validation: string;
    contributors: string;
    contributions: string;
  };
};

type FlowResponse = {
  summary: {
    ideas: number;
    with_spec: number;
    with_process: number;
    with_implementation: number;
    with_validation: number;
    with_contributors: number;
    with_contributions: number;
  };
  items: FlowItem[];
};

type Contributor = { id: string; name: string; type: string };
type Contribution = { id: string; contributor_id: string; asset_id: string; timestamp: string };

async function loadData(): Promise<{
  flow: FlowResponse;
  contributors: Contributor[];
  contributions: Contribution[];
}> {
  const API = getApiBase();
  const [flowRes, contributorsRes, contributionsRes] = await Promise.all([
    fetch(`${API}/api/inventory/flow?runtime_window_seconds=86400`, { cache: "no-store" }),
    fetch(`${API}/v1/contributors`, { cache: "no-store" }),
    fetch(`${API}/v1/contributions`, { cache: "no-store" }),
  ]);
  if (!flowRes.ok) throw new Error(`flow HTTP ${flowRes.status}`);
  if (!contributorsRes.ok) throw new Error(`contributors HTTP ${contributorsRes.status}`);
  if (!contributionsRes.ok) throw new Error(`contributions HTTP ${contributionsRes.status}`);

  return {
    flow: (await flowRes.json()) as FlowResponse,
    contributors: ((await contributorsRes.json()) as Contributor[]).slice(0, 500),
    contributions: ((await contributionsRes.json()) as Contribution[]).slice(0, 2000),
  };
}

function statLabel(value: boolean): string {
  return value ? "tracked" : "missing";
}

export default async function FlowPage() {
  const { flow, contributors, contributions } = await loadData();
  const contributorsById = new Map(contributors.map((c) => [c.id, c]));

  const topContributors = [...contributions]
    .reduce<Map<string, number>>((acc, row) => {
      acc.set(row.contributor_id, (acc.get(row.contributor_id) ?? 0) + 1);
      return acc;
    }, new Map())
    .entries();
  const topContributorsRows = [...topContributors]
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
      </div>

      <h1 className="text-2xl font-bold">Flow</h1>
      <p className="text-muted-foreground">
        Unified tracking of <code>idea -&gt; spec -&gt; process -&gt; implementation -&gt; validation</code> with contributor and contribution visibility.
      </p>

      <section className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <div className="rounded border p-3">
          <p className="text-muted-foreground">Ideas tracked</p>
          <p className="text-lg font-semibold">{flow.summary.ideas}</p>
        </div>
        <div className="rounded border p-3">
          <p className="text-muted-foreground">Flow complete (spec+process+impl+validation)</p>
          <p className="text-lg font-semibold">
            {flow.items.filter((row) => row.spec.tracked && row.process.tracked && row.implementation.tracked && row.validation.tracked).length}
          </p>
        </div>
        <div className="rounded border p-3">
          <p className="text-muted-foreground">Contributors in registry</p>
          <p className="text-lg font-semibold">{contributors.length}</p>
        </div>
        <div className="rounded border p-3">
          <p className="text-muted-foreground">Contributions in registry</p>
          <p className="text-lg font-semibold">{contributions.length}</p>
        </div>
      </section>

      <section className="rounded border p-4 space-y-2">
        <h2 className="font-semibold">Top Contributors by Contribution Count</h2>
        <ul className="space-y-1 text-sm">
          {topContributorsRows.map((row) => (
            <li key={row.contributorId} className="flex justify-between">
              <span>{row.name}</span>
              <span className="text-muted-foreground">{row.count}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="space-y-4">
        {flow.items.map((item) => (
          <article key={item.idea_id} className="rounded border p-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-semibold">{item.idea_name}</h2>
              <span className="text-xs text-muted-foreground">{item.idea_id}</span>
            </div>

            <div className="flex flex-wrap gap-2 text-xs">
              <span className="rounded border px-2 py-1">spec: {item.chain.spec}</span>
              <span className="rounded border px-2 py-1">process: {item.chain.process}</span>
              <span className="rounded border px-2 py-1">implementation: {item.chain.implementation}</span>
              <span className="rounded border px-2 py-1">validation: {item.chain.validation}</span>
              <span className="rounded border px-2 py-1">contributors: {item.chain.contributors}</span>
              <span className="rounded border px-2 py-1">contributions: {item.chain.contributions}</span>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-3 text-sm">
              <div className="rounded border p-3 space-y-1">
                <p className="font-medium">Spec + Process</p>
                <p className="text-muted-foreground">
                  specs {item.spec.count} ({statLabel(item.spec.tracked)}) | evidence {item.process.evidence_count} ({statLabel(item.process.tracked)})
                </p>
                <p className="text-muted-foreground">spec_ids {item.spec.spec_ids.slice(0, 8).join(", ") || "-"}</p>
                <p className="text-muted-foreground">task_ids {item.process.task_ids.slice(0, 8).join(", ") || "-"}</p>
                <p className="text-muted-foreground">threads {item.process.thread_branches.slice(0, 4).join(", ") || "-"}</p>
              </div>

              <div className="rounded border p-3 space-y-1">
                <p className="font-medium">Implementation + Contribution</p>
                <p className="text-muted-foreground">
                  lineage_links {item.implementation.lineage_link_count} ({statLabel(item.implementation.tracked)}) | runtime_events {item.implementation.runtime_events_count}
                </p>
                <p className="text-muted-foreground">
                  runtime_ms {item.implementation.runtime_total_ms.toFixed(2)} | runtime_cost {item.implementation.runtime_cost_estimate.toFixed(6)}
                </p>
                <p className="text-muted-foreground">
                  usage_events {item.contributions.usage_events_count} | measured_value {item.contributions.measured_value_total.toFixed(2)}
                </p>
              </div>

              <div className="rounded border p-3 space-y-1">
                <p className="font-medium">Validation</p>
                <p className="text-muted-foreground">
                  local pass {item.validation.local.pass} | ci pass {item.validation.ci.pass} | deploy pass {item.validation.deploy.pass} | e2e pass {item.validation.e2e.pass}
                </p>
                <p className="text-muted-foreground">
                  phase_gate pass {item.validation.phase_gate.pass_count} | blocked {item.validation.phase_gate.blocked_count}
                </p>
                <p className="text-muted-foreground">public_endpoints {item.validation.public_endpoints.length}</p>
              </div>

              <div className="rounded border p-3 space-y-1">
                <p className="font-medium">Contributors</p>
                <p className="text-muted-foreground">
                  unique {item.contributors.total_unique} ({statLabel(item.contributors.tracked)})
                </p>
                <ul className="space-y-1 text-muted-foreground">
                  {Object.entries(item.contributors.by_role)
                    .slice(0, 8)
                    .map(([role, ids]) => (
                      <li key={role}>
                        {role}: {ids.slice(0, 5).join(", ") || "-"}
                      </li>
                    ))}
                </ul>
              </div>
            </div>
          </article>
        ))}
      </section>
    </main>
  );
}

