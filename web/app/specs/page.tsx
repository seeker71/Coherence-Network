import Link from "next/link";

import { getApiBase } from "@/lib/api";

type SpecItem = {
  spec_id: string;
  title: string;
  path: string;
};

type InventoryResponse = {
  specs?: {
    items?: SpecItem[];
  };
};

async function loadSpecs(): Promise<SpecItem[]> {
  const API = getApiBase();
  const res = await fetch(`${API}/api/inventory/system-lineage?runtime_window_seconds=86400`, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const json = (await res.json()) as InventoryResponse;
  return (json.specs?.items ?? []).filter((s) => Boolean(s?.spec_id));
}

export default async function SpecsPage() {
  const specs = await loadSpecs();

  return (
    <main className="min-h-screen p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex gap-3">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Home
        </Link>
        <Link href="/portfolio" className="text-muted-foreground hover:text-foreground">
          Portfolio
        </Link>
        <Link href="/ideas" className="text-muted-foreground hover:text-foreground">
          Ideas
        </Link>
        <Link href="/usage" className="text-muted-foreground hover:text-foreground">
          Usage
        </Link>
      </div>

      <h1 className="text-2xl font-bold">Specs</h1>
      <p className="text-muted-foreground">Human interface for specs discovered via `GET /api/inventory/system-lineage`.</p>

      <section className="rounded border p-4 space-y-3">
        <p className="text-sm text-muted-foreground">Total: {specs.length}</p>
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
    </main>
  );
}
