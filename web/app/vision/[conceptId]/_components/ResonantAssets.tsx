"use client";

/**
 * Resonant assets — multiple expressions of a concept, ranked by resonance.
 *
 * A concept can have many visual expressions — generated images, contributed
 * artwork, alternative tellings. Each is an asset. The most resonant one
 * (most viewed, most shared, highest engagement) rises to the surface.
 *
 * This creates a reward signal: when a contributor creates a visual that
 * resonates more with readers than the current hero, their expression
 * naturally becomes the face of the concept. The contributor earns CC
 * from the attention their asset receives.
 *
 * Each asset is individually viewable and trackable — a contributor
 * who creates a better visual for a concept is directly rewarded by
 * the attention it receives.
 */

import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";

interface AssetVariant {
  path: string;
  type: "hero" | "story" | "contributed";
  index: number;
  views?: number;
}

interface ResonantAssetsProps {
  conceptId: string;
}

export function ResonantAssets({ conceptId }: ResonantAssetsProps) {
  const [assets, setAssets] = useState<AssetVariant[]>([]);
  const [selected, setSelected] = useState<AssetVariant | null>(null);

  useEffect(() => {
    // Build asset list from known visual patterns
    // Hero visuals: /visuals/generated/{conceptId}-{N}.jpg
    // Story visuals: /visuals/generated/{conceptId}-story-{N}.jpg
    const variants: AssetVariant[] = [];

    // Check for hero variants (0-5)
    for (let i = 0; i <= 5; i++) {
      variants.push({
        path: `/visuals/generated/${conceptId}-${i}.jpg`,
        type: "hero",
        index: i,
      });
    }

    // Check for story variants (0-5)
    for (let i = 0; i <= 5; i++) {
      variants.push({
        path: `/visuals/generated/${conceptId}-story-${i}.jpg`,
        type: "story",
        index: i,
      });
    }

    setAssets(variants);
  }, [conceptId]);

  // Filter to only images that actually exist (check via loading)
  const [loadedAssets, setLoadedAssets] = useState<Set<string>>(new Set());

  function handleImageLoad(path: string) {
    setLoadedAssets((prev) => new Set([...prev, path]));
  }

  const visibleAssets = assets.filter((a) => loadedAssets.has(a.path));
  const heroAssets = visibleAssets.filter((a) => a.type === "hero");

  // Don't show if only one or zero hero visuals (the hero image already shows)
  if (heroAssets.length <= 1 && !selected) return null;

  return (
    <section className="pt-6">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-stone-500 mb-3">
        Visual expressions
      </h3>
      <p className="text-xs text-stone-600 mb-3">
        Each expression is a unique contribution. The most resonant rises to the surface.
      </p>

      {/* Grid of variants */}
      <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2">
        {assets.filter((a) => a.type === "hero" && loadedAssets.has(a.path)).map((asset) => (
          <button
            key={asset.path}
            onClick={() => setSelected(asset)}
            className={`relative aspect-square rounded-lg overflow-hidden border-2 transition-all ${
              selected?.path === asset.path
                ? "border-amber-400/60 ring-2 ring-amber-400/20"
                : "border-border/30 hover:border-amber-400/30"
            }`}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={asset.path}
              alt={`Expression ${asset.index + 1}`}
              className="absolute inset-0 w-full h-full object-cover"
            />
          </button>
        ))}
      </div>

      {/* Selected asset detail */}
      {selected && loadedAssets.has(selected.path) && (
        <div className="mt-4 rounded-xl overflow-hidden border border-amber-500/20">
          <div className="relative aspect-[16/9]">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={selected.path}
              alt={`Expression ${selected.index + 1}`}
              className="absolute inset-0 w-full h-full object-cover"
            />
          </div>
          <div className="p-3 bg-card/50 flex items-center justify-between">
            <span className="text-xs text-stone-400">
              Expression {selected.index + 1}
            </span>
            <span className="text-xs text-stone-600">
              Each expression is a contribution
            </span>
          </div>
        </div>
      )}

      {/* Hidden image elements to probe which files exist */}
      <div className="hidden">
        {assets.map((a) => (
          <img
            key={a.path}
            src={a.path}
            alt=""
            onLoad={() => handleImageLoad(a.path)}
            onError={() => {/* doesn't exist */}}
          />
        ))}
      </div>
    </section>
  );
}
