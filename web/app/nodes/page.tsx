import type { Metadata } from "next";
import Link from "next/link";
import { cookies } from "next/headers";

import { getApiBase } from "@/lib/api";
import MessageForm from "./MessageForm";
import { createTranslator } from "@/lib/i18n";
import { DEFAULT_LOCALE, isSupportedLocale, type LocaleCode } from "@/lib/locales";

export const metadata: Metadata = {
  title: "Nodes",
  description: "Federation nodes, provider health, remote control, and network messaging.",
};

// ─── Types ────────────────────────────────────────────────────────────────────

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

type ProviderExecStatsEntry = {
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

type ProviderExecStatsResponse = {
  providers: Record<string, ProviderExecStatsEntry>;
  alerts: Array<{ provider: string; metric: string; value: number; threshold: number; message: string }>;
  summary: { total_providers: number; healthy_providers: number; attention_needed: number; total_measurements: number };
};

type ProviderReadinessRow = {
  provider: string;
  kind: string;
  status: string;
  required: boolean;
  configured: boolean;
  severity: string;
  missing_env: string[];
  notes: string[];
};

type ProviderReadinessResponse = {
  generated_at: string;
  required_providers: string[];
  all_required_ready: boolean;
  blocking_issues: string[];
  recommendations: string[];
  providers: ProviderReadinessRow[];
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

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

// ─── Data loader ─────────────────────────────────────────────────────────────

async function loadData() {
  const api = getApiBase();
  const [nodesRes, execStatsRes, readinessRes] = await Promise.all([
    fetch(`${api}/api/federation/nodes`, { cache: "no-store" }).catch(() => null),
    fetch(`${api}/api/providers/stats`, { cache: "no-store" }).catch(() => null),
    fetch(`${api}/api/automation/usage/readiness?force_refresh=true`, { cache: "no-store" }).catch(() => null),
  ]);

  const nodes: FederationNode[] = nodesRes?.ok ? ((await nodesRes.json()) as FederationNode[]) : [];

  let execStats: ProviderExecStatsResponse | null = null;
  if (execStatsRes?.ok) {
    execStats = (await execStatsRes.json()) as ProviderExecStatsResponse;
  }

  const readiness: ProviderReadinessResponse | null = readinessRes?.ok
    ? ((await readinessRes.json()) as ProviderReadinessResponse)
    : null;

  return { nodes, execStats, readiness };
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default async function NodesPage() {
  const cookieStore = await cookies();
  const cookieLang = cookieStore.get("NEXT_LOCALE")?.value;
  const lang: LocaleCode = isSupportedLocale(cookieLang) ? cookieLang : DEFAULT_LOCALE;
  const t = createTranslator(lang);
  const { nodes, execStats, readiness } = await loadData();
  const apiBase = getApiBase();
  const sorted = [...nodes].sort((a, b) => a.hostname.localeCompare(b.hostname));

  const onlineCount = nodes.filter((n) => statusColor(n.last_seen_at) === "green").length;
  const totalOk = nodes.reduce((s, n) => s + (n.streak?.completed ?? 0), 0);
  const totalResolved = nodes.reduce((s, n) => s + (n.streak?.total_resolved ?? 0), 0);
  const fleetRate = totalResolved > 0 ? Math.round((totalOk / totalResolved) * 100) : 0;

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-6xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight mb-2">{t("nodes.title")}</h1>
        <p className="text-muted-foreground max-w-2xl leading-relaxed">
          {t("nodes.lede")}
        </p>
      </div>

      {/* Fleet summary */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 text-sm">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div>
            <p className="text-2xl font-bold">{nodes.length}</p>
            <p className="text-xs text-muted-foreground">{t("nodes.statTotal")}</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-green-500">{onlineCount}</p>
            <p className="text-xs text-muted-foreground">{t("nodes.statOnline")}</p>
          </div>
          <div>
            <p className="text-2xl font-bold">
              {nodes.reduce((sum, n) => sum + (n.streak?.executing ?? 0), 0)}
            </p>
            <p className="text-xs text-muted-foreground">tasks running</p>
          </div>
          <div>
            <p className={`text-2xl font-bold ${fleetRate >= 70 ? "text-green-500" : fleetRate >= 40 ? "text-yellow-500" : "text-red-500"}`}>
              {fleetRate}%
            </p>
            <p className="text-xs text-muted-foreground">fleet success</p>
          </div>
        </div>
      </section>

      {/* Provider health */}
      {execStats && (
        <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold">{t("nodes.providerHealth")}</h2>
            <span className="text-xs text-muted-foreground">
              {execStats.summary.healthy_providers}/{execStats.summary.total_providers} healthy · {execStats.summary.total_measurements} measurements
            </span>
          </div>

          {execStats.alerts.length > 0 && (
            <ul className="space-y-1">
              {execStats.alerts.map((alert, i) => (
                <li
                  key={`alert-${alert.provider}-${alert.metric}-${i}`}
                  className={`rounded-xl px-3 py-1.5 text-sm font-medium ${
                    alert.value < alert.threshold * 0.5
                      ? "bg-red-500/10 text-red-600 dark:text-red-400"
                      : "bg-amber-500/10 text-amber-600 dark:text-amber-400"
                  }`}
                >
                  {alert.message}
                </li>
              ))}
            </ul>
          )}

          {/* Desktop table */}
          <div className="hidden md:block overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/30 text-left text-xs uppercase tracking-wider text-muted-foreground">
                  <th className="pb-2 pr-4">{t("nodes.colProvider")}</th>
                  <th className="pb-2 pr-4">{t("nodes.colOverall")}</th>
                  <th className="pb-2 pr-4">{t("nodes.colLast5")}</th>
                  <th className="pb-2 pr-4">{t("nodes.colSpeed")}</th>
                  <th className="pb-2">{t("nodes.colStatus")}</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(execStats.providers)
                  .sort(([a], [b]) => a.localeCompare(b))
                  .map(([name, entry]) => (
                    <tr key={`prov-${name}`} className="border-b border-border/30">
                      <td className="py-1.5 pr-4 font-medium">{name}</td>
                      <td className="py-1.5 pr-4">{(entry.success_rate * 100).toFixed(0)}%</td>
                      <td
                        className={`py-1.5 pr-4 ${
                          entry.last_5_rate < 0.5
                            ? "text-red-600 dark:text-red-400"
                            : entry.last_5_rate < 0.8
                              ? "text-amber-600 dark:text-amber-400"
                              : ""
                        }`}
                      >
                        {(entry.last_5_rate * 100).toFixed(0)}%
                      </td>
                      <td className="py-1.5 pr-4">{entry.avg_duration_s.toFixed(1)}s</td>
                      <td className="py-1.5">
                        {entry.blocked ? (
                          <span className="text-red-600 dark:text-red-400">blocked</span>
                        ) : entry.needs_attention ? (
                          <span className="text-amber-600 dark:text-amber-400">attention</span>
                        ) : (
                          <span className="text-green-600 dark:text-green-400">ok</span>
                        )}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>

          {/* Mobile stacked cards */}
          <div className="md:hidden space-y-2">
            {Object.entries(execStats.providers)
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([name, entry]) => (
                <div key={`prov-mob-${name}`} className="rounded-xl border border-border/20 bg-background/40 p-3 space-y-1">
                  <p className="font-medium text-sm">{name}</p>
                  <div className="grid grid-cols-3 gap-2 text-xs">
                    <div>
                      <p className="text-muted-foreground">{t("nodes.overall")}</p>
                      <p>{(entry.success_rate * 100).toFixed(0)}%</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">{t("nodes.last5")}</p>
                      <p className={entry.last_5_rate < 0.5 ? "text-red-600 dark:text-red-400" : entry.last_5_rate < 0.8 ? "text-amber-600 dark:text-amber-400" : ""}>
                        {(entry.last_5_rate * 100).toFixed(0)}%
                      </p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">{t("nodes.status")}</p>
                      <p>{entry.blocked ? "blocked" : entry.needs_attention ? "attention" : "ok"}</p>
                    </div>
                  </div>
                </div>
              ))}
          </div>
        </section>
      )}

      {/* Provider readiness */}
      {readiness && !readiness.all_required_ready && (
        <section className="rounded-2xl border border-red-500/30 bg-red-500/5 p-6 space-y-3">
          <h2 className="text-xl font-semibold text-red-600 dark:text-red-400">{t("nodes.providerConfigIssues")}</h2>
          {readiness.blocking_issues.map((issue, i) => (
            <p key={`issue-${i}`} className="text-sm text-red-600 dark:text-red-400">⚠ {issue}</p>
          ))}
          {readiness.recommendations.length > 0 && (
            <ul className="space-y-1 text-sm text-muted-foreground">
              {readiness.recommendations.map((rec, i) => (
                <li key={`rec-${i}`}>→ {rec}</li>
              ))}
            </ul>
          )}
        </section>
      )}

      {/* Node list */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3 text-sm">
        <h2 className="text-xl font-semibold">{t("nodes.registeredNodes")}</h2>
        {sorted.length === 0 && (
          <p className="text-muted-foreground">{t("nodes.noNodes")}</p>
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
                    {node.streak.success_rate != null && (
                      <span className={`text-xs font-medium ${
                        node.streak.success_rate >= 0.8 ? "text-green-500" :
                        node.streak.success_rate >= 0.5 ? "text-yellow-500" : "text-red-500"
                      }`}>
                        {Math.round(node.streak.success_rate * 100)}%
                      </span>
                    )}
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
                        const barColor = pct > 80 ? "bg-red-500" : pct > 60 ? "bg-yellow-500" : "bg-green-500";
                        return (
                          <div key={g.label} className="flex-1 min-w-0">
                            <div className="flex justify-between text-[10px] text-muted-foreground mb-0.5">
                              <span>{g.label}</span>
                              <span>{Math.round(g.value ?? 0)}{g.unit}</span>
                            </div>
                            <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                              <div className={`h-full rounded-full ${barColor}`} style={{ width: `${pct}%` }} />
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

      {/* Send message to nodes */}
      <MessageForm
        nodes={sorted.map((n) => ({ node_id: n.node_id, hostname: n.hostname }))}
        apiBase={apiBase}
      />

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
