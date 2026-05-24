// Federation surface — a window into the peer-to-peer geometry the network
// has chosen to know. Four sections, each read-only:
//   1. This instance — pulse + self-declared capabilities
//   2. Known peers — registered instances + observed pulses
//   3. Substrate alignment — per-peer recipe-shape attestations (aligned /
//      diverged / discovered, all equal in dignity)
//   4. Capability comparison — side-by-side providers / languages / canonicals
//
// Every label honors that each instance speaks its own truth. Nothing here
// implies any instance has authority over another.

import type { Metadata } from "next";
import Link from "next/link";
import { cookies } from "next/headers";

import { getApiBase } from "@/lib/api";
import { createTranslator } from "@/lib/i18n";
import { DEFAULT_LOCALE, isSupportedLocale, type LocaleCode } from "@/lib/locales";
import PeerVerifyButton from "@/components/federation/PeerVerifyButton";
import CapabilityComparison from "@/components/federation/CapabilityComparison";

export const metadata: Metadata = {
  title: "Federation",
  description:
    "Each instance's own breath, capabilities, and structural alignment with peers — a window into federation as peer-to-peer dignity.",
};

// ─── Types ────────────────────────────────────────────────────────────────────

type OrganPulse = {
  name: string;
  status: string;
  score?: number;
  detail?: string;
};

type SelfPulse = {
  instance_id: string;
  overall: string;
  organs: OrganPulse[];
  silences?: unknown[];
  uptime_seconds?: number;
  as_of?: string;
  sample_duration_ms?: number;
};

type PeerPulseRecord = {
  peer_instance_id: string;
  observed_at?: string | null;
  pulse: Partial<SelfPulse> & Record<string, unknown>;
};

type PeerPulsesResponse = {
  instance_id: string;
  peers: PeerPulseRecord[];
  count: number;
};

type CapabilityManifest = {
  instance_id: string;
  instance_url: string;
  providers: string[];
  language_coverage: string[];
  substrate_canonicals: string[];
  economics: Record<string, unknown>;
  extensions?: Record<string, unknown>;
  declared_at?: string;
  truth_source?: string;
};

type FederatedInstance = {
  instance_id: string;
  name: string;
  endpoint_url: string;
  public_key?: string | null;
  registered_at: string;
  last_sync_at?: string | null;
  trust_level: string;
};

type Attestation = {
  peer_instance_id: string;
  canonical_name: string;
  peer_content_hash: string;
  local_content_hash?: string | null;
  alignment_status: "aligned" | "diverged" | "discovered" | string;
  observed_at?: string;
};

type AttestationsResponse = {
  peer_instance_id: string;
  attestations: Attestation[];
  count: number;
};

// ─── Loaders ──────────────────────────────────────────────────────────────────

async function fetchJson<T>(url: string): Promise<T | null> {
  try {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatTimestamp(iso?: string | null): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function formatUptime(seconds?: number): string {
  if (!seconds || seconds < 0) return "—";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m`;
  return `${seconds}s`;
}

function overallColor(overall?: string): { dot: string; text: string } {
  switch (overall) {
    case "breathing":
      return { dot: "bg-emerald-400", text: "text-emerald-300" };
    case "strained":
      return { dot: "bg-amber-400", text: "text-amber-300" };
    case "silent":
      return { dot: "bg-rose-400", text: "text-rose-300" };
    default:
      return { dot: "bg-muted-foreground", text: "text-muted-foreground" };
  }
}

function alignmentColor(status: string): {
  badge: string;
  mark: string;
  label: string;
} {
  switch (status) {
    case "aligned":
      return {
        badge: "border-amber-300/30 bg-amber-500/5 text-amber-200",
        mark: "✦",
        label: "recognized",
      };
    case "diverged":
      return {
        badge: "border-amber-500/30 bg-amber-500/5 text-amber-300/90",
        mark: "≠",
        label: "differs",
      };
    case "discovered":
      return {
        badge: "border-blue-400/30 bg-blue-500/5 text-blue-200",
        mark: "○",
        label: "available",
      };
    default:
      return {
        badge: "border-border/30 bg-background/30 text-muted-foreground",
        mark: "·",
        label: status,
      };
  }
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default async function FederationPage() {
  const apiBase = getApiBase();
  const cookieStore = await cookies();
  const cookieLang = cookieStore.get("NEXT_LOCALE")?.value;
  const lang: LocaleCode = isSupportedLocale(cookieLang) ? cookieLang : DEFAULT_LOCALE;
  const t = createTranslator(lang);
  // Client-side fetches use a same-origin path (apiBase is "" in browser).
  const browserApiBase = "";

  const [selfPulse, selfCaps, instances, peerPulses] = await Promise.all([
    fetchJson<SelfPulse>(`${apiBase}/api/pulse/self`),
    fetchJson<CapabilityManifest>(`${apiBase}/api/federation/capabilities/self`),
    fetchJson<FederatedInstance[]>(`${apiBase}/api/federation/instances`),
    fetchJson<PeerPulsesResponse>(`${apiBase}/api/pulse/peers`),
  ]);

  const peerList = Array.isArray(instances) ? instances : [];
  const peerPulseByInstance = new Map<string, PeerPulseRecord>();
  for (const p of peerPulses?.peers ?? []) {
    peerPulseByInstance.set(p.peer_instance_id, p);
  }

  // Per-peer attestations (parallel).
  const attestationEntries = await Promise.all(
    peerList.map(async (peer) => {
      const a = await fetchJson<AttestationsResponse>(
        `${apiBase}/api/federation/substrate/attestations/${encodeURIComponent(peer.instance_id)}`
      );
      return [peer.instance_id, a] as const;
    })
  );
  const attestationsByPeer = new Map<string, AttestationsResponse | null>();
  for (const [id, a] of attestationEntries) attestationsByPeer.set(id, a);

  // Per-peer fetched manifest (best-effort, may not be reachable).
  const peerManifestEntries = await Promise.all(
    peerList.map(async (peer) => {
      const m = await fetchJson<CapabilityManifest>(
        `${peer.endpoint_url.replace(/\/$/, "")}/api/federation/capabilities/self`
      );
      return [peer.instance_id, m] as const;
    })
  );
  const peerManifestById = new Map<string, CapabilityManifest | null>();
  for (const [id, m] of peerManifestEntries) peerManifestById.set(id, m);

  const selfColor = overallColor(selfPulse?.overall);
  const economicsEntries = Object.entries(selfCaps?.economics ?? {});

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-5xl mx-auto space-y-10">
      {/* ─── Header ──────────────────────────────────────────────────── */}
      <header className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">{t("federation.title")}</h1>
        <p className="max-w-3xl text-muted-foreground leading-relaxed">
          {t("federation.lede")}
        </p>
        <div className="flex flex-wrap gap-2 pt-1">
          <Link
            href="/nodes"
            className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200"
          >
            {t("federation.linkNodes")}
          </Link>
          <Link
            href="/constellation"
            className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200"
          >
            {t("federation.linkConstellation")}
          </Link>
        </div>
      </header>

      {/* ─── 1. This instance ───────────────────────────────────────── */}
      <section className="space-y-3">
        <h2 className="text-lg font-medium">{t("federation.selfHeading")}</h2>
        {selfPulse || selfCaps ? (
          <article className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-4">
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className={`inline-flex items-center gap-2 ${selfColor.text}`}>
                <span className={`h-2 w-2 rounded-full ${selfColor.dot}`} />
                <span className="text-base font-medium">
                  {selfPulse?.overall ?? t("federation.unknown")}
                </span>
              </span>
              <span className="text-sm text-muted-foreground">
                {selfPulse?.instance_id ?? selfCaps?.instance_id ?? t("federation.unknown")}
              </span>
              {selfPulse?.uptime_seconds !== undefined ? (
                <span className="text-xs text-muted-foreground">
                  {t("federation.uptime")}: {formatUptime(selfPulse.uptime_seconds)}
                </span>
              ) : null}
            </div>

            {selfPulse?.organs && selfPulse.organs.length > 0 ? (
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {selfPulse.organs.map((o) => {
                  const oc = overallColor(o.status);
                  return (
                    <div
                      key={o.name}
                      className="flex items-center justify-between rounded-lg border border-border/20 bg-background/30 px-3 py-2"
                    >
                      <span className="text-sm">{o.name}</span>
                      <span className={`text-xs ${oc.text}`}>{o.status}</span>
                    </div>
                  );
                })}
              </div>
            ) : null}

            {selfCaps ? (
              <div className="space-y-3 pt-1">
                <div className="text-xs uppercase tracking-widest text-muted-foreground">
                  {t("federation.selfDeclares")}
                </div>
                {selfCaps.providers.length > 0 ? (
                  <CapRow
                    label={t("federation.capProviders")}
                    items={selfCaps.providers}
                    tone="emerald"
                  />
                ) : null}
                {selfCaps.language_coverage.length > 0 ? (
                  <CapRow
                    label={t("federation.capLanguages")}
                    items={selfCaps.language_coverage}
                    tone="blue"
                  />
                ) : null}
                {selfCaps.substrate_canonicals.length > 0 ? (
                  <CapRow
                    label={t("federation.capSubstrate")}
                    items={selfCaps.substrate_canonicals.slice(0, 12)}
                    tone="amber"
                    overflow={
                      selfCaps.substrate_canonicals.length > 12
                        ? selfCaps.substrate_canonicals.length - 12
                        : 0
                    }
                  />
                ) : null}
                {economicsEntries.length > 0 ? (
                  <div className="flex flex-wrap gap-2 items-baseline">
                    <span className="text-xs text-muted-foreground/80 min-w-[7rem]">
                      {t("federation.capEconomics")}
                    </span>
                    {economicsEntries.map(([k, v]) => (
                      <span
                        key={k}
                        className="rounded-full border border-border/20 bg-background/40 px-2 py-0.5 text-xs text-muted-foreground"
                      >
                        {k}: {String(v)}
                      </span>
                    ))}
                  </div>
                ) : null}
                <p className="text-xs text-muted-foreground/70 pt-1">
                  {t("federation.truthSource")}
                </p>
              </div>
            ) : null}
          </article>
        ) : (
          <p className="rounded-2xl border border-dashed border-border/30 bg-background/30 p-6 text-sm text-muted-foreground">
            {t("federation.selfEmpty")}
          </p>
        )}
      </section>

      {/* ─── 2. Known peers ─────────────────────────────────────────── */}
      <section className="space-y-3">
        <h2 className="text-lg font-medium">{t("federation.peersHeading")}</h2>
        <p className="text-sm text-muted-foreground">{t("federation.peersLede")}</p>

        {peerList.length === 0 ? (
          <p className="rounded-2xl border border-dashed border-border/30 bg-background/30 p-6 text-sm text-muted-foreground">
            {t("federation.peersEmpty")}
          </p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {peerList.map((peer) => {
              const pulse = peerPulseByInstance.get(peer.instance_id);
              const overall = (pulse?.pulse?.overall as string | undefined) ?? undefined;
              const pc = overallColor(overall);
              return (
                <article
                  key={peer.instance_id}
                  className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3"
                >
                  <div className="space-y-1">
                    <h3 className="text-base font-medium">{peer.name}</h3>
                    <p className="text-xs text-muted-foreground font-mono">
                      {peer.instance_id}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <span className={`inline-flex items-center gap-1.5 ${pc.text}`}>
                      <span className={`h-1.5 w-1.5 rounded-full ${pc.dot}`} />
                      {overall ?? t("federation.peerPulseUnknown")}
                    </span>
                    <span className="rounded-full border border-blue-400/20 bg-blue-500/5 px-2 py-0.5 text-blue-200">
                      {peer.trust_level}
                    </span>
                  </div>
                  <div className="text-xs text-muted-foreground space-y-0.5">
                    <p>
                      <a
                        href={peer.endpoint_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="hover:text-foreground hover:underline break-all"
                      >
                        {peer.endpoint_url}
                      </a>
                    </p>
                    <p>
                      {t("federation.peerObservedAt")}: {formatTimestamp(pulse?.observed_at)}
                    </p>
                  </div>
                  <PeerVerifyButton
                    peerInstanceId={peer.instance_id}
                    peerEndpoint={peer.endpoint_url}
                    apiBase={browserApiBase}
                    labels={{
                      verify: t("federation.verify"),
                      verifying: t("federation.verifying"),
                      verified: t("federation.verified"),
                      unsigned: t("federation.unsigned"),
                      absent: t("federation.verifyAbsent"),
                    }}
                  />
                </article>
              );
            })}
          </div>
        )}
      </section>

      {/* ─── 3. Substrate alignment with peers ──────────────────────── */}
      {peerList.length > 0 ? (
        <section className="space-y-3">
          <h2 className="text-lg font-medium">{t("federation.alignmentHeading")}</h2>
          <p className="text-sm text-muted-foreground">{t("federation.alignmentLede")}</p>

          <div className="space-y-4">
            {peerList.map((peer) => {
              const a = attestationsByPeer.get(peer.instance_id);
              const items = a?.attestations ?? [];
              const counts = {
                aligned: items.filter((x) => x.alignment_status === "aligned").length,
                diverged: items.filter((x) => x.alignment_status === "diverged").length,
                discovered: items.filter((x) => x.alignment_status === "discovered").length,
              };
              return (
                <article
                  key={`align-${peer.instance_id}`}
                  className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/40 to-card/20 p-5 space-y-3"
                >
                  <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                    <h3 className="text-sm font-medium">{peer.name}</h3>
                    <span className="text-xs text-muted-foreground font-mono">
                      {peer.instance_id}
                    </span>
                  </div>
                  {items.length === 0 ? (
                    <p className="text-xs text-muted-foreground">
                      {t("federation.alignmentEmpty")}
                    </p>
                  ) : (
                    <>
                      <div className="flex flex-wrap gap-3 text-xs">
                        <span className="text-amber-200">
                          ✦ {counts.aligned} {t("federation.statusAligned")}
                        </span>
                        <span className="text-amber-300/90">
                          ≠ {counts.diverged} {t("federation.statusDiverged")}
                        </span>
                        <span className="text-blue-200">
                          ○ {counts.discovered} {t("federation.statusDiscovered")}
                        </span>
                      </div>
                      <div className="overflow-x-auto">
                        <table className="w-full min-w-[360px] text-xs">
                          <thead>
                            <tr className="text-muted-foreground/80">
                              <th className="text-left font-normal py-1.5 pr-3">
                                {t("federation.colCanonical")}
                              </th>
                              <th className="text-left font-normal py-1.5">
                                {t("federation.colMark")}
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {items.slice(0, 24).map((row) => {
                              const ac = alignmentColor(row.alignment_status);
                              return (
                                <tr
                                  key={`${row.canonical_name}-${row.alignment_status}`}
                                  className="border-t border-border/15"
                                >
                                  <td className="py-1.5 pr-3 font-mono">{row.canonical_name}</td>
                                  <td className="py-1.5">
                                    <span
                                      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 ${ac.badge}`}
                                    >
                                      <span>{ac.mark}</span>
                                      <span>{ac.label}</span>
                                    </span>
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                        {items.length > 24 ? (
                          <p className="text-xs text-muted-foreground/70 pt-2">
                            {t("federation.alignmentMore", {
                              n: items.length - 24,
                            })}
                          </p>
                        ) : null}
                      </div>
                    </>
                  )}
                </article>
              );
            })}
          </div>
        </section>
      ) : null}

      {/* ─── 4. Capability comparison ───────────────────────────────── */}
      {peerList.length > 0 && selfCaps ? (
        <section className="space-y-3">
          <h2 className="text-lg font-medium">{t("federation.compareHeading")}</h2>
          <p className="text-sm text-muted-foreground">{t("federation.compareLede")}</p>
          <div className="space-y-3">
            {peerList.map((peer) => {
              const peerCaps = peerManifestById.get(peer.instance_id);
              if (!peerCaps) {
                return (
                  <div
                    key={`cmp-${peer.instance_id}`}
                    className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/40 to-card/20 p-4 text-sm text-muted-foreground"
                  >
                    <span className="font-medium text-foreground">{peer.name}</span> — {t("federation.compareUnreachable")}
                  </div>
                );
              }
              return (
                <CapabilityComparison
                  key={`cmp-${peer.instance_id}`}
                  peerInstanceId={peer.instance_id}
                  us={{
                    providers: selfCaps.providers,
                    language_coverage: selfCaps.language_coverage,
                    substrate_canonicals: selfCaps.substrate_canonicals,
                  }}
                  peer={{
                    providers: peerCaps.providers ?? [],
                    language_coverage: peerCaps.language_coverage ?? [],
                    substrate_canonicals: peerCaps.substrate_canonicals ?? [],
                  }}
                  labels={{
                    title: t("federation.compareTitle", { peer: peer.name }),
                    expand: t("federation.compareExpand"),
                    collapse: t("federation.compareCollapse"),
                    kindProviders: t("federation.capProviders"),
                    kindLanguages: t("federation.capLanguages"),
                    kindSubstrate: t("federation.capSubstrate"),
                    us: t("federation.us"),
                    both: t("federation.both"),
                    usOnly: t("federation.usOnly"),
                    peerOnly: t("federation.peerOnly"),
                  }}
                />
              );
            })}
          </div>
        </section>
      ) : null}

      {/* ─── Footer ─────────────────────────────────────────────────── */}
      <nav
        className="py-8 text-center space-y-2 border-t border-border/20"
        aria-label="Related pages"
      >
        <p className="text-xs text-muted-foreground/80 uppercase tracking-wider">
          {t("federation.exploreMore")}
        </p>
        <div className="flex flex-wrap justify-center gap-4 text-sm">
          <Link href="/nodes" className="text-blue-400 hover:underline">
            {t("federation.linkNodes")}
          </Link>
          <Link href="/constellation" className="text-purple-400 hover:underline">
            {t("federation.linkConstellation")}
          </Link>
          <Link href="/vitality" className="text-emerald-400 hover:underline">
            {t("federation.linkVitality")}
          </Link>
        </div>
      </nav>
    </main>
  );
}

// ─── CapRow ───────────────────────────────────────────────────────────────────

function CapRow({
  label,
  items,
  tone,
  overflow = 0,
}: {
  label: string;
  items: string[];
  tone: "emerald" | "blue" | "amber";
  overflow?: number;
}) {
  const toneClass =
    tone === "emerald"
      ? "border-emerald-400/20 bg-emerald-500/5 text-emerald-200"
      : tone === "blue"
      ? "border-blue-400/20 bg-blue-500/5 text-blue-200"
      : "border-amber-400/20 bg-amber-500/5 text-amber-200";
  return (
    <div className="flex flex-wrap gap-2 items-baseline">
      <span className="text-xs text-muted-foreground/80 min-w-[7rem]">{label}</span>
      {items.map((item) => (
        <span
          key={item}
          className={`rounded-full border px-2 py-0.5 text-xs font-mono ${toneClass}`}
        >
          {item}
        </span>
      ))}
      {overflow > 0 ? (
        <span className="text-xs text-muted-foreground/70">+{overflow}</span>
      ) : null}
    </div>
  );
}
