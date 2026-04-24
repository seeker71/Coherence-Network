import Link from "next/link";

import { getApiBase } from "@/lib/api";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Settlement — Coherence Network",
  description:
    "Daily CC settlement batches — render aggregates, evidence multipliers, concept pools.",
};

type ConceptPool = {
  concept_id: string;
  cc_amount: string | number;
};

type SettlementEntry = {
  asset_id: string;
  read_count: number;
  base_cc_pool: string | number;
  evidence_multiplier: string | number;
  effective_cc_pool: string | number;
  cc_to_asset_creator: string | number;
  cc_to_renderer_creators: string | number;
  cc_to_host_nodes: string | number;
  concept_pools: ConceptPool[];
};

type SettlementBatch = {
  id: string;
  batch_date: string;
  entries: SettlementEntry[];
  total_read_count: number;
  total_cc_distributed: string | number;
  computed_at: string;
};

async function fetchBatches(): Promise<SettlementBatch[] | null> {
  try {
    const response = await fetch(`${getApiBase()}/api/settlement?limit=30`, {
      cache: "no-store",
    });
    if (!response.ok) return null;
    return (await response.json()) as SettlementBatch[];
  } catch {
    return null;
  }
}

function formatCc(value: string | number): string {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return "CC 0.0000";
  return `CC ${n.toFixed(4)}`;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

function BatchCard({ batch }: { batch: SettlementBatch }) {
  return (
    <div className="rounded border border-stone-800 bg-stone-950/40 p-4">
      <div className="flex items-baseline justify-between mb-3">
        <div>
          <div className="text-lg font-light text-white">
            {formatDate(batch.batch_date)}
          </div>
          <div className="text-xs text-stone-500">
            {batch.total_read_count} read
            {batch.total_read_count === 1 ? "" : "s"} across{" "}
            {batch.entries.length} asset
            {batch.entries.length === 1 ? "" : "s"}
          </div>
        </div>
        <div className="text-right">
          <div className="text-amber-400/80 font-light">
            {formatCc(batch.total_cc_distributed)}
          </div>
          <div className="text-xs text-stone-500 uppercase tracking-wide">
            distributed
          </div>
        </div>
      </div>
      {batch.entries.length > 0 && (
        <div className="space-y-1 text-xs">
          {batch.entries.slice(0, 8).map((e) => (
            <div
              key={e.asset_id}
              className="flex items-center justify-between text-stone-400"
            >
              <span className="truncate">{e.asset_id}</span>
              <span className="flex items-center gap-3">
                <span>{e.read_count} reads</span>
                {Number(e.evidence_multiplier) > 1 && (
                  <span className="text-amber-400/80">
                    ×{Number(e.evidence_multiplier).toFixed(1)}
                  </span>
                )}
                <span className="text-stone-300">
                  {formatCc(e.effective_cc_pool)}
                </span>
              </span>
            </div>
          ))}
          {batch.entries.length > 8 && (
            <div className="text-stone-600 text-xs">
              + {batch.entries.length - 8} more
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default async function SettlementDashboardPage() {
  const batches = await fetchBatches();

  return (
    <main className="max-w-3xl mx-auto px-6 py-12">
      <nav
        className="text-sm text-stone-500 mb-8 flex items-center gap-2"
        aria-label="breadcrumb"
      >
        <Link href="/" className="hover:text-amber-400/80 transition-colors">
          Home
        </Link>
        <span className="text-stone-700">/</span>
        <span className="text-stone-300">Settlement</span>
      </nav>

      <h1 className="text-3xl font-extralight text-white mb-2">Settlement</h1>
      <p className="text-stone-400 text-sm leading-relaxed mb-8">
        Daily CC distribution batches. Each batch aggregates render events,
        applies the evidence-verification multiplier (up to 5× per verified
        asset), and splits CC across asset creator, renderer creator, and host
        node shares — then distributes the creator's share across the asset's
        concept pools by tag weight.
      </p>

      {!batches && (
        <div className="rounded border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-200">
          Could not reach the settlement API.
        </div>
      )}

      {batches && batches.length === 0 && (
        <div className="rounded border border-stone-800 bg-stone-950/40 p-6 text-stone-400 text-sm">
          No settlement batches computed yet. A batch is produced each day the
          daily settlement job runs (<code>POST /api/settlement/run</code>).
          Once render events accumulate against an asset, the first batch will
          appear here.
        </div>
      )}

      {batches && batches.length > 0 && (
        <div className="space-y-4">
          {batches.map((batch) => (
            <BatchCard key={batch.id} batch={batch} />
          ))}
        </div>
      )}

      <p className="text-xs text-stone-500 mt-8">
        Settlement math lives at{" "}
        <code className="text-stone-400">
          api/app/services/settlement_service.py
        </code>
        . See <code className="text-stone-400">story-protocol-integration.md</code> R8.
      </p>
    </main>
  );
}
