"use client";

/**
 * /energy-flow/simulate — CC flow simulator.
 *
 * The community senses how energy moves before it moves.
 * Adjust any input, see how CC flows change, read the vitality signals.
 * Every simulation uses the community's active policies.
 */

import React, { useState, useCallback } from "react";
import Link from "next/link";
import { getApiBase } from "@/lib/api";

const API = getApiBase();

type FlowNode = {
  id: string;
  label: string;
  cc_in: number;
  cc_out: number;
  detail: string;
};

type FlowEdge = {
  from_id: string;
  to_id: string;
  cc_amount: number;
  label: string;
};

type VitalitySignal = {
  signal: string;
  value: number;
  message: string;
  vitality: string;
};

type SimResult = {
  nodes: FlowNode[];
  edges: FlowEdge[];
  totals: Record<string, any>;
  policy_snapshot: Record<string, any>;
  vitality_signals: VitalitySignal[];
};

const DEFAULT_SCENARIO = {
  contributors: 10,
  assets_created: 5,
  views_per_asset: 100,
  referral_rate: 0.15,
  transaction_rate: 0.05,
  avg_transaction_cc: 50,
  avg_contribution_cc: 100,
  avg_coherence_score: 0.75,
  staking_rate: 0.3,
  workspace_id: "coherence-network",
};

export default function FlowSimulator() {
  const [scenario, setScenario] = useState(DEFAULT_SCENARIO);
  const [result, setResult] = useState<SimResult | null>(null);
  const [loading, setLoading] = useState(false);

  const simulate = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/flow/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(scenario),
      });
      if (res.ok) {
        setResult(await res.json());
      }
    } catch {
      // Simulation is exploratory
    } finally {
      setLoading(false);
    }
  }, [scenario]);

  function updateField(field: string, value: number) {
    setScenario((prev) => ({ ...prev, [field]: value }));
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8 px-4 py-8 sm:px-6">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Flow Simulator</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          See how CC flows through the community. Adjust any input to sense
          how energy moves — creation, attention, presence, commitment.
        </p>
      </header>

      <div className="grid gap-8 lg:grid-cols-2">
        {/* Input knobs */}
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">Community Scenario</h2>

          <SliderInput
            label="Active contributors"
            value={scenario.contributors}
            min={1} max={500} step={1}
            onChange={(v) => updateField("contributors", v)}
          />
          <SliderInput
            label="Assets created / month"
            value={scenario.assets_created}
            min={0} max={100} step={1}
            onChange={(v) => updateField("assets_created", v)}
          />
          <SliderInput
            label="Views per asset / month"
            value={scenario.views_per_asset}
            min={0} max={10000} step={10}
            onChange={(v) => updateField("views_per_asset", v)}
          />
          <SliderInput
            label="Referral rate"
            value={scenario.referral_rate}
            min={0} max={1} step={0.01}
            format={(v) => `${(v * 100).toFixed(0)}%`}
            onChange={(v) => updateField("referral_rate", v)}
          />
          <SliderInput
            label="Transaction rate"
            value={scenario.transaction_rate}
            min={0} max={0.5} step={0.01}
            format={(v) => `${(v * 100).toFixed(0)}%`}
            onChange={(v) => updateField("transaction_rate", v)}
          />
          <SliderInput
            label="Avg transaction (CC)"
            value={scenario.avg_transaction_cc}
            min={1} max={1000} step={5}
            onChange={(v) => updateField("avg_transaction_cc", v)}
          />
          <SliderInput
            label="Avg contribution reward (CC)"
            value={scenario.avg_contribution_cc}
            min={1} max={500} step={5}
            onChange={(v) => updateField("avg_contribution_cc", v)}
          />
          <SliderInput
            label="Community coherence"
            value={scenario.avg_coherence_score}
            min={0} max={1} step={0.05}
            format={(v) => v.toFixed(2)}
            onChange={(v) => updateField("avg_coherence_score", v)}
          />
          <SliderInput
            label="Staking rate"
            value={scenario.staking_rate}
            min={0} max={1} step={0.05}
            format={(v) => `${(v * 100).toFixed(0)}%`}
            onChange={(v) => updateField("staking_rate", v)}
          />

          <button
            onClick={simulate}
            disabled={loading}
            className="w-full rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {loading ? "Simulating..." : "Simulate Flow"}
          </button>
        </section>

        {/* Results */}
        <section className="space-y-6">
          {result ? (
            <>
              {/* Totals */}
              <div className="grid grid-cols-2 gap-2">
                <TotalCard label="Monthly CC minted" value={result.totals.monthly_cc_minted} />
                <TotalCard label="Per contributor" value={result.totals.cc_per_contributor} />
                <TotalCard label="Creation" value={result.totals.creation_cc} color="text-blue-500" />
                <TotalCard label="Attention" value={result.totals.attention_cc} color="text-green-500" />
                <TotalCard label="Presence" value={result.totals.presence_cc} color="text-purple-500" />
                <TotalCard label="Staked" value={result.totals.staked_cc} color="text-amber-500" />
              </div>

              {/* Flow visualization */}
              <div className="rounded-xl border border-border/40 bg-card/50 p-4">
                <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                  CC Flow
                </h3>
                <div className="space-y-2">
                  {result.edges
                    .filter((e) => e.cc_amount > 0)
                    .sort((a, b) => b.cc_amount - a.cc_amount)
                    .map((edge, i) => {
                      const maxCC = Math.max(...result.edges.map((e) => e.cc_amount), 1);
                      const width = Math.max(4, (edge.cc_amount / maxCC) * 100);
                      return (
                        <div key={i} className="space-y-1">
                          <div className="flex items-center justify-between text-xs">
                            <span className="text-muted-foreground">{edge.label}</span>
                            <span className="font-mono font-medium">
                              {edge.cc_amount.toLocaleString(undefined, { maximumFractionDigits: 2 })} CC
                            </span>
                          </div>
                          <div className="h-2 overflow-hidden rounded-full bg-muted">
                            <div
                              className="h-full rounded-full bg-primary/60 transition-all duration-500"
                              style={{ width: `${width}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                </div>
              </div>

              {/* Vitality signals */}
              {result.vitality_signals.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                    Vitality Signals
                  </h3>
                  {result.vitality_signals.map((sig, i) => (
                    <div
                      key={i}
                      className={`rounded-lg border p-3 text-sm ${
                        sig.vitality === "thriving"
                          ? "border-green-500/30 bg-green-500/5 text-green-700 dark:text-green-400"
                          : sig.vitality === "needs_energy"
                            ? "border-amber-500/30 bg-amber-500/5 text-amber-700 dark:text-amber-400"
                            : sig.vitality === "opportunity"
                              ? "border-blue-500/30 bg-blue-500/5 text-blue-700 dark:text-blue-400"
                              : "border-border/40 bg-card/50 text-muted-foreground"
                      }`}
                    >
                      {sig.message}
                    </div>
                  ))}
                </div>
              )}

              {/* Node details */}
              <div className="space-y-2">
                <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                  Flow Nodes
                </h3>
                {result.nodes.map((node) => (
                  <div
                    key={node.id}
                    className="rounded-lg border border-border/30 bg-card/30 p-3"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-sm">{node.label}</span>
                      <span className="font-mono text-xs text-muted-foreground">
                        {node.cc_out > 0 ? `${node.cc_out.toLocaleString(undefined, { maximumFractionDigits: 2 })} CC` : "—"}
                      </span>
                    </div>
                    <p className="mt-0.5 text-xs text-muted-foreground">{node.detail}</p>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border/40 py-16 text-center">
              <p className="text-sm text-muted-foreground">
                Adjust the community scenario and simulate to see how energy flows.
              </p>
            </div>
          )}
        </section>
      </div>

      <footer className="flex items-center justify-between border-t border-border/30 pt-4">
        <Link
          href="/energy-flow"
          className="text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          ← Energy Flow Dashboard
        </Link>
        <Link
          href="/analytics"
          className="text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          Analytics →
        </Link>
      </footer>
    </div>
  );
}

function SliderInput({
  label,
  value,
  min,
  max,
  step,
  format,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  format?: (v: number) => string;
  onChange: (v: number) => void;
}) {
  const display = format ? format(value) : value.toLocaleString();
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <label className="text-xs text-muted-foreground">{label}</label>
        <span className="font-mono text-xs font-medium">{display}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-primary"
      />
    </div>
  );
}

function TotalCard({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color?: string;
}) {
  return (
    <div className="rounded-lg border border-border/30 bg-card/50 p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={`mt-0.5 font-mono text-lg font-bold ${color || ""}`}>
        {value.toLocaleString(undefined, { maximumFractionDigits: 2 })}
        <span className="text-xs font-normal text-muted-foreground"> CC</span>
      </p>
    </div>
  );
}
