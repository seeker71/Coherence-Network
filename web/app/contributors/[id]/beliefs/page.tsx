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
  "integrative",
  "speculative",
] as const;

type BeliefProfile = {
  contributor_id: string;
  worldview: string;
  concept_weights: Record<string, number>;
  axis_values: Record<string, number>;
};

function polarPoint(cx: number, cy: number, r: number, angle: number) {
  return {
    x: cx + r * Math.cos(angle),
    y: cy + r * Math.sin(angle),
  };
}

function BeliefRadar({ axes }: { axes: Record<string, number> }) {
  const keys = Object.keys(axes).sort();
  const n = Math.max(keys.length, 3);
  const cx = 120;
  const cy = 120;
  const maxR = 90;
  const points = keys.map((k, i) => {
    const ang = (Math.PI * 2 * i) / n - Math.PI / 2;
    const v = Math.max(0, Math.min(1, axes[k] ?? 0));
    const p = polarPoint(cx, cy, maxR * v, ang);
    return { x: p.x, y: p.y, key: k, val: v };
  });
  const ring = keys.map((_, i) => {
    const ang = (Math.PI * 2 * i) / n - Math.PI / 2;
    const p = polarPoint(cx, cy, maxR, ang);
    return p;
  });
  const pathD =
    points.length > 0
      ? `M ${points.map((p) => `${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" L ")} Z`
      : "";
  return (
    <div className="flex flex-col items-center gap-3">
      <svg width="260" height="260" viewBox="0 0 240 240" className="text-zinc-500">
        <circle cx={cx} cy={cy} r={maxR} fill="none" stroke="currentColor" strokeWidth="1" opacity={0.25} />
        <circle cx={cx} cy={cy} r={maxR * 0.66} fill="none" stroke="currentColor" strokeWidth="1" opacity={0.2} />
        <circle cx={cx} cy={cy} r={maxR * 0.33} fill="none" stroke="currentColor" strokeWidth="1" opacity={0.15} />
        {ring.map((p, i) => (
          <line
            key={`spoke-${i}`}
            x1={cx}
            y1={cy}
            x2={p.x}
            y2={p.y}
            stroke="currentColor"
            strokeWidth="1"
            opacity={0.2}
          />
        ))}
        {pathD ? (
          <path d={pathD} fill="rgba(59,130,246,0.25)" stroke="rgb(59,130,246)" strokeWidth="2" />
        ) : null}
        {points.map((p, i) => (
          <text
            key={`lbl-${p.key}`}
            x={p.x + (p.x - cx) * 0.12}
            y={p.y + (p.y - cy) * 0.12}
            textAnchor="middle"
            dominantBaseline="middle"
            className="fill-zinc-600 text-[10px]"
          >
            {p.key}
          </text>
        ))}
      </svg>
      <p className="text-xs text-zinc-500">Value axes (0–1): how you weight each lens</p>
    </div>
  );
}

function TagCloud({ weights }: { weights: Record<string, number> }) {
  const entries = Object.entries(weights).sort((a, b) => b[1] - a[1]);
  if (!entries.length) {
    return (
      <p className="text-sm text-zinc-500">No concept tags yet. Add weights via PATCH or adjust below.</p>
    );
  }
  return (
    <div className="flex flex-wrap gap-2 justify-center max-w-2xl">
      {entries.map(([tag, w]) => {
        const size = 12 + Math.round(w * 14);
        return (
          <span
            key={tag}
            className="rounded-full bg-zinc-100 px-3 py-1 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-100"
            style={{ fontSize: `${size}px` }}
          >
            {tag}
          </span>
        );
      })}
    </div>
  );
}

export default function ContributorBeliefsPage() {
  const params = useParams();
  const id = useMemo(() => String(params?.id ?? "").trim(), [params]);
  const [profile, setProfile] = useState<BeliefProfile | null>(null);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);
  const [ideaId, setIdeaId] = useState("");
  const [resonance, setResonance] = useState<{
    resonance_score: number;
    breakdown: { concept_alignment: number; worldview_alignment: number; axis_alignment: number };
    matched_concepts: string[];
  } | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setStatus("loading");
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/contributors/${encodeURIComponent(id)}/beliefs`, {
        cache: "no-store",
      });
      const json = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(json));
      setProfile(json as BeliefProfile);
      setStatus("ok");
    } catch (e) {
      setStatus("error");
      setError(String(e));
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  const saveWorldview = async (wv: string) => {
    if (!id) return;
    const res = await fetch(`${API_URL}/api/contributors/${encodeURIComponent(id)}/beliefs`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ worldview: wv }),
    });
    const json = await res.json();
    if (!res.ok) {
      setError(JSON.stringify(json));
      return;
    }
    setProfile(json as BeliefProfile);
  };

  const runResonance = async () => {
    if (!id || !ideaId.trim()) return;
    setResonance(null);
    try {
      const q = new URLSearchParams({ idea_id: ideaId.trim() });
      const res = await fetch(
        `${API_URL}/api/contributors/${encodeURIComponent(id)}/beliefs/resonance?${q}`,
        { cache: "no-store" }
      );
      const json = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(json));
      setResonance(json);
    } catch (e) {
      setError(String(e));
    }
  };

  if (!id) {
    return <p className="p-6 text-muted-foreground">Missing contributor id.</p>;
  }

  return (
    <main className="mx-auto max-w-4xl px-4 py-10">
      <nav className="mb-6 text-sm text-zinc-500">
        <Link href="/contributors" className="hover:underline">
          Contributors
        </Link>
        <span className="mx-2">/</span>
        <span className="text-zinc-900 dark:text-zinc-100">{id}</span>
        <span className="mx-2">/</span>
        <span className="font-medium text-zinc-900 dark:text-zinc-100">Beliefs</span>
      </nav>

      <h1 className="text-2xl font-semibold tracking-tight">Belief profile</h1>
      <p className="mt-2 text-zinc-600 dark:text-zinc-400">
        Worldview, concept resonance weights, and value axes aligned with your ideas.
      </p>

      {status === "loading" && <p className="mt-8 text-zinc-500">Loading…</p>}
      {status === "error" && (
        <p className="mt-8 text-red-600">Failed to load beliefs: {error}</p>
      )}

      {status === "ok" && profile && (
        <div className="mt-10 space-y-12">
          <section className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
            <h2 className="text-lg font-medium">Worldview</h2>
            <p className="mt-1 text-sm text-zinc-500">Primary lens when interpreting ideas.</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {WORLDVIEWS.map((wv) => (
                <button
                  key={wv}
                  type="button"
                  onClick={() => void saveWorldview(wv)}
                  className={`rounded-full px-4 py-2 text-sm capitalize transition ${
                    profile.worldview === wv
                      ? "bg-blue-600 text-white"
                      : "bg-zinc-100 text-zinc-800 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-100"
                  }`}
                >
                  {wv}
                </button>
              ))}
            </div>
          </section>

          <section className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
            <h2 className="text-lg font-medium">Value axes</h2>
            <BeliefRadar axes={profile.axis_values} />
          </section>

          <section className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
            <h2 className="text-lg font-medium">Concept cloud</h2>
            <p className="mt-1 text-sm text-zinc-500">Tags you resonate with (weight drives size).</p>
            <div className="mt-6">
              <TagCloud weights={profile.concept_weights} />
            </div>
          </section>

          <section className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
            <h2 className="text-lg font-medium">Resonance with an idea</h2>
            <p className="mt-1 text-sm text-zinc-500">Compare this profile to an idea id in the network.</p>
            <div className="mt-4 flex flex-wrap gap-2">
              <input
                className="min-w-[240px] flex-1 rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                placeholder="idea id"
                value={ideaId}
                onChange={(e) => setIdeaId(e.target.value)}
              />
              <button
                type="button"
                className="rounded-lg bg-zinc-900 px-4 py-2 text-sm text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900"
                onClick={() => void runResonance()}
              >
                Compute
              </button>
            </div>
            {resonance && (
              <div className="mt-6 rounded-lg bg-zinc-50 p-4 text-sm dark:bg-zinc-900">
                <p>
                  <span className="font-medium">Score:</span> {(resonance.resonance_score * 100).toFixed(1)}%
                </p>
                <p className="mt-2 text-zinc-600 dark:text-zinc-400">
                  Concepts {(resonance.breakdown.concept_alignment * 100).toFixed(0)}% · Worldview{" "}
                  {(resonance.breakdown.worldview_alignment * 100).toFixed(0)}% · Axes{" "}
                  {(resonance.breakdown.axis_alignment * 100).toFixed(0)}%
                </p>
                {resonance.matched_concepts?.length ? (
                  <p className="mt-2">Matched: {resonance.matched_concepts.join(", ")}</p>
                ) : null}
              </div>
            )}
          </section>
        </div>
      )}
    </main>
  );
}
