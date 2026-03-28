"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { getApiBase } from "@/lib/api";

const API_URL = getApiBase();

const AXES = ["empirical", "collaborative", "strategic", "technical", "ethical"] as const;
const WORLDVIEWS = [
  "scientific",
  "spiritual",
  "pragmatic",
  "holistic",
  "artistic",
  "systems",
] as const;

type BeliefProfile = {
  contributor_id: string;
  worldview: string;
  axis_weights: Record<string, number>;
  concept_weights: Record<string, number>;
  updated_at?: string | null;
};

type Resonance = {
  resonance_score: number;
  concept_overlap: number;
  axis_alignment: number;
  worldview_alignment: number;
  matching_concepts: string[];
  idea_worldview_signal: string;
};

function radarPoints(values: number[], labels: string[], size: number): string {
  const n = labels.length;
  const cx = size / 2;
  const cy = size / 2;
  const r = size * 0.38;
  const pts: string[] = [];
  for (let i = 0; i < n; i++) {
    const angle = (-Math.PI / 2 + (2 * Math.PI * i) / n) as number;
    const vr = r * Math.max(0, Math.min(1, values[i] ?? 0.5));
    const x = cx + vr * Math.cos(angle);
    const y = cy + vr * Math.sin(angle);
    pts.push(`${x},${y}`);
  }
  return pts.join(" ");
}

function BeliefRadar({
  axisWeights,
  size,
}: {
  axisWeights: Record<string, number>;
  size: number;
}) {
  const values = AXES.map((a) => axisWeights[a] ?? 0.5);
  const poly = radarPoints(values, [...AXES], size);
  const grid = AXES.map((_, i) => {
    const angle = (-Math.PI / 2 + (2 * Math.PI * i) / AXES.length) as number;
    const cx = size / 2;
    const cy = size / 2;
    const r = size * 0.38;
    const x2 = cx + r * Math.cos(angle);
    const y2 = cy + r * Math.sin(angle);
    return (
      <line
        key={i}
        x1={cx}
        y1={cy}
        x2={x2}
        y2={y2}
        className="stroke-border/50"
        strokeWidth={1}
      />
    );
  });
  const labels = AXES.map((label, i) => {
    const angle = (-Math.PI / 2 + (2 * Math.PI * i) / AXES.length) as number;
    const cx = size / 2;
    const cy = size / 2;
    const r = size * 0.46;
    const x = cx + r * Math.cos(angle);
    const y = cy + r * Math.sin(angle);
    return (
      <text
        key={label}
        x={x}
        y={y}
        textAnchor="middle"
        dominantBaseline="middle"
        className="fill-muted-foreground text-[10px] sm:text-xs"
      >
        {label}
      </text>
    );
  });
  return (
    <svg width={size} height={size} className="mx-auto">
      <circle
        cx={size / 2}
        cy={size / 2}
        r={size * 0.38}
        fill="none"
        className="stroke-border/40"
        strokeWidth={1}
      />
      {grid}
      <polygon
        points={poly}
        fill="hsl(var(--primary) / 0.25)"
        stroke="hsl(var(--primary))"
        strokeWidth={2}
      />
      {labels}
    </svg>
  );
}

function BeliefsPageInner() {
  const params = useParams();
  const rawId = params?.id;
  const contributorId = typeof rawId === "string" ? rawId : Array.isArray(rawId) ? rawId[0] : "";

  const [profile, setProfile] = useState<BeliefProfile | null>(null);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);
  const [worldview, setWorldview] = useState<string>("pragmatic");
  const [ideaId, setIdeaId] = useState("");
  const [resonance, setResonance] = useState<Resonance | null>(null);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!contributorId) return;
    setStatus("loading");
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/contributors/${encodeURIComponent(contributorId)}/beliefs`, {
        cache: "no-store",
      });
      const j = await res.json();
      if (!res.ok) throw new Error(j.detail || res.statusText);
      setProfile(j as BeliefProfile);
      setWorldview(j.worldview || "pragmatic");
      setStatus("ok");
    } catch (e) {
      setStatus("error");
      setError(String(e));
    }
  }, [contributorId]);

  useEffect(() => {
    void load();
  }, [load]);

  const maxConcept = useMemo(() => {
    const cw = profile?.concept_weights || {};
    const vals = Object.values(cw);
    if (!vals.length) return 1;
    return Math.max(...vals, 0.01);
  }, [profile]);

  const runResonance = async () => {
    if (!contributorId || !ideaId.trim()) return;
    setResonance(null);
    try {
      const u = new URL(`${API_URL}/api/contributors/${encodeURIComponent(contributorId)}/beliefs/resonance`);
      u.searchParams.set("idea_id", ideaId.trim());
      const res = await fetch(u.toString(), { cache: "no-store" });
      const j = await res.json();
      if (!res.ok) throw new Error(j.detail || res.statusText);
      setResonance(j as Resonance);
    } catch (e) {
      setSaveMsg(String(e));
    }
  };

  const saveLocal = async () => {
    setSaveMsg(null);
    const key =
      typeof window !== "undefined" ? window.sessionStorage.getItem("coherence_api_key")?.trim() : "";
    if (!key) {
      setSaveMsg("Set sessionStorage key coherence_api_key to your dev API key, or use: cc beliefs patch …");
      return;
    }
    try {
      const res = await fetch(`${API_URL}/api/contributors/${encodeURIComponent(contributorId)}/beliefs`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": key,
        },
        body: JSON.stringify({
          worldview,
          axis_weights: profile?.axis_weights,
          concept_weights: profile?.concept_weights,
        }),
      });
      const j = await res.json();
      if (!res.ok) throw new Error(j.detail || res.statusText);
      setProfile(j as BeliefProfile);
      setSaveMsg("Saved.");
    } catch (e) {
      setSaveMsg(String(e));
    }
  };

  if (!contributorId) {
    return <main className="min-h-screen p-8"><p className="text-muted-foreground">Missing contributor id.</p></main>;
  }

  return (
    <main className="min-h-screen px-4 md:px-8 py-10 max-w-4xl mx-auto space-y-8">
      <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
        <Link href="/contributors" className="underline hover:text-foreground">
          Contributors
        </Link>
        <span>/</span>
        <span className="text-foreground">{contributorId}</span>
      </div>

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-2">
        <h1 className="text-3xl font-light tracking-tight">Belief profile</h1>
        <p className="text-muted-foreground max-w-2xl">
          Worldview, value axes, and concept preferences shape how this contributor resonates with ideas.
          Updates require an API key (CLI <code className="text-xs bg-muted px-1 rounded">cc beliefs patch</code> or session key below).
        </p>
      </section>

      {status === "loading" && <p className="text-muted-foreground">Loading…</p>}
      {status === "error" && <p className="text-destructive">Error: {error}</p>}

      {status === "ok" && profile && (
        <>
          <section className="grid md:grid-cols-2 gap-8 rounded-2xl border border-border/30 bg-card/40 p-6">
            <div>
              <h2 className="text-lg font-medium mb-4">Axes</h2>
              <BeliefRadar axisWeights={profile.axis_weights} size={280} />
            </div>
            <div className="space-y-4">
              <div>
                <label className="text-sm text-muted-foreground block mb-1">Worldview</label>
                <select
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
                  value={worldview}
                  onChange={(e) => setWorldview(e.target.value)}
                >
                  {WORLDVIEWS.map((w) => (
                    <option key={w} value={w}>
                      {w.charAt(0).toUpperCase() + w.slice(1)}
                    </option>
                  ))}
                </select>
              </div>
              {AXES.map((axis) => (
                <div key={axis}>
                  <div className="flex justify-between text-xs text-muted-foreground mb-1">
                    <span>{axis}</span>
                    <span>{(profile.axis_weights[axis] ?? 0.5).toFixed(2)}</span>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.05}
                    className="w-full accent-primary"
                    value={profile.axis_weights[axis] ?? 0.5}
                    onChange={(e) => {
                      const v = parseFloat(e.target.value);
                      setProfile({
                        ...profile,
                        axis_weights: { ...profile.axis_weights, [axis]: v },
                      });
                    }}
                  />
                </div>
              ))}
              <p className="text-xs text-muted-foreground">
                Session API key (dev):{" "}
                <input
                  type="password"
                  className="mt-1 w-full rounded border border-border bg-background px-2 py-1 text-xs"
                  placeholder="sessionStorage: coherence_api_key"
                  onBlur={(e) => {
                    if (e.target.value) sessionStorage.setItem("coherence_api_key", e.target.value);
                  }}
                />
              </p>
              <button
                type="button"
                className="rounded-lg bg-primary text-primary-foreground px-4 py-2 text-sm"
                onClick={() => void saveLocal()}
              >
                Save profile
              </button>
              {saveMsg && <p className="text-sm text-muted-foreground">{saveMsg}</p>}
              {profile.updated_at && (
                <p className="text-xs text-muted-foreground">Last updated: {profile.updated_at}</p>
              )}
            </div>
          </section>

          <section className="rounded-2xl border border-border/30 bg-card/40 p-6 space-y-3">
            <h2 className="text-lg font-medium">Concept preferences</h2>
            <p className="text-sm text-muted-foreground">
              Tag cloud (size ∝ weight). Edit weights in CLI via PATCH JSON for now.
            </p>
            <div className="flex flex-wrap gap-2">
              {Object.entries(profile.concept_weights).length === 0 ? (
                <span className="text-sm text-muted-foreground">No concepts yet — add via API/CLI.</span>
              ) : (
                Object.entries(profile.concept_weights).map(([k, w]) => (
                  <span
                    key={k}
                    className="inline-block rounded-full bg-primary/15 text-primary px-3 py-1"
                    style={{
                      fontSize: `${12 + (w / maxConcept) * 10}px`,
                      opacity: 0.75 + (w / maxConcept) * 0.25,
                    }}
                  >
                    {k}
                  </span>
                ))
              )}
            </div>
          </section>

          <section className="rounded-2xl border border-border/30 bg-card/40 p-6 space-y-3">
            <h2 className="text-lg font-medium">Idea resonance</h2>
            <div className="flex flex-wrap gap-2 items-end">
              <input
                className="flex-1 min-w-[200px] rounded-lg border border-border bg-background px-3 py-2 text-sm"
                placeholder="Idea id"
                value={ideaId}
                onChange={(e) => setIdeaId(e.target.value)}
              />
              <button
                type="button"
                className="rounded-lg border border-border px-4 py-2 text-sm hover:bg-muted/50"
                onClick={() => void runResonance()}
              >
                Compare
              </button>
            </div>
            {resonance && (
              <div className="text-sm space-y-1 mt-4 rounded-lg bg-muted/30 p-4">
                <p>
                  <strong>Resonance score:</strong> {resonance.resonance_score}
                </p>
                <p>Concept overlap: {resonance.concept_overlap} · Axis alignment: {resonance.axis_alignment}</p>
                <p>Worldview alignment: {resonance.worldview_alignment} (idea signal: {resonance.idea_worldview_signal})</p>
                {resonance.matching_concepts?.length > 0 && (
                  <p>Matching concepts: {resonance.matching_concepts.join(", ")}</p>
                )}
              </div>
            )}
          </section>
        </>
      )}
    </main>
  );
}

export default function ContributorBeliefsPage() {
  return (
    <Suspense fallback={<main className="min-h-screen p-8"><p className="text-muted-foreground">Loading…</p></main>}>
      <BeliefsPageInner />
    </Suspense>
  );
}
