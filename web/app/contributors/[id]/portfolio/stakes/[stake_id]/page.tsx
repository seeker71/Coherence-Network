"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getApiBase } from "@/lib/api";

const API = getApiBase();

interface HealthSignal {
  activity_signal: string;
  value_delta_pct: number | null;
  evidence_count: number;
}

interface IdeaActivityEvent {
  event_type: string;
  date: string | null;
  description: string;
  value_change: number | null;
}

interface StakeDetail {
  stake_id: string;
  contributor_id: string;
  idea_id: string;
  idea_title: string;
  idea_status: string;
  cc_staked: number;
  cc_valuation: number | null;
  roi_pct: number | null;
  staked_at: string | null;
  health: HealthSignal;
  idea_activity_since_staking: IdeaActivityEvent[];
  total_contributions_since_staking: number;
  network_total_supply: number | null;
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

function fmtCC(val: number | null): string {
  if (val === null || val === undefined) return "—";
  return val.toFixed(2);
}

function activityColor(signal: string): string {
  if (signal === "active") return "text-emerald-400";
  if (signal === "slow") return "text-yellow-400";
  if (signal === "dormant") return "text-muted-foreground";
  return "text-muted-foreground";
}

function gardenHealth(signal: string): { label: string; emoji: string; color: string } {
  const s = signal.trim().toLowerCase();
  if (s === "active") return { label: "Thriving", emoji: "🌿", color: "text-emerald-400" };
  if (s === "slow") return { label: "Growing", emoji: "🌱", color: "text-yellow-400" };
  if (s === "dormant") return { label: "Dormant", emoji: "🍂", color: "text-muted-foreground" };
  return { label: "Untested", emoji: "🫘", color: "text-muted-foreground" };
}

function roiColor(roi: number | null): string {
  if (roi === null) return "text-muted-foreground";
  return roi >= 0 ? "text-emerald-400" : "text-muted-foreground";
}

export default function StakeDrilldownPage() {
  const params = useParams<{ id: string; stake_id: string }>();
  const { id, stake_id } = params ?? {};
  const [stake, setStake] = useState<StakeDetail | null>(null);
  const [loadStatus, setLoadStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  const back = `/contributors/${id}/portfolio`;

  const load = useCallback(async () => {
    if (!id || !stake_id) return;
    setLoadStatus("loading");
    try {
      const res = await fetch(
        `${API}/api/contributors/${encodeURIComponent(id)}/stakes/${encodeURIComponent(stake_id)}`
      );
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j.detail ?? `Stake not found (${res.status})`);
      }
      setStake(await res.json());
      setLoadStatus("ok");
    } catch (e) {
      setError(String(e));
      setLoadStatus("error");
    }
  }, [id, stake_id]);

  useEffect(() => { void load(); }, [load]);

  if (loadStatus === "loading") {
    return (
      <main className="min-h-screen px-4 md:px-8 py-10 max-w-5xl mx-auto">
        <p className="text-muted-foreground">Loading stake detail…</p>
      </main>
    );
  }

  if (loadStatus === "error" || !stake) {
    return (
      <main className="min-h-screen px-4 md:px-8 py-10 max-w-5xl mx-auto space-y-4">
        <Link href={back} className="text-sm text-primary underline">← Portfolio</Link>
        <p className="text-destructive">{error ?? "Stake not found."}</p>
      </main>
    );
  }

  const networkPct =
    stake.network_total_supply && stake.cc_staked > 0
      ? ((stake.cc_staked / stake.network_total_supply) * 100).toFixed(4)
      : null;

  const currentPct =
    stake.network_total_supply && stake.cc_valuation != null && stake.cc_valuation > 0
      ? ((stake.cc_valuation / stake.network_total_supply) * 100).toFixed(4)
      : null;

  return (
    <main className="min-h-screen px-4 md:px-8 py-10 max-w-5xl mx-auto space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Link href={back} className="hover:text-foreground transition-colors">← Garden</Link>
        <span>/</span>
        <span>Seed</span>
      </div>

      {/* Header */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3">
        <p className="text-xs text-muted-foreground uppercase tracking-widest">Seed position</p>
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-2xl md:text-3xl font-light">
              <Link
                href={`/ideas/${encodeURIComponent(stake.idea_id)}`}
                className="hover:text-primary transition-colors"
              >
                {stake.idea_title}
              </Link>
            </h1>
            <div className="flex flex-wrap gap-2 text-xs">
              <span className="rounded-full border border-border/30 px-2 py-0.5 text-muted-foreground">
                {stake.idea_status}
              </span>
              <span
                className={`rounded-full border border-border/30 px-2 py-0.5 ${gardenHealth(stake.health.activity_signal).color}`}
                aria-label={`Garden health: ${gardenHealth(stake.health.activity_signal).label}`}
              >
                <span aria-hidden="true">{gardenHealth(stake.health.activity_signal).emoji}</span>{" "}
                {gardenHealth(stake.health.activity_signal).label}
              </span>
            </div>
          </div>
          <div className="text-right shrink-0">
            <p className="text-xs text-muted-foreground mb-1">Planted {fmtDate(stake.staked_at)}</p>
            <p className="text-xs font-mono text-muted-foreground truncate max-w-40">{stake.stake_id}</p>
          </div>
        </div>
      </section>

      {/* Position metrics */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
          <p className="text-xs text-muted-foreground">Seeds Planted</p>
          <p className="text-2xl font-light text-primary">{fmtCC(stake.cc_staked)}</p>
          {networkPct && (
            <p className="text-xs text-muted-foreground">{networkPct}% of garden</p>
          )}
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
          <p className="text-xs text-muted-foreground">Current Value</p>
          <p className="text-2xl font-light">
            {stake.cc_valuation != null ? (
              <span className={roiColor(stake.roi_pct)}>{fmtCC(stake.cc_valuation)} seeds</span>
            ) : (
              <span className="text-muted-foreground">—</span>
            )}
          </p>
          {currentPct && (
            <p className="text-xs text-muted-foreground">{currentPct}% of garden</p>
          )}
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
          <p className="text-xs text-muted-foreground">Yield</p>
          <p className={`text-2xl font-light font-mono ${roiColor(stake.roi_pct)}`}>
            {stake.roi_pct != null
              ? `×${(1 + stake.roi_pct / 100).toFixed(2)} (${stake.roi_pct >= 0 ? "+" : ""}${stake.roi_pct.toFixed(2)}%)`
              : "—"}
          </p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-1">
          <p className="text-xs text-muted-foreground">Growth Since Planting</p>
          <p className="text-2xl font-light text-primary">{stake.total_contributions_since_staking}</p>
          <p className="text-xs text-muted-foreground">contributions</p>
        </div>
      </section>

      {/* Activity timeline since staking */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-4">
        <div className="flex items-baseline justify-between">
          <h2 className="text-lg font-medium">Growth Since Planting</h2>
          <span className="text-xs text-muted-foreground">
            {stake.total_contributions_since_staking} total
            {stake.idea_activity_since_staking.length < stake.total_contributions_since_staking
              ? ` · showing ${stake.idea_activity_since_staking.length}`
              : ""}
          </span>
        </div>

        {stake.idea_activity_since_staking.length > 0 ? (
          <ol className="relative border-l border-border/30 space-y-4 pl-6">
            {stake.idea_activity_since_staking.map((evt, i) => (
              <li key={i} className="relative">
                <span className="absolute -left-[25px] flex items-center justify-center w-4 h-4 rounded-full border border-border/40 bg-background text-[9px] text-muted-foreground">
                  {i + 1}
                </span>
                <div className="rounded-xl border border-border/20 bg-background/40 p-3 space-y-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs px-1.5 py-0.5 rounded bg-zinc-700/30 text-zinc-300">
                      {evt.event_type}
                    </span>
                    <span className="text-xs text-muted-foreground">{fmtDate(evt.date)}</span>
                  </div>
                  <p className="text-sm text-muted-foreground">{evt.description}</p>
                  {evt.value_change != null && evt.value_change > 0 && (
                    <p className="text-xs font-mono text-primary">+{evt.value_change.toFixed(2)} seeds</p>
                  )}
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <p className="text-sm text-muted-foreground">
            No growth on this seed since you planted. Check back later.
          </p>
        )}
      </section>

      {/* Health detail */}
      {stake.health.value_delta_pct != null && (
        <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-2">
          <h2 className="text-base font-medium">Plant Health</h2>
          <div className="flex flex-wrap gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">Value delta: </span>
              <span className={stake.health.value_delta_pct >= 0 ? "text-emerald-400" : "text-muted-foreground"}>
                {stake.health.value_delta_pct >= 0 ? "+" : ""}
                {stake.health.value_delta_pct.toFixed(1)}%
              </span>
            </div>
            <div>
              <span className="text-muted-foreground">Evidence count: </span>
              <span>{stake.health.evidence_count}</span>
            </div>
          </div>
        </section>
      )}

      {/* Footer nav */}
      <div className="flex gap-4 text-sm text-muted-foreground pt-2">
        <Link href={back} className="hover:text-foreground transition-colors">← Back to Garden</Link>
        <Link
          href={`/ideas/${encodeURIComponent(stake.idea_id)}`}
          className="hover:text-foreground transition-colors"
        >
          View Idea →
        </Link>
      </div>
    </main>
  );
}
