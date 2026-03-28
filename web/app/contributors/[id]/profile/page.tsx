"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { getApiBase } from "@/lib/api";

const API_URL = getApiBase();

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
  axes: Record<string, number>;
  concepts: Record<string, number>;
};

type AxisEntry = { key: string; value: number };

function RadarChart({ axes }: { axes: AxisEntry[] }) {
  const n = Math.max(axes.length, 3);
  const size = 220;
  const cx = size / 2;
  const cy = size / 2;
  const r = 90;
  const points = axes.map((_, i) => {
    const angle = (-Math.PI / 2) + (2 * Math.PI * i) / n;
    const dist = r * axes[i].value;
    return `${cx + dist * Math.cos(angle)},${cy + dist * Math.sin(angle)}`;
  });
  const poly = points.join(" ");
  const rings = [0.25, 0.5, 0.75, 1.0].map((t) => (
    <circle
      key={t}
      cx={cx}
      cy={cy}
      r={r * t}
      fill="none"
      stroke="currentColor"
      className="text-border/40"
      strokeWidth={1}
    />
  ));
  const labels = axes.map((a, i) => {
    const angle = (-Math.PI / 2) + (2 * Math.PI * i) / n;
    const lr = r + 14;
    const x = cx + lr * Math.cos(angle);
    const y = cy + lr * Math.sin(angle);
    return (
      <text
        key={a.key}
        x={x}
        y={y}
        textAnchor="middle"
        dominantBaseline="middle"
        className="fill-muted-foreground text-[10px] uppercase tracking-wide"
      >
        {a.key}
      </text>
    );
  });
  return (
    <svg width={size} height={size} className="text-foreground">
      {rings}
      {labels}
      <polygon points={poly} fill="hsl(var(--primary) / 0.25)" stroke="hsl(var(--primary))" strokeWidth={1.5} />
    </svg>
  );
}

export default function ContributorBeliefProfilePage() {
  const params = useParams();
  const rawId = params?.id;
  const contributorId = typeof rawId === "string" ? decodeURIComponent(rawId) : "";

  const [profile, setProfile] = useState<BeliefProfile | null>(null);
  const [worldview, setWorldview] = useState<string>("pragmatic");
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [ideaId, setIdeaId] = useState("coherence-network-agent-pipeline");
  const [resonance, setResonance] = useState<Record<string, unknown> | null>(null);

  const load = useCallback(async () => {
    if (!contributorId) return;
    setStatus("loading");
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/contributors/${encodeURIComponent(contributorId)}/beliefs`, {
        cache: "no-store",
      });
      if (!res.ok) throw new Error(await res.text());
      const data = (await res.json()) as BeliefProfile;
      setProfile(data);
      setWorldview(data.worldview || "pragmatic");
      setStatus("ok");
    } catch (e) {
      setStatus("error");
      setError(String(e));
    }
  }, [contributorId]);

  useEffect(() => {
    void load();
  }, [load]);

  const axisEntries: AxisEntry[] = useMemo(() => {
    if (!profile) return [];
    return Object.entries(profile.axes).map(([key, value]) => ({ key, value }));
  }, [profile]);

  const save = async () => {
    if (!contributorId) return;
    setSaving(true);
    try {
      const res = await fetch(`${API_URL}/api/contributors/${encodeURIComponent(contributorId)}/beliefs`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ worldview }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = (await res.json()) as BeliefProfile;
      setProfile(data);
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  const runResonance = async () => {
    if (!contributorId || !ideaId.trim()) return;
    setError(null);
    try {
      const u = new URL(
        `${API_URL}/api/contributors/${encodeURIComponent(contributorId)}/beliefs/resonance`
      );
      u.searchParams.set("idea_id", ideaId.trim());
      const res = await fetch(u.toString(), { cache: "no-store" });
      if (!res.ok) throw new Error(await res.text());
      setResonance((await res.json()) as Record<string, unknown>);
    } catch (e) {
      setError(String(e));
    }
  };

  if (!contributorId) {
    return (
      <main className="min-h-screen px-4 py-10 max-w-3xl mx-auto">
        <p className="text-muted-foreground">Missing contributor id.</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen px-4 md:px-8 py-10 max-w-4xl mx-auto space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm text-muted-foreground">Belief profile</p>
          <h1 className="text-3xl font-light tracking-tight">Worldview & preferences</h1>
          <p className="text-sm text-muted-foreground mt-1">Contributor {contributorId}</p>
        </div>
        <Link href="/contributors" className="text-sm underline text-muted-foreground hover:text-foreground">
          ← Contributors
        </Link>
      </div>

      {status === "loading" && <p className="text-muted-foreground">Loading…</p>}
      {status === "error" && <p className="text-destructive">Error: {error}</p>}

      {status === "ok" && profile && (
        <>
          <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-4">
            <h2 className="text-lg font-medium">Worldview</h2>
            <p className="text-sm text-muted-foreground">
              How you tend to approach ideas (scientific, spiritual, pragmatic, holistic, artistic, systems).
            </p>
            <div className="flex flex-wrap gap-2">
              {WORLDVIEWS.map((w) => (
                <button
                  key={w}
                  type="button"
                  onClick={() => setWorldview(w)}
                  className={`rounded-full px-3 py-1 text-sm border transition-colors ${
                    worldview === w
                      ? "border-primary bg-primary/10 text-foreground"
                      : "border-border/40 text-muted-foreground hover:border-border"
                  }`}
                >
                  {w}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={() => void save()}
              disabled={saving}
              className="rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save worldview"}
            </button>
          </section>

          <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-4">
            <h2 className="text-lg font-medium">Value axes</h2>
            <p className="text-sm text-muted-foreground">Relative emphasis across dimensions (API defaults at 0.5).</p>
            <div className="flex justify-center py-2">
              <RadarChart axes={axisEntries} />
            </div>
          </section>

          <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-4">
            <h2 className="text-lg font-medium">Concept preferences</h2>
            <p className="text-sm text-muted-foreground">Tags you resonate with (weight = size).</p>
            <div className="flex flex-wrap gap-2 items-end">
              {Object.entries(profile.concepts).length === 0 ? (
                <span className="text-sm text-muted-foreground">No concepts yet — set via API PATCH.</span>
              ) : (
                Object.entries(profile.concepts).map(([tag, w]) => (
                  <span
                    key={tag}
                    className="inline-block rounded-full bg-muted/60 px-2 py-1 text-muted-foreground"
                    style={{ fontSize: `${12 + w * 10}px` }}
                  >
                    {tag}
                  </span>
                ))
              )}
            </div>
          </section>

          <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-4">
            <h2 className="text-lg font-medium">Resonance with an idea</h2>
            <div className="flex flex-wrap gap-2 items-center">
              <input
                className="flex-1 min-w-[200px] rounded-lg border border-border/40 bg-background px-3 py-2 text-sm"
                value={ideaId}
                onChange={(e) => setIdeaId(e.target.value)}
                placeholder="idea id"
              />
              <button
                type="button"
                onClick={() => void runResonance()}
                className="rounded-lg border border-border/40 px-4 py-2 text-sm hover:bg-muted/40"
              >
                Compare
              </button>
            </div>
            {resonance && (
              <pre className="text-xs overflow-auto rounded-lg bg-background/50 p-3 border border-border/20">
                {JSON.stringify(resonance, null, 2)}
              </pre>
            )}
          </section>
        </>
      )}
    </main>
  );
}
