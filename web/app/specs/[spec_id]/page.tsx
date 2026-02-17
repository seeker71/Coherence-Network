import Link from "next/link";

import { getApiBase } from "@/lib/api";

const REPO_BLOB_MAIN = "https://github.com/seeker71/Coherence-Network/blob/main";
const REPO_TREE = "https://github.com/seeker71/Coherence-Network/tree";

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
  idea_name: string;
  spec: { spec_ids: string[] };
  process: {
    task_ids: string[];
    thread_branches: string[];
    evidence_refs: string[];
    source_files: string[];
  };
  implementation: {
    lineage_ids: string[];
    implementation_refs: string[];
  };
  validation: {
    public_endpoints: string[];
  };
  contributors: {
    all: string[];
    by_role: Record<string, string[]>;
  };
};

type FlowResponse = {
  items: FlowItem[];
};

function toRepoHref(pathOrUrl: string): string {
  if (/^https?:\/\//.test(pathOrUrl)) return pathOrUrl;
  return `${REPO_BLOB_MAIN}/${pathOrUrl.replace(/^\/+/, "")}`;
}

function toBranchHref(branch: string): string {
  return `${REPO_TREE}/${encodeURIComponent(branch)}`;
}

async function loadSpecContext(specId: string): Promise<{
  source: string;
  inventoryItem: SpecItem | null;
  registryItem: SpecRegistryEntry | null;
  relatedFlow: FlowItem[];
}> {
  const API = getApiBase();
  const [inventoryRes, registryRes, flowRes] = await Promise.all([
    fetch(`${API}/api/inventory/system-lineage?runtime_window_seconds=86400`, { cache: "no-store" }),
    fetch(`${API}/api/spec-registry`, { cache: "no-store" }),
    fetch(`${API}/api/inventory/flow?runtime_window_seconds=86400`, { cache: "no-store" }),
  ]);
  if (!inventoryRes.ok || !registryRes.ok || !flowRes.ok) {
    throw new Error(`HTTP ${inventoryRes.status}/${registryRes.status}/${flowRes.status}`);
  }

  const inventoryJson = (await inventoryRes.json()) as InventoryResponse;
  const registryJson = (await registryRes.json()) as SpecRegistryEntry[];
  const flowJson = (await flowRes.json()) as FlowResponse;

  const inventoryItems = inventoryJson.specs?.items ?? [];
  const inventoryItem = inventoryItems.find((item) => item.spec_id === specId) ?? null;
  const registryItem = (Array.isArray(registryJson) ? registryJson : []).find((item) => item.spec_id === specId) ?? null;
  const relatedFlow = (Array.isArray(flowJson?.items) ? flowJson.items : []).filter((item) => item.spec.spec_ids.includes(specId));

  return {
    source: inventoryJson.specs?.source ?? "unknown",
    inventoryItem,
    registryItem,
    relatedFlow,
  };
}

export default async function SpecDetailPage({ params }: { params: Promise<{ spec_id: string }> }) {
  const resolved = await params;
  const specId = decodeURIComponent(resolved.spec_id);
  const { source, inventoryItem, registryItem, relatedFlow } = await loadSpecContext(specId);

  const ideaIds = new Set<string>();
  const contributorByRole = new Map<string, Set<string>>();
  const taskIds = new Set<string>();
  const threadBranches = new Set<string>();
  const sourceFiles = new Set<string>();
  const evidenceRefs = new Set<string>();
  const implementationRefs = new Set<string>();
  const lineageIds = new Set<string>();
  const publicEndpoints = new Set<string>();

  if (registryItem?.idea_id) ideaIds.add(registryItem.idea_id);
  for (const flow of relatedFlow) {
    ideaIds.add(flow.idea_id);
    for (const taskId of flow.process.task_ids) taskIds.add(taskId);
    for (const branch of flow.process.thread_branches) threadBranches.add(branch);
    for (const sourceFile of flow.process.source_files) sourceFiles.add(sourceFile);
    for (const evidenceRef of flow.process.evidence_refs) evidenceRefs.add(evidenceRef);
    for (const implementationRef of flow.implementation.implementation_refs) implementationRefs.add(implementationRef);
    for (const lineageId of flow.implementation.lineage_ids) lineageIds.add(lineageId);
    for (const endpoint of flow.validation.public_endpoints) publicEndpoints.add(endpoint);
    for (const [role, contributorIds] of Object.entries(flow.contributors.by_role)) {
      if (!contributorByRole.has(role)) contributorByRole.set(role, new Set<string>());
      const bucket = contributorByRole.get(role);
      if (!bucket) continue;
      for (const contributorId of contributorIds) bucket.add(contributorId);
    }
  }
  if (registryItem?.created_by_contributor_id) {
    if (!contributorByRole.has("spec_created_by")) contributorByRole.set("spec_created_by", new Set<string>());
    contributorByRole.get("spec_created_by")?.add(registryItem.created_by_contributor_id);
  }
  if (registryItem?.updated_by_contributor_id) {
    if (!contributorByRole.has("spec_updated_by")) contributorByRole.set("spec_updated_by", new Set<string>());
    contributorByRole.get("spec_updated_by")?.add(registryItem.updated_by_contributor_id);
  }

  const allContributors = [...new Set([...contributorByRole.values()].flatMap((ids) => [...ids]))].sort();

  return (
    <main className="min-h-screen p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Home
        </Link>
        <Link href="/specs" className="text-muted-foreground hover:text-foreground">
          Specs
        </Link>
        <Link href="/ideas" className="text-muted-foreground hover:text-foreground">
          Ideas
        </Link>
        <Link href="/contributors" className="text-muted-foreground hover:text-foreground">
          Contributors
        </Link>
        <Link href="/flow" className="text-muted-foreground hover:text-foreground">
          Flow
        </Link>
        <Link href="/contribute" className="text-muted-foreground hover:text-foreground">
          Contribute
        </Link>
      </div>

      <div className="space-y-1">
        <h1 className="text-2xl font-bold">Spec {specId}</h1>
        <p className="text-muted-foreground">{registryItem?.title || inventoryItem?.title || "(title not yet registered)"}</p>
      </div>

      <section className="rounded border p-4 space-y-2 text-sm">
        <h2 className="font-semibold">Spec Source</h2>
        <p className="text-muted-foreground">
          inventory_source {source} | spec_api {inventoryItem?.api_path || `/api/spec-registry/${specId}`} | registry_updated {registryItem?.updated_at || "-"}
        </p>
        {inventoryItem ? (
          <p>
            <a
              href={inventoryItem.api_path || `/api/spec-registry/${encodeURIComponent(specId)}`}
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-foreground"
            >
              Open spec API record
            </a>
          </p>
        ) : (
          <p className="text-muted-foreground">
            Spec file path missing.{" "}
            <Link href="/contribute" className="underline hover:text-foreground">
              Add/update registry metadata
            </Link>
            .
          </p>
        )}
      </section>

      <section className="rounded border p-4 space-y-2 text-sm">
        <h2 className="font-semibold">Spec Value/Cost/Gap Tracking</h2>
        <p className="text-muted-foreground">
          potential_value {registryItem?.potential_value?.toFixed(2) ?? "-"} | actual_value {registryItem?.actual_value?.toFixed(2) ?? "-"} |
          value_gap {registryItem?.value_gap?.toFixed(2) ?? "-"}
        </p>
        <p className="text-muted-foreground">
          estimated_cost {registryItem?.estimated_cost?.toFixed(2) ?? "-"} | actual_cost {registryItem?.actual_cost?.toFixed(2) ?? "-"} |
          cost_gap {registryItem?.cost_gap?.toFixed(2) ?? "-"}
        </p>
        <p className="text-muted-foreground">
          estimated_roi {registryItem?.estimated_roi?.toFixed(2) ?? "-"} | actual_roi {registryItem?.actual_roi?.toFixed(2) ?? "-"}
        </p>
        {!registryItem ? (
          <p className="text-muted-foreground">
            Spec registry metrics missing.{" "}
            <Link href="/contribute" className="underline hover:text-foreground">
              Add spec value/cost measurements
            </Link>
            .
          </p>
        ) : null}
      </section>

      <section className="rounded border p-4 space-y-2 text-sm">
        <h2 className="font-semibold">Linked Ideas</h2>
        {[...ideaIds].sort().length > 0 ? (
          <ul className="space-y-1">
            {[...ideaIds].sort().map((ideaId) => (
              <li key={ideaId}>
                <Link href={`/ideas/${encodeURIComponent(ideaId)}`} className="underline hover:text-foreground">
                  {ideaId}
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-muted-foreground">
            Missing idea linkage.{" "}
            <Link href="/contribute" className="underline hover:text-foreground">
              Add idea_id to this spec
            </Link>
            .
          </p>
        )}
      </section>

      <section className="rounded border p-4 space-y-2 text-sm">
        <h2 className="font-semibold">Linked Contributors</h2>
        {allContributors.length > 0 ? (
          <ul className="space-y-1">
            {[...contributorByRole.entries()]
              .sort((a, b) => a[0].localeCompare(b[0]))
              .map(([role, ids]) => (
                <li key={role}>
                  {role}:{" "}
                  {[...ids].sort().map((contributorId, idx) => (
                    <span key={`${role}-${contributorId}`}>
                      {idx > 0 ? ", " : ""}
                      <Link
                        href={`/contributors?contributor_id=${encodeURIComponent(contributorId)}`}
                        className="underline hover:text-foreground"
                      >
                        {contributorId}
                      </Link>
                    </span>
                  ))}
                </li>
              ))}
          </ul>
        ) : (
          <p className="text-muted-foreground">
            Missing contributor linkage.{" "}
            <Link href="/contribute" className="underline hover:text-foreground">
              Submit a change request with contributor attribution
            </Link>
            .
          </p>
        )}
      </section>

      <section className="rounded border p-4 space-y-2 text-sm">
        <h2 className="font-semibold">Linked Process</h2>
        <p>
          <Link href={`/flow?spec_id=${encodeURIComponent(specId)}`} className="underline hover:text-foreground">
            Open process view for this spec
          </Link>
        </p>
        <p className="text-muted-foreground">
          task_ids{" "}
          {[...taskIds].sort().length > 0
            ? [...taskIds].sort().map((taskId, idx) => (
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
          branches{" "}
          {[...threadBranches].sort().length > 0
            ? [...threadBranches].sort().map((branch, idx) => (
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
          {[...sourceFiles].sort().length > 0
            ? [...sourceFiles].sort().slice(0, 8).map((filePath, idx) => (
                <span key={filePath}>
                  {idx > 0 ? ", " : ""}
                  <a href={toRepoHref(filePath)} target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">
                    {filePath}
                  </a>
                </span>
              ))
            : "-"}
        </p>
        <p className="text-muted-foreground">evidence_refs {[...evidenceRefs].sort().slice(0, 5).join(" | ") || "-"}</p>
      </section>

      <section className="rounded border p-4 space-y-2 text-sm">
        <h2 className="font-semibold">Linked Implementation</h2>
        <p>
          <Link href={`/flow?spec_id=${encodeURIComponent(specId)}`} className="underline hover:text-foreground">
            Open implementation view for this spec
          </Link>
        </p>
        <p className="text-muted-foreground">
          implementation_refs{" "}
          {[...implementationRefs].sort().length > 0
            ? [...implementationRefs].sort().slice(0, 8).map((ref, idx) => (
                <span key={ref}>
                  {idx > 0 ? ", " : ""}
                  <a href={toRepoHref(ref)} target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">
                    {ref}
                  </a>
                </span>
              ))
            : "-"}
        </p>
        <p className="text-muted-foreground">
          lineage_ids{" "}
          {[...lineageIds].sort().length > 0
            ? [...lineageIds].sort().slice(0, 8).map((lineageId, idx) => (
                <span key={lineageId}>
                  {idx > 0 ? ", " : ""}
                  <a
                    href={`/api/value-lineage/links/${encodeURIComponent(lineageId)}`}
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
          public_endpoints{" "}
          {[...publicEndpoints].sort().length > 0
            ? [...publicEndpoints].sort().slice(0, 6).map((endpoint, idx) => (
                <span key={endpoint}>
                  {idx > 0 ? ", " : ""}
                  <a href={endpoint} target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">
                    {endpoint}
                  </a>
                </span>
              ))
            : "-"}
        </p>
      </section>

      <section className="rounded border p-4 space-y-2 text-sm">
        <h2 className="font-semibold">Spec Summary + Process + Pseudocode + Implementation Notes</h2>
        <p className="text-muted-foreground">summary {registryItem?.summary || "-"}</p>
        <p className="text-muted-foreground">process_summary {registryItem?.process_summary || "-"}</p>
        <p className="text-muted-foreground">pseudocode_summary {registryItem?.pseudocode_summary || "-"}</p>
        <p className="text-muted-foreground">implementation_summary {registryItem?.implementation_summary || "-"}</p>
      </section>

      <section className="rounded border p-4 space-y-2 text-sm">
        <h2 className="font-semibold">API Links</h2>
        <ul className="space-y-1 text-muted-foreground">
          <li>
            <a href={`/api/spec-registry/${encodeURIComponent(specId)}`} target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">
              /api/spec-registry/{specId}
            </a>
          </li>
          <li>
            <a href="/api/inventory/flow?runtime_window_seconds=86400" target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">
              /api/inventory/flow
            </a>
          </li>
          <li>
            <a href="/api/inventory/system-lineage?runtime_window_seconds=86400" target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">
              /api/inventory/system-lineage
            </a>
          </li>
        </ul>
      </section>
    </main>
  );
}
