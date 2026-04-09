import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "Discover",
  description:
    "Ideas, people, and connections that resonate with you. Serendipity at the speed of thought.",
};

type DiscoveryItem = {
  kind: string;
  id: string;
  title: string;
  summary: string;
  score: number;
  reason: string;
  tags: string[];
};

type DiscoveryResponse = {
  contributor_id: string;
  items: DiscoveryItem[];
  generated_at: string;
};

type CrossDomainBridge = {
  idea_a_id: string;
  idea_a_name: string;
  idea_b_id: string;
  idea_b_name: string;
  bridge_concepts: string[];
  resonance_score: number;
  explanation: string;
};

type CrossDomainResponse = {
  bridges: CrossDomainBridge[];
};

type ResonanceProof = {
  total_pairs: number;
  cross_domain_pairs: number;
  proof_quality: number;
  computed_at: string;
};

const KIND_STYLES: Record<string, { bg: string; text: string; border: string; label: string }> = {
  resonant_idea: {
    bg: "bg-blue-500/10",
    text: "text-blue-400",
    border: "border-blue-500/20",
    label: "Idea",
  },
  resonant_peer: {
    bg: "bg-emerald-500/10",
    text: "text-emerald-400",
    border: "border-emerald-500/20",
    label: "Peer",
  },
  cross_domain: {
    bg: "bg-purple-500/10",
    text: "text-purple-400",
    border: "border-purple-500/20",
    label: "Cross-Domain",
  },
  resonant_news: {
    bg: "bg-amber-500/10",
    text: "text-amber-400",
    border: "border-amber-500/20",
    label: "News",
  },
  growth_edge: {
    bg: "bg-pink-500/10",
    text: "text-pink-400",
    border: "border-pink-500/20",
    label: "Growth Edge",
  },
};

function getKindStyle(kind: string) {
  return (
    KIND_STYLES[kind] ?? {
      bg: "bg-muted",
      text: "text-muted-foreground",
      border: "border-border/30",
      label: kind.replace(/_/g, " "),
    }
  );
}

async function loadDiscovery(): Promise<DiscoveryItem[]> {
  try {
    const API = getApiBase();
    const res = await fetch(
      `${API}/api/discover/default-contributor?limit=30`,
      { cache: "no-store" },
    );
    if (!res.ok) return [];
    const data = (await res.json()) as DiscoveryResponse;
    return Array.isArray(data.items) ? data.items : [];
  } catch {
    return [];
  }
}

async function loadCrossDomain(): Promise<CrossDomainBridge[]> {
  try {
    const API = getApiBase();
    const res = await fetch(`${API}/api/resonance/cross-domain?limit=10`, {
      cache: "no-store",
    });
    if (!res.ok) return [];
    const data = (await res.json()) as CrossDomainResponse;
    return Array.isArray(data.bridges) ? data.bridges : [];
  } catch {
    return [];
  }
}

async function loadResonanceProof(): Promise<ResonanceProof | null> {
  try {
    const API = getApiBase();
    const res = await fetch(`${API}/api/resonance/proof`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as ResonanceProof;
  } catch {
    return null;
  }
}

export default async function DiscoverPage() {
  const [discoveryItems, crossDomainBridges, proof] = await Promise.all([
    loadDiscovery(),
    loadCrossDomain(),
    loadResonanceProof(),
  ]);

  const useFallback = discoveryItems.length === 0;
  const items = discoveryItems;

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-6xl mx-auto space-y-8">
      {/* Header */}
      <header className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Discover</h1>
        <p className="max-w-3xl text-muted-foreground leading-relaxed">
          Ideas, people, and connections that resonate. Let serendipity guide
          you to what matters.
        </p>
      </header>

      {/* Resonance proof stats bar */}
      {proof ? (
        <section className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4">
            <p className="text-xs uppercase tracking-widest text-muted-foreground">
              Total Pairs
            </p>
            <p className="mt-2 text-3xl font-light">
              {proof.total_pairs.toLocaleString()}
            </p>
          </div>
          <div className="rounded-2xl border border-purple-500/20 bg-gradient-to-b from-purple-500/5 to-card/30 p-4">
            <p className="text-xs uppercase tracking-widest text-purple-400">
              Cross-Domain
            </p>
            <p className="mt-2 text-3xl font-light text-purple-300">
              {proof.cross_domain_pairs.toLocaleString()}
            </p>
          </div>
          <div className="rounded-2xl border border-emerald-500/20 bg-gradient-to-b from-emerald-500/5 to-card/30 p-4">
            <p className="text-xs uppercase tracking-widest text-emerald-400">
              Proof Quality
            </p>
            <p className="mt-2 text-3xl font-light text-emerald-300">
              {(proof.proof_quality * 100).toFixed(0)}%
            </p>
          </div>
        </section>
      ) : null}

      {/* Main discovery feed */}
      {!useFallback && items.length > 0 ? (
        <section className="space-y-4">
          <h2 className="text-lg font-medium">Your Feed</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {items.map((item, idx) => {
              const style = getKindStyle(item.kind);
              return (
                <article
                  key={`${item.kind}-${item.id}`}
                  className={`rounded-2xl border ${style.border} bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3 animate-fade-in-up`}
                  style={{ animationDelay: `${idx * 0.04}s` }}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1 space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${style.bg} ${style.text}`}
                        >
                          {style.label}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {(item.score * 100).toFixed(0)}% match
                        </span>
                      </div>
                      <h3 className="text-base font-medium leading-snug">
                        {item.title}
                      </h3>
                    </div>
                  </div>

                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {item.summary}
                  </p>

                  <p className="text-xs text-muted-foreground/80 italic">
                    {item.reason}
                  </p>

                  {item.tags.length > 0 ? (
                    <div className="flex flex-wrap gap-1.5">
                      {item.tags.map((tag) => (
                        <span
                          key={tag}
                          className="rounded-full border border-border/20 bg-background/40 px-2 py-0.5 text-xs text-muted-foreground"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </article>
              );
            })}
          </div>
        </section>
      ) : null}

      {/* Fallback: cross-domain bridges shown directly */}
      {useFallback && crossDomainBridges.length > 0 ? (
        <section className="space-y-4">
          <h2 className="text-lg font-medium">Cross-Domain Bridges</h2>
          <p className="text-sm text-muted-foreground">
            Discovery feed is warming up. Here are resonant connections across
            domains.
          </p>
          <div className="space-y-3">
            {crossDomainBridges.map((bridge, idx) => (
              <article
                key={`${bridge.idea_a_id}-${bridge.idea_b_id}`}
                className="rounded-2xl border border-purple-500/20 bg-gradient-to-b from-purple-500/5 to-card/30 p-5 space-y-3 animate-fade-in-up"
                style={{ animationDelay: `${idx * 0.05}s` }}
              >
                <div className="flex items-center gap-3 text-sm">
                  <Link
                    href={`/ideas/${encodeURIComponent(bridge.idea_a_id)}`}
                    className="font-medium hover:text-purple-400 transition-colors"
                  >
                    {bridge.idea_a_name}
                  </Link>
                  <span className="text-purple-400/60">---</span>
                  <Link
                    href={`/ideas/${encodeURIComponent(bridge.idea_b_id)}`}
                    className="font-medium hover:text-purple-400 transition-colors"
                  >
                    {bridge.idea_b_name}
                  </Link>
                  <span className="ml-auto text-xs text-purple-400">
                    {(bridge.resonance_score * 100).toFixed(0)}%
                  </span>
                </div>

                <p className="text-sm text-muted-foreground">
                  {bridge.explanation}
                </p>

                {bridge.bridge_concepts.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {bridge.bridge_concepts.map((concept) => (
                      <span
                        key={concept}
                        className="rounded-full border border-purple-500/20 bg-purple-500/5 px-2 py-0.5 text-xs text-purple-300"
                      >
                        {concept}
                      </span>
                    ))}
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {/* Cross-domain section (shown alongside main feed, not as fallback) */}
      {!useFallback && crossDomainBridges.length > 0 ? (
        <section className="space-y-4">
          <h2 className="text-lg font-medium">Cross-Domain Bridges</h2>
          <p className="text-sm text-muted-foreground">
            Unexpected connections between different domains.
          </p>
          <div className="space-y-3">
            {crossDomainBridges.map((bridge, idx) => (
              <article
                key={`${bridge.idea_a_id}-${bridge.idea_b_id}`}
                className="rounded-2xl border border-purple-500/20 bg-gradient-to-b from-purple-500/5 to-card/30 p-5 space-y-3 animate-fade-in-up"
                style={{ animationDelay: `${idx * 0.05}s` }}
              >
                <div className="flex items-center gap-3 text-sm">
                  <Link
                    href={`/ideas/${encodeURIComponent(bridge.idea_a_id)}`}
                    className="font-medium hover:text-purple-400 transition-colors"
                  >
                    {bridge.idea_a_name}
                  </Link>
                  <span className="text-purple-400/60">---</span>
                  <Link
                    href={`/ideas/${encodeURIComponent(bridge.idea_b_id)}`}
                    className="font-medium hover:text-purple-400 transition-colors"
                  >
                    {bridge.idea_b_name}
                  </Link>
                  <span className="ml-auto text-xs text-purple-400">
                    {(bridge.resonance_score * 100).toFixed(0)}%
                  </span>
                </div>
                <p className="text-sm text-muted-foreground">
                  {bridge.explanation}
                </p>
                {bridge.bridge_concepts.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {bridge.bridge_concepts.map((concept) => (
                      <span
                        key={concept}
                        className="rounded-full border border-purple-500/20 bg-purple-500/5 px-2 py-0.5 text-xs text-purple-300"
                      >
                        {concept}
                      </span>
                    ))}
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {/* Empty state */}
      {items.length === 0 && crossDomainBridges.length === 0 ? (
        <section className="rounded-2xl border border-dashed border-border/30 bg-background/30 p-8 text-center space-y-3">
          <p className="text-muted-foreground">
            The discovery engine is still gathering signals. Check back soon as
            the network learns what resonates with you.
          </p>
          <div className="flex flex-wrap justify-center gap-4 text-sm">
            <Link
              href="/ideas"
              className="text-blue-400 hover:underline"
            >
              Browse ideas
            </Link>
            <Link
              href="/resonance"
              className="text-purple-400 hover:underline"
            >
              View resonance
            </Link>
          </div>
        </section>
      ) : null}

      {/* Navigation */}
      <nav
        className="py-8 text-center space-y-2 border-t border-border/20"
        aria-label="Related pages"
      >
        <p className="text-xs text-muted-foreground/80 uppercase tracking-wider">
          Explore more
        </p>
        <div className="flex flex-wrap justify-center gap-4 text-sm">
          <Link href="/resonance" className="text-purple-400 hover:underline">
            Resonance
          </Link>
          <Link href="/constellation" className="text-blue-400 hover:underline">
            Constellation
          </Link>
          <Link href="/vitality" className="text-emerald-400 hover:underline">
            Vitality
          </Link>
          <Link href="/ideas" className="text-amber-400 hover:underline">
            All Ideas
          </Link>
        </div>
      </nav>
    </main>
  );
}
