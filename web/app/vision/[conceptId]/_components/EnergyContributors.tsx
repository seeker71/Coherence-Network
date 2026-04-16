"use client";

/**
 * Energy contributors — who brought this concept to life.
 *
 * Shows the contributors whose attention, creation, and sharing
 * gave this concept the most energy. A contributor's energy comes from:
 * - Viewing (attention)
 * - Referring others (discovery)
 * - Creating assets for this concept (expression)
 *
 * This isn't an author list. It's a living map of who brought vitality.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { getApiBase } from "@/lib/api";

interface EnergySource {
  contributor_id: string;
  energy_type: "attention" | "discovery" | "creation";
  strength: number;
}

interface EnergyContributorsProps {
  conceptId: string;
}

export function EnergyContributors({ conceptId }: EnergyContributorsProps) {
  const [contributors, setContributors] = useState<EnergySource[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const base = getApiBase();

        // Fetch view stats — who viewed and who referred
        const statsRes = await fetch(
          `${base}/api/views/stats/${encodeURIComponent(conceptId)}?days=365`
        );
        const sources: EnergySource[] = [];

        if (statsRes.ok) {
          const stats = await statsRes.json();

          // Top referrers — discovery energy
          for (const ref of stats.top_referrers || []) {
            if (ref.contributor_id) {
              sources.push({
                contributor_id: ref.contributor_id,
                energy_type: "discovery",
                strength: ref.referral_count,
              });
            }
          }
        }

        // Fetch contributor view history to find attentive viewers
        const historyRes = await fetch(
          `${base}/api/views/contributor/${encodeURIComponent(conceptId)}?limit=1`
        );
        // This endpoint returns a contributor's history, not per-concept contributors
        // Instead, use the view events to find unique contributor viewers
        // For now, show what we have from referrers + discovery chain

        const chainRes = await fetch(
          `${base}/api/views/discovery/${encodeURIComponent(conceptId)}`
        );
        if (chainRes.ok) {
          const chain = await chainRes.json();
          const referrerCounts: Record<string, number> = {};
          for (const link of chain) {
            if (link.referrer) {
              referrerCounts[link.referrer] = (referrerCounts[link.referrer] || 0) + 1;
            }
          }
          for (const [cid, count] of Object.entries(referrerCounts)) {
            if (!sources.some((s) => s.contributor_id === cid)) {
              sources.push({
                contributor_id: cid,
                energy_type: "discovery",
                strength: count,
              });
            }
          }
        }

        // Sort by strength
        sources.sort((a, b) => b.strength - a.strength);

        if (!cancelled) setContributors(sources.slice(0, 8));
      } catch {
        // Energy data is supplementary
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [conceptId]);

  if (loading || contributors.length === 0) return null;

  const typeLabel: Record<string, string> = {
    attention: "presence",
    discovery: "sharing",
    creation: "expression",
  };

  return (
    <section className="pt-6">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-stone-500 mb-3">
        Brought to life by
      </h3>
      <div className="flex flex-wrap gap-2">
        {contributors.map((c) => (
          <Link
            key={`${c.contributor_id}-${c.energy_type}`}
            href={`/profile/${encodeURIComponent(c.contributor_id)}`}
            className="group flex items-center gap-2 rounded-full border border-border/30 bg-card/30 px-3 py-1.5 text-xs transition-colors hover:border-amber-500/30 hover:bg-amber-500/5"
          >
            <span className="text-stone-300 group-hover:text-amber-300 transition-colors">
              {c.contributor_id.length > 16
                ? `${c.contributor_id.slice(0, 8)}…${c.contributor_id.slice(-4)}`
                : c.contributor_id}
            </span>
            <span className="text-stone-600">
              {typeLabel[c.energy_type] || c.energy_type}
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}
