import Link from "next/link";
import { notFound } from "next/navigation";

import { getApiBase } from "@/lib/api";
import { ModelViewer } from "./_components/ModelViewer";

type Asset = {
  id: string;
  type: string;
  description: string;
  total_cost: string;
  created_at?: string;
};

type Contribution = {
  id: string;
  contributor_id: string;
  asset_id: string;
  cost_amount: string;
  coherence_score: number;
  timestamp: string;
  metadata?: {
    description?: string;
    summary?: string;
    commit_hash?: string;
  };
};

type Contributor = {
  id: string;
  name: string;
};

function formatCost(value: string | number): string {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return "CC 0.00";
  return `CC ${n.toFixed(2)}`;
}

function formatDate(value: string | undefined): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return value;
  }
}

async function loadAssetPage(assetId: string): Promise<{ asset: Asset | null; contributions: Contribution[]; contributorsById: Map<string, string> }> {
  const API = getApiBase();

  // All assets are graph nodes. Single source of truth.
  // Try direct node ID first, then legacy "asset:{uuid}" prefix.
  let asset: Asset | null = null;

  for (const nodeId of [assetId, `asset:${assetId}`]) {
    try {
      const res = await fetch(`${API}/api/graph/nodes/${encodeURIComponent(nodeId)}`, { cache: "no-store" });
      if (res.ok) {
        const node = await res.json();
        asset = {
          id: node.id,
          type: node.properties?.asset_type || node.type || "asset",
          description: node.description || node.name || assetId,
          total_cost: node.properties?.total_cost || "0",
          created_at: node.created_at,
          ...node.properties,
          name: node.name,
        } as any;
        break;
      }
    } catch {}
  }

  if (!asset) {
    return { asset: null, contributions: [], contributorsById: new Map() };
  }

  // Try to load contributions
  let contributions: Contribution[] = [];
  try {
    const res = await fetch(`${API}/api/assets/${encodeURIComponent(assetId)}/contributions`, { cache: "no-store" });
    if (res.ok) {
      const data = await res.json();
      contributions = data?.items ?? (Array.isArray(data) ? data : []);
    }
  } catch {}

  const contributorsById = new Map<string, string>();
  try {
    const res = await fetch(`${API}/api/contributors`, { cache: "no-store" });
    if (res.ok) {
      const data = await res.json();
      const list = data?.items ?? (Array.isArray(data) ? data : []);
      for (const c of list as Contributor[]) {
        if (c.id && c.name) contributorsById.set(c.id, c.name);
      }
    }
  } catch {}

  return { asset, contributions: Array.isArray(contributions) ? contributions : [], contributorsById };
}

export default async function AssetDetailPage({ params }: { params: Promise<{ asset_id: string }> }) {
  const resolved = await params;
  const assetId = decodeURIComponent(resolved.asset_id);
  const { asset, contributions, contributorsById } = await loadAssetPage(assetId);

  // Return a proper 404 status instead of rendering a 200 with "not found"
  // copy. Next.js will fall through to app/not-found.tsx (or the root
  // loading boundary) and set `Cache-Control: private, no-cache, no-store`.
  if (!asset) {
    notFound();
  }

  const totalContributionCost = contributions.reduce((sum, item) => sum + (Number(item.cost_amount) || 0), 0);
  const avgCoherence = contributions.length
    ? contributions.reduce((sum, item) => sum + (Number(item.coherence_score) || 0), 0) / contributions.length
    : null;

  return (
    <main className="min-h-screen p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/assets" className="text-muted-foreground hover:text-foreground">
          ← Assets
        </Link>
        <Link href={`/contributions?asset_id=${encodeURIComponent(asset.id)}`} className="text-muted-foreground hover:text-foreground">
          Contributions
        </Link>
      </div>

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-3xl font-bold tracking-tight">{asset.description || asset.type || "Untitled asset"}</h1>
              <span className="rounded-full border border-border/30 px-2 py-0.5 text-xs text-muted-foreground">
                {asset.type}
              </span>
            </div>
            <p className="text-sm text-muted-foreground font-mono">{asset.id}</p>
          </div>
          <div className="text-right text-sm text-muted-foreground">
            <p>Total tracked cost</p>
            <p className="text-2xl font-light text-foreground">{formatCost(asset.total_cost)}</p>
          </div>
        </div>
      </section>

      <section className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">Contributions</p>
          <p className="mt-2 text-3xl font-light">{contributions.length}</p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">Ledger Cost</p>
          <p className="mt-2 text-3xl font-light">{formatCost(totalContributionCost)}</p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">Avg Coherence</p>
          <p className="mt-2 text-3xl font-light">{avgCoherence === null ? "—" : avgCoherence.toFixed(2)}</p>
        </div>
      </section>

      {/* 3D Model / NFT rendering */}
      {(asset.type === "MODEL_3D" || asset.description?.includes("3D") || asset.id?.includes("model-")) && (
        <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 overflow-hidden">
          <ModelViewer
            modelUrl="/assets/models/community-nest.gltf"
            caption={`${asset.description || asset.type} — interactive 3D model. Drag to rotate, scroll to zoom.`}
          />
          <div className="p-4 space-y-2 border-t border-stone-800/20">
            <div className="flex items-center gap-2">
              <span className="text-xs px-2 py-0.5 rounded-full border border-amber-500/30 text-amber-300/80">NFT</span>
              <span className="text-xs px-2 py-0.5 rounded-full border border-teal-500/30 text-teal-300/80">3D Model</span>
              <span className="text-xs text-stone-500 ml-auto">Rendered by gltf-viewer-v1</span>
            </div>
            <p className="text-xs text-stone-600">
              Every view earns CC: 80% asset creator / 15% renderer / 5% host node
            </p>
          </div>
        </section>
      )}

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-medium">Contribution History</h2>
          <Link href={`/contributions?asset_id=${encodeURIComponent(asset.id)}`} className="text-sm underline hover:text-foreground">
            Open filtered ledger
          </Link>
        </div>
        {contributions.length > 0 ? (
          <ul className="space-y-2 text-sm">
            {contributions.map((contribution) => (
              <li key={contribution.id} className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-medium">
                      {contribution.metadata?.description || contribution.metadata?.summary || "Contribution"}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {formatDate(contribution.timestamp)} · coherence {Number(contribution.coherence_score || 0).toFixed(2)}
                    </p>
                  </div>
                  <p className="font-medium">{formatCost(contribution.cost_amount)}</p>
                </div>
                <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                  <Link
                    href={`/contributors/${encodeURIComponent(contribution.contributor_id)}/portfolio`}
                    className="underline hover:text-foreground"
                  >
                    {contributorsById.get(contribution.contributor_id) || contribution.contributor_id}
                  </Link>
                  <Link
                    href={`/contributors/${encodeURIComponent(contribution.contributor_id)}/portfolio/contributions/${encodeURIComponent(contribution.id)}`}
                    className="underline hover:text-foreground font-mono"
                  >
                    {contribution.id}
                  </Link>
                  {contribution.metadata?.commit_hash ? <span className="font-mono">commit {contribution.metadata.commit_hash.slice(0, 12)}</span> : null}
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">
            No contribution history is attached to this asset yet. When contributions land, this page will show who worked on it, when, and what it cost.
          </p>
        )}
      </section>
    </main>
  );
}
