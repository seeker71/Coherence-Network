"use client";

import { useState } from "react";

// ─── Type mirrors from page.tsx (passed as props) ────────────────────────────

export type UsageMetric = {
  id: string;
  label: string;
  unit: string;
  used: number;
  remaining?: number | null;
  limit?: number | null;
  window?: string | null;
};

export type ProviderSnapshot = {
  id: string;
  provider: string;
  kind: string;
  status: string;
  collected_at: string;
  metrics: UsageMetric[];
  cost_usd?: number | null;
  capacity_tasks_per_day?: number | null;
  actual_current_usage?: number | null;
  actual_current_usage_unit?: string | null;
  usage_per_time?: string | null;
  usage_remaining?: number | null;
  usage_remaining_unit?: string | null;
  official_records: string[];
  data_source: string;
  notes: string[];
};

export type ProviderReadinessRow = {
  provider: string;
  kind: string;
  status: string;
  required: boolean;
  configured: boolean;
  severity: string;
  missing_env: string[];
  notes: string[];
};

export type ProviderExecStatsEntry = {
  total_runs: number;
  successes: number;
  failures: number;
  success_rate: number;
  last_5_rate: number;
  avg_duration_s: number;
  selection_probability: number;
  blocked: boolean;
  needs_attention: boolean;
  error_breakdown: Record<string, number>;
};

export type UsageAlert = {
  id: string;
  provider: string;
  metric_id: string;
  severity: string;
  message: string;
  remaining_ratio?: number | null;
  created_at: string;
};

export type NetworkNodeInfo = {
  hostname: string;
  os_type: string;
  status: string;
  last_seen_at: string;
};

export type FederationNodeCapabilities = {
  executors?: string[];
  tools?: string[];
  hardware?: {
    cpu_count?: number;
    memory_total_gb?: number | null;
    gpu_available?: boolean;
    gpu_type?: string | null;
  };
  models_by_executor?: Record<string, string[]>;
  probed_at?: string;
};

export type FederationNode = {
  node_id: string;
  hostname: string;
  os_type: string;
  providers: string[];
  capabilities: FederationNodeCapabilities;
  registered_at: string;
  last_seen_at: string;
  status: string;
};

export type GardenMapProps = {
  providers: ProviderSnapshot[];
  readiness: { providers: ProviderReadinessRow[]; all_required_ready?: boolean; blocking_issues?: string[] };
  execStats: Record<string, ProviderExecStatsEntry> | null;
  alerts: UsageAlert[];
  federationNodes: FederationNode[];
  networkNodes: Record<string, NetworkNodeInfo>;
  totalMeasurements: number;
  unavailableProviders: string[];
  limitCoverage?: {
    coverage_ratio: number;
    providers_missing_limit_metrics: string[];
  } | null;
  generatedAt: string;
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

function healthColor(status: string, rate?: number): string {
  if (status === "blocked") return "red";
  if (rate !== undefined) {
    if (rate >= 0.85) return "emerald";
    if (rate >= 0.6) return "amber";
    return "red";
  }
  switch (status) {
    case "ok":
    case "active":
    case "ready":
    case "online":
      return "emerald";
    case "degraded":
      return "amber";
    default:
      return "red";
  }
}

function colorClass(color: string, variant: "bg" | "text" | "border" | "ring" | "shadow") {
  const map: Record<string, Record<string, string>> = {
    emerald: {
      bg: "bg-emerald-500/15",
      text: "text-emerald-400",
      border: "border-emerald-500/40",
      ring: "ring-emerald-500/30",
      shadow: "shadow-emerald-500/20",
    },
    amber: {
      bg: "bg-amber-500/15",
      text: "text-amber-400",
      border: "border-amber-500/40",
      ring: "ring-amber-500/30",
      shadow: "shadow-amber-500/20",
    },
    red: {
      bg: "bg-red-500/15",
      text: "text-red-400",
      border: "border-red-500/40",
      ring: "ring-red-500/30",
      shadow: "shadow-red-500/20",
    },
  };
  return map[color]?.[variant] ?? "";
}

function timeAgo(iso: string): string {
  try {
    const ms = Date.now() - new Date(iso).getTime();
    const s = Math.floor(ms / 1000);
    if (s < 60) return `${s}s ago`;
    const m = Math.floor(s / 60);
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h ago`;
    return `${Math.floor(h / 24)}d ago`;
  } catch {
    return "unknown";
  }
}

// ─── Radial gauge SVG ────────────────────────────────────────────────────────

function RadialGauge({
  value,
  label,
  color,
  size = 72,
}: {
  value: number; // 0–1
  label: string;
  color: string;
  size?: number;
}) {
  const stroke = 6;
  const r = (size - stroke * 2) / 2;
  const circ = 2 * Math.PI * r;
  const filled = Math.min(1, Math.max(0, value)) * circ;
  const strokeColor =
    color === "emerald" ? "#34d399" : color === "amber" ? "#fbbf24" : "#f87171";
  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="currentColor"
          strokeWidth={stroke}
          className="text-border/20"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={strokeColor}
          strokeWidth={stroke}
          strokeDasharray={`${filled} ${circ}`}
          strokeLinecap="round"
          style={{ filter: `drop-shadow(0 0 4px ${strokeColor}60)` }}
        />
        <text
          x={size / 2}
          y={size / 2}
          textAnchor="middle"
          dominantBaseline="central"
          fontSize={size * 0.22}
          fontWeight="600"
          fill={strokeColor}
          style={{ transform: "rotate(90deg)", transformOrigin: `${size / 2}px ${size / 2}px` }}
        >
          {Math.round(value * 100)}%
        </text>
      </svg>
      <span className="text-[10px] text-muted-foreground leading-none text-center">{label}</span>
    </div>
  );
}

// ─── Provider orb ────────────────────────────────────────────────────────────

function ProviderOrb({
  snapshot,
  readiness,
  execEntry,
  alerts,
}: {
  snapshot: ProviderSnapshot;
  readiness?: ProviderReadinessRow;
  execEntry?: ProviderExecStatsEntry;
  alerts: UsageAlert[];
}) {
  const [expanded, setExpanded] = useState(false);
  const rate = execEntry?.success_rate;
  const color = healthColor(snapshot.status, rate);
  const isBlocked = execEntry?.blocked ?? false;
  const providerAlerts = alerts.filter((a) => a.provider === snapshot.provider);

  // Find a usage/remaining metric to show a gauge
  const gaugeMetric = snapshot.metrics.find(
    (m) => m.remaining !== undefined && m.remaining !== null && m.limit
  );
  const gaugeValue = gaugeMetric
    ? Math.min(1, (gaugeMetric.remaining ?? 0) / (gaugeMetric.limit ?? 1))
    : null;

  return (
    <button
      onClick={() => setExpanded((v) => !v)}
      className={`
        relative group text-left w-full rounded-2xl border p-4 space-y-3
        transition-all duration-300
        ${colorClass(color, "border")} ${colorClass(color, "bg")}
        hover:shadow-lg ${colorClass(color, "shadow")}
        hover:scale-[1.02]
        ${isBlocked ? "opacity-60" : ""}
      `}
      aria-expanded={expanded}
    >
      {/* Pulse ring when healthy */}
      {color === "emerald" && (
        <span
          className="absolute -inset-px rounded-2xl border border-emerald-500/20 animate-pulse pointer-events-none"
          style={{ animationDuration: "3s" }}
        />
      )}

      {/* Header row */}
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className={`font-semibold text-sm ${colorClass(color, "text")}`}>
            {snapshot.provider}
          </p>
          <p className="text-[11px] text-muted-foreground">{snapshot.kind}</p>
        </div>
        <div className="flex flex-col items-end gap-1">
          {/* Vitality dot */}
          <span
            className={`inline-block w-2.5 h-2.5 rounded-full ${
              color === "emerald"
                ? "bg-emerald-400 shadow-[0_0_6px_#34d399]"
                : color === "amber"
                  ? "bg-amber-400 shadow-[0_0_6px_#fbbf24]"
                  : "bg-red-400 shadow-[0_0_6px_#f87171]"
            }`}
            style={color === "emerald" ? { animation: "pulse 2s ease-in-out infinite" } : undefined}
          />
          {providerAlerts.length > 0 && (
            <span className="text-[10px] text-amber-400">⚠ {providerAlerts.length}</span>
          )}
        </div>
      </div>

      {/* Gauges row */}
      <div className="flex items-center gap-3 flex-wrap">
        {execEntry && (
          <RadialGauge
            value={execEntry.success_rate}
            label="success"
            color={healthColor("", execEntry.success_rate)}
            size={60}
          />
        )}
        {gaugeValue !== null && (
          <RadialGauge
            value={gaugeValue}
            label="remaining"
            color={gaugeValue > 0.5 ? "emerald" : gaugeValue > 0.2 ? "amber" : "red"}
            size={60}
          />
        )}
        {execEntry && (
          <div className="flex flex-col gap-1 text-[11px]">
            <span className="text-muted-foreground">
              {execEntry.total_runs} runs
            </span>
            <span className="text-muted-foreground">
              {execEntry.avg_duration_s.toFixed(1)}s avg
            </span>
            {execEntry.selection_probability > 0 && (
              <span className="text-muted-foreground">
                {(execEntry.selection_probability * 100).toFixed(0)}% sel
              </span>
            )}
          </div>
        )}
      </div>

      {/* Expandable detail */}
      {expanded && (
        <div className="space-y-2 text-[11px] border-t border-border/20 pt-2">
          {snapshot.metrics.map((m) => (
            <div key={m.id} className="flex justify-between gap-2">
              <span className="text-muted-foreground">{m.label}</span>
              <span>
                {m.used}
                {m.limit ? ` / ${m.limit}` : ""}
                {m.remaining != null ? ` (${m.remaining} left)` : ""}
                {m.window ? ` · ${m.window}` : ""}
              </span>
            </div>
          ))}
          {snapshot.cost_usd != null && snapshot.cost_usd > 0 && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Cost</span>
              <span>${snapshot.cost_usd.toFixed(4)}</span>
            </div>
          )}
          {readiness?.missing_env && readiness.missing_env.length > 0 && (
            <div className="text-red-400">
              Missing env: {readiness.missing_env.join(", ")}
            </div>
          )}
          {providerAlerts.map((a) => (
            <div key={a.id} className="text-amber-400">⚠ {a.message}</div>
          ))}
          <p className="text-muted-foreground">
            Collected {timeAgo(snapshot.collected_at)} · {snapshot.data_source}
          </p>
        </div>
      )}
    </button>
  );
}

// ─── Federation node organism ─────────────────────────────────────────────────

function NodeOrganism({ node }: { node: FederationNode }) {
  const [expanded, setExpanded] = useState(false);
  const isOnline = node.status === "online" || node.status === "active";
  const color = isOnline ? "emerald" : "red";
  const cpus = node.capabilities?.hardware?.cpu_count ?? 0;
  const memGb = node.capabilities?.hardware?.memory_total_gb ?? 0;
  const executors = node.capabilities?.executors ?? [];
  const gpu = node.capabilities?.hardware?.gpu_available ?? false;

  return (
    <button
      onClick={() => setExpanded((v) => !v)}
      className={`
        relative group text-left rounded-2xl border p-4 space-y-2
        transition-all duration-300 hover:shadow-lg
        ${colorClass(color, "border")} ${colorClass(color, "bg")} ${colorClass(color, "shadow")}
        hover:scale-[1.01]
      `}
    >
      {isOnline && (
        <span
          className="absolute -inset-px rounded-2xl border border-emerald-500/20 animate-pulse pointer-events-none"
          style={{ animationDuration: "4s" }}
        />
      )}

      <div className="flex items-center justify-between gap-2">
        <div>
          <p className={`font-semibold text-sm ${colorClass(color, "text")}`}>
            {node.hostname.split(".")[0]}
          </p>
          <p className="text-[10px] text-muted-foreground">{node.os_type}</p>
        </div>
        <span
          className={`w-3 h-3 rounded-full ${
            isOnline
              ? "bg-emerald-400 shadow-[0_0_8px_#34d399]"
              : "bg-gray-500"
          }`}
        />
      </div>

      {/* CPU cores as a dot grid */}
      {cpus > 0 && (
        <div className="flex flex-wrap gap-0.5">
          {Array.from({ length: Math.min(cpus, 16) }).map((_, i) => (
            <span
              key={i}
              className={`inline-block w-1.5 h-1.5 rounded-full ${isOnline ? "bg-emerald-500/60" : "bg-gray-600"}`}
            />
          ))}
          {cpus > 16 && (
            <span className="text-[9px] text-muted-foreground">+{cpus - 16}</span>
          )}
        </div>
      )}

      {/* Memory bar */}
      {memGb > 0 && (
        <div className="space-y-0.5">
          <p className="text-[10px] text-muted-foreground">{memGb.toFixed(1)} GB RAM</p>
        </div>
      )}

      {gpu && (
        <span className="inline-block text-[10px] px-1.5 py-0.5 rounded-full bg-purple-500/20 text-purple-400">
          GPU
        </span>
      )}

      {expanded && (
        <div className="border-t border-border/20 pt-2 space-y-1 text-[11px]">
          <p className="text-muted-foreground">ID: {node.node_id}</p>
          <p className="text-muted-foreground">Last seen: {timeAgo(node.last_seen_at)}</p>
          {executors.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {executors.map((e) => (
                <span key={e} className="px-1.5 py-0.5 rounded bg-muted text-muted-foreground text-[10px]">
                  {e}
                </span>
              ))}
            </div>
          )}
          {node.providers.length > 0 && (
            <p className="text-muted-foreground">Providers: {node.providers.join(", ")}</p>
          )}
        </div>
      )}
    </button>
  );
}

// ─── Activity stream item ─────────────────────────────────────────────────────

function StreamItem({ alert }: { alert: UsageAlert }) {
  const color =
    alert.severity === "critical"
      ? "red"
      : alert.severity === "warning"
        ? "amber"
        : "emerald";
  return (
    <div
      className={`flex items-start gap-3 py-2.5 px-3 rounded-xl border text-sm
        ${colorClass(color, "border")} ${colorClass(color, "bg")}`}
    >
      <span
        className={`mt-0.5 shrink-0 w-2 h-2 rounded-full ${
          color === "emerald" ? "bg-emerald-400" : color === "amber" ? "bg-amber-400" : "bg-red-400"
        }`}
      />
      <div className="min-w-0 flex-1">
        <p className="font-medium text-[13px]">{alert.provider}</p>
        <p className="text-muted-foreground text-xs leading-relaxed">{alert.message}</p>
      </div>
      <span className="shrink-0 text-[10px] text-muted-foreground whitespace-nowrap">
        {timeAgo(alert.created_at)}
      </span>
    </div>
  );
}

// ─── Main GardenMap component ─────────────────────────────────────────────────

export function GardenMap({
  providers,
  readiness,
  execStats,
  alerts,
  federationNodes,
  networkNodes,
  totalMeasurements,
  unavailableProviders,
  limitCoverage,
  generatedAt,
}: GardenMapProps) {
  const readinessByProvider = Object.fromEntries(
    (readiness.providers ?? []).map((r) => [r.provider, r])
  );

  // Ecosystem vitality score: average of available provider health
  const healthyCount = providers.filter((p) =>
    ["ok", "active", "ready"].includes(p.status)
  ).length;
  const vitalityRatio = providers.length > 0 ? healthyCount / providers.length : 0;
  const ecosystemColor = healthColor("", vitalityRatio);

  const onlineNodes = Object.values(networkNodes).filter((n) => n.status === "online").length;
  const totalNodes = Object.keys(networkNodes).length;

  // Sort providers: healthy first, then degraded, then unavailable
  const sortedProviders = [...providers].sort((a, b) => {
    const order = (s: string) =>
      ["ok", "active", "ready"].includes(s) ? 0 : s === "degraded" ? 1 : 2;
    return order(a.status) - order(b.status);
  });

  return (
    <div className="space-y-8">
      {/* ── Ecosystem header ──────────────────────────────────────────────── */}
      <div
        className={`
          relative overflow-hidden rounded-3xl border p-6
          ${colorClass(ecosystemColor, "border")} ${colorClass(ecosystemColor, "bg")}
        `}
      >
        {/* Background organic pattern */}
        <div
          className="absolute inset-0 opacity-5 pointer-events-none"
          style={{
            backgroundImage:
              "radial-gradient(circle at 20% 50%, currentColor 1px, transparent 1px), radial-gradient(circle at 80% 20%, currentColor 1px, transparent 1px)",
            backgroundSize: "40px 40px",
          }}
        />

        <div className="relative flex flex-col sm:flex-row items-start sm:items-center gap-6">
          {/* Vitality gauge */}
          <RadialGauge value={vitalityRatio} label="ecosystem vitality" color={ecosystemColor} size={96} />

          <div className="flex-1 space-y-2">
            <h2 className={`text-xl font-bold ${colorClass(ecosystemColor, "text")}`}>
              {vitalityRatio >= 0.85
                ? "Ecosystem is thriving"
                : vitalityRatio >= 0.6
                  ? "Ecosystem is adapting"
                  : "Ecosystem needs attention"}
            </h2>
            <p className="text-muted-foreground text-sm">
              {healthyCount} of {providers.length} providers healthy
              {federationNodes.length > 0 && ` · ${federationNodes.filter(n => n.status === "online" || n.status === "active").length} of ${federationNodes.length} nodes alive`}
              {alerts.length > 0 && ` · ${alerts.length} active alert${alerts.length !== 1 ? "s" : ""}`}
            </p>
            {unavailableProviders.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {unavailableProviders.map((p) => (
                  <span key={p} className="text-[10px] px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                    {p} dormant
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Mini metric pills */}
          <div className="flex flex-wrap gap-2 text-xs sm:flex-col sm:items-end">
            {totalMeasurements > 0 && (
              <span className="px-2.5 py-1 rounded-full bg-background/60 text-muted-foreground">
                {totalMeasurements.toLocaleString()} measurements
              </span>
            )}
            {limitCoverage && (
              <span className="px-2.5 py-1 rounded-full bg-background/60 text-muted-foreground">
                {Math.round(limitCoverage.coverage_ratio * 100)}% limit coverage
              </span>
            )}
            <span className="px-2.5 py-1 rounded-full bg-background/60 text-muted-foreground">
              updated {timeAgo(generatedAt)}
            </span>
          </div>
        </div>
      </div>

      {/* ── Provider grove ────────────────────────────────────────────────── */}
      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-muted-foreground uppercase tracking-wider text-xs">
          Provider Grove
          <span className="ml-2 text-foreground/60 font-normal normal-case tracking-normal text-sm">
            — tap any provider to inspect
          </span>
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {sortedProviders.map((p) => (
            <ProviderOrb
              key={p.id}
              snapshot={p}
              readiness={readinessByProvider[p.provider]}
              execEntry={execStats?.[p.provider]}
              alerts={alerts}
            />
          ))}
          {unavailableProviders.map((name) => (
            <div
              key={`unavail-${name}`}
              className="rounded-2xl border border-border/20 bg-background/20 p-4 opacity-40 flex items-center gap-3"
            >
              <span className="w-2.5 h-2.5 rounded-full bg-gray-600" />
              <div>
                <p className="font-medium text-sm">{name}</p>
                <p className="text-[10px] text-muted-foreground">dormant · no recent data</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Federation node garden ─────────────────────────────────────────── */}
      {federationNodes.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-muted-foreground uppercase tracking-wider text-xs">
            Node Garden
            <span className="ml-2 text-foreground/60 font-normal normal-case tracking-normal text-sm">
              — {federationNodes.filter(n => n.status === "online" || n.status === "active").length} of {federationNodes.length} alive
            </span>
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {federationNodes
              .sort((a, b) => {
                const aOnline = a.status === "online" || a.status === "active";
                const bOnline = b.status === "online" || b.status === "active";
                return (bOnline ? 1 : 0) - (aOnline ? 1 : 0);
              })
              .map((n) => (
                <NodeOrganism key={n.node_id} node={n} />
              ))}
          </div>
        </section>
      )}

      {/* ── Network node status row (when no FederationNode detail available) */}
      {federationNodes.length === 0 && Object.keys(networkNodes).length > 0 && (
        <section className="space-y-3">
          <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Network Nodes
          </h2>
          <div className="flex flex-wrap gap-2">
            {Object.entries(networkNodes).map(([id, node]) => {
              const c = node.status === "online" ? "emerald" : "red";
              return (
                <div
                  key={id}
                  className={`flex items-center gap-2 px-3 py-2 rounded-xl border text-sm
                    ${colorClass(c, "border")} ${colorClass(c, "bg")}`}
                >
                  <span
                    className={`w-2 h-2 rounded-full ${c === "emerald" ? "bg-emerald-400" : "bg-red-400"}`}
                  />
                  <span className="font-medium">{node.hostname.split(".")[0]}</span>
                  <span className="text-[10px] text-muted-foreground">{timeAgo(node.last_seen_at)}</span>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* ── Alert stream ──────────────────────────────────────────────────── */}
      {alerts.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Activity Stream
          </h2>
          <div className="space-y-1.5">
            {alerts.map((a) => (
              <StreamItem key={a.id} alert={a} />
            ))}
          </div>
        </section>
      )}

      {/* ── Blocking issues ───────────────────────────────────────────────── */}
      {(readiness.blocking_issues?.length ?? 0) > 0 && (
        <section className="rounded-2xl border border-red-500/30 bg-red-500/5 p-4 space-y-2">
          <h2 className="text-sm font-semibold text-red-400 uppercase tracking-wider">
            Blocking Issues
          </h2>
          <ul className="space-y-1">
            {readiness.blocking_issues!.map((issue) => (
              <li key={issue} className="text-sm text-red-400 flex items-start gap-2">
                <span className="mt-1.5 shrink-0 w-1.5 h-1.5 rounded-full bg-red-400" />
                {issue}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* ── Floor hint ────────────────────────────────────────────────────── */}
      <p className="text-center text-[11px] text-muted-foreground/50 pb-2">
        Each plant is a living entity. Tap to inspect. Data refreshes on each page load.
      </p>
    </div>
  );
}
