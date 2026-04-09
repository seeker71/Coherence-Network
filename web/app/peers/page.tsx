import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "Peers",
  description:
    "Discover contributors who share your interests and worldview through resonance matching.",
};

type PeerMatch = {
  contributor_id: string;
  name: string;
  resonance_score: number;
  shared_tags: string[];
  distance_km: number | null;
  city: string | null;
};

type PeerDiscoveryResponse = {
  peers: PeerMatch[];
  total: number;
};

async function loadPeers(): Promise<PeerDiscoveryResponse | null> {
  try {
    const API = getApiBase();
    const res = await fetch(
      `${API}/api/peers/resonant?contributor_id=system&limit=20`,
      { cache: "no-store" },
    );
    if (!res.ok) return null;
    return (await res.json()) as PeerDiscoveryResponse;
  } catch {
    return null;
  }
}

export default async function PeersPage() {
  const data = await loadPeers();
  const peers = data?.peers ?? [];

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-5xl mx-auto space-y-8">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Peer Discovery</h1>
        <p className="max-w-3xl text-muted-foreground leading-relaxed">
          Find contributors who share your interests and worldview. Peer
          discovery uses structural resonance -- comparing worldview axes,
          interest tags, and concept resonances -- to surface meaningful
          connections across the network.
        </p>
        <div className="flex flex-wrap gap-2">
          <Link
            href="/beliefs"
            className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200"
          >
            Beliefs
          </Link>
          <Link
            href="/discover"
            className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200"
          >
            Discover
          </Link>
        </div>
      </header>

      {/* Explanation */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3">
        <h2 className="text-lg font-medium">How Peer Matching Works</h2>
        <div className="space-y-2 text-sm text-muted-foreground">
          <p>
            Each contributor has a belief profile with worldview axes (scientific,
            spiritual, pragmatic, holistic, relational, systemic), interest tags,
            and concept resonances.
          </p>
          <p>
            The resonance score combines tag overlap (Jaccard similarity),
            worldview alignment (cosine similarity), and concept resonance overlap
            (weighted intersection) into a single 0.0--1.0 score.
          </p>
          <p>
            Use the{" "}
            <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
              /api/peers/resonant?contributor_id=YOUR_ID
            </code>{" "}
            endpoint to find your own resonant peers, or{" "}
            <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
              /api/peers/nearby
            </code>{" "}
            for geographically close contributors.
          </p>
        </div>
      </section>

      {/* Peer cards */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium">Sample Peer Matches</h2>
          <span className="text-xs text-muted-foreground">
            {data ? `${data.total} total matches` : "No data"}
          </span>
        </div>

        {peers.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/30 bg-background/30 p-8 text-center space-y-3">
            <p className="text-muted-foreground">
              No peers found. Peer matching requires contributors with belief
              profiles. Set up your profile to start discovering resonant peers.
            </p>
            <div className="flex flex-wrap justify-center gap-4 text-sm">
              <Link
                href="/beliefs"
                className="text-purple-400 hover:underline"
              >
                Set up belief profile
              </Link>
            </div>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {peers.map((peer) => {
              const scorePercent = Math.round(peer.resonance_score * 100);
              return (
                <article
                  key={peer.contributor_id}
                  className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <h3 className="text-base font-medium">
                        <Link
                          href={`/contributors?contributor_id=${encodeURIComponent(peer.contributor_id)}`}
                          className="hover:text-emerald-400 transition-colors"
                        >
                          {peer.name}
                        </Link>
                      </h3>
                      <p className="text-xs text-muted-foreground">
                        {peer.contributor_id}
                      </p>
                    </div>
                    <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-emerald-500/10 text-emerald-400">
                      {scorePercent}% resonance
                    </span>
                  </div>

                  {peer.shared_tags.length > 0 ? (
                    <div className="space-y-1">
                      <p className="text-xs text-muted-foreground">
                        Shared interests
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {peer.shared_tags.map((tag) => (
                          <span
                            key={tag}
                            className="rounded-full border border-emerald-500/20 bg-emerald-500/5 px-2 py-0.5 text-xs text-emerald-300"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground">
                      Resonance based on worldview alignment and concepts
                    </p>
                  )}

                  {peer.city ? (
                    <p className="text-xs text-muted-foreground">
                      Location: {peer.city}
                      {peer.distance_km != null
                        ? ` (${peer.distance_km.toFixed(0)} km)`
                        : ""}
                    </p>
                  ) : null}
                </article>
              );
            })}
          </div>
        )}
      </section>

      {/* Navigation */}
      <nav
        className="py-8 text-center space-y-2 border-t border-border/20"
        aria-label="Related pages"
      >
        <p className="text-xs text-muted-foreground/80 uppercase tracking-wider">
          Explore more
        </p>
        <div className="flex flex-wrap justify-center gap-4 text-sm">
          <Link href="/beliefs" className="text-violet-400 hover:underline">
            Beliefs
          </Link>
          <Link href="/discover" className="text-purple-400 hover:underline">
            Discover
          </Link>
          <Link href="/resonance" className="text-blue-400 hover:underline">
            Resonance
          </Link>
          <Link href="/contributors" className="text-amber-400 hover:underline">
            Contributors
          </Link>
        </div>
      </nav>
    </main>
  );
}
