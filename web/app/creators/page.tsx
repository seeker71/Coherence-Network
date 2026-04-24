import Link from "next/link";

import { getApiBase } from "@/lib/api";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Creators — Coherence Network",
  description:
    "Contribute your blueprints, designs, research. Earn CC when others use them. Provably fair, no paywalls.",
};

type CreatorStats = {
  total_creators: number;
  total_blueprints: number;
  total_cc_distributed: string | number;
  total_uses: number;
  verified_since: string | null;
};

type FeaturedAsset = {
  asset_id: string;
  name: string;
  creator_handle: string;
  asset_type: string;
  use_count: number;
  cc_earned: string | number;
  community_tags: string[];
};

type FeaturedResponse = {
  items: FeaturedAsset[];
  total: number;
  limit: number;
  offset: number;
};

async function fetchJson<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(`${getApiBase()}${path}`, {
      cache: "no-store",
    });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

function formatCc(value: string | number): string {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return "CC 0";
  return `CC ${n.toFixed(2)}`;
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-stone-800 bg-stone-950/40 p-4">
      <div className="text-2xl font-light text-white">{value}</div>
      <div className="text-xs text-stone-500 uppercase tracking-wide mt-1">
        {label}
      </div>
    </div>
  );
}

export default async function CreatorsLandingPage() {
  const [stats, featured] = await Promise.all([
    fetchJson<CreatorStats>("/api/creator-economy/stats"),
    fetchJson<FeaturedResponse>("/api/creator-economy/featured?limit=6"),
  ]);

  return (
    <main className="max-w-4xl mx-auto px-6 py-12">
      <nav
        className="text-sm text-stone-500 mb-8 flex items-center gap-2"
        aria-label="breadcrumb"
      >
        <Link href="/" className="hover:text-amber-400/80 transition-colors">
          Home
        </Link>
        <span className="text-stone-700">/</span>
        <span className="text-stone-300">Creators</span>
      </nav>

      <h1 className="text-4xl font-extralight text-white mb-4">
        Your work, provably yours.
      </h1>
      <p className="text-lg text-stone-300 leading-relaxed mb-10 max-w-2xl">
        Contribute blueprints, designs, research. Earn CC when others use your
        work. Every use is attributed on-chain and verifiable from outside the
        platform. No paywalls. No subscriptions. The audit trail is the proof.
      </p>

      <section className="mb-12">
        <h2 className="text-lg font-light text-stone-300 mb-4">
          Live stats
        </h2>
        {stats ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard
              label="Creators"
              value={stats.total_creators.toString()}
            />
            <StatCard
              label="Blueprints / designs / research"
              value={stats.total_blueprints.toString()}
            />
            <StatCard
              label="CC distributed"
              value={formatCc(stats.total_cc_distributed)}
            />
            <StatCard label="Uses" value={stats.total_uses.toLocaleString()} />
          </div>
        ) : (
          <div className="text-stone-500 text-sm">
            Stats are loading — if this persists, the API may be unreachable.
          </div>
        )}
      </section>

      <section className="mb-12">
        <Link
          href="/creators/submit"
          className="inline-block rounded border border-amber-500/40 bg-amber-500/10 px-6 py-3 text-amber-200 hover:bg-amber-500/20 transition-colors"
        >
          Submit your work →
        </Link>
      </section>

      <section>
        <h2 className="text-lg font-light text-stone-300 mb-4">Featured</h2>
        {featured && featured.items.length > 0 ? (
          <div className="space-y-3">
            {featured.items.map((item) => (
              <Link
                key={item.asset_id}
                href={`/assets/${item.asset_id}/proof`}
                className="block rounded border border-stone-800 bg-stone-950/40 p-4 hover:border-amber-500/40 transition-colors"
              >
                <div className="flex items-baseline justify-between gap-4">
                  <div>
                    <div className="text-white">{item.name}</div>
                    <div className="text-xs text-stone-500 mt-1">
                      {item.creator_handle} · {item.asset_type}
                      {item.community_tags.length > 0 &&
                        ` · ${item.community_tags.slice(0, 3).join(" · ")}`}
                    </div>
                  </div>
                  <div className="text-right text-sm">
                    <div className="text-stone-300">
                      {item.use_count} use{item.use_count === 1 ? "" : "s"}
                    </div>
                    <div className="text-amber-400/80">
                      {formatCc(item.cc_earned)}
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <div className="text-stone-500 text-sm">
            No featured assets yet. Be the first —{" "}
            <Link
              href="/creators/submit"
              className="text-amber-400/80 hover:text-amber-300"
            >
              submit your work
            </Link>
            .
          </div>
        )}
      </section>
    </main>
  );
}
