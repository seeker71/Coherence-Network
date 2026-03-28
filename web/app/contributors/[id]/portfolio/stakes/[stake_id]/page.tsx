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
  health: HealthSignal;
  idea_status: string;
  idea_contribution_count: number;
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
  if (signal === "active") return "text-green-400";
  if (signal === "slow") return "text-yellow-400";
  return "text-muted-foreground";
}

export default function StakeDrilldownPage() {
  const params = useParams<{ id: string; stake_id: string }>();
  const { id, stake_id } = params ?? {};
  const [stake, setStake] = useState<StakeDetail | null>(null);
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
      setStake(await res.json());
      setStatus("ok");
    } catch (e) {
      setStatus("error");
      setError(String(e));
    }
  }, [id, stake_id]);

  useEffect(() => {
    void load();
  }, [load]);

  const back = `/contributors/${id}/portfolio`;

  if (status === "loading") {
    return (
      <main className="min-h-screen px-4 md:px-8 py-10 max-w-5xl mx-auto">
        <p className="text-muted-foreground">Loading stake detail…</p>
      </main>
    );
  }

  if (status === "error" || !stake) {
    return (
      <main className="min-h-screen px-4 md:px-8 py-10 max-w-5xl mx-auto space-y-4">
        <Link href={back} className="text-sm text-primary underline">
          ← Portfolio
        </Link>
        <p className="text-destructive">{error ?? "Stake not found."}</p>
      </main>
    );
  }

  const roiPositive = stake.roi_pct !== null && stake.roi_pct >= 0;

  return (
    <main className="min-h-screen px-4 md:px-8 py-10 max-w-5xl mx-auto space-y-6">
      <Link
        href={back}
        className="text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        ← Portfolio
      </Link>

      {/* Header */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 sm:p-7 space-y-3">
        <p className="text-sm text-muted-foreground">Stake position</p>
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
            className={`rounded-full border border-border/30 px-2 py-0.5 ${activityColor(stake.health.activity_signal)}`}
          >
            {stake.health.activity_signal}
          </span>
        </div>
      </section>

      {/* Key metrics */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 space-y-1">
          <p className="text-xs text-muted-foreground">CC Staked</p>
          <p className="text-2xl font-light text-primary">{fmtCC(stake.cc_staked)}</p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 space-y-1">
          <p className="text-xs text-muted-foreground">Current Valuation</p>
          <p className="text-2xl font-light text-primary">{fmtCC(stake.cc_valuation)}</p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 space-y-1">
          <p className="text-xs text-muted-foreground">ROI</p>
          <p
            className={`text-2xl font-light font-mono ${
              stake.roi_pct === null
                ? "text-muted-foreground"
                : roiPositive
                ? "text-green-400"
                : "text-red-400"
            }`}
          >
            {stake.roi_pct === null
              ? "—"
              : `${roiPositive ? "+" : ""}${stake.roi_pct.toFixed(2)}%`}
          </p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 space-y-1">
          <p className="text-xs text-muted-foreground">My Contributions</p>
          <p className="text-2xl font-light text-primary">{stake.idea_contribution_count}</p>
        </div>
      </section>

      {/* Timeline */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3">
        <h2 className="text-lg font-medium">Timeline</h2>
        <div className="space-y-2 text-sm">
          <div className="flex items-center justify-between border-b border-border/10 pb-2">
            <span className="text-muted-foreground">Staked at</span>
            <span>{fmtDate(stake.staked_at)}</span>
          </div>
          <div className="flex items-center justify-between border-b border-border/10 pb-2">
            <span className="text-muted-foreground">Last valued</span>
            <span>{fmtDate(stake.last_valued_at)}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Recent activity (30d)</span>
            <span>{stake.health.evidence_count} event{stake.health.evidence_count !== 1 ? "s" : ""}</span>
          </div>
        </div>
      </section>

      {/* Idea health */}
      {stake.health.value_delta_pct !== null && (
        <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-2">
          <h2 className="text-lg font-medium">Idea Health Signal</h2>
          <div className="flex items-center gap-3">
            <div className="h-2 w-full bg-zinc-700/40 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${
                  stake.health.value_delta_pct >= 0 ? "bg-green-500" : "bg-red-500"
                }`}
                style={{
                  width: `${Math.min(Math.abs(stake.health.value_delta_pct), 100)}%`,
                }}
              />
            </div>
            <span
              className={`text-sm font-mono shrink-0 ${
                stake.health.value_delta_pct >= 0 ? "text-green-400" : "text-red-400"
              }`}
            >
              {stake.health.value_delta_pct >= 0 ? "+" : ""}
              {stake.health.value_delta_pct.toFixed(1)}%
            </span>
          </div>
          <p className="text-xs text-muted-foreground">
            Value delta relative to network baseline (coherence score vs 0.5 midpoint)
          </p>
        </section>
      )}

      {/* Navigate to idea contributions */}
      <div className="flex gap-4 text-sm">
        <Link
          href={`/contributors/${encodeURIComponent(id ?? "")}/portfolio/ideas/${encodeURIComponent(stake.idea_id)}`}
          className="text-primary hover:underline"
        >
          View my contributions to this idea →
        </Link>
        <Link
          href={`/ideas/${encodeURIComponent(stake.idea_id)}`}
          className="text-muted-foreground hover:text-foreground transition-colors"
        >
          View idea page →
        </Link>
      </div>
    </main>
  );
}
