import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { getApiBase } from "@/lib/api";
import MessageForm from "./MessageForm";
import { RemoteControlSection } from "./RemoteControlSection";

export const metadata: Metadata = {
  title: "Nodes",
  description: "Federation nodes — status, health, providers, messaging, and remote control.",
};

type SystemMetrics = {
  cpu_percent?: number;
  cpu_count?: number;
  load_avg?: number[];
  memory_percent?: number;
  memory_total_gb?: number;
  memory_available_gb?: number;
  disk_percent?: number;
  disk_free_gb?: number;
  disk_read_mb?: number;
  disk_write_mb?: number;
  net_sent_mb?: number;
  net_recv_mb?: number;
  process_count?: number;
  runner_cpu_percent?: number;
  runner_memory_mb?: number;
  runner_threads?: number;
};

type FederationNodeCapabilities = {
  executors?: string[];
  tools?: string[];
  hardware?: {
    platform?: string;
    processor?: string;
    python?: string;
    cpu_count?: number;
    memory_total_gb?: number | null;
    gpu_available?: boolean;
    gpu_type?: string | null;
  };
  system_metrics?: SystemMetrics;
  system_metrics_at?: string;
  models_by_executor?: Record<string, string[]>;
  probed_at?: string;
};

type ProviderStat = {
  ok: number;
  fail: number;
  timeout: number;
  total: number;
  success_rate: number | null;
  last_5: string[];
};

type NodeStreak = {
  completed?: number;
  failed?: number;
  timed_out?: number;
  executing?: number;
  total_resolved?: number;
  success_rate?: number;
  last_10?: string[];
  providers_used?: string[];
  by_provider?: Record<string, ProviderStat>;
  attention?: string;
  attention_detail?: string;
};

type FederationNode = {
  node_id: string;
  hostname: string;
  os_type: string;
  providers: string[];
  capabilities: FederationNodeCapabilities;
  registered_at: string;
  last_seen_at: string;
  status: string;
  git_sha?: string;
  git_sha_updated_at?: string;
  streak?: NodeStreak;
};

function osIcon(osType: string): string {
  const lower = osType.toLowerCase();
  if (lower.includes("mac") || lower.includes("darwin")) return "\uD83C\uDF4E";
  if (lower.includes("win")) return "\uD83E\uDE9F";
  if (lower.includes("linux")) return "\uD83D\uDC27";
  return "\uD83D\uDDA5\uFE0F";
}

function statusColor(lastSeen: string): "green" | "yellow" | "red" {
  const diff = Date.now() - new Date(lastSeen).getTime();
  const mins = diff / 60000;
  if (mins < 5) return "green";
  if (mins < 60) return "yellow";
  return "red";
}

function statusDotClass(color: "green" | "yellow" | "red"): string {
  switch (color) {
    case "green":
      return "bg-green-500 shadow-green-500/50 shadow-sm";
    case "yellow":
      return "bg-yellow-500 shadow-yellow-500/50 shadow-sm";
    case "red":
      return "bg-red-500 shadow-red-500/50 shadow-sm";
  }
}

function streakDot(result: string): { char: string; cls: string } {
  switch (result) {
    case "ok":
      return { char: "✓", cls: "text-green-500" };
    case "fail":
      return { char: "✗", cls: "text-red-500" };
    case "timeout":
      return { char: "T", cls: "text-yellow-500" };
    default:
      return { char: "·", cls: "text-muted-foreground" };
  }
}

function attentionBadge(attention: string): { label: string; cls: string } {
  switch (attention) {
    case "healthy":
      return { label: "healthy", cls: "bg-green-500/10 text-green-500 border-green-500/30" };
    case "slow":
      return { label: "slow", cls: "bg-yellow-500/10 text-yellow-500 border-yellow-500/30" };
    case "failing":
      return { label: "failing", cls: "bg-red-500/10 text-red-500 border-red-500/30" };
    default:
      return { label: attention || "unknown", cls: "bg-muted text-muted-foreground border-border/30" };
  }
}

function providerHeatColor(stat: ProviderStat | undefined): string {
  if (!stat || stat.total === 0) return "bg-muted border-border/30 text-muted-foreground";
  const rate = stat.success_rate ?? 0;
  if (rate >= 0.8) return "bg-green-500/15 border-green-500/30 text-green-600 dark:text-green-400";
  if (rate >= 0.5) return "bg-yellow-500/15 border-yellow-500/30 text-yellow-600 dark:text-yellow-400";
  return "bg-red-500/15 border-red-500/30 text-red-600 dark:text-red-400";
}

function providerTooltip(name: string, stat: ProviderStat | undefined): string {
  if (!stat || stat.total === 0) return `${name}: no data`;
  return `${name}: ${stat.ok}/${stat.total} (${Math.round((stat.success_rate ?? 0) * 100)}%) — ${stat.fail} fail, ${stat.timeout} timeout`;
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

async function loadNodes(): Promise<FederationNode[]> {
  const api = getApiBase();
  try {
    const res = await fetch(`${api}/api/federation/nodes`, { cache: "no-store" });
    if (!res.ok) return [];
    return (await res.json()) as FederationNode[];
  } catch {
    return [];
  }
}

export default async function NodesPage() {
  const nodes = await loadNodes();
  const apiBase = getApiBase();
  const sorted = [...nodes].sort((a, b) => a.hostname.localeCompare(b.hostname));

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-6xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight mb-2">Nodes</h1>
        <p className="text-muted-foreground max-w-2xl leading-relaxed">
          Everything about the network's nodes — who is online, their capabilities, provider health, messaging, and remote dispatch controls.
        </p>
      </div>

      {/* Summary */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 text-sm">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div>
            <p className="text-2xl font-bold">{nodes.length}</p>
            <p className="text-xs text-muted-foreground">total nodes</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-green-500">
              {nodes.filter((n) => statusColor(n.last_seen_at) === "green").length}
            </p>
            <p className="text-xs text-muted-foreground">online</p>
          </div>
          <div>
            <p className="text-2xl font-bold">
              {nodes.reduce((sum, n) => sum + (n.streak?.executing ?? 0), 0)}
            </p>
            <p className="text-xs text-muted-foreground">tasks running</p>
          </div>
          <div>
            {(() => {
              const totalOk = nodes.reduce((s, n) => s + (n.streak?.completed ?? 0), 0);
              const totalResolved = nodes.reduce((s, n) => s + (n.streak?.total_resolved ?? 0), 0);
              const rate = totalResolved > 0 ? Math.round((totalOk / totalResolved) * 100) : 0;
              return (
                <>
                  <p className={`text-2xl font-bold ${rate >= 70 ? "text-green-500" : rate >= 40 ? "text-yellow-500" : "text-red-500"}`}>
                    {rate}%
                  </p>
                  <p className="text-xs text-muted-foreground">fleet success</p>
                </>
              );
            })()}
          </div>
        </div>
      </section>

      {/* Node list */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3 text-sm">
        <h2 className="text-xl font-semibold">Registered Nodes</h2>
        {sorted.length === 0 && (
          <p className="text-muted-foreground">No federation nodes registered yet.</p>
        )}
        <ul className="space-y-3">
          {sorted.map((node) => {
            const color = statusColor(node.last_seen_at);
            return (
              <li
                key={node.node_id}
                className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-3"
              >
                {/* Row 1: Status dot, name, attention badge, last seen */}
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-block w-2.5 h-2.5 rounded-full ${statusDotClass(color)}`}
                  />
                  <span className="text-lg mr-1">{osIcon(node.os_type)}</span>
                  <span className="font-semibold">{node.hostname}</span>
                  {node.streak?.attention && (() => {
                    const badge = attentionBadge(node.streak.attention);
                    return (
                      <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${badge.cls}`}>
                        {badge.label}
                      </span>
                    );
                  })()}
                  <span className="text-muted-foreground text-xs ml-auto">
                    {relativeTime(node.last_seen_at)}
                  </span>
                </div>

                {/* Row 2: Streak visualization + success rate + running count */}
                {node.streak && (
                  <div className="flex items-center gap-3">
                    {/* Streak dots */}
                    <div className="flex items-center gap-0.5 font-mono text-sm">
                      {(node.streak.last_10 ?? []).map((result, idx) => {
                        const dot = streakDot(result);
                        return (
                          <span key={`${node.node_id}-streak-${idx}`} className={dot.cls}>
                            {dot.char}
                          </span>
                        );
                      })}
                    </div>
                    {/* Success rate */}
                    {node.streak.success_rate != null && (
                      <span className={`text-xs font-medium ${
                        node.streak.success_rate >= 0.8 ? "text-green-500" :
                        node.streak.success_rate >= 0.5 ? "text-yellow-500" : "text-red-500"
                      }`}>
                        {Math.round(node.streak.success_rate * 100)}%
                      </span>
                    )}
                    {/* Running count */}
                    {(node.streak.executing ?? 0) > 0 && (
                      <span className="text-xs text-amber-500 font-medium">
                        {node.streak.executing} running
                      </span>
                    )}
                  </div>
                )}

                {/* Row 3: SHA + update time */}
                {node.git_sha && (
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span className="font-mono text-cyan-500">{node.git_sha.slice(0, 7)}</span>
                    {node.git_sha_updated_at && (
                      <span>updated {relativeTime(node.git_sha_updated_at)}</span>
                    )}
                  </div>
                )}

                {/* Row 4: Providers with performance heatmap */}
                <div className="flex flex-wrap gap-1.5">
                  {node.providers.map((p) => {
                    const stat = node.streak?.by_provider?.[p];
                    const heatClass = providerHeatColor(stat);
                    const tip = providerTooltip(p, stat);
                    return (
                      <span
                        key={`${node.node_id}-${p}`}
                        className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${heatClass}`}
                        title={tip}
                      >
                        {p}
                        {stat && stat.total > 0 && (
                          <span className="ml-1 opacity-70">
                            {Math.round((stat.success_rate ?? 0) * 100)}%
                          </span>
                        )}
                      </span>
                    );
                  })}
                  {node.providers.length === 0 && (
                    <span className="text-muted-foreground text-xs">no providers</span>
                  )}
                </div>

                {/* Row 5: Attention detail hint */}
                {node.streak?.attention_detail && node.streak.attention !== "healthy" && (
                  <p className="text-xs text-muted-foreground">
                    → {node.streak.attention_detail}
                  </p>
                )}

                {/* Row 6: System metrics gauges */}
                {node.capabilities?.system_metrics && (() => {
                  const m = node.capabilities.system_metrics!;
                  const gauges = [
                    { label: "CPU", value: m.cpu_percent, max: 100, unit: "%" },
                    { label: "RAM", value: m.memory_percent, max: 100, unit: "%" },
                    { label: "Disk", value: m.disk_percent, max: 100, unit: "%" },
                    { label: "Procs", value: m.process_count, max: 500, unit: "" },
                  ].filter(g => g.value != null);
                  return gauges.length > 0 ? (
                    <div className="flex gap-3">
                      {gauges.map(g => {
                        const pct = Math.min(100, ((g.value ?? 0) / g.max) * 100);
                        const color = pct > 80 ? "bg-red-500" : pct > 60 ? "bg-yellow-500" : "bg-green-500";
                        return (
                          <div key={g.label} className="flex-1 min-w-0">
                            <div className="flex justify-between text-[10px] text-muted-foreground mb-0.5">
                              <span>{g.label}</span>
                              <span>{Math.round(g.value ?? 0)}{g.unit}</span>
                            </div>
                            <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                              <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
                            </div>
                          </div>
                        );
                      })}
                      {m.net_sent_mb != null && (
                        <div className="flex-shrink-0 text-[10px] text-muted-foreground self-end">
                          ↑{m.net_sent_mb}MB ↓{m.net_recv_mb ?? 0}MB
                        </div>
                      )}
                    </div>
                  ) : null;
                })()}
                {/* Row 7: Platform + registered */}
                <p className="text-[10px] text-muted-foreground">
                  {node.capabilities?.hardware?.platform && (
                    <>{node.capabilities.hardware.platform.split("-").slice(0, 2).join(" ")} · </>
                  )}
                  {node.capabilities?.hardware?.processor && (
                    <>{node.capabilities.hardware.processor.length > 25
                      ? node.capabilities.hardware.processor.split(",")[0]
                      : node.capabilities.hardware.processor} · </>
                  )}
                  registered {new Date(node.registered_at).toLocaleDateString()}
                  {node.capabilities?.system_metrics_at && (
                    <> · metrics {relativeTime(node.capabilities.system_metrics_at)}</>
                  )}
                </p>
              </li>
            );
          })}
        </ul>
      </section>

      <MessageForm
        nodes={sorted.map((n) => ({ node_id: n.node_id, hostname: n.hostname }))}
        apiBase={apiBase}
      />

      {/* Remote control section */}
      <section className="space-y-3">
        <div>
          <h2 className="text-xl font-semibold mb-1">Remote Control</h2>
          <p className="text-sm text-muted-foreground">
            Dispatch tasks, monitor the queue, and check deployment status.
          </p>
        </div>
        <Suspense fallback={<p className="text-sm text-muted-foreground">Loading controls…</p>}>
          <RemoteControlSection />
        </Suspense>
      </section>

      {/* Navigation */}
      <nav
        className="py-8 text-center space-y-2 border-t border-border/20"
        aria-label="Where to go next"
      >
        <p className="text-xs text-muted-foreground/80 uppercase tracking-wider">
          Where to go next
        </p>
        <div className="flex flex-wrap justify-center gap-4 text-sm">
          <Link href="/pipeline" className="text-amber-600 dark:text-amber-400 hover:underline">
            Pipeline
          </Link>
          <Link href="/flow" className="text-amber-600 dark:text-amber-400 hover:underline">
            Flow
          </Link>
          <Link href="/specs" className="text-amber-600 dark:text-amber-400 hover:underline">
            Specs
          </Link>
        </div>
      </nav>
    </main>
  );
}
