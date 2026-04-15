import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getApiBase } from "@/lib/api";
import { ModelViewer } from "./_components/ModelViewer";

export const dynamic = "force-dynamic";

async function fetchAsset(id: string) {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/graph/nodes/${id}`, { next: { revalidate: 30 } });
    if (!res.ok) return null;
    return res.json();
  } catch { return null; }
}

export async function generateMetadata({ params }: { params: Promise<{ assetId: string }> }): Promise<Metadata> {
  const { assetId } = await params;
  const asset = await fetchAsset(assetId);
  return {
    title: asset ? `${asset.name} — Coherence Network` : "Asset",
    description: asset?.description?.slice(0, 300) || "",
  };
}

export default async function AssetPage({ params }: { params: Promise<{ assetId: string }> }) {
  const { assetId } = await params;
  const asset = await fetchAsset(assetId);

  if (!asset) notFound();

  const isModel = asset.asset_type === "MODEL_3D" || asset.name?.includes("3D") || asset.file_path?.endsWith(".gltf");
  const isImage = asset.asset_type === "IMAGE" || asset.file_path?.endsWith(".jpg");
  const creatorId = asset.creator_id || asset.properties?.creator_id || "unknown";
  const contentHash = asset.content_hash || asset.properties?.content_hash || "";
  const isNFT = asset.nft || asset.properties?.nft;
  const conceptId = asset.concept_id || asset.properties?.concept_id || "";
  const filePath = asset.file_path || asset.properties?.file_path || "";

  return (
    <main className="max-w-4xl mx-auto px-6 py-12">
      <nav className="text-sm text-stone-500 mb-6 flex items-center gap-2" aria-label="breadcrumb">
        <Link href="/vision" className="hover:text-amber-400/80 transition-colors">The Living Collective</Link>
        <span className="text-stone-700">/</span>
        {conceptId && (
          <>
            <Link href={`/vision/${conceptId}`} className="hover:text-amber-400/80 transition-colors">{conceptId}</Link>
            <span className="text-stone-700">/</span>
          </>
        )}
        <span className="text-stone-300">{asset.name || assetId}</span>
      </nav>

      <div className="mb-8 space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-3xl font-extralight text-white">{asset.name || assetId}</h1>
          {isNFT && (
            <span className="text-xs px-2.5 py-1 rounded-full border border-amber-500/30 text-amber-300/80">NFT</span>
          )}
        </div>
        <p className="text-stone-400 leading-relaxed">{asset.description}</p>
      </div>

      {/* Render the asset based on type */}
      {isModel && (
        <ModelViewer
          modelUrl={filePath || "/assets/models/community-nest.gltf"}
          caption={`${asset.name} — interactive 3D model. Drag to rotate, scroll to zoom.`}
        />
      )}

      {isImage && filePath && (
        <figure className="mb-8">
          <div className="relative aspect-[16/9] rounded-xl overflow-hidden bg-stone-800/50">
            <img src={filePath} alt={asset.name} className="object-cover w-full h-full" />
          </div>
          <figcaption className="text-xs text-stone-600 mt-2 italic">{asset.name}</figcaption>
        </figure>
      )}

      {/* Asset metadata */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-8">
        <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-5 space-y-3">
          <h2 className="text-sm font-medium text-stone-500 uppercase tracking-wider">Provenance</h2>
          <div className="space-y-2 text-sm text-stone-400">
            <div>Creator: <Link href={`/profile/${creatorId}`} className="text-amber-300/70 hover:text-amber-300">{creatorId}</Link></div>
            <div>Type: <span className="text-stone-300">{asset.asset_type || asset.type}</span></div>
            {contentHash && (
              <div>Hash: <code className="text-xs text-amber-400/40 font-mono">{contentHash.slice(0, 32)}...</code></div>
            )}
            {isNFT && <div className="text-amber-300/60">Tracked NFT — views flow CC to creator</div>}
          </div>
        </section>

        <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-5 space-y-3">
          <h2 className="text-sm font-medium text-stone-500 uppercase tracking-wider">Verification</h2>
          <div className="space-y-2 text-xs text-stone-500">
            <p>This asset is publicly verifiable:</p>
            <code className="block text-amber-400/40 font-mono bg-stone-900/50 p-2 rounded-lg break-all">
              GET /api/profile/{assetId}
            </code>
            <code className="block text-amber-400/40 font-mono bg-stone-900/50 p-2 rounded-lg break-all">
              GET /api/verification/chain/{assetId}
            </code>
          </div>
        </section>
      </div>

      {/* Renderer attribution */}
      {isModel && (
        <section className="mt-6 rounded-2xl border border-teal-800/20 bg-teal-900/5 p-5 space-y-2">
          <h2 className="text-sm font-medium text-teal-400/70 uppercase tracking-wider">Renderer</h2>
          <p className="text-sm text-stone-400">
            3D rendering by <span className="text-teal-300/70">gltf-viewer-v1</span> (Three.js + React Three Fiber).
            The renderer creator earns CC on every view alongside the asset creator.
          </p>
          <p className="text-xs text-stone-600">
            CC split: 80% asset creator / 15% renderer / 5% host
          </p>
        </section>
      )}
    </main>
  );
}
