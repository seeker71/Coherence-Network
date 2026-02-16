import Link from "next/link";

import { getApiBase } from "@/lib/api";

const REPO_BLOB_MAIN = "https://github.com/seeker71/Coherence-Network/blob/main";
const REPO_TREE = "https://github.com/seeker71/Coherence-Network/tree";

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
    evidence_refs: string[];
    source_files: string[];
  };
  implementation: {
    tracked: boolean;
    lineage_link_count: number;
    lineage_ids: string[];
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
    all: string[];
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
  interdependencies: {
    blocked: boolean;
    blocking_stage: string | null;
    upstream_required: string[];
    downstream_blocked: string[];
    estimated_unblock_cost: number;
    estimated_unblock_value: number;
    unblock_priority_score: number;
    task_fingerprint: string | null;
    next_unblock_task: { task_type: string; direction: string } | null;
  };
  idea_signals: {
    value_gap: number;
    confidence: number;
    estimated_cost: number;
    potential_value: number;
    actual_value: number;
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
    blocked_ideas: number;
    queue_items: number;
  };
  unblock_queue: Array<{
    idea_id: string;
    idea_name: string;
    blocking_stage: string;
    upstream_required: string[];
    downstream_blocked: string[];
    estimated_unblock_cost: number;
    estimated_unblock_value: number;
    unblock_priority_score: number;
    task_fingerprint: string;
    task_type: string;
    direction: string;
    active_task?: { id: string; status: string; claimed_by?: string | null } | null;
  }>;
  items: FlowItem[];
};

type Contributor = { id: string; name: string; type: string };
type Contribution = { id: string; contributor_id: string; asset_id: string; timestamp: string };

type FlowSearchParams = Promise<{
  idea_id?: string | string[];
  spec_id?: string | string[];
  contributor_id?: string | string[];
}>;

function normalizeFilter(value: string | string[] | undefined): string {
  if (Array.isArray(value)) return (value[0] || "").trim();
  return (value || "").trim();
}

function toRepoHref(pathOrUrl: string): string {
  if (/^https?:\/\//.test(pathOrUrl)) return pathOrUrl;
  return `${REPO_BLOB_MAIN}/${pathOrUrl.replace(/^\/+/, "")}`;
}

function toBranchHref(branch: string): string {
  return `${REPO_TREE}/${encodeURIComponent(branch)}`;
}

async function loadData(): Promise<{
  flow: FlowResponse;
  contributors: Contributor[];
  contributions: Contribution[];
}> {
  return loadDataForIdea("");
}

async function loadDataForIdea(ideaId: string): Promise<{
  flow: FlowResponse;
  contributors: Contributor[];
  contributions: Contribution[];
}> {
  const API = getApiBase();
  const flowParams = new URLSearchParams({ runtime_window_seconds: "86400" });
  if (ideaId) flowParams.set("idea_id", ideaId);
  const [flowRes, contributorsRes, contributionsRes] = await Promise.all([
    fetch(`${API}/api/inventory/flow?${flowParams.toString()}`, { cache: "no-store" }),
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

  const topContributors = [...filteredContributions]
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
        Unified tracking of <code>idea -&gt; spec -&gt; process -&gt; implementation -&gt; validation</code> with contributor and contribution visibility.
      </p>
      {(ideaFilter || specFilter || contributorFilter) && (
        <p className="text-sm text-muted-foreground">
          Filters:
          {ideaFilter ? (
            <>
              {" "}
              idea <code>{ideaFilter}</code>
            </>
          ) : null}
          {specFilter ? (
            <>
              {" "}
              spec <code>{specFilter}</code>
            </>
          ) : null}
          {contributorFilter ? (
            <>
              {" "}
              contributor <code>{contributorFilter}</code>
            </>
          ) : null}
          {" | "}
          <Link href="/flow" className="underline hover:text-foreground">
            Clear filters
          </Link>
        </p>
      )}

      <section className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <div className="rounded border p-3">
          <p className="text-muted-foreground">Ideas tracked</p>
          <p className="text-lg font-semibold">{filteredItems.length}</p>
        </div>
        <div className="rounded border p-3">
          <p className="text-muted-foreground">Flow complete (spec+process+impl+validation)</p>
          <p className="text-lg font-semibold">
            {filteredItems.filter((row) => row.spec.tracked && row.process.tracked && row.implementation.tracked && row.validation.tracked).length}
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
        <div className="rounded border p-3">
          <p className="text-muted-foreground">Blocked ideas</p>
          <p className="text-lg font-semibold">{flow.summary.blocked_ideas}</p>
        </div>
        <div className="rounded border p-3">
          <p className="text-muted-foreground">Unblock queue items</p>
          <p className="text-lg font-semibold">{flow.summary.queue_items}</p>
        </div>
      </section>

      <section className="rounded border p-4 space-y-2">
        <h2 className="font-semibold">Top Contributors by Contribution Count</h2>
        <ul className="space-y-1 text-sm">
          {topContributorsRows.map((row) => (
            <li key={row.contributorId} className="flex justify-between">
              <span>
                <Link
                  href={`/contributors?contributor_id=${encodeURIComponent(row.contributorId)}`}
                  className="underline hover:text-foreground"
                >
                  {row.name}
                </Link>
              </span>
              <span className="text-muted-foreground">{row.count}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded border p-4 space-y-2">
        <h2 className="font-semibold">Unblock Priority Queue</h2>
        <p className="text-sm text-muted-foreground">
          Ordered by estimated unlock value per cost. Work top-down to unblock more downstream tasks.
        </p>
        <ul className="space-y-2 text-sm">
          {flow.unblock_queue.slice(0, 12).map((row) => (
            <li key={row.task_fingerprint} className="rounded border p-2 space-y-1">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <Link href={`/flow?idea_id=${encodeURIComponent(row.idea_id)}`} className="font-medium underline hover:text-foreground">
                  {row.idea_name}
                </Link>
                <span className="text-xs text-muted-foreground">
                  stage {row.blocking_stage} | priority {row.unblock_priority_score.toFixed(2)}
                </span>
              </div>
              <p className="text-muted-foreground">
                cost {row.estimated_unblock_cost.toFixed(2)} | unlock value {row.estimated_unblock_value.toFixed(2)} |
                blocked {row.downstream_blocked.length > 0 ? row.downstream_blocked.join(", ") : "none"}
              </p>
              {row.active_task ? (
                <p className="text-muted-foreground">
                  active task{" "}
                  <Link href={`/tasks?task_id=${encodeURIComponent(row.active_task.id)}`} className="underline hover:text-foreground">
                    {row.active_task.id}
                  </Link>{" "}
                  ({row.active_task.status})
                </p>
              ) : (
                <p className="text-muted-foreground">ready to create as <code>{row.task_type}</code> task</p>
              )}
            </li>
          ))}
          {flow.unblock_queue.length === 0 && (
            <li className="text-muted-foreground">No blockers detected in current flow scope.</li>
          )}
        </ul>
      </section>

      <section className="space-y-4">
        {filteredItems.map((item) => (
          <article key={item.idea_id} className="rounded border p-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-semibold">
                <Link href={`/ideas/${encodeURIComponent(item.idea_id)}`} className="hover:underline">
                  {item.idea_name}
                </Link>
              </h2>
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
            <p className="text-xs text-muted-foreground">
              blocker {item.interdependencies.blocking_stage ?? "none"} | unblock priority{" "}
              {item.interdependencies.unblock_priority_score.toFixed(2)} | idea value gap{" "}
              {item.idea_signals.value_gap.toFixed(2)} | confidence {item.idea_signals.confidence.toFixed(2)}
            </p>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-3 text-sm">
              <div className="rounded border p-3 space-y-1">
                <p className="font-medium">Spec + Process</p>
                <p className="text-muted-foreground">
                  specs {item.spec.count} ({statLabel(item.spec.tracked)}) | evidence {item.process.evidence_count} ({statLabel(item.process.tracked)})
                </p>
                <p className="text-muted-foreground">
                  spec_ids{" "}
                  {item.spec.spec_ids.length > 0
                    ? item.spec.spec_ids.slice(0, 8).map((specId, idx) => (
                        <span key={specId}>
                          {idx > 0 ? ", " : ""}
                          <Link href={`/specs/${encodeURIComponent(specId)}`} className="underline hover:text-foreground">
                            {specId}
                          </Link>
                        </span>
                      ))
                    : "-"}
                </p>
                <p className="text-muted-foreground">
                  task_ids{" "}
                  {item.process.task_ids.length > 0
                    ? item.process.task_ids.slice(0, 8).map((taskId, idx) => (
                        <span key={taskId}>
                          {idx > 0 ? ", " : ""}
                          <Link href={`/tasks?task_id=${encodeURIComponent(taskId)}`} className="underline hover:text-foreground">
                            {taskId}
                          </Link>
                        </span>
                      ))
                    : "-"}
                </p>
                <p className="text-muted-foreground">
                  threads{" "}
                  {item.process.thread_branches.length > 0
                    ? item.process.thread_branches.slice(0, 4).map((branch, idx) => (
                        <span key={branch}>
                          {idx > 0 ? ", " : ""}
                          <a href={toBranchHref(branch)} target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">
                            {branch}
                          </a>
                        </span>
                      ))
                    : "-"}
                </p>
                <p className="text-muted-foreground">
                  source_files{" "}
                  {item.process.source_files.length > 0
                    ? item.process.source_files.slice(0, 6).map((filePath, idx) => (
                        <span key={filePath}>
                          {idx > 0 ? ", " : ""}
                          <a
                            href={toRepoHref(filePath)}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="underline hover:text-foreground"
                          >
                            {filePath}
                          </a>
                        </span>
                      ))
                    : "-"}
                </p>
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
                <p className="text-muted-foreground">
                  lineage_ids{" "}
                  {item.implementation.lineage_ids.length > 0
                    ? item.implementation.lineage_ids.slice(0, 6).map((lineageId, idx) => (
                        <span key={lineageId}>
                          {idx > 0 ? ", " : ""}
                          <a
                            href={`${getApiBase()}/api/value-lineage/links/${encodeURIComponent(lineageId)}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="underline hover:text-foreground"
                          >
                            {lineageId}
                          </a>
                        </span>
                      ))
                    : "-"}
                </p>
                <p className="text-muted-foreground">
                  implementation_refs{" "}
                  {item.implementation.implementation_refs.length > 0
                    ? item.implementation.implementation_refs.slice(0, 6).map((ref, idx) => (
                        <span key={ref}>
                          {idx > 0 ? ", " : ""}
                          <a href={toRepoHref(ref)} target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">
                            {ref}
                          </a>
                        </span>
                      ))
                    : "-"}
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
                <p className="text-muted-foreground">
                  public_endpoints{" "}
                  {item.validation.public_endpoints.length > 0
                    ? item.validation.public_endpoints.slice(0, 5).map((endpoint, idx) => (
                        <span key={endpoint}>
                          {idx > 0 ? ", " : ""}
                          <a href={endpoint} target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">
                            {endpoint}
                          </a>
                        </span>
                      ))
                    : "-"}
                </p>
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
                        {role}:{" "}
                        {ids.length > 0
                          ? ids.slice(0, 5).map((contributorId, idx) => (
                              <span key={`${role}-${contributorId}`}>
                                {idx > 0 ? ", " : ""}
                                <Link
                                  href={`/contributors?contributor_id=${encodeURIComponent(contributorId)}`}
                                  className="underline hover:text-foreground"
                                >
                                  {contributorId}
                                </Link>
                              </span>
                            ))
                          : "-"}
                      </li>
                    ))}
                </ul>
              </div>
            </div>
          </article>
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
