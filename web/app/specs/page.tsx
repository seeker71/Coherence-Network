import Link from "next/link";

import { getApiBase } from "@/lib/api";

type SpecItem = {
  spec_id: string;
  title: string;
  path: string;
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
  idea_id?: string | null;
  created_by_contributor_id?: string | null;
  updated_by_contributor_id?: string | null;
  updated_at: string;
};

async function loadSpecs(): Promise<{ source: string; items: SpecItem[]; registry: SpecRegistryEntry[] }> {
  const API = getApiBase();
  const [inventoryRes, registryRes] = await Promise.all([
    fetch(`${API}/api/inventory/system-lineage?runtime_window_seconds=86400`, { cache: "no-store" }),
    fetch(`${API}/api/spec-registry`, { cache: "no-store" }),
  ]);
  if (!inventoryRes.ok || !registryRes.ok) throw new Error(`HTTP ${inventoryRes.status}/${registryRes.status}`);
  const json = (await inventoryRes.json()) as InventoryResponse;
  const registryJson = (await registryRes.json()) as SpecRegistryEntry[];
  return {
    source: json.specs?.source ?? "unknown",
    items: (json.specs?.items ?? []).filter((s) => Boolean(s?.spec_id)),
    registry: Array.isArray(registryJson) ? registryJson : [],
  };
}

export default async function SpecsPage() {
  const { source, items: specs, registry } = await loadSpecs();

  return (
    <main className="min-h-screen p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Home
        </Link>
        <Link href="/portfolio" className="text-muted-foreground hover:text-foreground">
          Portfolio
        </Link>
        <Link href="/contribute" className="text-muted-foreground hover:text-foreground">
          Contribute
        </Link>
        <Link href="/ideas" className="text-muted-foreground hover:text-foreground">
          Ideas
        </Link>
        <Link href="/usage" className="text-muted-foreground hover:text-foreground">
          Usage
        </Link>
        <Link href="/flow" className="text-muted-foreground hover:text-foreground">
          Flow
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

      <h1 className="text-2xl font-bold">Specs</h1>
      <p className="text-muted-foreground">
        Human interface for specs discovered via `GET /api/inventory/system-lineage` plus contributor-authored registry via `GET /api/spec-registry`.
      </p>

      <section className="rounded border p-4 space-y-3">
        <p className="text-sm text-muted-foreground">
          Total: {specs.length} | source: {source}
        </p>
        <ul className="space-y-2 text-sm">
          {specs.map((s) => (
            <li key={s.spec_id} className="rounded border p-3">
              <div className="flex justify-between gap-3">
                <span className="font-medium">Spec {s.spec_id}</span>
                <span className="text-muted-foreground">{s.path}</span>
              </div>
              <p>{s.title}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded border p-4 space-y-3">
        <p className="text-sm text-muted-foreground">
          Registry specs: {registry.length} | create/update via{" "}
          <Link href="/contribute" className="underline hover:text-foreground">Contribution Console</Link>
        </p>
        <ul className="space-y-2 text-sm">
          {registry.map((s) => (
            <li key={s.spec_id} className="rounded border p-3">
              <div className="flex justify-between gap-3">
                <span className="font-medium">Spec {s.spec_id}</span>
                <span className="text-muted-foreground">updated {s.updated_at}</span>
              </div>
              <p>{s.title}</p>
              <p className="text-muted-foreground">{s.summary}</p>
              <p className="text-xs text-muted-foreground">
                idea {s.idea_id || "-"} | created_by {s.created_by_contributor_id || "-"} | updated_by{" "}
                {s.updated_by_contributor_id || "-"}
              </p>
            </li>
          ))}
          {registry.length === 0 && (
            <li className="text-muted-foreground">No contributor-authored registry specs yet.</li>
          )}
        </ul>
      </section>
    </main>
  );
}
