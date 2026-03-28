"use client";

import { useMemo } from "react";
import clsx from "clsx";

import type {
  AutomationGardenPayload,
  ProviderSnapshot,
  ProviderExecStatsEntry,
} from "./types";

function formatTime(iso: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

function healthHue(rate: number, blocked?: boolean): string {
  if (blocked) return "from-red-500/90 to-red-600/70";
  if (rate >= 0.85) return "from-emerald-400/90 to-teal-600/80";
  if (rate >= 0.5) return "from-amber-400/85 to-orange-600/75";
  return "from-rose-500/85 to-red-700/70";
}

function statusPulse(status: string): string {
  const s = status.toLowerCase();
  if (s === "online" || s === "ok" || s === "ready" || s === "active") {
    return "bg-emerald-400 shadow-[0_0_12px_hsl(158_64%_52%/0.65)]";
  }
  if (s === "degraded" || s === "warning") {
    return "bg-amber-400 shadow-[0_0_10px_hsl(38_92%_50%/0.5)]";
  }
  return "bg-slate-400 shadow-[0_0_8px_hsl(220_14%_46%/0.4)]";
}

function metricRemainingRatio(m: ProviderSnapshot): number | null {
  for (const x of m.metrics) {
    if (x.limit != null && x.limit > 0 && x.remaining != null) {
      return Math.max(0, Math.min(1, x.remaining / x.limit));
    }
  }
  return null;
}

function readinessScore(
  providerName: string,
  readiness: AutomationGardenPayload["readiness"],
  validation: AutomationGardenPayload["validation"],
): number {
  const r = readiness.providers.find((p) => p.provider === providerName);
  const v = validation.providers.find((p) => p.provider === providerName);
  let score = 0.5;
  if (r) {
    if (r.status === "ready") score = 0.95;
    else if (r.status === "degraded") score = 0.65;
    else score = 0.35;
    if (!r.configured) score *= 0.6;
  }
  if (v) {
    if (v.validated_execution) score = Math.max(score, 0.9);
    if (v.readiness_status === "ready") score = Math.max(score, 0.85);
  }
  return Math.max(0, Math.min(1, score));
}

type StreamLine = { key: string; text: string; tone: "calm" | "warm" | "alert" };

function buildActivityStream(data: AutomationGardenPayload): StreamLine[] {
  const lines: StreamLine[] = [];
  const { usage, alerts, execStats, networkStats, federationNodes, readiness, validation } = data;

  lines.push({
    key: "pulse-usage",
    text: `Ecosystem sampled at ${formatTime(usage.generated_at)} — ${usage.tracked_providers} providers in view`,
    tone: "calm",
  });

  if (readiness.generated_at) {
    lines.push({
      key: "pulse-ready",
      text: `Readiness ${readiness.all_required_ready ? "blooms" : "needs tending"} — checked ${formatTime(readiness.generated_at)}`,
      tone: readiness.all_required_ready ? "calm" : "warm",
    });
  }

  if (validation.generated_at) {
    lines.push({
      key: "pulse-val",
      text: `Validation path ${validation.all_required_validated ? "clear" : "blocked"} — ${formatTime(validation.generated_at)}`,
      tone: validation.all_required_validated ? "calm" : "warm",
    });
  }

  for (const a of alerts.alerts.slice(0, 4)) {
    lines.push({
      key: `al-${a.id}`,
      text: `${a.provider}: ${a.message}`,
      tone: a.severity === "critical" ? "alert" : "warm",
    });
  }

  if (execStats) {
    const top = Object.entries(execStats.providers)
      .sort(([, x], [, y]) => y.total_runs - x.total_runs)
      .slice(0, 4);
    for (const [name, e] of top) {
      lines.push({
        key: `ex-${name}`,
        text: `${name} — ${(e.success_rate * 100).toFixed(0)}% success over ${e.total_runs} runs`,
        tone: e.blocked ? "alert" : e.needs_attention ? "warm" : "calm",
      });
    }
  }

  if (networkStats && Object.keys(networkStats.nodes).length > 0) {
    for (const [id, n] of Object.entries(networkStats.nodes).slice(0, 5)) {
      lines.push({
        key: `nd-${id}`,
        text: `${n.hostname} · ${n.status} · last ripple ${formatTime(n.last_seen_at)}`,
        tone: n.status === "online" ? "calm" : "warm",
      });
    }
  }

  for (const node of federationNodes.slice(0, 4)) {
    lines.push({
      key: `fn-${node.node_id}`,
      text: `${node.hostname} carries ${node.providers?.length ?? 0} provider links — ${node.status}`,
      tone: "calm",
    });
  }

  if (lines.length < 3) {
    lines.push({
      key: "filler",
      text: "The garden waits for more telemetry — run automation tasks to stir the stream.",
      tone: "calm",
    });
  }

  return lines;
}

function Gauge({
  label,
  value01,
  className,
  blocked,
}: {
  label: string;
  value01: number;
  className?: string;
  blocked?: boolean;
}) {
  const pct = Math.round(Math.max(0, Math.min(100, value01 * 100)));
  return (
    <div className={clsx("space-y-1", className)}>
      <div className="flex justify-between text-[10px] uppercase tracking-wide text-muted-foreground">
        <span>{label}</span>
        <span>{pct}%</span>
      </div>
      <div
        className="h-2.5 w-full rounded-full bg-muted/60 overflow-hidden border border-border/40"
        role="meter"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
      >
        <div
          className={clsx(
            "h-full rounded-full bg-gradient-to-r transition-all duration-700 ease-out",
            healthHue(value01, blocked),
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function AutomationGardenExperience({ data }: { data: AutomationGardenPayload }) {
  const providers = useMemo(
    () => [...data.usage.providers].sort((a, b) => a.provider.localeCompare(b.provider)),
    [data.usage.providers],
  );

  const stream = useMemo(() => buildActivityStream(data), [data]);

  const streamDup = useMemo(() => [...stream, ...stream], [stream]);

  const ecosystemOk = data.readiness.all_required_ready && data.validation.all_required_validated;
  const freshnessMs = useMemo(() => {
    const times = [
      data.usage.generated_at,
      data.readiness.generated_at,
      data.validation.generated_at,
      data.alerts.generated_at,
    ].filter(Boolean);
    const parsed = times.map((t) => new Date(t).getTime()).filter((n) => !Number.isNaN(n));
    if (!parsed.length) return null;
    return Math.min(...parsed);
  }, [data]);

  const nodeOrbs = useMemo(() => {
    const out: { key: string; label: string; sub: string; status: string }[] = [];
    if (data.networkStats) {
      for (const [id, n] of Object.entries(data.networkStats.nodes)) {
        out.push({
          key: `net-${id}`,
          label: n.hostname.split(".")[0] || n.hostname,
          sub: `${n.os_type}`,
          status: n.status,
        });
      }
    }
    for (const n of data.federationNodes) {
      if (out.some((o) => o.label === n.hostname.split(".")[0])) continue;
      out.push({
        key: `fed-${n.node_id}`,
        label: n.hostname.split(".")[0] || n.hostname,
        sub: "federation",
        status: n.status,
      });
    }
    if (out.length === 0) {
      out.push({
        key: "control",
        label: "Control plane",
        sub: "orchestration",
        status: "ready",
      });
    }
    return out.slice(0, 12);
  }, [data.networkStats, data.federationNodes]);

  return (
    <section
      className="rounded-3xl border border-emerald-500/15 bg-gradient-to-b from-emerald-950/20 via-card/40 to-card/20 p-6 md:p-8 shadow-[inset_0_1px_0_0_hsl(158_40%_40%/0.12)]"
      aria-labelledby="automation-garden-heading"
    >
      <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between mb-6">
        <div>
          <h2 id="automation-garden-heading" className="text-xl md:text-2xl font-semibold tracking-tight">
            Living ecosystem map
          </h2>
          <p className="text-sm text-muted-foreground max-w-xl mt-1">
            Nodes pulse with status, providers grow as gauges, and the stream below carries recent signals — not raw
            server logs.
          </p>
        </div>
        <div
          className={clsx(
            "rounded-2xl border px-4 py-2 text-xs md:text-sm shrink-0",
            ecosystemOk
              ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-200"
              : "border-amber-500/35 bg-amber-500/5 text-amber-100",
          )}
        >
          <p className="font-medium">{ecosystemOk ? "Garden in balance" : "Garden needs attention"}</p>
          <p className="text-muted-foreground mt-0.5">
            Freshness: {freshnessMs ? formatTime(new Date(freshnessMs).toISOString()) : "—"} · Alerts:{" "}
            {data.alerts.alerts.length}
          </p>
        </div>
      </div>

      {/* Meadow canvas */}
      <div className="relative rounded-2xl border border-border/25 bg-[radial-gradient(ellipse_at_50%_0%,hsl(158_32%_28%/0.25),transparent_55%),radial-gradient(ellipse_at_80%_100%,hsl(36_40%_35%/0.12),transparent_50%),linear-gradient(180deg,hsl(var(--card)/0.5),transparent)] p-4 md:p-6 mb-8 overflow-hidden">
        <div className="pointer-events-none absolute inset-0 opacity-[0.07] bg-[url('data:image/svg+xml,%3Csvg width=\'60\' height=\'60\' viewBox=\'0 0 60 60\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cpath d=\'M30 5 L35 25 L55 30 L35 35 L30 55 L25 35 L5 30 L25 25 Z\' fill=\'none\' stroke=\'%23fff\' stroke-width=\'0.5\'/%3E%3C/svg%3E')]" />

        {/* Nodes row */}
        <p className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground mb-3">Network organisms</p>
        <div className="flex flex-wrap items-end gap-4 md:gap-6 relative">
          <div className="hidden md:block absolute top-1/2 left-0 right-0 h-px bg-gradient-to-r from-transparent via-emerald-500/25 to-transparent pointer-events-none" />
          {nodeOrbs.map((n) => (
            <div key={n.key} className="relative flex flex-col items-center gap-2 z-[1]">
              <div
                className={clsx(
                  "relative w-14 h-14 md:w-16 md:h-16 rounded-full border-2 border-emerald-400/30 bg-gradient-to-br from-emerald-900/40 to-card/80 flex items-center justify-center",
                  "ring-2 ring-offset-2 ring-offset-transparent",
                  n.status === "online" || n.status === "ready" || n.status === "ok"
                    ? "ring-emerald-500/40 animate-[garden-breathe_4s_ease-in-out_infinite]"
                    : "ring-amber-500/25",
                )}
              >
                <span className={clsx("absolute top-2 right-2 w-2 h-2 rounded-full", statusPulse(n.status))} />
                <span className="text-lg font-semibold text-emerald-100/90">{n.label.slice(0, 2).toUpperCase()}</span>
              </div>
              <div className="text-center max-w-[100px]">
                <p className="text-xs font-medium leading-tight truncate">{n.label}</p>
                <p className="text-[10px] text-muted-foreground truncate">{n.sub}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Provider beds */}
        <p className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground mt-8 mb-3">Provider beds</p>
        <div className="grid gap-3 md:grid-cols-2">
          {providers.length === 0 && (
            <p className="text-sm text-muted-foreground col-span-full rounded-2xl border border-dashed border-border/40 p-6 text-center">
              No provider snapshots yet — when telemetry arrives, each adapter appears here as a bed with living gauges.
            </p>
          )}
          {providers.map((p) => {
            const exec: ProviderExecStatsEntry | undefined = data.execStats?.providers[p.provider];
            const rem = metricRemainingRatio(p);
            const health = exec
              ? exec.success_rate
              : readinessScore(p.provider, data.readiness, data.validation);
            const blocked = exec?.blocked ?? false;

            return (
              <div
                key={p.id}
                className="rounded-2xl border border-border/30 bg-background/35 backdrop-blur-[2px] p-4 space-y-3 hover:border-emerald-500/20 transition-colors"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-medium text-sm">{p.provider}</p>
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider">{p.kind}</p>
                  </div>
                  <span
                    className={clsx(
                      "text-[10px] px-2 py-0.5 rounded-full border",
                      p.status === "ready" || p.status === "ok" || p.status === "active"
                        ? "border-emerald-500/40 text-emerald-300"
                        : p.status === "degraded"
                          ? "border-amber-500/40 text-amber-200"
                          : "border-border text-muted-foreground",
                    )}
                  >
                    {p.status}
                  </span>
                </div>
                <Gauge label={exec ? "Execution success" : "Adapter health"} value01={health} blocked={blocked} />
                {rem != null && <Gauge label="Capacity remaining" value01={rem} />}
                {exec && (
                  <p className="text-[10px] text-muted-foreground">
                    Last five: {(exec.last_5_rate * 100).toFixed(0)}% · Avg {exec.avg_duration_s.toFixed(1)}s · Runs{" "}
                    {exec.total_runs}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Ecosystem meters */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div className="rounded-2xl border border-border/25 bg-background/30 p-3">
          <p className="text-[10px] uppercase text-muted-foreground">Providers</p>
          <p className="text-2xl font-semibold">{data.usage.tracked_providers}</p>
        </div>
        <div className="rounded-2xl border border-border/25 bg-background/30 p-3">
          <p className="text-[10px] uppercase text-muted-foreground">Unavailable</p>
          <p className="text-2xl font-semibold">{data.usage.unavailable_providers?.length ?? 0}</p>
        </div>
        <div className="rounded-2xl border border-border/25 bg-background/30 p-3">
          <p className="text-[10px] uppercase text-muted-foreground">Limit coverage</p>
          <p className="text-2xl font-semibold">
            {data.usage.limit_coverage
              ? `${Math.round((data.usage.limit_coverage.coverage_ratio ?? 0) * 100)}%`
              : "—"}
          </p>
        </div>
        <div className="rounded-2xl border border-border/25 bg-background/30 p-3">
          <p className="text-[10px] uppercase text-muted-foreground">Exec healthy</p>
          <p className="text-2xl font-semibold">
            {data.execStats
              ? `${data.execStats.summary.healthy_providers}/${data.execStats.summary.total_providers}`
              : "—"}
          </p>
        </div>
      </div>

      {/* Flowing stream */}
      <div>
        <p className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground mb-2">Activity stream</p>
        <div
          className="relative rounded-2xl border border-cyan-500/10 bg-gradient-to-r from-cyan-950/20 via-background/40 to-teal-950/15 overflow-hidden py-3"
          role="region"
          aria-label="Recent automation activity"
        >
          <div className="garden-stream flex gap-10 whitespace-nowrap px-4 text-sm">
            {streamDup.map((line, i) => (
              <span
                key={`${line.key}-${i}`}
                className={clsx(
                  "inline-flex items-center gap-2 after:content-['·'] after:text-muted-foreground/50 after:pl-6 last:after:content-none",
                  line.tone === "alert" && "text-rose-300",
                  line.tone === "warm" && "text-amber-200/90",
                  line.tone === "calm" && "text-muted-foreground",
                )}
              >
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-cyan-400/80 shrink-0" />
                {line.text}
              </span>
            ))}
          </div>
        </div>
      </div>

      <p className="mt-4 text-xs text-muted-foreground">
        Proof: this view reads the same APIs as before —{" "}
        <code className="text-[10px] rounded bg-muted/50 px-1 py-0.5">GET /api/automation/usage</code>,{" "}
        <code className="text-[10px] rounded bg-muted/50 px-1 py-0.5">/readiness</code>,{" "}
        <code className="text-[10px] rounded bg-muted/50 px-1 py-0.5">/provider-validation</code>,{" "}
        <code className="text-[10px] rounded bg-muted/50 px-1 py-0.5">/api/providers/stats</code>, federation endpoints.
        Open the detailed panel below for full tables.
      </p>
    </section>
  );
}
