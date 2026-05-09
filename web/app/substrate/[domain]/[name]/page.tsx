import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getApiBase } from "@/lib/api";

export const dynamic = "force-dynamic";

type NodeIdOut = {
  package: number;
  level: number;
  type: number;
  instance: number;
};

type CellOut = {
  cell_id: number;
  name: string;
  domain: string;
  blueprint: NodeIdOut;
  base?: NodeIdOut | null;
  access?: NodeIdOut | null;
  ctor?: NodeIdOut | null;
  source_path: string | null;
};

type EquivalentResponse = {
  blueprint: NodeIdOut;
  cells: CellOut[];
  count: number;
};

type AnnotateResponse = {
  path: string;
  cell?: CellOut | null;
  blueprint?: NodeIdOut | null;
  domain?: string | null;
  equivalents: CellOut[];
  equivalents_count: number;
  in_substrate: boolean;
};

function formatNodeId(nid: NodeIdOut | null | undefined) {
  if (!nid) return "—";
  return `@${nid.package}.${nid.level}.${nid.type}.${nid.instance}`;
}

async function fetchWithTimeout(url: string, timeoutMs = 3000): Promise<Response | null> {
  try {
    const controller = new AbortController();
    const t = setTimeout(() => controller.abort(), timeoutMs);
    const res = await fetch(url, {
      next: { revalidate: 30 },
      signal: controller.signal,
    });
    clearTimeout(t);
    return res.ok ? res : null;
  } catch {
    return null;
  }
}

function resolveApiBase(): string {
  // In dev, prefer localhost — the configured production base would
  // time out during local browsing.
  if (process.env.NODE_ENV !== "production") {
    return process.env.API_URL || "http://localhost:8000";
  }
  return getApiBase() || "";
}

async function fetchCell(domain: string, name: string): Promise<CellOut | null> {
  const res = await fetchWithTimeout(
    `${resolveApiBase()}/api/substrate/cell/${encodeURIComponent(domain)}/${encodeURIComponent(name)}`,
  );
  return res ? res.json() : null;
}

async function fetchEquivalents(
  domain: string,
  name: string,
): Promise<EquivalentResponse | null> {
  const res = await fetchWithTimeout(
    `${resolveApiBase()}/api/substrate/equivalent/${encodeURIComponent(domain)}/${encodeURIComponent(name)}`,
  );
  return res ? res.json() : null;
}

type PageProps = {
  params: Promise<{ domain: string; name: string }>;
};

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { domain, name } = await params;
  const decodedName = decodeURIComponent(name);
  return {
    title: `${decodedName} — ${domain} cell — Substrate`,
    description: `Substrate cell @${domain}('${decodedName}'): blueprint, structural equivalents, source.`,
  };
}

export default async function CellPage({ params }: PageProps) {
  const { domain, name } = await params;
  const decodedName = decodeURIComponent(name);

  const cell = await fetchCell(domain, decodedName);
  if (!cell) {
    notFound();
  }

  const equivalents = await fetchEquivalents(domain, decodedName);

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <nav className="mb-6 text-sm">
        <Link href="/substrate" className="text-muted-foreground hover:underline">
          ← substrate
        </Link>
      </nav>

      <header className="mb-8">
        <div className="mb-2 text-xs font-mono text-muted-foreground">
          @{cell.domain}({JSON.stringify(cell.name)})
        </div>
        <h1 className="text-2xl font-semibold">{cell.name}</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {cell.domain} cell, blueprint{" "}
          <code className="font-mono">{formatNodeId(cell.blueprint)}</code>
        </p>
      </header>

      <section className="mb-8 grid grid-cols-2 gap-4">
        <div className="rounded border p-4">
          <div className="text-xs text-muted-foreground">Blueprint NodeID</div>
          <div className="mt-1 font-mono text-sm">{formatNodeId(cell.blueprint)}</div>
          <div className="mt-2 text-xs text-muted-foreground">
            (ice phase — structural identity)
          </div>
        </div>
        <div className="rounded border p-4">
          <div className="text-xs text-muted-foreground">Constructor recipe</div>
          <div className="mt-1 font-mono text-sm">{formatNodeId(cell.ctor)}</div>
          <div className="mt-2 text-xs text-muted-foreground">
            (water phase — the seed-recipe)
          </div>
        </div>
      </section>

      {cell.source_path && (
        <section className="mb-8">
          <h2 className="mb-2 text-lg font-semibold">Source</h2>
          <code className="block rounded bg-muted px-3 py-2 font-mono text-xs break-all">
            {cell.source_path}
          </code>
        </section>
      )}

      <section className="mb-8">
        <h2 className="mb-2 text-lg font-semibold">
          Structural family
          {equivalents && (
            <span className="ml-2 text-sm font-normal text-muted-foreground">
              ({equivalents.count} other cell{equivalents.count !== 1 ? "s" : ""})
            </span>
          )}
        </h2>
        <p className="mb-3 text-sm text-muted-foreground">
          Cells whose Blueprint NodeID matches this one. Two cells in the same
          family are structurally identical regardless of name or domain — same
          frontmatter shape, same structural identity.
        </p>
        {equivalents && equivalents.cells.length > 0 ? (
          <ul className="space-y-1">
            {equivalents.cells.map((c) => (
              <li key={`${c.domain}/${c.name}`} className="text-sm">
                <Link
                  href={`/substrate/${c.domain}/${encodeURIComponent(c.name)}`}
                  className="hover:underline"
                >
                  <span className="font-mono text-xs text-muted-foreground">
                    [{c.domain}]
                  </span>{" "}
                  {c.name}
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">
            This cell has a unique shape. No other cell in the body shares its
            Blueprint NodeID — it's a singleton.
          </p>
        )}
      </section>

      <footer className="mt-12 border-t pt-6 text-xs text-muted-foreground">
        <p>
          See <code className="font-mono">docs/coherence-substrate/</code> for the
          architectural lineage and Form notation reference.
        </p>
      </footer>
    </main>
  );
}
