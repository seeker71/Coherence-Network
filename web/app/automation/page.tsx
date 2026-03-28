import type { Metadata } from "next";
import Link from "next/link";

import { AutomationGardenExperience } from "@/components/automation_garden/automation_garden_experience";
import type {
  AutomationUsageResponse,
  UsageAlertResponse,
  ProviderReadinessResponse,
  ProviderValidationResponse,
  ProviderExecStatsResponse,
  NetworkStatsResponse,
  FederationNode,
  FleetCapabilitiesResponse,
} from "@/components/automation_garden/types";
import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "Automation",
  description: "Provider automation readiness and subscription status.",
};

async function loadAutomationData(): Promise<{
  usage: AutomationUsageResponse;
  alerts: UsageAlertResponse;
  readiness: ProviderReadinessResponse;
  validation: ProviderValidationResponse;
  execStats: ProviderExecStatsResponse | null;
  networkStats: NetworkStatsResponse | null;
  federationNodes: FederationNode[];
  fleetCapabilities: FleetCapabilitiesResponse | null;
}> {
  const api = getApiBase();
  const [usageRes, alertsRes, readinessRes, validationRes, execStatsRes, networkStatsRes, federationNodesRes, fleetCapsRes] =
    await Promise.all([
    fetch(`${api}/api/automation/usage?force_refresh=true`, { cache: "no-store" }),
    fetch(`${api}/api/automation/usage/alerts?threshold_ratio=0.2`, { cache: "no-store" }).catch(() => null),
    fetch(`${api}/api/automation/usage/readiness?force_refresh=true`, { cache: "no-store" }).catch(() => null),
    fetch(`${api}/api/automation/usage/provider-validation?runtime_window_seconds=86400&min_execution_events=1&force_refresh=true`, {
      cache: "no-store",
    }).catch(() => null),
    fetch(`${api}/api/providers/stats`, { cache: "no-store" }).catch(() => null),
    fetch(`${api}/api/federation/nodes/stats`, { cache: "no-store" }).catch(() => null),
    fetch(`${api}/api/federation/nodes`, { cache: "no-store" }).catch(() => null),
    fetch(`${api}/api/federation/nodes/capabilities`, { cache: "no-store" }).catch(() => null),
  ]);
  if (!usageRes.ok) {
    throw new Error(`automation usage HTTP ${usageRes.status}`);
  }
  // alerts, readiness, validation are optional — graceful degradation
  let execStats: ProviderExecStatsResponse | null = null;
  if (execStatsRes && execStatsRes.ok) {
    execStats = (await execStatsRes.json()) as ProviderExecStatsResponse;
  }
  let networkStats: NetworkStatsResponse | null = null;
  if (networkStatsRes && networkStatsRes.ok) {
    networkStats = (await networkStatsRes.json()) as NetworkStatsResponse;
  }
  let federationNodes: FederationNode[] = [];
  if (federationNodesRes && federationNodesRes.ok) {
    federationNodes = (await federationNodesRes.json()) as FederationNode[];
  }
  let fleetCapabilities: FleetCapabilitiesResponse | null = null;
  if (fleetCapsRes && fleetCapsRes.ok) {
    fleetCapabilities = (await fleetCapsRes.json()) as FleetCapabilitiesResponse;
  }
  return {
    usage: (await usageRes.json()) as AutomationUsageResponse,
    alerts: alertsRes?.ok ? ((await alertsRes.json()) as UsageAlertResponse) : ({ alerts: [], generated_at: "" } as unknown as UsageAlertResponse),
    readiness: readinessRes?.ok
      ? ((await readinessRes.json()) as ProviderReadinessResponse)
      : ({
          providers: [],
          required_providers: [],
          all_required_ready: true,
          blocking_issues: [],
          recommendations: [],
          generated_at: "",
        } as ProviderReadinessResponse),
    validation: validationRes?.ok
      ? ((await validationRes.json()) as ProviderValidationResponse)
      : ({
          providers: [],
          required_providers: [],
          runtime_window_seconds: 86400,
          min_execution_events: 1,
          all_required_validated: true,
          blocking_issues: [],
          generated_at: "",
        } as ProviderValidationResponse),
    execStats,
    networkStats,
    federationNodes,
    fleetCapabilities,
  };
}

export default async function AutomationPage() {
  const { usage, alerts, readiness, validation, execStats, networkStats, federationNodes, fleetCapabilities } =
    await loadAutomationData();
  const providers = [...usage.providers].sort((a, b) => a.provider.localeCompare(b.provider));

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-6xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight mb-2">Automation Capacity</h1>
        <p className="text-muted-foreground max-w-2xl leading-relaxed">
          A living map of adapters, nodes, and capacity — explore the garden first; open the detailed panel when you need
          raw tables and contract rows.
        </p>
      </div>

      <AutomationGardenExperience
        data={{
          usage,
          alerts,
          readiness,
          validation,
          execStats,
          networkStats,
          federationNodes,
          fleetCapabilities,
        }}
      />

      <details className="group rounded-2xl border border-border/25 bg-card/20 open:border-border/40">
        <summary className="cursor-pointer list-none rounded-2xl px-4 py-3 text-sm font-medium text-muted-foreground hover:text-foreground flex items-center justify-between gap-2">
          <span>Detailed metrics &amp; tables</span>
          <span className="text-xs font-normal opacity-70 group-open:rotate-90 transition-transform">▸</span>
        </summary>
        <div className="px-4 pb-8 pt-2 space-y-8 border-t border-border/15">

      {usage.limit_coverage && (usage.limit_coverage.providers_missing_limit_metrics.length > 0 || usage.limit_coverage.providers_partial_limit_metrics.length > 0) && (
        <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3 text-sm">
          <h2 className="text-xl font-semibold">Usage Limit Coverage</h2>
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-xl border border-border/20 bg-background/40 p-3">
              <p className="text-muted-foreground text-xs">With limits</p>
              <p className="text-lg font-semibold">{usage.limit_coverage.providers_with_limit_metrics} / {usage.limit_coverage.providers_considered}</p>
            </div>
            <div className="rounded-xl border border-border/20 bg-background/40 p-3">
              <p className="text-muted-foreground text-xs">With remaining</p>
              <p className="text-lg font-semibold">{usage.limit_coverage.providers_with_remaining_metrics}</p>
            </div>
            <div className="rounded-xl border border-border/20 bg-background/40 p-3">
              <p className="text-muted-foreground text-xs">Coverage</p>
              <p className="text-lg font-semibold">{Math.round((usage.limit_coverage.coverage_ratio ?? 0) * 100)}%</p>
            </div>
          </div>
          {usage.limit_coverage.providers_missing_limit_metrics.length > 0 && (
            <div>
              <p className="text-muted-foreground text-xs mb-1">Missing limit metrics</p>
              <div className="flex flex-wrap gap-1.5">
                {usage.limit_coverage.providers_missing_limit_metrics.map((p) => (
                  <span key={p} className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-red-500/10 text-red-500">{p}</span>
                ))}
              </div>
            </div>
          )}
          {usage.limit_coverage.providers_partial_limit_metrics.length > 0 && (
            <div>
              <p className="text-muted-foreground text-xs mb-1">Partial limit metrics</p>
              <div className="flex flex-wrap gap-1.5">
                {usage.limit_coverage.providers_partial_limit_metrics.map((p) => (
                  <span key={p} className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-amber-500/10 text-amber-500">{p}</span>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3 text-sm">
        <h2 className="text-xl font-semibold">Provider Validation Contract</h2>
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-xl border border-border/20 bg-background/40 p-3">
            <p className="text-muted-foreground text-xs">Runtime window</p>
            <p className="text-lg font-semibold">{Math.round(validation.runtime_window_seconds / 3600)}h</p>
          </div>
          <div className="rounded-xl border border-border/20 bg-background/40 p-3">
            <p className="text-muted-foreground text-xs">Min execution events</p>
            <p className="text-lg font-semibold">{validation.min_execution_events}</p>
          </div>
        </div>
        {(validation?.blocking_issues?.length ?? 0) > 0 && (
          <ul className="space-y-1 text-destructive">
            {validation.blocking_issues.map((item) => (
              <li key={`validation-block-${item}`}>{item}</li>
            ))}
          </ul>
        )}
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-border/30 text-muted-foreground text-xs">
                <th className="py-2 pr-3">Provider</th>
                <th className="py-2 pr-3 text-center">Configured</th>
                <th className="py-2 pr-3 text-center">Readiness</th>
                <th className="py-2 pr-3 text-right">Usage events</th>
                <th className="py-2 pr-3 text-right">Successful</th>
                <th className="py-2 pr-3 text-center">Validated</th>
              </tr>
            </thead>
            <tbody>
              {validation.providers.map((provider) => (
                <tr key={`validation-${provider.provider}`} className="border-b border-border/10">
                  <td className="py-2 pr-3 font-medium">{provider.provider}</td>
                  <td className="py-2 pr-3 text-center">
                    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                      provider.configured ? "bg-green-500/10 text-green-500" : "bg-red-500/10 text-red-500"
                    }`}>
                      {provider.configured ? "Yes" : "No"}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-center">
                    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                      provider.readiness_status === "ready" ? "bg-green-500/10 text-green-500"
                        : provider.readiness_status === "degraded" ? "bg-amber-500/10 text-amber-500"
                          : "bg-red-500/10 text-red-500"
                    }`}>
                      {provider.readiness_status}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-right">{provider.usage_events}</td>
                  <td className="py-2 pr-3 text-right">{provider.successful_events}</td>
                  <td className="py-2 pr-3 text-center">
                    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                      provider.validated_execution ? "bg-green-500/10 text-green-500" : "bg-muted text-muted-foreground"
                    }`}>
                      {provider.validated_execution ? "Yes" : "No"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3 text-sm">
        <h2 className="text-xl font-semibold">Provider Execution Stats</h2>
        {execStats ? (
          <>
            <div className="grid grid-cols-3 gap-3">
              <div className="rounded-xl border border-border/20 bg-background/40 p-3">
                <p className="text-muted-foreground text-xs">Healthy</p>
                <p className="text-lg font-semibold">{execStats.summary.healthy_providers} / {execStats.summary.total_providers}</p>
              </div>
              <div className="rounded-xl border border-border/20 bg-background/40 p-3">
                <p className="text-muted-foreground text-xs">Need attention</p>
                <p className="text-lg font-semibold">{execStats.summary.attention_needed}</p>
              </div>
              <div className="rounded-xl border border-border/20 bg-background/40 p-3">
                <p className="text-muted-foreground text-xs">Measurements</p>
                <p className="text-lg font-semibold">{execStats.summary.total_measurements}</p>
              </div>
            </div>
            <ul className="space-y-2">
              {Object.entries(execStats.providers)
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([name, entry]) => (
                  <li
                    key={`exec-${name}`}
                    className={`rounded-xl border p-4 space-y-2 ${entry.blocked ? "border-red-500/50 bg-red-500/5" : "border-border/20 bg-background/40"}`}
                  >
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <span className="font-medium">{name}</span>
                      <span className="flex gap-1.5">
                        {entry.blocked && (
                          <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-red-500/10 text-red-500">Blocked</span>
                        )}
                        {entry.needs_attention && (
                          <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-amber-500/10 text-amber-500">Needs attention</span>
                        )}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                      <div>
                        <p className="text-muted-foreground text-xs">Overall rate</p>
                        <p className="font-medium">{(entry.success_rate * 100).toFixed(0)}%</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground text-xs">Last 5 rate</p>
                        <p className={`font-medium ${
                          entry.last_5_rate < 0.5 ? "text-red-500" : entry.last_5_rate < 0.8 ? "text-amber-500" : ""
                        }`}>{(entry.last_5_rate * 100).toFixed(0)}%</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground text-xs">Runs</p>
                        <p className="font-medium">{entry.total_runs} <span className="text-xs text-muted-foreground">({entry.successes} ok, {entry.failures} fail)</span></p>
                      </div>
                      <div>
                        <p className="text-muted-foreground text-xs">Avg duration</p>
                        <p className="font-medium">{entry.avg_duration_s.toFixed(1)}s</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground text-xs">Selection probability</p>
                        <p className="font-medium">{(entry.selection_probability * 100).toFixed(1)}%</p>
                      </div>
                    </div>
                    {Object.keys(entry.error_breakdown).length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {Object.entries(entry.error_breakdown).map(([errClass, count]) => (
                          <span key={`exec-err-${name}-${errClass}`} className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-red-500/10 text-red-500">
                            {errClass} x{count}
                          </span>
                        ))}
                      </div>
                    )}
                  </li>
                ))}
            </ul>
          </>
        ) : (
          <p className="text-muted-foreground">No data available.</p>
        )}
      </section>

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3 text-sm">
        <h2 className="text-xl font-semibold">Provider Readiness</h2>
        {(readiness?.blocking_issues?.length ?? 0) > 0 && (
          <ul className="space-y-1 text-destructive">
            {readiness.blocking_issues.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        )}
        {(readiness?.recommendations?.length ?? 0) > 0 && (
          <ul className="space-y-1 text-muted-foreground">
            {readiness.recommendations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        )}
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-border/30 text-muted-foreground text-xs">
                <th className="py-2 pr-3">Provider</th>
                <th className="py-2 pr-3 text-center">Status</th>
                <th className="py-2 pr-3 text-center">Required</th>
                <th className="py-2 pr-3 text-center">Configured</th>
                <th className="py-2 pr-3 text-center">Severity</th>
                <th className="py-2 pr-3">Notes</th>
              </tr>
            </thead>
            <tbody>
              {readiness.providers.map((provider) => (
                <tr key={`ready-${provider.provider}`} className="border-b border-border/10">
                  <td className="py-2 pr-3 font-medium">{provider.provider}</td>
                  <td className="py-2 pr-3 text-center">
                    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                      provider.status === "ready" ? "bg-green-500/10 text-green-500"
                        : provider.status === "degraded" ? "bg-amber-500/10 text-amber-500"
                          : "bg-red-500/10 text-red-500"
                    }`}>
                      {provider.status}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-center">{provider.required ? "Yes" : "No"}</td>
                  <td className="py-2 pr-3 text-center">
                    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                      provider.configured ? "bg-green-500/10 text-green-500" : "bg-red-500/10 text-red-500"
                    }`}>
                      {provider.configured ? "Yes" : "No"}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-center">
                    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                      provider.severity === "critical" ? "bg-red-500/10 text-red-500"
                        : provider.severity === "warning" ? "bg-amber-500/10 text-amber-500"
                          : "bg-blue-500/10 text-blue-500"
                    }`}>
                      {provider.severity}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-muted-foreground text-xs">
                    {provider.missing_env.length > 0 && (
                      <span>Missing: {provider.missing_env.join(", ")}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3 text-sm">
        <h2 className="text-xl font-semibold">Provider Usage</h2>
        <ul className="space-y-3">
          {providers.map((provider) => (
            <li key={provider.id} className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-3">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <span className="font-medium">{provider.provider}</span>
                <span className="flex gap-1.5">
                  <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                    provider.status === "ok" || provider.status === "active" || provider.status === "ready" ? "bg-green-500/10 text-green-500"
                      : provider.status === "degraded" ? "bg-amber-500/10 text-amber-500"
                        : "bg-red-500/10 text-red-500"
                  }`}>
                    {provider.status}
                  </span>
                  <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-muted text-muted-foreground">
                    {provider.kind}
                  </span>
                </span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {provider.actual_current_usage !== null && provider.actual_current_usage !== undefined && (
                  <div>
                    <p className="text-muted-foreground text-xs">Current usage</p>
                    <p className="font-medium">{provider.actual_current_usage} {provider.actual_current_usage_unit ?? ""}</p>
                  </div>
                )}
                {provider.usage_per_time && (
                  <div>
                    <p className="text-muted-foreground text-xs">Usage rate</p>
                    <p className="font-medium">{provider.usage_per_time}</p>
                  </div>
                )}
                {provider.usage_remaining !== null && provider.usage_remaining !== undefined && (
                  <div>
                    <p className="text-muted-foreground text-xs">Remaining</p>
                    <p className="font-medium">{provider.usage_remaining} {provider.usage_remaining_unit ?? ""}</p>
                  </div>
                )}
                {(provider.cost_usd ?? 0) > 0 && (
                  <div>
                    <p className="text-muted-foreground text-xs">Cost</p>
                    <p className="font-medium">${(provider.cost_usd ?? 0).toFixed(2)}</p>
                  </div>
                )}
                {(provider.capacity_tasks_per_day ?? 0) > 0 && (
                  <div>
                    <p className="text-muted-foreground text-xs">Capacity / day</p>
                    <p className="font-medium">{provider.capacity_tasks_per_day}</p>
                  </div>
                )}
              </div>
              {provider.metrics.length > 0 && (
                <div className="space-y-1">
                  {provider.metrics.map((metric) => (
                    <div key={`${provider.id}-${metric.id}`} className="flex justify-between text-xs">
                      <span>{metric.label}</span>
                      <span className="text-muted-foreground">
                        {metric.used}{metric.limit ? ` / ${metric.limit}` : ""}
                        {metric.remaining !== null && metric.remaining !== undefined ? ` (${metric.remaining} remaining)` : ""}
                        {metric.window ? ` -- ${metric.window}` : ""}
                      </span>
                    </div>
                  ))}
                </div>
              )}
              <p className="text-xs text-muted-foreground">Source: {provider.data_source}</p>
              {provider.official_records.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {provider.official_records.map((url) => (
                    <a key={`${provider.id}-${url}`} href={url} target="_blank" rel="noreferrer" className="text-xs underline text-muted-foreground hover:text-foreground">
                      Official record
                    </a>
                  ))}
                </div>
              )}
              {provider.notes.length > 0 && (
                <ul className="space-y-1 text-muted-foreground text-xs">
                  {provider.notes.map((note) => (
                    <li key={`${provider.id}-${note}`}>{note}</li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      </section>

      {networkStats && (Object.keys(networkStats.nodes).length > 0 || networkStats.total_measurements > 0) && (
        <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3 text-sm">
          <h2 className="text-xl font-semibold">Federation Network — Provider Stats by Node</h2>
          <p className="text-muted-foreground">
            {Object.keys(networkStats.nodes).length} node(s) | {networkStats.total_measurements} measurements | {networkStats.window_days}d window
          </p>

          {networkStats.alerts.length > 0 && (
            <div className="rounded-xl border border-amber-500/50 bg-amber-500/10 p-4 space-y-1">
              {networkStats.alerts.map((a, i) => (
                <p key={i} className="text-amber-600 dark:text-amber-400">{a.provider}: {a.message}</p>
              ))}
            </div>
          )}

          {/* Node list */}
          <div className="space-y-2">
            {Object.entries(networkStats.nodes).map(([nodeId, node]) => (
              <div key={nodeId} className="rounded-xl border border-border/20 bg-background/40 p-3">
                <p className="font-medium">
                  <span className={`inline-block w-2 h-2 rounded-full mr-2 ${node.status === "online" ? "bg-green-500" : "bg-gray-400"}`} />
                  {node.hostname} <span className="text-muted-foreground">({node.os_type})</span>
                </p>
                <p className="text-muted-foreground text-xs">
                  ID: {nodeId} | Last seen: {new Date(node.last_seen_at).toLocaleString()}
                </p>
              </div>
            ))}
          </div>

          {/* Provider table per node — stacks vertically on mobile */}
          {/* Desktop table */}
          <div className="hidden md:block overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-border/30 text-muted-foreground">
                  <th className="py-1 pr-3">Provider</th>
                  <th className="py-1 pr-3 text-right">Runs</th>
                  <th className="py-1 pr-3 text-right">Rate</th>
                  <th className="py-1 pr-3 text-right">Avg Speed</th>
                  {Object.keys(networkStats.nodes).map((nodeId) => (
                    <th key={nodeId} className="py-1 pr-3 text-right">{networkStats.nodes[nodeId].hostname.split(".")[0]}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Object.entries(networkStats.providers)
                  .sort(([, a], [, b]) => b.total_samples - a.total_samples)
                  .map(([provider, data]) => (
                  <tr key={provider} className="border-b border-border/30">
                    <td className="py-1 pr-3 font-medium">{provider}</td>
                    <td className="py-1 pr-3 text-right">{data.total_samples}</td>
                    <td className={`py-1 pr-3 text-right ${data.overall_success_rate < 0.5 ? "text-red-500" : data.overall_success_rate < 0.8 ? "text-amber-500" : "text-green-500"}`}>
                      {(data.overall_success_rate * 100).toFixed(0)}%
                    </td>
                    <td className="py-1 pr-3 text-right text-muted-foreground">{data.avg_duration_s.toFixed(0)}s</td>
                    {Object.keys(networkStats.nodes).map((nodeId) => {
                      const nodeData = data.per_node[nodeId];
                      if (!nodeData) return <td key={nodeId} className="py-1 pr-3 text-right text-muted-foreground">—</td>;
                      return (
                        <td key={nodeId} className={`py-1 pr-3 text-right ${nodeData.success_rate < 0.5 ? "text-red-500" : nodeData.success_rate < 0.8 ? "text-amber-500" : ""}`}>
                          {(nodeData.success_rate * 100).toFixed(0)}% <span className="text-muted-foreground">({nodeData.samples})</span>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Mobile stacked cards */}
          <div className="md:hidden space-y-3">
            {Object.entries(networkStats.providers)
              .sort(([, a], [, b]) => b.total_samples - a.total_samples)
              .map(([provider, data]) => (
              <div key={provider} className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-1">
                <p className="font-medium">{provider}</p>
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div>
                    <p className="text-muted-foreground">Runs</p>
                    <p>{data.total_samples}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Rate</p>
                    <p className={data.overall_success_rate < 0.5 ? "text-red-500" : data.overall_success_rate < 0.8 ? "text-amber-500" : "text-green-500"}>
                      {(data.overall_success_rate * 100).toFixed(0)}%
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Avg Speed</p>
                    <p>{data.avg_duration_s.toFixed(0)}s</p>
                  </div>
                </div>
                {Object.keys(networkStats.nodes).map((nodeId) => {
                  const nodeData = data.per_node[nodeId];
                  if (!nodeData) return null;
                  return (
                    <p key={nodeId} className="text-xs">
                      <span className="text-muted-foreground">{networkStats.nodes[nodeId].hostname.split(".")[0]}:</span>{" "}
                      <span className={nodeData.success_rate < 0.5 ? "text-red-500" : nodeData.success_rate < 0.8 ? "text-amber-500" : ""}>
                        {(nodeData.success_rate * 100).toFixed(0)}%
                      </span>{" "}
                      <span className="text-muted-foreground">({nodeData.samples})</span>
                    </p>
                  );
                })}
              </div>
            ))}
          </div>
        </section>
      )}

      {(fleetCapabilities || federationNodes.length > 0) && (
        <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3 text-sm">
          <h2 className="text-xl font-semibold">Federation Node Capability Discovery</h2>
          {fleetCapabilities && (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="rounded-xl border border-border/20 bg-background/40 p-3">
                  <p className="text-muted-foreground text-xs">Nodes</p>
                  <p className="text-lg font-semibold">{fleetCapabilities.total_nodes}</p>
                </div>
                <div className="rounded-xl border border-border/20 bg-background/40 p-3">
                  <p className="text-muted-foreground text-xs">Total CPUs</p>
                  <p className="text-lg font-semibold">{fleetCapabilities.hardware_summary.total_cpus}</p>
                </div>
                <div className="rounded-xl border border-border/20 bg-background/40 p-3">
                  <p className="text-muted-foreground text-xs">Total memory</p>
                  <p className="text-lg font-semibold">{fleetCapabilities.hardware_summary.total_memory_gb} GB</p>
                </div>
                <div className="rounded-xl border border-border/20 bg-background/40 p-3">
                  <p className="text-muted-foreground text-xs">GPU nodes</p>
                  <p className="text-lg font-semibold">{fleetCapabilities.hardware_summary.gpu_capable_nodes}</p>
                </div>
              </div>
              {Object.keys(fleetCapabilities.executors).length > 0 && (
                <div>
                  <p className="text-muted-foreground text-xs mb-1">Executors</p>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(fleetCapabilities.executors).map(([name, data]) => (
                      <span key={name} className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-muted text-muted-foreground">
                        {name} ({data.node_count} nodes)
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {Object.keys(fleetCapabilities.tools).length > 0 && (
                <div>
                  <p className="text-muted-foreground text-xs mb-1">Tools</p>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(fleetCapabilities.tools).map(([name, data]) => (
                      <span key={name} className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-muted text-muted-foreground">
                        {name} ({data.node_count})
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
          <div className="space-y-2">
            {federationNodes
              .sort((a, b) => a.hostname.localeCompare(b.hostname))
              .map((node) => (
                <div key={node.node_id} className="rounded-xl border border-border/20 bg-background/40 p-3 space-y-1">
                  <p className="font-medium">
                    {node.hostname} <span className="text-muted-foreground">({node.os_type})</span>
                  </p>
                  <p className="text-muted-foreground text-xs">
                    ID: {node.node_id} | status: {node.status} | last_seen: {new Date(node.last_seen_at).toLocaleString()}
                  </p>
                  <p>
                    executors:{" "}
                    {node.capabilities?.executors && node.capabilities.executors.length > 0
                      ? node.capabilities.executors.join(", ")
                      : "none"}
                  </p>
                  <p>
                    tools:{" "}
                    {node.capabilities?.tools && node.capabilities.tools.length > 0 ? node.capabilities.tools.join(", ") : "none"}
                  </p>
                  {node.capabilities?.models_by_executor && Object.keys(node.capabilities.models_by_executor).length > 0 && (
                    <ul className="text-muted-foreground text-xs space-y-0.5">
                      {Object.entries(node.capabilities.models_by_executor)
                        .sort(([a], [b]) => a.localeCompare(b))
                        .map(([executor, models]) => (
                          <li key={`${node.node_id}-${executor}`}>
                            models[{executor}]: {models.join(", ")}
                          </li>
                        ))}
                    </ul>
                  )}
                </div>
              ))}
          </div>
        </section>
      )}

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3 text-sm">
        <h2 className="text-xl font-semibold">Capacity Alerts</h2>
        <p className="text-muted-foreground text-xs">Threshold: {(alerts.threshold_ratio * 100).toFixed(0)}% remaining</p>
        <ul className="space-y-2">
          {alerts.alerts.map((alert) => (
            <li key={alert.id} className="rounded-xl border border-border/20 bg-background/40 p-3 space-y-1">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{alert.provider}</span>
                <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                  alert.severity === "critical" ? "bg-red-500/10 text-red-500"
                    : alert.severity === "warning" ? "bg-amber-500/10 text-amber-500"
                      : "bg-blue-500/10 text-blue-500"
                }`}>
                  {alert.severity}
                </span>
              </div>
              <p className="text-muted-foreground text-xs">{alert.message}</p>
              <p className="text-muted-foreground text-xs">Metric: {alert.metric_id}{alert.remaining_ratio !== null && alert.remaining_ratio !== undefined ? ` -- ${(alert.remaining_ratio * 100).toFixed(0)}% remaining` : ""}</p>
            </li>
          ))}
          {(alerts?.alerts?.length ?? 0) === 0 && <li className="text-muted-foreground">No capacity alerts.</li>}
        </ul>
      </section>

        </div>
      </details>

      {/* Where to go next */}
      <nav className="py-8 text-center space-y-2 border-t border-border/20" aria-label="Where to go next">
        <p className="text-xs text-muted-foreground/80 uppercase tracking-wider">Where to go next</p>
        <div className="flex flex-wrap justify-center gap-4 text-sm">
          <Link href="/usage" className="text-amber-600 dark:text-amber-400 hover:underline">Usage</Link>
          <Link href="/flow" className="text-amber-600 dark:text-amber-400 hover:underline">Flow</Link>
          <Link href="/specs" className="text-amber-600 dark:text-amber-400 hover:underline">Specs</Link>
        </div>
      </nav>
    </main>
  );
}
