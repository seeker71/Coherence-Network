"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { getApiBase } from "@/lib/api";

const API = getApiBase();

interface MarketplaceListing {
  id: string;
  idea_id: string;
  idea_title: string;
  author_id: string;
  author_display_name: string;
  confidence: number;
  fork_count: number;
  total_downstream_value: number;
  coherence_score: number;
  tags: string[];
  visibility: string;
  published_at: string;
}

interface BrowseResponse {
  listings: MarketplaceListing[];
  total: number;
  page: number;
  page_size: number;
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  } catch {
    return iso;
  }
}

function confidenceColor(score: number): string {
  if (score >= 0.7) return "text-emerald-400";
  if (score >= 0.4) return "text-yellow-400";
  return "text-muted-foreground";
}

export default function MarketplacePage() {
  const [listings, setListings] = useState<MarketplaceListing[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<"recent" | "popular" | "value">("popular");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        page: String(page),
        page_size: "20",
        sort,
      });
      if (search) params.set("search", search);
      const res = await fetch(`${API}/api/marketplace/browse?${params}`);
      if (!res.ok) throw new Error(`Browse failed (${res.status})`);
      const data: BrowseResponse = await res.json();
      setListings(data.listings);
      setTotal(data.total);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [page, sort, search]);

  useEffect(() => { void load(); }, [load]);

  return (
    <main className="min-h-screen px-4 md:px-8 py-10 max-w-4xl mx-auto space-y-6">
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3">
        <p className="text-xs text-muted-foreground uppercase tracking-widest">Marketplace</p>
        <h1 className="text-3xl font-light tracking-tight">Idea Garden Marketplace</h1>
        <p className="text-muted-foreground">
          Browse ideas published across instances. Fork what resonates, give credit to original authors.
        </p>
        <div className="flex flex-wrap gap-3">
          <input
            type="text"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            placeholder="Search ideas..."
            className="flex-1 min-w-48 rounded-xl border border-border/40 bg-card/60 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
          <select
            value={sort}
            onChange={(e) => { setSort(e.target.value as "recent" | "popular" | "value"); setPage(1); }}
            className="rounded-xl border border-border/40 bg-card/60 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="popular">Most Forked</option>
            <option value="value">Highest Value</option>
            <option value="recent">Newest</option>
          </select>
        </div>
      </section>

      {loading && <p className="text-muted-foreground">Loading marketplace listings…</p>}
      {error && <p className="text-destructive">Error: {error}</p>}

      {!loading && !error && listings.length === 0 && (
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-8 text-center space-y-3">
          <p className="text-4xl" aria-hidden="true">🌱</p>
          <p className="text-lg text-muted-foreground">
            No seeds in the marketplace yet. Publish an idea to get started.
          </p>
          <Link href="/ideas" className="inline-block text-primary hover:text-foreground transition-colors underline underline-offset-4">
            Browse local ideas →
          </Link>
        </div>
      )}

      {!loading && !error && listings.length > 0 && (
        <div className="space-y-3">
          {listings.map((listing) => (
            <div
              key={listing.id}
              className="hover-lift rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 md:p-6 space-y-3"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <Link
                    href={`/ideas/${encodeURIComponent(listing.idea_id)}`}
                    className="text-lg font-medium hover:text-primary transition-colors"
                  >
                    {listing.idea_title}
                  </Link>
                  <p className="text-xs text-muted-foreground mt-1">
                    by {listing.author_display_name} · Published {fmtDate(listing.published_at)}
                  </p>
                </div>
                <span className={`text-sm font-mono ${confidenceColor(listing.confidence)}`}>
                  {(listing.confidence * 100).toFixed(0)}% confidence
                </span>
              </div>

              <div className="flex flex-wrap gap-2 text-xs">
                {listing.tags.slice(0, 5).map((tag) => (
                  <span key={tag} className="rounded-full border border-primary/30 px-2 py-0.5 text-primary/80">
                    {tag}
                  </span>
                ))}
              </div>

              <div className="flex items-center gap-4 text-sm text-muted-foreground">
                <span>🍴 {listing.fork_count} forks</span>
                <span>🌿 Coherence: {(listing.coherence_score * 100).toFixed(0)}%</span>
                <span>💰 {listing.total_downstream_value.toFixed(1)} CC downstream value</span>
              </div>
            </div>
          ))}

          {total > 20 && (
            <div className="flex items-center justify-between text-sm">
              <p className="text-muted-foreground">
                Showing {(page - 1) * 20 + 1}–{Math.min(page * 20, total)} of {total}
              </p>
              <div className="flex gap-2">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                  className="rounded-lg border border-border/30 px-3 py-1.5 text-sm disabled:opacity-40 hover:text-foreground transition-colors"
                >
                  ← Prev
                </button>
                <button
                  disabled={page * 20 >= total}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded-lg border border-border/30 px-3 py-1.5 text-sm disabled:opacity-40 hover:text-foreground transition-colors"
                >
                  Next →
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="flex gap-4 text-sm text-muted-foreground pt-2">
        <Link href="/invest" className="hover:text-foreground transition-colors">← Visit the Garden</Link>
        <Link href="/ideas" className="hover:text-foreground transition-colors">Browse Local Ideas →</Link>
      </div>
    </main>
  );
}
