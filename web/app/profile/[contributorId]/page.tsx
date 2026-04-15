import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getApiBase } from "@/lib/api";

export const dynamic = "force-dynamic";

/* ── Types ────────────────────────────────────────────────────────── */

type PublicKeyResponse = {
  contributor_id: string;
  public_key_hex: string;
};

type ProfileDimension = {
  dimension: string;
  strength: number;
};

type FrequencyProfile = {
  entity_id: string;
  dimensions: number;
  magnitude: number;
  hash: string;
  top: ProfileDimension[];
  profile: Record<string, number>;
};

type AssetNode = {
  id: string;
  type: string;
  name: string;
  description?: string;
  phase?: string;
  creator_id?: string;
  nft_token_id?: string;
  asset_type?: string;
  [key: string]: unknown;
};

type AssetListResponse = {
  items: AssetNode[];
  total: number;
};

/* ── Data fetching ────────────────────────────────────────────────── */

async function fetchPublicKey(contributorId: string): Promise<PublicKeyResponse | null> {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/contributors/${encodeURIComponent(contributorId)}/public-key`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

async function fetchFrequencyProfile(contributorId: string): Promise<FrequencyProfile | null> {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/profile/${encodeURIComponent(contributorId)}`, {
      next: { revalidate: 30 },
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

async function fetchAssets(contributorId: string): Promise<AssetNode[]> {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/graph/nodes?type=asset&limit=200`, {
      next: { revalidate: 30 },
    });
    if (!res.ok) return [];
    const data: AssetListResponse = await res.json();
    const items = Array.isArray(data.items) ? data.items : [];
    return items.filter(
      (node) => node.creator_id === contributorId || node.id.startsWith(`${contributorId}/`)
    );
  } catch {
    return [];
  }
}

function fingerprint(hex: string): string {
  if (!hex || hex.length < 16) return hex || "none";
  const segments: string[] = [];
  for (let i = 0; i < Math.min(hex.length, 40); i += 4) {
    segments.push(hex.slice(i, i + 4));
  }
  return segments.join(":").toUpperCase();
}

/* ── Dimension color mapping ──────────────────────────────────────── */

const DIMENSION_COLORS: Record<string, { bg: string; text: string }> = {
  concept: { bg: "bg-amber-500/15", text: "text-amber-400" },
  keyword: { bg: "bg-blue-500/15", text: "text-blue-400" },
  domain: { bg: "bg-purple-500/15", text: "text-purple-400" },
  edge: { bg: "bg-emerald-500/15", text: "text-emerald-400" },
  content: { bg: "bg-pink-500/15", text: "text-pink-400" },
};

function dimensionColor(dim: string): { bg: string; text: string } {
  const prefix = dim.split(":")[0]?.toLowerCase() || "";
  return (
    DIMENSION_COLORS[prefix] ?? { bg: "bg-stone-500/15", text: "text-stone-400" }
  );
}

/* ── Metadata ─────────────────────────────────────────────────────── */

export async function generateMetadata({
  params,
}: {
  params: Promise<{ contributorId: string }>;
}): Promise<Metadata> {
  const { contributorId } = await params;
  return {
    title: `${contributorId} — Contributor Profile`,
    description: `Public profile and frequency fingerprint for contributor ${contributorId} on the Coherence Network.`,
  };
}

/* ── Page ─────────────────────────────────────────────────────────── */

export default async function ContributorProfilePage({
  params,
}: {
  params: Promise<{ contributorId: string }>;
}) {
  const { contributorId } = await params;

  const [publicKeyData, profile, assets] = await Promise.all([
    fetchPublicKey(contributorId),
    fetchFrequencyProfile(contributorId),
    fetchAssets(contributorId),
  ]);

  // If there is no profile AND no public key, this contributor does not exist
  if (!profile && !publicKeyData) {
    notFound();
  }

  const pubKeyHex = publicKeyData?.public_key_hex;
  const fp = pubKeyHex ? fingerprint(pubKeyHex) : null;

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-4xl mx-auto space-y-8">
      {/* ── Identity ────────────────────────────────────────────── */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 sm:p-8 space-y-4">
        <p className="text-xs uppercase tracking-widest text-muted-foreground">
          Contributor Profile
        </p>
        <h1 className="text-3xl md:text-4xl font-light tracking-tight">
          {contributorId}
        </h1>

        {pubKeyHex ? (
          <div className="space-y-2">
            <div className="space-y-1">
              <p className="text-xs uppercase tracking-widest text-muted-foreground">
                Public Key
              </p>
              <p className="text-sm font-mono text-stone-300 break-all bg-stone-900/50 rounded-lg px-3 py-2 border border-border/20">
                {pubKeyHex}
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-xs uppercase tracking-widest text-muted-foreground">
                Fingerprint
              </p>
              <p className="text-sm font-mono text-amber-400/90 tracking-wider">
                {fp}
              </p>
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground italic">
            No public key registered yet. Keys can be registered via the Contribution Console.
          </p>
        )}
      </section>

      {/* ── Frequency Profile ───────────────────────────────────── */}
      <section className="rounded-2xl border border-amber-500/20 bg-gradient-to-b from-amber-500/5 to-card/30 p-6 sm:p-8 space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-widest text-amber-400">
              Frequency Profile
            </p>
            <p className="text-sm text-muted-foreground mt-1">
              Multi-dimensional resonance fingerprint derived from graph activity
            </p>
          </div>
          {profile && (
            <div className="text-right">
              <p className="text-2xl font-light text-amber-300">
                {profile.magnitude.toFixed(2)}
              </p>
              <p className="text-xs text-muted-foreground">magnitude</p>
            </div>
          )}
        </div>

        {profile ? (
          <>
            {/* Dimension pills */}
            <div className="flex flex-wrap gap-2">
              {profile.top.map((dim) => {
                const color = dimensionColor(dim.dimension);
                return (
                  <span
                    key={dim.dimension}
                    className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${color.bg} ${color.text}`}
                  >
                    <span>{dim.dimension}</span>
                    <span className="opacity-60">
                      {(dim.strength * 100).toFixed(0)}%
                    </span>
                  </span>
                );
              })}
            </div>

            {/* Stats row */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-2">
              <div className="rounded-xl border border-border/20 bg-background/40 p-3">
                <p className="text-xs text-muted-foreground">Dimensions</p>
                <p className="text-lg font-light mt-1">{profile.dimensions}</p>
              </div>
              <div className="rounded-xl border border-border/20 bg-background/40 p-3">
                <p className="text-xs text-muted-foreground">Magnitude</p>
                <p className="text-lg font-light mt-1">
                  {profile.magnitude.toFixed(4)}
                </p>
              </div>
              <div className="rounded-xl border border-border/20 bg-background/40 p-3 col-span-2 sm:col-span-1">
                <p className="text-xs text-muted-foreground">Profile Hash</p>
                <p className="text-xs font-mono text-stone-400 mt-1 truncate" title={profile.hash}>
                  {profile.hash.slice(0, 16)}...
                </p>
              </div>
            </div>
          </>
        ) : (
          <p className="text-sm text-muted-foreground italic">
            No frequency profile yet. Profile builds as this contributor interacts with the network.
          </p>
        )}
      </section>

      {/* ── Assets Created ──────────────────────────────────────── */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 sm:p-8 space-y-4">
        <p className="text-xs uppercase tracking-widest text-muted-foreground">
          Assets Created
        </p>

        {assets.length > 0 ? (
          <ul className="space-y-3">
            {assets.map((asset) => (
              <li
                key={asset.id}
                className="flex items-center justify-between gap-3 rounded-xl border border-border/20 bg-background/40 p-4"
              >
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-sm truncate">{asset.name}</p>
                  <div className="flex flex-wrap items-center gap-2 mt-1">
                    {asset.asset_type && (
                      <span className="inline-flex items-center rounded-full bg-blue-500/10 px-2 py-0.5 text-xs text-blue-400">
                        {asset.asset_type}
                      </span>
                    )}
                    <span className="inline-flex items-center rounded-full bg-stone-500/10 px-2 py-0.5 text-xs text-stone-400">
                      {asset.type}
                    </span>
                    {asset.phase && (
                      <span className="text-xs text-muted-foreground">
                        {asset.phase}
                      </span>
                    )}
                  </div>
                  {asset.description && (
                    <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                      {asset.description}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {asset.nft_token_id ? (
                    <span className="inline-flex items-center rounded-full bg-amber-500/15 px-2.5 py-0.5 text-xs font-medium text-amber-400 border border-amber-500/20">
                      NFT
                    </span>
                  ) : null}
                  <Link
                    href={`/nodes/${encodeURIComponent(asset.id)}`}
                    className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                  >
                    View
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground italic">
            No assets created yet.
          </p>
        )}
      </section>

      {/* ── Reading Activity ────────────────────────────────────── */}
      <section className="rounded-2xl border border-dashed border-border/30 bg-background/30 p-6 sm:p-8 space-y-3 text-center">
        <p className="text-xs uppercase tracking-widest text-muted-foreground">
          Reading Activity
        </p>
        <p className="text-sm text-muted-foreground">
          Reading history builds over time. As this contributor explores concepts,
          ideas, and stories across the network, their reading trail will appear here
          — a living map of curiosity.
        </p>
      </section>

      {/* ── Verification ────────────────────────────────────────── */}
      <section className="rounded-2xl border border-emerald-500/20 bg-gradient-to-b from-emerald-500/5 to-card/30 p-6 sm:p-8 space-y-4">
        <p className="text-xs uppercase tracking-widest text-emerald-400">
          Verification
        </p>
        <p className="text-sm text-muted-foreground">
          All profiles and keys are publicly verifiable. Use these endpoints to
          independently confirm this contributor's identity and frequency profile.
        </p>
        <div className="flex flex-wrap gap-3">
          {profile && (
            <Link
              href={`/verify?entity_id=${encodeURIComponent(contributorId)}&hash=${encodeURIComponent(profile.hash)}`}
              className="inline-flex items-center rounded-full border border-emerald-500/20 bg-emerald-500/10 px-4 py-1.5 text-sm text-emerald-400 hover:bg-emerald-500/20 transition-colors"
            >
              Verify Profile Hash
            </Link>
          )}
          {pubKeyHex && (
            <Link
              href={`/verify?contributor_id=${encodeURIComponent(contributorId)}&type=public-key`}
              className="inline-flex items-center rounded-full border border-emerald-500/20 bg-emerald-500/10 px-4 py-1.5 text-sm text-emerald-400 hover:bg-emerald-500/20 transition-colors"
            >
              Verify Public Key
            </Link>
          )}
          <Link
            href={`/contributors?contributor_id=${encodeURIComponent(contributorId)}`}
            className="inline-flex items-center rounded-full border border-border/20 bg-background/40 px-4 py-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            View Contributions
          </Link>
        </div>
      </section>

      {/* ── Navigation ──────────────────────────────────────────── */}
      <nav
        className="py-6 text-center space-y-2 border-t border-border/20"
        aria-label="Related pages"
      >
        <div className="flex flex-wrap justify-center gap-4 text-sm">
          <Link href="/contributors" className="text-muted-foreground hover:text-foreground transition-colors">
            All Contributors
          </Link>
          <Link href="/discover" className="text-purple-400 hover:underline">
            Discover
          </Link>
          <Link href="/resonance" className="text-amber-400 hover:underline">
            Resonance
          </Link>
        </div>
      </nav>
    </main>
  );
}
