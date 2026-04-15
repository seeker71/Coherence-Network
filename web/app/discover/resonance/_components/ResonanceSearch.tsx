"use client";

import { useState } from "react";
import Link from "next/link";
import { getApiBase } from "@/lib/api";

/* ── Types ────────────────────────────────────────────────────────── */

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

type ResonantEntity = {
  entity_id: string;
  resonance: number;
};

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

function entityLink(entityId: string): string {
  if (entityId.startsWith("lc-")) return `/vision/${entityId}`;
  if (entityId.startsWith("idea-") || entityId.startsWith("idea_")) return `/ideas/${entityId}`;
  return `/nodes/${encodeURIComponent(entityId)}`;
}

function entityLabel(entityId: string): string {
  return entityId
    .replace(/^lc-/, "")
    .replace(/^idea[-_]/, "")
    .replace(/[-_]/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/* ── Component ────────────────────────────────────────────────────── */

export default function ResonanceSearch() {
  const [entityId, setEntityId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [profile, setProfile] = useState<FrequencyProfile | null>(null);
  const [results, setResults] = useState<ResonantEntity[]>([]);
  const [searched, setSearched] = useState(false);

  async function handleSearch() {
    const trimmed = entityId.trim();
    if (!trimmed) return;

    setLoading(true);
    setError(null);
    setProfile(null);
    setResults([]);
    setSearched(true);

    const API = getApiBase();

    try {
      // Fetch profile and resonant entities in parallel
      const [profileRes, resonantRes] = await Promise.all([
        fetch(`${API}/api/profile/${encodeURIComponent(trimmed)}`),
        fetch(`${API}/api/profile/${encodeURIComponent(trimmed)}/resonant?top=20`),
      ]);

      if (!profileRes.ok) {
        const body = await profileRes.json().catch(() => ({}));
        throw new Error(
          body.detail || `Entity "${trimmed}" not found or has no profile`
        );
      }

      const profileData: FrequencyProfile = await profileRes.json();
      setProfile(profileData);

      if (resonantRes.ok) {
        const resonantData: ResonantEntity[] = await resonantRes.json();
        setResults(Array.isArray(resonantData) ? resonantData : []);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") {
      handleSearch();
    }
  }

  return (
    <div className="space-y-8">
      {/* Search input */}
      <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 sm:p-8 space-y-4">
        <div>
          <label
            htmlFor="entity-id"
            className="text-xs uppercase tracking-widest text-muted-foreground"
          >
            Entity ID
          </label>
          <p className="text-sm text-muted-foreground mt-1">
            Enter a concept ID (e.g. lc-coherence), contributor ID, or any entity
            in the graph.
          </p>
        </div>
        <div className="flex gap-3">
          <input
            id="entity-id"
            type="text"
            value={entityId}
            onChange={(e) => setEntityId(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="lc-coherence"
            className="flex-1 rounded-xl border border-border/30 bg-background/60 px-4 py-2.5 text-sm placeholder:text-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-amber-500/30 focus:border-amber-500/30 transition-colors"
          />
          <button
            onClick={handleSearch}
            disabled={loading || !entityId.trim()}
            className="rounded-xl bg-amber-500/15 border border-amber-500/30 px-6 py-2.5 text-sm font-medium text-amber-400 hover:bg-amber-500/25 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? "Searching..." : "Find Resonant"}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-5 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Source entity profile */}
      {profile && (
        <section className="rounded-2xl border border-amber-500/20 bg-gradient-to-b from-amber-500/5 to-card/30 p-6 sm:p-8 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-widest text-amber-400">
                Frequency Profile
              </p>
              <p className="text-lg font-light mt-1">
                {entityLabel(profile.entity_id)}
              </p>
            </div>
            <div className="text-right">
              <p className="text-2xl font-light text-amber-300">
                {profile.magnitude.toFixed(2)}
              </p>
              <p className="text-xs text-muted-foreground">magnitude</p>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            {profile.top.slice(0, 12).map((dim) => {
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

          <div className="flex items-center gap-4 text-xs text-muted-foreground pt-1">
            <span>{profile.dimensions} dimensions</span>
            <span className="font-mono truncate" title={profile.hash}>
              {profile.hash.slice(0, 16)}...
            </span>
          </div>
        </section>
      )}

      {/* Resonant results */}
      {searched && !loading && results.length > 0 && (
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-medium">
              Most Resonant ({results.length})
            </h2>
            <p className="text-xs text-muted-foreground">
              Sorted by resonance score
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {results.map((entity, idx) => (
              <Link
                key={entity.entity_id}
                href={entityLink(entity.entity_id)}
                className="group rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3 hover:border-amber-500/30 transition-colors animate-fade-in-up"
                style={{ animationDelay: `${idx * 0.03}s` }}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <h3 className="text-sm font-medium leading-snug group-hover:text-amber-400 transition-colors">
                      {entityLabel(entity.entity_id)}
                    </h3>
                    <p className="text-xs text-muted-foreground mt-0.5 font-mono">
                      {entity.entity_id}
                    </p>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="text-lg font-light text-amber-300">
                      {(entity.resonance * 100).toFixed(0)}%
                    </p>
                    <p className="text-xs text-muted-foreground">resonance</p>
                  </div>
                </div>

                {/* Resonance bar */}
                <div className="w-full bg-stone-800 rounded-full h-1.5">
                  <div
                    className="bg-gradient-to-r from-amber-500/60 to-amber-400 h-1.5 rounded-full transition-all"
                    style={{ width: `${Math.max(entity.resonance * 100, 2)}%` }}
                  />
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Empty state after search */}
      {searched && !loading && !error && results.length === 0 && profile && (
        <section className="rounded-2xl border border-dashed border-border/30 bg-background/30 p-8 text-center space-y-3">
          <p className="text-muted-foreground">
            No resonant entities found for this profile. The resonance map grows as
            more concepts and contributors join the network.
          </p>
        </section>
      )}
    </div>
  );
}
