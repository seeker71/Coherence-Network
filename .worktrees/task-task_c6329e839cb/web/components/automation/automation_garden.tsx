"use client";

import { useMemo } from "react";

import type { AutomationPagePayload, ProviderSnapshot } from "@/lib/automation-page-data";
import { buildActivityBrookItems } from "@/lib/automation-page-data";

type Props = {
  payload: AutomationPagePayload;
  /** Public API base for proof links (e.g. https://api.example.com) */
  apiBase: string;
};

function clampPct(n: number): number {
  if (!Number.isFinite(n)) return 0;
  return Math.min(100, Math.max(0, n));
}

function readinessPct(status: string): number {
  const s = status.toLowerCase();
  if (s === "ready" || s === "ok" || s === "active") return 88;
  if (s === "degraded") return 52;
  return 28;
}

function plotGaugePercent(
  provider: ProviderSnapshot,
  execName: string | undefined,
  payload: AutomationPagePayload,
): { pct: number; label: string } {
  const ex = execName ? payload.execStats?.providers[execName] : undefined;
  if (ex) {
    return { pct: clampPct(ex.success_rate * 100), label: `Success ${(ex.success_rate * 100).toFixed(0)}%` };
  }
  const readyRow = payload.readiness.providers.find((p) => p.provider === provider.provider);
  if (readyRow) {
    return { pct: readinessPct(readyRow.status), label: `Readiness ${readyRow.status}` };
  }
  const valRow = payload.validation.providers.find((p) => p.provider === provider.provider);
  if (valRow) {
    return {
      pct: valRow.validated_execution ? 92 : valRow.configured ? 55 : 22,
      label: valRow.validated_execution ? "Validated" : valRow.configured ? "Configured" : "Not configured",
    };
  }
  const m = provider.metrics[0];
  if (m?.limit && m.limit > 0) {
    return { pct: clampPct((m.used / m.limit) * 100), label: `${m.label} load` };
  }
  return { pct: readinessPct(provider.status), label: `Status ${provider.status}` };
}

function plotMood(pct: number): { ring: string; glyph: string } {
  if (pct >= 78) return { ring: "from-emerald-400/80 to-teal-500/90", glyph: "🌿" };
  if (pct >= 45) return { ring: "from-amber-400/70 to-orange-500/80", glyph: "🌱" };
  return { ring: "from-rose-500/70 to-red-600/80", glyph: "🥀" };
}

export function AutomationGarden({ payload, apiBase }: Props) {
  const { usage, alerts, readiness, validation, execStats, networkStats, federationNodes } = payload;
  const providers = useMemo(() => [...usage.providers].sort((a, b) => a.provider.localeCompare(b.provider)), [usage.providers]);
  const brook = useMemo(() => buildActivityBrookItems(payload), [payload]);

  const canopyOk = readiness.all_required_ready && validation.all_required_validated;
  const fleetCount = federationNodes.length || (networkStats ? Object.keys(networkStats.nodes).length : 0);

  return (
    <section
      data-testid="automation-garden"
      className="relative overflow-hidden rounded-[2rem] border border-emerald-500/15 bg-gradient-to-br from-emerald-950/40 via-card/80 to-amber-950/20 p-6 sm:p-8 shadow-[0_0_60px_-12px_rgba(16,185,129,0.25)]"
    >
      <div className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full bg-emerald-500/10 blur-3xl" />
      <div className="pointer-events-none absolute -left-16 bottom-0 h-48 w-48 rounded-full bg-amber-500/10 blur-3xl" />

      <header className="relative z-10 mb-8 space-y-2">
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-emerald-400/90">Living capacity</p>
        <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">Automation Garden</h2>
        <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
          Providers grow as cultivated plots; nodes wander the meadow; signals run like a brook. This is the same telemetry as before — arranged for intuition, not noise.
        </p>
      </header>

      {/* Proof strip */}
      <div
        data-testid="garden-proof-strip"
        className="relative z-10 mb-8 flex flex-col gap-3 rounded-2xl border border-white/5 bg-black/20 px-4 py-3 text-xs sm:flex-row sm:items-center sm:justify-between"
      >
        <div className="space-y-1">
          <p className="font-medium text-emerald-200/90">Proof of freshness</p>
          <p className="text-muted-foreground">
            Usage snapshot: <time dateTime={usage.generated_at}>{new Date(usage.generated_at).toLocaleString()}</time>
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <a
            href={`${apiBase.replace(/\/$/, "")}/api/automation/usage`}
            target="_blank"
            rel="noreferrer"
            className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-emerald-200 hover:bg-emerald-500/20"
          >
            View usage JSON
          </a>
          <span className={`rounded-full px-3 py-1 ${canopyOk ? "bg-emerald-500/15 text-emerald-300" : "bg-amber-500/15 text-amber-200"}`}>
            {canopyOk ? "Canopy balanced" : "Canopy needs care"}
          </span>
        </div>
      </div>

      {/* Canopy stats */}
      <div data-testid="garden-canopy" className="relative z-10 mb-10 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          { k: "Plots", v: String(usage.tracked_providers), sub: "tracked providers" },
          { k: "Fallow", v: String(usage.unavailable_providers?.length ?? 0), sub: "unavailable" },
          { k: "Ripples", v: String(alerts.alerts.length), sub: "capacity alerts" },
          {
            k: "Fleet",
            v: String(fleetCount),
            sub: "nodes in view",
          },
        ].map((cell) => (
          <div
            key={cell.k}
            className="rounded-2xl border border-white/10 bg-gradient-to-b from-white/5 to-transparent p-4 shadow-inner"
          >
            <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{cell.k}</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums">{cell.v}</p>
            <p className="text-[11px] text-muted-foreground/80">{cell.sub}</p>
          </div>
        ))}
      </div>

      <div className="relative z-10 grid gap-10 lg:grid-cols-12">
        {/* Provider plots */}
        <div className="lg:col-span-7">
          <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold">
            <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-emerald-500/20 text-lg">🪴</span>
            Provider plots
          </h3>
          {providers.length === 0 ? (
            <p className="rounded-2xl border border-dashed border-white/20 p-6 text-sm text-muted-foreground" data-testid="garden-empty-plots">
              No provider shoots yet — seed the automation adapters and refresh.
            </p>
          ) : (
            <ul className="space-y-4">
              {providers.map((provider) => {
                const execName =
                  execStats?.providers ? Object.keys(execStats.providers).find((k) => k.toLowerCase() === provider.provider.toLowerCase()) : undefined;
                const { pct, label } = plotGaugePercent(provider, execName ?? undefined, payload);
                const mood = plotMood(pct);
                return (
                  <li
                    key={provider.id}
                    data-testid="garden-provider-plot"
                    className="group rounded-2xl border border-white/10 bg-black/25 p-4 transition hover:border-emerald-500/30"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="flex items-center gap-2 font-medium">
                          <span className="text-xl" aria-hidden>
                            {mood.glyph}
                          </span>
                          {provider.provider}
                        </p>
                        <p className="text-xs text-muted-foreground">{provider.kind}</p>
                      </div>
                      <span
                        className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                          provider.status === "ok" || provider.status === "active" || provider.status === "ready"
                            ? "bg-emerald-500/15 text-emerald-300"
                            : provider.status === "degraded"
                              ? "bg-amber-500/15 text-amber-200"
                              : "bg-red-500/15 text-red-300"
                        }`}
                      >
                        {provider.status}
                      </span>
                    </div>
                    <div className="mt-4 space-y-1.5">
                      <div className="flex justify-between text-[11px] text-muted-foreground">
                        <span>Vitality</span>
                        <span>{label}</span>
                      </div>
                      <div
                        className="relative h-3 overflow-hidden rounded-full bg-muted/40"
                        role="meter"
                        aria-valuenow={Math.round(pct)}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-label={`${provider.provider} vitality`}
                      >
                        <div
                          className={`h-full rounded-full bg-gradient-to-r ${mood.ring} transition-all duration-700 ease-out`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* Activity brook + node meadow */}
        <div className="space-y-8 lg:col-span-5">
          <div>
            <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold">
              <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-sky-500/20 text-lg">💧</span>
              Activity brook
            </h3>
            <div
              data-testid="garden-activity-brook"
              className="garden-brook-scroll max-h-[min(420px,55vh)] space-y-0 overflow-y-auto rounded-2xl border border-sky-500/20 bg-gradient-to-b from-sky-950/30 to-transparent p-4"
            >
              <div className="relative space-y-3 pl-4">
                <div className="absolute bottom-0 left-[7px] top-0 w-px bg-gradient-to-b from-sky-400/50 via-emerald-400/40 to-transparent" />
                {brook.map((item, i) => (
                  <div
                    key={item.id}
                    className="relative opacity-95"
                    style={{ animationDelay: `${Math.min(i * 40, 400)}ms` }}
                  >
                    <span
                      className={`absolute -left-[5px] top-2 h-2.5 w-2.5 rounded-full border-2 border-background ${
                        item.accent === "alert"
                          ? "bg-amber-400"
                          : item.accent === "node"
                            ? "bg-emerald-400"
                            : item.accent === "pulse"
                              ? "bg-sky-400"
                              : "bg-violet-400"
                      }`}
                    />
                    <div className="rounded-xl border border-white/5 bg-black/20 px-3 py-2">
                      <p className="text-[11px] text-muted-foreground">{new Date(item.at).toLocaleString()}</p>
                      <p className="text-sm font-medium leading-snug">{item.title}</p>
                      <p className="text-xs text-muted-foreground">{item.detail}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div data-testid="garden-node-meadow">
            <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold">
              <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-violet-500/20 text-lg">🦋</span>
              Node meadow
            </h3>
            {federationNodes.length === 0 && (!networkStats || Object.keys(networkStats.nodes).length === 0) ? (
              <p className="rounded-2xl border border-dashed border-white/15 p-4 text-sm text-muted-foreground">
                No creatures on the wire yet — federation nodes will appear here when they register.
              </p>
            ) : (
              <ul className="space-y-3">
                {federationNodes.length > 0
                  ? federationNodes
                      .slice()
                      .sort((a, b) => a.hostname.localeCompare(b.hostname))
                      .map((node) => {
                        const alive = node.status.toLowerCase() === "online" || node.status.toLowerCase() === "active";
                        return (
                          <li
                            key={node.node_id}
                            data-testid="garden-federation-node"
                            className={`flex items-center justify-between gap-3 rounded-2xl border px-4 py-3 ${
                              alive ? "border-emerald-500/30 shadow-[0_0_24px_-8px_rgba(52,211,153,0.45)]" : "border-white/10 opacity-80"
                            }`}
                          >
                            <div>
                              <p className="font-medium">{node.hostname}</p>
                              <p className="text-xs text-muted-foreground">{node.os_type}</p>
                            </div>
                            <span
                              className={`relative h-3 w-3 rounded-full ${
                                alive ? "animate-warm-pulse bg-emerald-400 shadow-[0_0_12px_2px_rgba(52,211,153,0.6)]" : "bg-zinc-500"
                              }`}
                              title={node.status}
                            />
                          </li>
                        );
                      })
                  : networkStats &&
                    Object.entries(networkStats.nodes).map(([nodeId, node]) => (
                      <li
                        key={`net-${nodeId}`}
                        data-testid="garden-network-node"
                        className="flex items-center justify-between gap-3 rounded-2xl border border-white/10 px-4 py-3"
                      >
                        <div>
                          <p className="font-medium">{node.hostname}</p>
                          <p className="text-xs text-muted-foreground">{node.os_type}</p>
                        </div>
                        <span
                          className={`h-3 w-3 rounded-full ${
                            node.status === "online" ? "bg-emerald-400 shadow-[0_0_12px_2px_rgba(52,211,153,0.5)]" : "bg-zinc-500"
                          }`}
                        />
                      </li>
                    ))}
              </ul>
            )}
          </div>

          {execStats && (
            <div className="rounded-2xl border border-violet-500/20 bg-violet-950/20 p-4 text-sm">
              <p className="text-xs font-medium uppercase tracking-wider text-violet-200/90">Routing health</p>
              <div className="mt-3 grid grid-cols-3 gap-2 text-center">
                <div>
                  <p className="text-2xl font-semibold text-emerald-300">{execStats.summary.healthy_providers}</p>
                  <p className="text-[10px] text-muted-foreground">healthy</p>
                </div>
                <div>
                  <p className="text-2xl font-semibold text-amber-300">{execStats.summary.attention_needed}</p>
                  <p className="text-[10px] text-muted-foreground">attention</p>
                </div>
                <div>
                  <p className="text-2xl font-semibold">{execStats.summary.total_measurements}</p>
                  <p className="text-[10px] text-muted-foreground">samples</p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
