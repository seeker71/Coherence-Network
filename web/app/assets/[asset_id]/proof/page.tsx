import Link from "next/link";

import { getApiBase } from "@/lib/api";
import { CopyShareButton } from "./_components/CopyShareButton";

export const dynamic = "force-dynamic";

type ProofCard = {
  asset_id: string;
  name: string;
  creator_handle: string;
  asset_type: string;
  use_count: number;
  cc_earned: string | number;
  arweave_url: string | null;
  verification_url: string;
  community_tags: string[];
};

async function fetchProofCard(assetId: string): Promise<ProofCard | null> {
  try {
    const response = await fetch(
      `${getApiBase()}/api/assets/${encodeURIComponent(assetId)}/proof-card`,
      { cache: "no-store" },
    );
    if (!response.ok) return null;
    return (await response.json()) as ProofCard;
  } catch {
    return null;
  }
}

function formatCc(value: string | number): string {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return "CC 0";
  return `CC ${n.toFixed(2)}`;
}

export default async function AssetProofPage({
  params,
}: {
  params: Promise<{ asset_id: string }>;
}) {
  const { asset_id } = await params;
  const card = await fetchProofCard(asset_id);

  if (!card) {
    return (
      <main className="max-w-2xl mx-auto px-6 py-12">
        <nav
          className="text-sm text-stone-500 mb-8 flex items-center gap-2"
          aria-label="breadcrumb"
        >
          <Link href="/" className="hover:text-amber-400/80 transition-colors">
            Home
          </Link>
          <span className="text-stone-700">/</span>
          <Link
            href="/creators"
            className="hover:text-amber-400/80 transition-colors"
          >
            Creators
          </Link>
          <span className="text-stone-700">/</span>
          <span className="text-stone-300">Proof</span>
        </nav>

        <h1 className="text-3xl font-extralight text-white mb-2">
          Asset not found
        </h1>
        <p className="text-stone-400 text-sm">
          No proof card exists for <code>{asset_id}</code>. The asset may not
          yet be published, or the id may be incorrect.
        </p>
      </main>
    );
  }

  const apiBase = getApiBase();
  const verificationHref = card.verification_url.startsWith("http")
    ? card.verification_url
    : `${apiBase}${card.verification_url}`;

  return (
    <main className="max-w-2xl mx-auto px-6 py-12">
      <nav
        className="text-sm text-stone-500 mb-8 flex items-center gap-2"
        aria-label="breadcrumb"
      >
        <Link href="/" className="hover:text-amber-400/80 transition-colors">
          Home
        </Link>
        <span className="text-stone-700">/</span>
        <Link
          href="/creators"
          className="hover:text-amber-400/80 transition-colors"
        >
          Creators
        </Link>
        <span className="text-stone-700">/</span>
        <span className="text-stone-300">Proof</span>
      </nav>

      <div className="rounded border border-stone-800 bg-stone-950/40 p-6">
        <div className="mb-4">
          <div className="text-xs text-stone-500 uppercase tracking-wide">
            {card.asset_type}
          </div>
          <h1 className="text-3xl font-extralight text-white mt-1">
            {card.name}
          </h1>
          <div className="text-sm text-stone-400 mt-1">
            by <span className="text-amber-400/80">{card.creator_handle}</span>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 mb-6">
          <div>
            <div className="text-3xl font-light text-white">
              {card.use_count}
            </div>
            <div className="text-xs text-stone-500 uppercase tracking-wide mt-1">
              {card.use_count === 1 ? "use" : "uses"}
            </div>
          </div>
          <div>
            <div className="text-3xl font-light text-amber-400/90">
              {formatCc(card.cc_earned)}
            </div>
            <div className="text-xs text-stone-500 uppercase tracking-wide mt-1">
              earned by creator
            </div>
          </div>
        </div>

        {card.community_tags.length > 0 && (
          <div className="mb-6 flex flex-wrap gap-2">
            {card.community_tags.map((tag) => (
              <span
                key={tag}
                className="text-xs rounded bg-stone-900 border border-stone-800 px-2 py-1 text-stone-300"
              >
                {tag}
              </span>
            ))}
          </div>
        )}

        <div className="flex flex-wrap gap-3">
          {card.arweave_url ? (
            <a
              href={card.arweave_url}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded border border-stone-700 bg-stone-900/50 px-4 py-2 text-sm text-stone-200 hover:border-amber-500/40 transition-colors"
            >
              Verify on Arweave →
            </a>
          ) : (
            <span
              className="rounded border border-stone-800 bg-stone-950/40 px-4 py-2 text-sm text-stone-500"
              title="No Arweave snapshot yet; verification still available via chain below"
            >
              Arweave pending
            </span>
          )}
          <a
            href={verificationHref}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded border border-stone-700 bg-stone-900/50 px-4 py-2 text-sm text-stone-200 hover:border-amber-500/40 transition-colors"
          >
            Check verification chain →
          </a>
          <CopyShareButton assetId={card.asset_id} />
        </div>
      </div>

      <p className="text-xs text-stone-500 mt-6">
        This page is shareable. Send the link to community admins as proof of
        provable, fair attribution.
      </p>
    </main>
  );
}
