import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getApiBase } from "@/lib/api";
import { FrequencySpectrum } from "./_components/FrequencySpectrum";
import { PresenceStory } from "./_components/PresenceStory";

export const dynamic = "force-dynamic";

/* ── Types ────────────────────────────────────────────────────────── */

type PublicKeyResponse = {
  contributor_id: string;
  public_key_hex: string;
};

type ProfileDimension = {
  view: string; // 'structural' | 'categorical' | 'semantic'
  dimension: string;
  strength: number;
};

type ViewSummary = { dimensions: number; magnitude: number };

type FrequencyProfile = {
  entity_id: string;
  dimensions: number;
  magnitude: number;
  hash: string;
  top: ProfileDimension[];
  views: Record<string, ViewSummary>;
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

type ContributorNode = {
  id: string;
  name?: string;
  description?: string;
  author_display_name?: string;
  email?: string;
  location?: string;
  skills?: string;
  offering?: string;
  resonant_roles?: string[];
  locale?: string;
  [key: string]: unknown;
};

/* ── Data fetching ────────────────────────────────────────────────── */

async function fetchContributorNode(contributorId: string): Promise<ContributorNode | null> {
  // Check the graph node itself — this is the source of truth for
  // "does this contributor exist". The public-key and frequency-
  // profile endpoints 404 for any contributor who registered
  // without a keypair (most humans) or hasn't built up enough graph
  // activity to derive a frequency fingerprint yet. The profile page
  // should still render for them — that's most visitors on day one.
  const base = getApiBase();
  const nodeId = contributorId.startsWith("contributor:")
    ? contributorId
    : `contributor:${contributorId}`;
  try {
    const res = await fetch(`${base}/api/graph/nodes/${encodeURIComponent(nodeId)}`, {
      next: { revalidate: 30 },
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

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

/* ── Dimension resolution ─────────────────────────────────────────── */

type ResolvedDim = { label: string; href: string | null; nodeType: string | null };

function hrefForNode(id: string): string {
  // Every node id routes through the universal /nodes/[id] viewer,
  // which picks the right typed page inline.
  return `/nodes/${encodeURIComponent(id)}`;
}

function humanizeSynthetic(dim: string): string {
  if (dim === "_living") return "Living text";
  if (dim === "_source_backed") return "Source-backed";
  const rest = dim.slice(1);
  const colonIdx = rest.indexOf(":");
  const prefix = colonIdx === -1 ? rest : rest.slice(0, colonIdx);
  const value = colonIdx === -1 ? "" : rest.slice(colonIdx + 1);
  const labels: Record<string, string> = {
    domain: "Domain",
    kw: "Keyword",
    edge: "Edge",
    type: "Type",
    phase: "Phase",
    hz: "Hz",
    marker: "Marker",
    extraction: "Extraction",
    ingestion_policy: "Policy",
  };
  const label = labels[prefix] ?? prefix;
  return value ? `${label}: ${value}` : label;
}

async function resolveDimension(dim: string): Promise<ResolvedDim> {
  if (dim.startsWith("_")) {
    return { label: humanizeSynthetic(dim), href: null, nodeType: null };
  }
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/graph/nodes/${encodeURIComponent(dim)}`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) {
      return { label: dim, href: hrefForNode(dim), nodeType: null };
    }
    const node = await res.json();
    const name = node?.name || node?.author_display_name || dim;
    return { label: name, href: hrefForNode(dim), nodeType: node?.type ?? null };
  } catch {
    return { label: dim, href: hrefForNode(dim), nodeType: null };
  }
}

function dimensionColor(dim: string, nodeType: string | null): { bg: string; text: string } {
  if (dim === "_living") return { bg: "bg-pink-500/15", text: "text-pink-400" };
  if (dim === "_source_backed") return { bg: "bg-teal-500/15", text: "text-teal-400" };
  if (dim.startsWith("_")) return { bg: "bg-stone-500/15", text: "text-stone-400" };
  if (dim.startsWith("contributor:")) return { bg: "bg-rose-500/15", text: "text-rose-400" };
  if (dim.startsWith("asset:")) return { bg: "bg-blue-500/15", text: "text-blue-400" };
  if (dim.startsWith("idea:")) return { bg: "bg-emerald-500/15", text: "text-emerald-400" };
  if (dim.startsWith("spec:")) return { bg: "bg-cyan-500/15", text: "text-cyan-400" };
  if (dim.startsWith("community:") || dim.startsWith("event:") || dim.startsWith("gathering:")) {
    return { bg: "bg-purple-500/15", text: "text-purple-400" };
  }
  if (dim.startsWith("lc-") || nodeType === "concept") return { bg: "bg-amber-500/15", text: "text-amber-400" };
  return { bg: "bg-stone-500/15", text: "text-stone-400" };
}

/* ── Metadata ─────────────────────────────────────────────────────── */

export async function generateMetadata({
  params,
}: {
  params: Promise<{ contributorId: string }>;
}): Promise<Metadata> {
  const contributorId = decodeURIComponent((await params).contributorId);
  const contributor = await fetchContributorNode(contributorId);
  const name = contributor?.author_display_name || contributor?.name || contributorId;
  const lede = contributor?.offering || contributor?.skills
    || `Public profile and frequency fingerprint for contributor ${name} on the Coherence Network.`;
  return {
    title: `${name} — Contributor Profile`,
    description: lede.slice(0, 200),
  };
}

/* ── Page ─────────────────────────────────────────────────────────── */

export default async function ContributorProfilePage({
  params,
}: {
  params: Promise<{ contributorId: string }>;
}) {
  const rawContributorId = (await params).contributorId;
  // Next.js delivers dynamic params still URL-encoded. Node ids here
  // commonly contain a colon (contributor:liquid-bloom-xxx), which
  // arrives as contributor%3A... — failing the "starts with
  // contributor:" check and cascading into a 404. Decode once, up
  // front, so every downstream fetch and comparison sees the real id.
  const contributorId = decodeURIComponent(rawContributorId);

  const [contributor, publicKeyData, profile, assets] = await Promise.all([
    fetchContributorNode(contributorId),
    fetchPublicKey(contributorId),
    fetchFrequencyProfile(contributorId),
    fetchAssets(contributorId),
  ]);

  // Resolve each top dimension to a human label + href. Node-id dims
  // (lc-sensing, contributor:xxx, asset:xxx, community:xxx) get a name
  // fetched from /api/graph/nodes. Synthetic dims (_living, _domain:X)
  // get a readable label. Done in parallel so 15 dims resolve together.
  const resolvedDims = profile
    ? await Promise.all(profile.top.map((d) => resolveDimension(d.dimension)))
    : [];

  // A contributor exists when any of three signals land: the graph
  // node (source of truth), a registered public key, or a built-up
  // frequency profile. 404 only when ALL three are missing — a real
  // 'nobody's here' case, not just 'hasn't generated keys yet'.
  if (!contributor && !profile && !publicKeyData) {
    notFound();
  }

  const pubKeyHex = publicKeyData?.public_key_hex;
  const fp = pubKeyHex ? fingerprint(pubKeyHex) : null;
  const displayName = contributor?.author_display_name || contributor?.name || contributorId;

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-4xl mx-auto space-y-8">
      {/* ── Identity ────────────────────────────────────────────── */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 sm:p-8 space-y-4">
        <p className="text-xs uppercase tracking-widest text-muted-foreground">
          Contributor Profile
        </p>
        <h1 className="text-3xl md:text-4xl font-light tracking-tight">
          {displayName}
        </h1>
        {contributor?.location && (
          <p className="text-sm text-muted-foreground">{contributor.location}</p>
        )}
        {contributor?.skills && (
          <p className="text-sm text-foreground/85 leading-relaxed max-w-2xl">
            {contributor.skills}
          </p>
        )}
        {contributor?.offering && (
          <p className="text-sm text-foreground/85 leading-relaxed max-w-2xl italic">
            {contributor.offering}
          </p>
        )}
        {contributor?.resonant_roles && contributor.resonant_roles.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-1">
            {contributor.resonant_roles.map((role) => (
              <span
                key={role}
                className="inline-flex items-center rounded-full bg-amber-500/10 px-3 py-1 text-xs text-amber-400 border border-amber-500/20"
              >
                {role.replace(/-/g, " ")}
              </span>
            ))}
          </div>
        )}

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

      {/* ── Presence — their voice, first. The markdown story saved to the
         contributor's description; rendered as warm prose before any
         metrics or keys so a visitor meets the person before the profile. */}
      <PresenceStory
        content={contributor?.description as string | undefined}
        displayName={displayName}
      />

      {/* ── Living Frequency Spectrum — shaped by attention ──── */}
      <FrequencySpectrum contributorId={contributorId} />

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
            {/* Dimension pills — resolved names, linked where a page exists */}
            <div className="flex flex-wrap gap-2">
              {profile.top.map((dim, i) => {
                const resolved = resolvedDims[i] ?? { label: dim.dimension, href: null, nodeType: null };
                const color = dimensionColor(dim.dimension, resolved.nodeType);
                const chipClass = `inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${color.bg} ${color.text}`;
                const inner = (
                  <>
                    <span>{resolved.label}</span>
                    <span className="opacity-60 font-mono">{dim.strength.toFixed(2)}</span>
                  </>
                );
                return resolved.href ? (
                  <Link
                    key={`${dim.view}:${dim.dimension}`}
                    href={resolved.href}
                    className={`${chipClass} hover:opacity-80 transition-opacity`}
                  >
                    {inner}
                  </Link>
                ) : (
                  <span key={`${dim.view}:${dim.dimension}`} className={chipClass}>
                    {inner}
                  </span>
                );
              })}
            </div>
            <div className="grid grid-cols-3 gap-3">
              {(["structural", "categorical", "semantic"] as const).map((name) => {
                const v = profile.views?.[name];
                if (!v) return null;
                return (
                  <div key={name} className="rounded-xl border border-border/20 bg-background/40 p-3">
                    <p className="text-xs text-muted-foreground capitalize">{name}</p>
                    <p className="text-sm font-light mt-1">
                      <span className="font-mono">{v.magnitude.toFixed(2)}</span>
                      <span className="text-xs text-muted-foreground ml-1">· {v.dimensions} dims</span>
                    </p>
                  </div>
                );
              })}
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              The profile is three views fused for resonance matching.
              <em> Structural</em> weights come from personalized PageRank across the graph — multi-hop resonance with natural attenuation, not just direct edges.
              <em> Categorical</em> weights come from IDF (rare domain/keyword/type values carry more signal; values on every node carry near-zero signal).
              <em> Semantic</em> weights come from text frequency-scoring markers. Every weight emerges from the graph&apos;s own statistics, not hand-tuned constants.
              Resonance between two entities = cosine per view, fused by inverse-variance so no view dominates by scale alone.
            </p>

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
                    href={`/assets/${encodeURIComponent(asset.id)}`}
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
