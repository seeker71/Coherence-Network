"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { getApiBase } from "@/lib/api";
import { BeliefRadarChart } from "@/components/beliefs/BeliefRadarChart";
import { ConceptTagCloud } from "@/components/beliefs/ConceptTagCloud";
import { WorldviewSelector, type WorldviewAxes } from "@/components/beliefs/WorldviewSelector";

type ConceptResonance = {
  concept_id: string;
  weight: number;
};

type BeliefProfile = {
  contributor_id: string;
  worldview_axes: WorldviewAxes;
  concept_resonances: ConceptResonance[];
  interest_tags: string[];
  updated_at: string;
};

const DEFAULT_AXES: WorldviewAxes = {
  scientific: 0,
  spiritual: 0,
  pragmatic: 0,
  holistic: 0,
  relational: 0,
  systemic: 0,
};

export default function BeliefProfilePage() {
  const params = useParams();
  const handle = Array.isArray(params?.handle) ? params.handle[0] : params?.handle ?? "";

  const [profile, setProfile] = useState<BeliefProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newTag, setNewTag] = useState("");
  const [addingTag, setAddingTag] = useState(false);

  const fetchProfile = useCallback(async () => {
    if (!handle) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${getApiBase()}/api/contributors/${encodeURIComponent(handle)}/beliefs`, {
        cache: "no-store",
      });
      if (res.status === 404) {
        setError("Contributor not found");
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: BeliefProfile = await res.json();
      setProfile(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load belief profile");
    } finally {
      setLoading(false);
    }
  }, [handle]);

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  const handleSaveAxes = async (updated: WorldviewAxes) => {
    const res = await fetch(`${getApiBase()}/api/contributors/${encodeURIComponent(handle)}/beliefs`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ worldview_axes: updated }),
    });
    if (!res.ok) throw new Error(`Save failed: HTTP ${res.status}`);
    const data: BeliefProfile = await res.json();
    setProfile(data);
  };

  const handleAddTag = async () => {
    if (!newTag.trim()) return;
    setAddingTag(true);
    try {
      const res = await fetch(`${getApiBase()}/api/contributors/${encodeURIComponent(handle)}/beliefs`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ interest_tags: [newTag.trim()] }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: BeliefProfile = await res.json();
      setProfile(data);
      setNewTag("");
    } finally {
      setAddingTag(false);
    }
  };

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8 max-w-3xl">
        <p className="text-muted-foreground animate-pulse">Loading belief profile…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-8 max-w-3xl">
        <p className="text-destructive">{error}</p>
      </div>
    );
  }

  const axes = profile?.worldview_axes ?? DEFAULT_AXES;

  return (
    <div className="container mx-auto px-4 py-8 max-w-3xl space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Belief Profile</h1>
        <p className="text-muted-foreground">
          @{handle}
          {profile?.updated_at && (
            <span className="ml-2 text-xs">
              · updated {new Date(profile.updated_at).toLocaleDateString()}
            </span>
          )}
        </p>
      </div>

      {/* Radar chart */}
      <section className="rounded-xl border p-6 space-y-2">
        <h2 className="text-lg font-semibold">Worldview Radar</h2>
        <BeliefRadarChart axes={axes} />
      </section>

      {/* Concept tag cloud */}
      <section className="rounded-xl border p-6 space-y-4">
        <h2 className="text-lg font-semibold">Concepts &amp; Tags</h2>
        <ConceptTagCloud
          interestTags={profile?.interest_tags ?? []}
          conceptResonances={profile?.concept_resonances ?? []}
        />
        <div className="flex gap-2 mt-2">
          <input
            type="text"
            value={newTag}
            onChange={(e) => setNewTag(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAddTag()}
            placeholder="Add interest tag…"
            className="flex-1 rounded-md border px-3 py-1.5 text-sm bg-background"
          />
          <button
            onClick={handleAddTag}
            disabled={addingTag || !newTag.trim()}
            className="px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-sm disabled:opacity-50"
          >
            {addingTag ? "…" : "Add"}
          </button>
        </div>
      </section>

      {/* Worldview axis sliders */}
      <section className="rounded-xl border p-6">
        <WorldviewSelector axes={axes} onSave={handleSaveAxes} />
      </section>

      {/* Resonance hint */}
      <p className="text-xs text-muted-foreground text-center pb-4">
        Your belief profile shapes idea recommendations and resonance scoring across the network.
      </p>
    </div>
  );
}
