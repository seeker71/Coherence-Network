"use client";

/**
 * /profile/[handle]/beliefs — contributor belief profile page.
 * Radar chart, concept tag cloud, worldview axis sliders.
 * spec-169 (belief-system-interface)
 */

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getApiBase } from "@/lib/api";
import { BeliefRadarChart, WorldviewAxes } from "@/components/beliefs/BeliefRadarChart";
import { ConceptTagCloud, ConceptResonance } from "@/components/beliefs/ConceptTagCloud";
import { WorldviewSelector } from "@/components/beliefs/WorldviewSelector";

type BeliefProfile = {
  contributor_id: string;
  worldview_axes: Record<string, number>;
  concept_resonances: ConceptResonance[];
  interest_tags: string[];
  updated_at: string;
};

const API_BASE = getApiBase();

export default function BeliefProfilePage() {
  const params = useParams();
  const handle = typeof params?.handle === "string" ? params.handle : "";

  const [profile, setProfile] = useState<BeliefProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!handle) return;
    setLoading(true);
    fetch(`${API_BASE}/api/contributors/${encodeURIComponent(handle)}/beliefs`)
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail ?? `HTTP ${res.status}`);
        }
        return res.json() as Promise<BeliefProfile>;
      })
      .then((data) => {
        setProfile(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message ?? "Failed to load belief profile");
        setLoading(false);
      });
  }, [handle]);

  function handleAxesSaved(axes: Record<string, number>) {
    setProfile((prev) =>
      prev
        ? { ...prev, worldview_axes: Object.fromEntries(Object.entries(axes).map(([k, v]) => [k, v / 100])) }
        : prev
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[200px]">
        <p className="text-sm text-muted-foreground">Loading belief profile…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-6 text-sm text-destructive">
        {error === "Contributor not found"
          ? `Contributor "@${handle}" not found.`
          : `Error: ${error}`}
      </div>
    );
  }

  if (!profile) return null;

  const axes = profile.worldview_axes as WorldviewAxes;

  function resonanceLabel(score: number): { label: string; color: string } {
    if (score >= 0.7) return { label: "High resonance", color: "text-green-600 dark:text-green-400" };
    if (score >= 0.3) return { label: "Moderate resonance", color: "text-yellow-600 dark:text-yellow-400" };
    return { label: "Low resonance", color: "text-muted-foreground" };
  }

  const avgAxes =
    Object.values(axes).reduce((s, v) => s + v, 0) /
    Math.max(Object.values(axes).length, 1);
  const { label: resLabel, color: resColor } = resonanceLabel(avgAxes);

  return (
    <div className="mx-auto max-w-2xl px-4 py-8 space-y-8">
      <header>
        <h1 className="text-2xl font-bold">Belief Profile</h1>
        <p className="text-sm text-muted-foreground mt-1">
          @{handle} &middot; last updated{" "}
          {new Date(profile.updated_at).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
          })}
        </p>
        <p className={`text-xs mt-1 font-medium ${resColor}`}>{resLabel}</p>
      </header>

      {/* Radar chart */}
      <section aria-labelledby="radar-heading">
        <h2 id="radar-heading" className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-3">
          Worldview Axes
        </h2>
        <div className="flex justify-center">
          <BeliefRadarChart axes={axes} />
        </div>
      </section>

      {/* Concept tag cloud */}
      <section aria-labelledby="tags-heading">
        <h2 id="tags-heading" className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-3">
          Concept Resonances
        </h2>
        <ConceptTagCloud
          interestTags={profile.interest_tags}
          conceptResonances={profile.concept_resonances}
        />
      </section>

      {/* Worldview selector */}
      <section aria-labelledby="selector-heading">
        <h2 id="selector-heading" className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-3">
          Edit Worldview
        </h2>
        <WorldviewSelector
          contributorId={handle}
          initialAxes={axes}
          onSaved={handleAxesSaved}
        />
      </section>
    </div>
  );
}
