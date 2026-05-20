import type { Metadata } from "next";
import Link from "next/link";
import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "Substrate — Coherence Network",
  description:
    "Browse the body's content-addressed lattice: every memory, spec, idea, concept, presence, and witness as a structural cell.",
};

export const dynamic = "force-dynamic";

type LatticeStats = {
  blueprints_total: number;
  recipes_total: number;
  cells_total: number;
};

type CellSummary = {
  cell_id: number;
  name: string;
  domain: string;
  blueprint: { package: number; level: number; type: number; instance: number };
  source_path: string | null;
};

type HistogramEntry = {
  blueprint: { package: number; level: number; type: number; instance: number };
  count: number;
  sample_names: string[];
};

type HistogramResponse = {
  domain: string;
  entries: HistogramEntry[];
};

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

async function fetchStats(): Promise<LatticeStats | null> {
  const res = await fetchWithTimeout(`${resolveApiBase()}/api/substrate/lattice/stats`);
  return res ? res.json() : null;
}

async function fetchHistogram(domain: string): Promise<HistogramResponse | null> {
  const res = await fetchWithTimeout(`${resolveApiBase()}/api/substrate/histogram/${domain}`);
  return res ? res.json() : null;
}

function formatNodeId(nid: { package: number; level: number; type: number; instance: number }) {
  return `@${nid.package}.${nid.level}.${nid.type}.${nid.instance}`;
}

const DOMAINS = [
  "concept",
  "spec",
  "idea",
  "presence",
  "lineage",
  "guide",
  "transmission",
  "kb_page",
  "language_view",
  "memory",
  "witness",
  "task",
  "resource",
  "harmonic",
  "topology",
] as const;

const DOMAIN_LABELS: Record<string, string> = {
  concept: "Concept",
  spec: "Spec",
  idea: "Idea",
  presence: "Presence",
  lineage: "Lineage",
  guide: "Guide",
  transmission: "Transmission",
  kb_page: "KB page",
  language_view: "Language view",
  memory: "Memory",
  witness: "Witness",
  task: "Task",
  resource: "Resource",
  harmonic: "Harmonic",
  topology: "Topology",
};

const DOMAIN_DESCRIPTIONS: Record<string, string> = {
  concept: "Vision-kb story: cross-refs, visuals, parent, geometry",
  spec: "Executable form: source, requirements, done_when, test, constraints",
  idea: "Problem-shape with capabilities, absorbed-ideas, spec-links",
  presence: "Contributor cell — HUMAN / AGENT / SYSTEM — with role and edges",
  lineage: "Transmission / embodiment records — where teachings entered the body",
  guide: "Practice and reader guides paired with concepts",
  transmission: "Source-marked teaching cells — what flowed through whom",
  kb_page: "General vision-KB pages and indexes outside the concept set",
  language_view: "Translated / localized projections of the KB content",
  memory: "Auto-loaded notes carrying tender context across sessions",
  witness: "Event-as-proof cells — the trace the body leaves of its own life",
  task: "Pipeline work-unit cells — open threads under tending",
  resource: "Source / extraction records — what was read, what was lifted",
  harmonic: "Solfeggio frequency bands carried by concepts (hz cells)",
  topology: "Topological shape vocabulary — values authored as geometry",
};

export default async function SubstratePage() {
  const stats = await fetchStats();
  const histograms = await Promise.all(
    DOMAINS.map(async (domain) => ({
      domain,
      data: await fetchHistogram(domain),
    })),
  );

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold">The body's substrate</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          A content-addressed numeric lattice. Every memory, spec, idea, concept,
          and presence in the body lives here as a cell with a Blueprint NodeID.
          Two structurally-identical cells share the same Blueprint — automatically.
        </p>
        <p className="mt-3 flex flex-wrap items-center gap-3 text-sm">
          <Link
            href="/substrate/form"
            className="inline-flex items-center gap-2 rounded border border-amber-500/20 bg-amber-500/10 px-3 py-1.5 text-amber-300/90 hover:bg-amber-500/20 transition-colors"
          >
            Form playground →
          </Link>
          <Link
            href="/substrate/ingest"
            className="inline-flex items-center gap-2 rounded border border-stone-800/40 px-3 py-1.5 text-stone-300 hover:border-amber-500/30 hover:text-amber-300/90 transition-colors"
          >
            Ingest content →
          </Link>
          <span className="text-muted-foreground">
            Ask the lattice structural questions, or place new content into it.
          </span>
        </p>
        {/* Doors for both kinds of visitor — the human curious about how
            the body works, and the AI arriving without a prior map. The
            agent guide is the canonical "how to ground reasoning in the
            lattice" doc; the language doc carries Form's design. */}
        <p className="mt-3 flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
          <Link
            href="https://github.com/seeker71/Coherence-Network/blob/main/docs/coherence-substrate/agents-using-substrate.md"
            className="underline hover:text-amber-300/80 transition-colors"
          >
            How AI agents use this lattice
          </Link>
          <Link
            href="https://github.com/seeker71/Coherence-Network/blob/main/docs/coherence-substrate/form-language.md"
            className="underline hover:text-amber-300/80 transition-colors"
          >
            Form language design
          </Link>
          <Link
            href="https://api.coherencycoin.com/docs#/substrate"
            className="underline hover:text-amber-300/80 transition-colors"
          >
            REST endpoints (Swagger)
          </Link>
        </p>
      </header>

      {stats && (
        <section className="mb-10 grid grid-cols-3 gap-4">
          <div className="rounded border p-4">
            <div className="text-3xl font-mono">{stats.cells_total}</div>
            <div className="text-xs text-muted-foreground">named cells</div>
          </div>
          <div className="rounded border p-4">
            <div className="text-3xl font-mono">{stats.blueprints_total}</div>
            <div className="text-xs text-muted-foreground">unique blueprint shapes</div>
          </div>
          <div className="rounded border p-4">
            <div className="text-3xl font-mono">{stats.recipes_total}</div>
            <div className="text-xs text-muted-foreground">recipe shapes</div>
          </div>
        </section>
      )}

      <section className="space-y-8">
        {histograms.map(({ domain, data }) => (
          <div key={domain}>
            <header className="mb-3 flex items-baseline justify-between">
              <h2 className="text-xl font-semibold">{DOMAIN_LABELS[domain]}</h2>
              <span className="text-xs text-muted-foreground">
                {data ? `${data.entries.reduce((s, e) => s + e.count, 0)} cells` : "loading"}
              </span>
            </header>
            <p className="mb-3 text-sm text-muted-foreground">
              {DOMAIN_DESCRIPTIONS[domain]}
            </p>

            {data && data.entries.length > 0 ? (
              <ul className="space-y-2">
                {data.entries.slice(0, 5).map((entry) => (
                  <li
                    key={`${domain}-${formatNodeId(entry.blueprint)}`}
                    className="rounded border p-3"
                  >
                    <div className="flex items-baseline justify-between">
                      <span className="font-mono text-xs text-muted-foreground">
                        {formatNodeId(entry.blueprint)}
                      </span>
                      <span className="text-sm">
                        {entry.count} cell{entry.count !== 1 ? "s" : ""} sharing this shape
                      </span>
                    </div>
                    <ul className="mt-2 flex flex-wrap gap-2 text-sm">
                      {entry.sample_names.map((name) => (
                        <li key={name}>
                          <Link
                            href={`/substrate/${domain}/${encodeURIComponent(name)}`}
                            className="rounded bg-muted px-2 py-1 hover:bg-muted/80"
                          >
                            {name}
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </li>
                ))}
                {data.entries.length > 5 && (
                  <li className="text-xs text-muted-foreground">
                    + {data.entries.length - 5} more shape
                    {data.entries.length - 5 !== 1 ? "s" : ""}
                  </li>
                )}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">No cells in this domain.</p>
            )}
          </div>
        ))}
      </section>

      <footer className="mt-12 border-t pt-6 text-xs text-muted-foreground">
        <p>
          The substrate is the body's content-addressed lattice. Background:{" "}
          <code className="font-mono">docs/coherence-substrate/</code> in the repo.
        </p>
      </footer>
    </main>
  );
}
