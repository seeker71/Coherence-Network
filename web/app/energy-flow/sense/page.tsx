"use client";

/**
 * /energy-flow/sense — Frequency harmony dashboard.
 *
 * The organism sees itself as frequencies. Every signal carries energy
 * at a frequency. Harmonies emerge when signals resonate together.
 * Dissonances reveal where attention and energy are needed.
 */

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { getApiBase } from "@/lib/api";

const API = getApiBase();

type Signal = {
  id: string;
  label: string;
  value: number;
  max: number;
  frequency_hz: number;
  vitality: string;
  detail: string;
};

type Harmony = {
  pair: string;
  resonance: number;
  average_energy: number;
  state: string;
};

type Dissonance = {
  pair: string;
  divergence: number;
  stronger: string;
  weaker: string;
  message: string;
};

type EnergyData = {
  sensed_at: string;
  internal: { scale: string; signals: Signal[] };
  community: { scale: string; signals: Signal[] };
  external: { scale: string; signals: Signal[] };
  harmonies: {
    overall_energy: number;
    overall_vitality: string;
    signal_count: number;
    harmonies: Harmony[];
    dissonances: Dissonance[];
    frequency_spectrum: { label: string; hz: number; energy: number; vitality: string }[];
  };
  sensing_cost_ms: number;
};

export default function EnergySensing() {
  const [data, setData] = useState<EnergyData | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/energy/sense`);
      if (res.ok) setData(await res.json());
    } catch {
      // Sensing is observational
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8">
        <div className="animate-pulse space-y-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-12 rounded-xl bg-muted/50" />
          ))}
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8 text-sm text-muted-foreground">
        Energy sensing is quiet. The signals are resting.
      </div>
    );
  }

  const { harmonies } = data;

  return (
    <div className="mx-auto max-w-4xl space-y-8 px-4 py-8 sm:px-6">
      {/* Header with overall energy */}
      <header className="text-center">
        <h1 className="text-2xl font-bold tracking-tight">Energy Sensing</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {harmonies.signal_count} signals sensed in {data.sensing_cost_ms.toFixed(0)}ms
        </p>
        <div className="mt-4 inline-flex flex-col items-center">
          <div className="relative h-24 w-24">
            <svg viewBox="0 0 100 100" className="h-24 w-24">
              <circle
                cx="50" cy="50" r="45"
                fill="none"
                stroke="currentColor"
                strokeWidth="4"
                className="text-muted/30"
              />
              <circle
                cx="50" cy="50" r="45"
                fill="none"
                stroke="currentColor"
                strokeWidth="4"
                strokeDasharray={`${harmonies.overall_energy * 283} 283`}
                strokeLinecap="round"
                transform="rotate(-90 50 50)"
                className={
                  harmonies.overall_vitality === "thriving" ? "text-green-500"
                    : harmonies.overall_vitality === "growing" ? "text-blue-500"
                      : harmonies.overall_vitality === "resting" ? "text-amber-500"
                        : "text-muted-foreground"
                }
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-lg font-bold">{(harmonies.overall_energy * 100).toFixed(0)}%</span>
              <span className="text-xs text-muted-foreground capitalize">{harmonies.overall_vitality}</span>
            </div>
          </div>
        </div>
      </header>

      {/* Frequency spectrum */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Frequency Spectrum
        </h2>
        <div className="space-y-1.5">
          {harmonies.frequency_spectrum.map((freq, i) => (
            <div key={i} className="flex items-center gap-3">
              <span className="w-8 text-right font-mono text-xs text-muted-foreground">
                {freq.hz}
              </span>
              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium">{freq.label}</span>
                  <span className={`text-xs capitalize ${vitalityColor(freq.vitality)}`}>
                    {freq.vitality}
                  </span>
                </div>
                <div className="mt-0.5 h-1.5 overflow-hidden rounded-full bg-muted/50">
                  <div
                    className={`h-full rounded-full transition-all duration-700 ${
                      freq.vitality === "thriving" || freq.vitality === "pulsing"
                        ? "bg-green-500/70"
                        : freq.vitality === "growing"
                          ? "bg-blue-500/70"
                          : freq.vitality === "resting"
                            ? "bg-amber-500/70"
                            : "bg-muted-foreground/30"
                    }`}
                    style={{ width: `${freq.energy * 100}%` }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Harmonies */}
      {harmonies.harmonies.length > 0 && (
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Harmonies
          </h2>
          <div className="space-y-2">
            {harmonies.harmonies.map((h, i) => (
              <div
                key={i}
                className="rounded-lg border border-green-500/20 bg-green-500/5 p-3"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">{h.pair}</span>
                  <span className="text-xs font-medium text-green-600 dark:text-green-400">
                    {(h.resonance * 100).toFixed(0)}% resonance
                  </span>
                </div>
                <p className="mt-0.5 text-xs text-muted-foreground capitalize">
                  {h.state} — energy {(h.average_energy * 100).toFixed(0)}%
                </p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Dissonances */}
      {harmonies.dissonances.length > 0 && (
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Dissonances
          </h2>
          <div className="space-y-2">
            {harmonies.dissonances.map((d, i) => (
              <div
                key={i}
                className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">{d.pair}</span>
                  <span className="text-xs font-medium text-amber-600 dark:text-amber-400">
                    {(d.divergence * 100).toFixed(0)}% divergence
                  </span>
                </div>
                <p className="mt-0.5 text-xs text-muted-foreground">{d.message}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Signal groups */}
      <SignalGroup title="Internal Body" signals={data.internal.signals} />
      <SignalGroup title="Community Body" signals={data.community.signals} />
      <SignalGroup title="The World" signals={data.external.signals} />

      {/* Navigation */}
      <footer className="flex items-center justify-between border-t border-border/30 pt-4">
        <Link
          href="/energy-flow"
          className="text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          ← Flow Dashboard
        </Link>
        <button
          onClick={load}
          className="rounded-lg bg-muted/60 px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          Sense again
        </button>
        <Link
          href="/energy-flow/simulate"
          className="text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          Simulate →
        </Link>
      </footer>
    </div>
  );
}

function SignalGroup({ title, signals }: { title: string; signals: Signal[] }) {
  if (signals.length === 0) return null;
  return (
    <section>
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </h2>
      <div className="grid gap-2 sm:grid-cols-2">
        {signals.map((s) => (
          <div
            key={s.id}
            className="rounded-lg border border-border/30 bg-card/30 p-3"
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">{s.label}</span>
              <div className="flex items-center gap-1.5">
                <span className="font-mono text-xs">{s.frequency_hz} Hz</span>
                <span className={`inline-block h-2 w-2 rounded-full ${
                  s.vitality === "thriving" || s.vitality === "pulsing" || s.vitality === "healthy"
                    ? "bg-green-500"
                    : s.vitality === "growing" || s.vitality === "sensing" || s.vitality === "connected"
                      ? "bg-blue-500"
                      : s.vitality === "resting" || s.vitality === "warning"
                        ? "bg-amber-500"
                        : "bg-muted-foreground/40"
                }`} />
              </div>
            </div>
            <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-muted/50">
              <div
                className="h-full rounded-full bg-primary/50 transition-all duration-500"
                style={{ width: `${(s.value / s.max) * 100}%` }}
              />
            </div>
            <p className="mt-1 text-xs text-muted-foreground">{s.detail}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function vitalityColor(vitality: string): string {
  switch (vitality) {
    case "thriving":
    case "pulsing":
    case "healthy":
      return "text-green-600 dark:text-green-400";
    case "growing":
    case "sensing":
    case "connected":
      return "text-blue-600 dark:text-blue-400";
    case "resting":
    case "warning":
      return "text-amber-600 dark:text-amber-400";
    default:
      return "text-muted-foreground";
  }
}
