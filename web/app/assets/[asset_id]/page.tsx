import type { Metadata } from "next";
import { cookies, headers } from "next/headers";
import Link from "next/link";
import { notFound } from "next/navigation";

import { getApiBase } from "@/lib/api";
import { decodeEntities } from "@/lib/html-entities";
import { DEFAULT_LOCALE, isSupportedLocale, type LocaleCode } from "@/lib/locales";
import { createTranslator } from "@/lib/i18n";
import { loadPublicWebConfig } from "@/lib/app-config";
import { AssetGlyph } from "@/app/_components/AssetGlyph";
import { assetTypeLabel } from "@/lib/asset-types";
import { LedgerNav } from "@/app/_components/LedgerNav";
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

function formatDate(value: string | undefined, locale: string): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleDateString(locale, {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return value;
  }
}

// Smaller helper used by generateMetadata — only resolves the asset itself.
// Avoids the extra contributions + contributors round-trips that aren't
// needed for share-card metadata.
async function loadAsset(assetId: string): Promise<Asset | null> {
  const API = getApiBase();

  let canonical: any = null;
  try {
    const res = await fetch(`${API}/api/assets/${encodeURIComponent(assetId)}`, { cache: "no-store" });
    if (res.ok) canonical = await res.json();
  } catch {}

  let node: any = null;
  for (const nodeId of [assetId, `asset:${assetId}`]) {
    try {
      const res = await fetch(`${API}/api/graph/nodes/${encodeURIComponent(nodeId)}`, { cache: "no-store" });
      if (res.ok) {
        node = await res.json();
        break;
      }
    } catch {}
  }

  if (!canonical && !node) return null;

  const merged: any = { ...(node || {}), ...(canonical || {}) };
  return {
    id: merged.id || canonical?.id || node?.id,
    type: canonical?.type || node?.asset_type || node?.type || "asset",
    description: canonical?.description || node?.description || node?.name || assetId,
    total_cost: canonical?.total_cost || node?.total_cost || "0",
    created_at: canonical?.created_at || node?.created_at,
    ...merged,
    name: node?.name || canonical?.name || canonical?.description,
  } as Asset;
}

async function loadAssetPage(assetId: string): Promise<{ asset: Asset | null; contributions: Contribution[]; contributorsById: Map<string, string> }> {
  const API = getApiBase();

  const asset = await loadAsset(assetId);
  if (!asset) {
    return { asset: null, contributions: [], contributorsById: new Map() };
  }

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

function truncateText(s: string, n: number): string {
  if (s.length <= n) return s;
  return `${s.slice(0, n - 1)}…`;
}

function absoluteAssetUrl(src: string | null | undefined, webUiBaseUrl: string): string | null {
  if (!src) return null;
  if (/^https?:\/\//i.test(src)) return src;
  if (src.startsWith("/")) return `${webUiBaseUrl.replace(/\/$/, "")}${src}`;
  return src;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ asset_id: string }>;
}): Promise<Metadata> {
  const resolved = await params;
  const assetId = decodeURIComponent(resolved.asset_id);
  const asset = await loadAsset(assetId);

  if (!asset) {
    return { title: "Vessel not found — Coherence Network" };
  }

  const webUiBaseUrl = loadPublicWebConfig().webUiBaseUrl;
  const displayName = decodeEntities((asset as any).name || asset.description || assetId);
  const displayDescription = decodeEntities(asset.description || displayName);
  const description = truncateText(displayDescription, 200);
  const title = `${displayName} — Coherence Network`;
  const url = `${webUiBaseUrl.replace(/\/$/, "")}/assets/${encodeURIComponent(asset.id)}`;

  const rawImage = (asset as any).image_url || (asset as any).file_path;
  const imageUrl = absoluteAssetUrl(rawImage, webUiBaseUrl) || `${webUiBaseUrl.replace(/\/$/, "")}/visuals/05-nourishing.png`;

  const mimeType: string | undefined = (asset as any).mime_type || undefined;
  const upperType = (asset.type || "").toUpperCase();
  const isMedia =
    !!mimeType && (mimeType.startsWith("audio/") || mimeType.startsWith("image/") || mimeType.startsWith("video/"))
    || upperType === "IMAGE"
    || upperType === "AUDIO"
    || upperType === "VIDEO"
    || upperType === "MODEL_3D";

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      url,
      images: [{ url: imageUrl }],
      type: isMedia ? "article" : "website",
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [imageUrl],
    },
  };
}

export default async function AssetDetailPage({ params }: { params: Promise<{ asset_id: string }> }) {
  const cookieLocale = (await cookies()).get("NEXT_LOCALE")?.value;
  const headerLang = (await headers()).get("accept-language")?.split(",")[0]?.split("-")[0];
  const candidate = cookieLocale || headerLang;
  const lang: LocaleCode = isSupportedLocale(candidate) ? candidate : DEFAULT_LOCALE;
  const t = createTranslator(lang);

  const resolved = await params;
  const assetId = decodeURIComponent(resolved.asset_id);
  const { asset, contributions, contributorsById } = await loadAssetPage(assetId);

  if (!asset) {
    notFound();
  }

  const totalContributionCost = contributions.reduce((sum, item) => sum + (Number(item.cost_amount) || 0), 0);
  const avgCoherence = contributions.length
    ? contributions.reduce((sum, item) => sum + (Number(item.coherence_score) || 0), 0) / contributions.length
    : null;

  const displayName = decodeEntities((asset as any).name || asset.description || assetId);
  const displayDescription = decodeEntities(asset.description || "");
  const imageSrc = (asset as any).file_path || (asset as any).image_url;

  const rawConceptTags = (asset as any).concept_tags;
  const conceptTags: { concept_id: string; weight: number }[] = Array.isArray(rawConceptTags)
    ? [...rawConceptTags]
        .filter((tag) => tag && typeof tag.concept_id === "string")
        .map((tag) => ({
          concept_id: String(tag.concept_id),
          weight: Number.isFinite(Number(tag.weight)) ? Number(tag.weight) : 0,
        }))
        .sort((a, b) => b.weight - a.weight)
    : [];

  const creatorId: string | undefined = (asset as any).creator_id || undefined;
  const mimeType: string | undefined = (asset as any).mime_type || undefined;
  const contentHash: string | undefined = (asset as any).content_hash || undefined;
  const ipfsCid: string | undefined = (asset as any).ipfs_cid || undefined;
  const arweaveTx: string | undefined = (asset as any).arweave_tx || undefined;
  const hasProvenance = !!(creatorId || mimeType || contentHash || ipfsCid || arweaveTx);
  const truncate = (s: string, n: number) => (s.length > n ? `${s.slice(0, n)}…` : s);

  // Schema.org JSON-LD — lets Google rich results, social aggregators and AI
  // crawlers correctly classify the asset. Type is picked from mime_type
  // (audio/image/video) or asset.type (IMAGE/VIDEO/MODEL_3D); everything
  // else falls back to CreativeWork. Null/undefined fields are skipped so
  // the JSON stays compact.
  const webUiBaseUrl = loadPublicWebConfig().webUiBaseUrl;
  const canonicalAssetUrl = `${webUiBaseUrl.replace(/\/$/, "")}/assets/${encodeURIComponent(asset.id)}`;
  const upperAssetType = (asset.type || "").toUpperCase();
  const schemaType = (() => {
    if (mimeType?.startsWith("audio/")) return "AudioObject";
    if (mimeType?.startsWith("image/") || upperAssetType === "IMAGE") return "ImageObject";
    if (mimeType?.startsWith("video/") || upperAssetType === "VIDEO") return "VideoObject";
    if (upperAssetType === "MODEL_3D") return "3DModel";
    return "CreativeWork";
  })();
  const contentUrl = absoluteAssetUrl((asset as any).image_url || (asset as any).file_path, webUiBaseUrl);
  const creatorName = creatorId ? contributorsById.get(creatorId) : undefined;
  const jsonLd: Record<string, unknown> = {
    "@context": "https://schema.org",
    "@type": schemaType,
    name: displayName,
    url: canonicalAssetUrl,
  };
  if (displayDescription) jsonLd.description = displayDescription;
  if (contentUrl) jsonLd.contentUrl = contentUrl;
  if (mimeType) jsonLd.encodingFormat = mimeType;
  if (contentHash) jsonLd.sha256 = contentHash;
  if (creatorId) {
    const creator: Record<string, unknown> = {
      "@type": "Person",
      url: `${webUiBaseUrl.replace(/\/$/, "")}/contributors/${encodeURIComponent(creatorId)}/portfolio`,
    };
    if (creatorName) creator.name = creatorName;
    jsonLd.creator = creator;
  }

  return (
    <main className="bg-stone-950 min-h-screen">
      <script
        type="application/ld+json"
        // Server-rendered, single object — embedding via dangerouslySetInnerHTML
        // is the standard Next.js pattern for JSON-LD and is what crawlers parse.
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <div className="mx-auto max-w-5xl px-4 sm:px-6 py-6 sm:py-10 space-y-6">
        <div className="flex items-center gap-3 text-sm">
          <Link href="/assets" className="text-stone-400 hover:text-amber-300 transition-colors">
            {t("assets.detail.backToAssets")}
          </Link>
        </div>

        <LedgerNav />

        {/* Hero card */}
        <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 sm:p-7 space-y-4">
          <div className="flex flex-wrap items-start gap-4 sm:gap-5">
            <AssetGlyph type={asset.type} className="flex-shrink-0 !w-14 !h-14" />
            <div className="flex-1 min-w-0 space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full border border-border/30 bg-card/40 px-2.5 py-0.5 text-[11px] uppercase tracking-[0.14em] text-stone-400">
                  {assetTypeLabel(t, asset.type)}
                </span>
              </div>
              <h1 className="text-2xl sm:text-4xl font-light tracking-tight text-stone-50 break-words">
                {displayName}
              </h1>
              {displayDescription && displayDescription !== displayName && (
                <p className="text-stone-300 leading-relaxed">{displayDescription}</p>
              )}
              <p className="text-xs text-stone-500 font-mono break-all">{asset.id}</p>
            </div>
            {Number(asset.total_cost) > 0 && (
              <div className="text-right shrink-0">
                <p className="text-[10px] uppercase tracking-[0.18em] text-stone-500">{t("assets.detail.totalCost")}</p>
                <p className="text-2xl font-light text-amber-300">{formatCost(asset.total_cost)}</p>
              </div>
            )}
          </div>
        </section>

        {/* Image / visual */}
        {imageSrc && (
          <section className="rounded-2xl border border-border/30 bg-card/30 overflow-hidden">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={imageSrc}
              alt={displayName}
              className="w-full h-auto max-h-[70vh] object-contain mx-auto"
            />
          </section>
        )}

        {/* Stats */}
        <section className="grid gap-3 grid-cols-3">
          <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4">
            <p className="text-[10px] uppercase tracking-[0.18em] text-stone-500">{t("assets.detail.statTouches")}</p>
            <p className="mt-2 text-2xl sm:text-3xl font-light text-stone-100">{contributions.length}</p>
            <p className="mt-1 text-xs text-stone-400">{t("assets.detail.statTouchesHint")}</p>
          </div>
          <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-amber-500/10 to-amber-500/5 p-4">
            <p className="text-[10px] uppercase tracking-[0.18em] text-amber-400/80">{t("assets.detail.statLedgerCost")}</p>
            <p className="mt-2 text-2xl sm:text-3xl font-light text-stone-100">{formatCost(totalContributionCost)}</p>
            <p className="mt-1 text-xs text-stone-400">{t("assets.detail.statLedgerCostHint")}</p>
          </div>
          <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4">
            <p className="text-[10px] uppercase tracking-[0.18em] text-stone-500">{t("assets.detail.statCoherence")}</p>
            <p className="mt-2 text-2xl sm:text-3xl font-light text-stone-100">{avgCoherence === null ? "—" : avgCoherence.toFixed(2)}</p>
            <p className="mt-1 text-xs text-stone-400">{t("assets.detail.statCoherenceHint")}</p>
          </div>
        </section>

        {/* 3D model */}
        {(asset.type === "MODEL_3D" || asset.description?.includes("3D") || asset.id?.includes("model-")) && (
          <section className="rounded-2xl border border-emerald-500/20 bg-stone-900/30 overflow-hidden">
            <ModelViewer
              modelUrl="/assets/models/community-nest.gltf"
              caption={t("assets.detail.modelCaption", {
                description: displayDescription || assetTypeLabel(t, asset.type),
              })}
            />
            <div className="p-4 space-y-2 border-t border-stone-800/30">
              <div className="flex items-center gap-2">
                <span className="text-xs px-2 py-0.5 rounded-full border border-amber-500/30 text-amber-300/80">{t("assets.detail.modelBadgeNft")}</span>
                <span className="text-xs px-2 py-0.5 rounded-full border border-emerald-500/30 text-emerald-300/80">{t("assets.detail.modelBadge3d")}</span>
                <span className="text-xs text-stone-500 ml-auto">{t("assets.detail.modelRenderer")}</span>
              </div>
              <p className="text-xs text-stone-500">{t("assets.detail.modelEarnings")}</p>
            </div>
          </section>
        )}

        {/* Contribution history */}
        <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 sm:p-6 space-y-4">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <h2 className="text-lg font-medium text-stone-100">{t("assets.detail.historyTitle")}</h2>
            {contributions.length > 0 && (
              <Link
                href={`/contributions?asset_id=${encodeURIComponent(asset.id)}`}
                className="text-sm text-stone-400 hover:text-amber-300 underline-offset-4 hover:underline"
              >
                {t("assets.detail.historyOpenLedger")}
              </Link>
            )}
          </div>
          {contributions.length > 0 ? (
            <ul className="space-y-3">
              {contributions.map((contribution) => {
                const summary = decodeEntities(
                  contribution.metadata?.description || contribution.metadata?.summary || t("assets.detail.historyContribution")
                );
                const coherence = Number(contribution.coherence_score || 0);
                return (
                  <li key={contribution.id} className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-2">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-stone-100 truncate">{summary}</p>
                        <p className="text-xs text-stone-400 mt-0.5">
                          {t("assets.detail.historySubtitle", {
                            date: formatDate(contribution.timestamp, lang),
                            coherence: coherence.toFixed(2),
                          })}
                        </p>
                      </div>
                      <p className="font-medium text-amber-300 whitespace-nowrap">{formatCost(contribution.cost_amount)}</p>
                    </div>
                    <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-stone-400">
                      <Link
                        href={`/contributors/${encodeURIComponent(contribution.contributor_id)}/portfolio`}
                        className="hover:text-amber-300 underline-offset-4 hover:underline"
                      >
                        {contributorsById.get(contribution.contributor_id) || contribution.contributor_id.slice(0, 8)}
                      </Link>
                      {contribution.metadata?.commit_hash && (
                        <span className="font-mono">{t("contributions.commit", { hash: contribution.metadata.commit_hash.slice(0, 12) })}</span>
                      )}
                      <Link
                        href={`/contributors/${encodeURIComponent(contribution.contributor_id)}/portfolio/contributions/${encodeURIComponent(contribution.id)}`}
                        className="ml-auto hover:text-amber-300 underline-offset-4 hover:underline"
                      >
                        {t("assets.detail.historyLinkAudit")}
                      </Link>
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="text-sm text-stone-400">{t("assets.detail.historyEmpty")}</p>
          )}
        </section>

        {/* Concepts — what this vessel resonates with */}
        {conceptTags.length > 0 && (
          <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 sm:p-6 space-y-4">
            <div className="space-y-1">
              <h2 className="text-lg font-medium text-stone-100">{t("assets.detail.conceptsTitle")}</h2>
              <p className="text-sm text-stone-400">{t("assets.detail.conceptsLede")}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              {conceptTags.map((tag) => (
                <Link
                  key={tag.concept_id}
                  href={`/vision/${encodeURIComponent(tag.concept_id)}`}
                  className="rounded-full border border-border/30 bg-card/40 px-3 py-1.5 text-xs whitespace-nowrap text-stone-300 transition-all hover:border-amber-400/30 hover:text-amber-200"
                >
                  {tag.concept_id}
                </Link>
              ))}
            </div>
          </section>
        )}

        {/* Provenance — origin and integrity of the vessel */}
        {hasProvenance && (
          <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 sm:p-6 space-y-4">
            <h2 className="text-lg font-medium text-stone-100">{t("assets.detail.provenanceTitle")}</h2>
            <dl className="grid gap-3 sm:grid-cols-2">
              {creatorId && (
                <div className="space-y-1">
                  <dt className="text-[10px] uppercase tracking-[0.18em] text-stone-500">{t("assets.detail.provenanceCreator")}</dt>
                  <dd>
                    <Link
                      href={`/contributors/${encodeURIComponent(creatorId)}/portfolio`}
                      className="text-stone-200 hover:text-amber-300 underline-offset-4 hover:underline"
                    >
                      {contributorsById.get(creatorId) || creatorId.slice(0, 12)}
                    </Link>
                  </dd>
                </div>
              )}
              {mimeType && (
                <div className="space-y-1">
                  <dt className="text-[10px] uppercase tracking-[0.18em] text-stone-500">{t("assets.detail.provenanceMimeType")}</dt>
                  <dd>
                    <span className="inline-flex items-center rounded-full border border-border/30 bg-card/40 px-2 py-0.5 text-[11px] font-mono text-stone-300">
                      {mimeType}
                    </span>
                  </dd>
                </div>
              )}
              {contentHash && (
                <div className="space-y-1">
                  <dt className="text-[10px] uppercase tracking-[0.18em] text-stone-500">{t("assets.detail.provenanceContentHash")}</dt>
                  <dd>
                    <span className="font-mono text-xs text-stone-300" title={contentHash}>
                      {truncate(contentHash, 12)}
                    </span>
                  </dd>
                </div>
              )}
              {ipfsCid && (
                <div className="space-y-1">
                  <dt className="text-[10px] uppercase tracking-[0.18em] text-stone-500">{t("assets.detail.provenanceIpfs")}</dt>
                  <dd>
                    <a
                      href={`https://ipfs.io/ipfs/${encodeURIComponent(ipfsCid)}`}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="font-mono text-xs text-stone-300 hover:text-amber-300 underline-offset-4 hover:underline"
                      title={ipfsCid}
                    >
                      {truncate(ipfsCid, 12)} <span className="text-stone-500">{t("assets.detail.provenanceLinkOpen")}</span>
                    </a>
                  </dd>
                </div>
              )}
              {arweaveTx && (
                <div className="space-y-1">
                  <dt className="text-[10px] uppercase tracking-[0.18em] text-stone-500">{t("assets.detail.provenanceArweave")}</dt>
                  <dd>
                    <a
                      href={`https://viewblock.io/arweave/tx/${encodeURIComponent(arweaveTx)}`}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="font-mono text-xs text-stone-300 hover:text-amber-300 underline-offset-4 hover:underline"
                      title={arweaveTx}
                    >
                      {truncate(arweaveTx, 12)} <span className="text-stone-500">{t("assets.detail.provenanceLinkOpen")}</span>
                    </a>
                  </dd>
                </div>
              )}
            </dl>
          </section>
        )}
      </div>
    </main>
  );
}
