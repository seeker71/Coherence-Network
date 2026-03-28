"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getApiBase } from "@/lib/api";

const API = getApiBase();

interface StakeIdeaActivity {
  activity_since_staking: string;
  coherence_at_staking: number | null;
  coherence_current: number | null;
  contributions_since_staking: number;
}

interface ValueLineageSummary {
  lineage_id: string | null;
  total_value: number;
  roi_ratio: number | null;
  stage_events: number;
}

interface StakeDetail {
  stake_id: string;
  contributor_id: string;
  idea_id: string;
  idea_title: string;
  cc_staked: number;
  cc_valuation: number | null;
  roi_pct: number | null;
  staked_at: string | null;
  last_valued_at: string | null;
  idea_activity: StakeIdeaActivity;
  value_lineage: ValueLineageSummary;
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  } catch {
    return iso;
  }
}

function fmtCC(val: number | null): string {
  if (val === null || val === undefined) return "—";
  return val.toFixed(2);
}

function activityIcon(signal: string): { label: string; cls: string } {
  switch (signal) {
    case "improved": return { label: "Improved", cls: "text-green-400" };
    case "stable":   return { label: "Stable",   cls: "text-blue-400" };
    case "declined": return { label: "Declined",  cls: "text-red-400" };
    default:         return { label: "Unknown",   cls: "text-muted-foreground" };
  }
}

function CoherenceBar({ value, label }: { value: number | null; label: string }) {
  if (value === null) return null;
  const pct = Math.min(Math.max(value * 100, 0), 100);
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{label}</span>
        <span>{pct.toFixed(1)}%</span>
      </div>
      <div className="h-1.5 w-full bg-zinc-700/40 rounded-full overflow-hidden">
        <div className="h-full bg-primary rounded-full transition-all" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export default function StakeDrilldownPage() {
  const params = useParams<{ id: string; stake_id: string }>();
  const { id, stake_id } = params ?? {};
  const [data, setData] = useState<StakeDetail | null>(null);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id || !stake_id) return;
    setStatus("loading");
    try {
      const res = await fetch(
        `${API}/api/contributors/${encodeURIComponent(id)}/stakes/${encodeURIComponent(stake_id)}`
      );
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j.detail ?? `Failed to load stake (${res.status})`);
      }
      setData(await res.json());
      setStatus("ok");
    } catch (e) {
      setStatus("error");
      setError(String(e));
    }
  }, [id, stake_id]);

  useEffect(() => { void load(); }, [load]);

  const back = `/contributors/${id}/portfolio`;

  if (status === "loading") {
    return (
      <main className="min-h-screen px-4 md:px-8 py-10 max-w-5xl mx-auto">
        <p className="text-muted-foreground">Loading stake detail…</p>
      </main>
    );
  }

  if (status === "error" || !data) {
    return (
      <main className="min-h-screen px-4 md:px-8 py-10 max-w-5xl mx-auto space-y-4">
        <Link href={back} className="text-sm text-primary underline">← Portfolio</Link>
        <p className="text-destructive">{error ?? "Stake not found."}</p>
      </main>
    );
  }

  const { idea_activity, value_lineage } = data;
  const actSig = activityIcon(idea_activity.activity_since_staking);
  const roiPositive = data.roi_pct !== null && data.roi_pct >= 0;

  return (
    <main className="min-h-screen px-4 md:px-8 py-10 max-w-5xl mx-auto space-y-6">
      {/* Breadcrumb */}
      <Link href={back} className="text-sm text-muted-foreground hover:text-foreground transition-colors">
        ← Portfolio
      </Link>

      {/* Header */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 sm:p-7 space-y-2">
        <p className="text-sm text-muted-foreground">Stake position</p>
        <h1 className="text-2xl md:text-3xl font-light leading-snug">
          <Link
            href={`/ideas/${encodeURIComponent(data.idea_id)}`}
            className="hover:text-primary transition-colors"
          >
            {data.idea_title}
          </Link>
        </h1>
        <div className="flex flex-wrap gap-2 pt-1 text-xs">
          <span className={`font-medium ${actSig.cls}`}>{actSig.label} since staking</span>
          <span className="text-muted-foreground">·</span>
          <span className="text-muted-foreground">Staked {fmtDate(data.staked_at)}</span>
          {data.last_valued_at && (
            <>
              <span className="text-muted-foreground">·</span>
              <span className="text-muted-foreground">Valued {fmtDate(data.last_valued_at)}</span>
            </>
          )}
        </div>
      </section>

      {/* Key metrics */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 space-y-1">
          <p className="text-muted-foreground text-xs">CC Staked</p>
          <p className="text-2xl font-light font-mono text-primary">{fmtCC(data.cc_staked)}</p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 space-y-1">
          <p className="text-muted-foreground text-xs">Current Valuation</p>
          <p className="text-2xl font-light font-mono">{fmtCC(data.cc_valuation)}</p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 space-y-1">
          <p className="text-muted-foreground text-xs">ROI</p>
          <p className={`text-2xl font-light font-mono font-medium ${data.roi_pct !== null ? (roiPositive ? "text-green-400" : "text-red-400") : ""}`}>
            {data.roi_pct !== null ? `${roiPositive ? "+" : ""}${data.roi_pct.toFixed(2)}%` : "—"}
          </p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 space-y-1">
          <p className="text-muted-foreground text-xs">ROI Ratio</p>
          <p className="text-2xl font-light font-mono">
            {value_lineage.roi_ratio != null ? `${value_lineage.roi_ratio.toFixed(3)}×` : "—"}
          </p>
        </div>
      </section>

      {/* Idea activity since staking */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 sm:p-7 space-y-4">
        <h2 className="text-lg font-medium">Idea Activity Since Staking</h2>

        <div className="space-y-3">
          <CoherenceBar value={idea_activity.coherence_at_staking} label="Coherence at staking" />
          <CoherenceBar value={idea_activity.coherence_current} label="Coherence now" />
        </div>

        {idea_activity.coherence_at_staking !== null && idea_activity.coherence_current !== null && (
          <div className="text-sm">
            {(() => {
              const delta = idea_activity.coherence_current - idea_activity.coherence_at_staking;
              const deltaAbs = Math.abs(delta * 100).toFixed(1);
              if (delta > 0.001) return <p className="text-green-400">↑ Coherence improved by {deltaAbs}pp since staking</p>;
              if (delta < -0.001) return <p className="text-red-400">↓ Coherence declined by {deltaAbs}pp since staking</p>;
              return <p className="text-muted-foreground">Coherence unchanged since staking</p>;
            })()}
          </div>
        )}

        <div className="flex items-center gap-2 text-sm">
          <span className="text-2xl font-light font-mono text-primary">
            {idea_activity.contributions_since_staking}
          </span>
          <span className="text-muted-foreground">
            contribution{idea_activity.contributions_since_staking !== 1 ? "s" : ""} to this idea since you staked
          </span>
        </div>
      </section>

      {/* Value lineage */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 sm:p-7 space-y-3">
        <h2 className="text-lg font-medium">Value Lineage</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
          <div className="space-y-1">
            <p className="text-muted-foreground text-xs">Total value tracked</p>
            <p className="text-xl font-light font-mono">{fmtCC(value_lineage.total_value)} CC</p>
          </div>
          <div className="space-y-1">
            <p className="text-muted-foreground text-xs">Stage events</p>
            <p className="text-xl font-light">{value_lineage.stage_events}</p>
          </div>
          {value_lineage.lineage_id && (
            <div className="space-y-1">
              <p className="text-muted-foreground text-xs">Lineage chain</p>
              <p className="text-xs font-mono text-muted-foreground truncate">{value_lineage.lineage_id}</p>
            </div>
          )}
        </div>
      </section>

      {/* Navigation */}
      <div className="flex gap-4 text-sm text-muted-foreground pt-2">
        <Link href={back} className="hover:text-foreground transition-colors">← Portfolio</Link>
        <Link href={`/ideas/${encodeURIComponent(data.idea_id)}`} className="hover:text-foreground transition-colors">
          View Idea →
        </Link>
      </div>
    </main>
  );
}
