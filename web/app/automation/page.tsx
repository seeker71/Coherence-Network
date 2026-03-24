import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "Automation",
  description: "Provider automation readiness and subscription status.",
};

type UsageMetric = {
  id: string;
  label: string;
  unit: string;
  used: number;
  remaining?: number | null;
  limit?: number | null;
  window?: string | null;
};

type ProviderSnapshot = {
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

type AutomationUsageResponse = {
  generated_at: string;
  providers: ProviderSnapshot[];
  unavailable_providers: string[];
  tracked_providers: number;
  limit_coverage?: {
    providers_considered: number;
    providers_with_limit_metrics: number;
    providers_with_remaining_metrics: number;
    providers_missing_limit_metrics: string[];
    providers_partial_limit_metrics: string[];
    coverage_ratio: number;
  };
};

type UsageAlert = {
  id: string;
  provider: string;
  metric_id: string;
  severity: string;
  message: string;
  remaining_ratio?: number | null;
  created_at: string;
};

type UsageAlertResponse = {
  generated_at: string;
  threshold_ratio: number;
  alerts: UsageAlert[];
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

type ProviderExecStatsAlert = {
  provider: string;
  metric: string;
  value: number;
  threshold: number;
  message: string;
};

type ProviderExecStatsSummary = {
  total_providers: number;
  healthy_providers: number;
  attention_needed: number;
  total_measurements: number;
};

type ProviderExecStatsResponse = {
  providers: Record<string, ProviderExecStatsEntry>;
  task_types: Record<string, { providers: Record<string, ProviderExecStatsEntry> }>;
  alerts: ProviderExecStatsAlert[];
  summary: ProviderExecStatsSummary;
};

type NetworkNodeInfo = {
  hostname: string;
  os_type: string;
  status: string;
  last_seen_at: string;
};

type NetworkProviderNode = {
  success_rate: number;
  samples: number;
  avg_duration_s: number;
};

type NetworkProvider = {
  node_count: number;
  total_samples: number;
  total_successes: number;
  total_failures: number;
  overall_success_rate: number;
  avg_duration_s: number;
  per_node: Record<string, NetworkProviderNode>;
};

type NetworkStatsResponse = {
  nodes: Record<string, NetworkNodeInfo>;
  providers: Record<string, NetworkProvider>;
  alerts: Array<{ provider: string; message: string }>;
  window_days: number;
  total_measurements: number;
};

type FederationNodeCapabilities = {
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

type FederationNode = {
  node_id: string;
  hostname: string;
  os_type: string;
  providers: string[];
  capabilities: FederationNodeCapabilities;
  registered_at: string;
  last_seen_at: string;
  status: string;
};

type FleetCapabilitiesResponse = {
  total_nodes: number;
  executors: Record<string, { node_count: number; node_ids: string[] }>;
  tools: Record<string, { node_count: number }>;
  hardware_summary: {
    total_cpus: number;
    total_memory_gb: number;
    gpu_capable_nodes: number;
  };
};

type ProviderValidationRow = {
  provider: string;
  configured: boolean;
  readiness_status: string;
  usage_events: number;
  successful_events: number;
  validated_execution: boolean;
  last_event_at?: string | null;
  notes: string[];
};

type ProviderValidationResponse = {
  generated_at: string;
  required_providers: string[];
  runtime_window_seconds: number;
  min_execution_events: number;
  all_required_validated: boolean;
  blocking_issues: string[];
  providers: ProviderValidationRow[];
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
    readiness: readinessRes?.ok ? ((await readinessRes.json()) as ProviderReadinessResponse) : ({ providers: [], ready: true, generated_at: "" } as unknown as ProviderReadinessResponse),
    validation: validationRes?.ok ? ((await validationRes.json()) as ProviderValidationResponse) : ({ providers: [], generated_at: "" } as unknown as ProviderValidationResponse),
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
          A live view of provider adapters, capacity metrics, and threshold alerts. Use this to plan automation runs and spot bottlenecks early.
        </p>
      </div>

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 text-sm space-y-2">
        <p className="text-muted-foreground">
          providers {usage.tracked_providers} | unavailable {(usage?.unavailable_providers?.length ?? 0)} | alerts {(alerts?.alerts?.length ?? 0)}
        </p>
        <p className="text-muted-foreground">
          {"required_providers "}{readiness?.required_providers?.length ?? 0}{" | all_required_ready "}{readiness?.all_required_ready ? "yes" : "no"}{" | "}
          {"blocking "}{readiness?.blocking_issues?.length ?? 0}
        </p>
        <p className="text-muted-foreground">
          {"validation_required "}{validation?.required_providers?.length ?? 0}{" | all_required_validated "}{validation?.all_required_validated ? "yes" : "no"}{" | "}
          {"blocking "}{validation?.blocking_issues?.length ?? 0}
        </p>
        {usage.limit_coverage && (
          <p className="text-muted-foreground">
            limit_coverage {Math.round((usage.limit_coverage.coverage_ratio ?? 0) * 100)}% | with_limit{" "}
            {usage.limit_coverage.providers_with_limit_metrics}/{usage.limit_coverage.providers_considered} | with_remaining{" "}
            {usage.limit_coverage.providers_with_remaining_metrics}
          </p>
        )}
      </section>

      {usage.limit_coverage && (
        <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-2 text-sm">
          <h2 className="text-xl font-semibold">Usage Limit Coverage</h2>
          {usage.limit_coverage.providers_missing_limit_metrics.length > 0 && (
            <p className="text-muted-foreground">
              missing_limit_metrics {usage.limit_coverage.providers_missing_limit_metrics.join(", ")}
            </p>
          )}
          {usage.limit_coverage.providers_partial_limit_metrics.length > 0 && (
            <p className="text-muted-foreground">
              partial_limit_metrics {usage.limit_coverage.providers_partial_limit_metrics.join(", ")}
            </p>
          )}
        </section>
      )}

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3 text-sm">
        <h2 className="text-xl font-semibold">Provider Validation Contract</h2>
        <p className="text-muted-foreground">
          runtime_window_seconds {validation.runtime_window_seconds} | min_execution_events {validation.min_execution_events}
        </p>
        {(validation?.blocking_issues?.length ?? 0) > 0 && (
          <ul className="space-y-1 text-destructive">
            {validation.blocking_issues.map((item) => (
              <li key={`validation-block-${item}`}>{item}</li>
            ))}
          </ul>
        )}
        <ul className="space-y-2">
          {validation.providers.map((provider) => (
            <li key={`validation-${provider.provider}`} className="rounded-xl border border-border/20 bg-background/40 p-3">
              <p>
                {provider.provider} | configured {provider.configured ? "yes" : "no"} | readiness {provider.readiness_status} | usage_events{" "}
                {provider.usage_events} | successful_events {provider.successful_events} | validated_execution{" "}
                {provider.validated_execution ? "yes" : "no"}
              </p>
              {provider.notes.length > 0 && (
                <ul className="space-y-1 text-muted-foreground">
                  {provider.notes.map((note) => (
                    <li key={`validation-note-${provider.provider}-${note}`}>{note}</li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3 text-sm">
        <h2 className="text-xl font-semibold">Provider Execution Stats</h2>
        {execStats ? (
          <>
            <p className="text-muted-foreground">
              {execStats.summary.healthy_providers}/{execStats.summary.total_providers} healthy | {execStats.summary.attention_needed} need attention | {execStats.summary.total_measurements} measurements
            </p>
            <ul className="space-y-2">
              {Object.entries(execStats.providers)
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([name, entry]) => (
                  <li
                    key={`exec-${name}`}
                    className={`rounded-xl border p-3 ${entry.blocked ? "border-red-500/50 bg-red-500/5" : "border-border/20 bg-background/40"}`}
                  >
                    <p>
                      <span className="font-medium">{name}</span>
                      {entry.blocked && <span className="ml-2 text-red-600 dark:text-red-400 font-medium">[BLOCKED]</span>}
                      {" "}| overall {(entry.success_rate * 100).toFixed(0)}%
                      {" "}| last_5{" "}
                      <span
                        className={
                          entry.last_5_rate < 0.5
                            ? "text-red-600 dark:text-red-400"
                            : entry.last_5_rate < 0.8
                              ? "text-amber-600 dark:text-amber-400"
                              : ""
                        }
                      >
                        {(entry.last_5_rate * 100).toFixed(0)}%
                      </span>
                      {" "}| runs {entry.total_runs} ({entry.successes}ok {entry.failures}fail)
                      {" "}| avg {entry.avg_duration_s.toFixed(1)}s
                    </p>
                    <p className="text-muted-foreground">
                      selection_probability {(entry.selection_probability * 100).toFixed(1)}%
                      {entry.needs_attention && (
                        <span className="ml-2 text-amber-600 dark:text-amber-400">needs attention</span>
                      )}
                    </p>
                    {Object.keys(entry.error_breakdown).length > 0 && (
                      <ul className="mt-1 space-y-0.5 text-muted-foreground">
                        {Object.entries(entry.error_breakdown).map(([errClass, count]) => (
                          <li key={`exec-err-${name}-${errClass}`}>
                            error: {errClass} x{count}
                          </li>
                        ))}
                      </ul>
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
        <ul className="space-y-2">
          {readiness.providers.map((provider) => (
            <li key={`ready-${provider.provider}`} className="rounded-xl border border-border/20 bg-background/40 p-3">
              <p>
                {provider.provider} | status {provider.status} | required {provider.required ? "yes" : "no"} | configured{" "}
                {provider.configured ? "yes" : "no"} | severity {provider.severity}
              </p>
              {provider.missing_env.length > 0 && (
                <p className="text-muted-foreground">missing_env {provider.missing_env.join(", ")}</p>
              )}
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3 text-sm">
        <h2 className="text-xl font-semibold">Provider Usage</h2>
        <ul className="space-y-3">
          {providers.map((provider) => (
            <li key={provider.id} className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-2">
              <p className="font-medium">
                {provider.provider} | status {provider.status} | kind {provider.kind}
              </p>
              <p className="text-muted-foreground">
                source {provider.data_source} | current_usage{" "}
                {provider.actual_current_usage !== null && provider.actual_current_usage !== undefined
                  ? `${provider.actual_current_usage} ${provider.actual_current_usage_unit ?? ""}`.trim()
                  : "n/a"}{" "}
                | usage_per_time {provider.usage_per_time ?? "n/a"} | remaining{" "}
                {provider.usage_remaining !== null && provider.usage_remaining !== undefined
                  ? `${provider.usage_remaining} ${provider.usage_remaining_unit ?? ""}`.trim()
                  : "n/a"}
              </p>
              <ul className="space-y-1">
                {provider.metrics.map((metric) => (
                  <li key={`${provider.id}-${metric.id}`} className="flex justify-between">
                    <span>{metric.label}</span>
                    <span className="text-muted-foreground">
                      used {metric.used}
                      {metric.limit ? ` / ${metric.limit}` : ""}
                      {metric.remaining !== null && metric.remaining !== undefined ? ` | remaining ${metric.remaining}` : ""}
                      {metric.window ? ` | ${metric.window}` : ""}
                    </span>
                  </li>
                ))}
                {provider.metrics.length === 0 && (
                  <li className="text-muted-foreground">No metrics available for this provider.</li>
                )}
              </ul>
              <p className="text-muted-foreground">
                cost_usd {provider.cost_usd ?? 0} | capacity_tasks_per_day {provider.capacity_tasks_per_day ?? 0}
              </p>
              {provider.official_records.length > 0 && (
                <ul className="space-y-1 text-muted-foreground">
                  {provider.official_records.map((url) => (
                    <li key={`${provider.id}-${url}`}>
                      <a href={url} target="_blank" rel="noreferrer" className="underline">
                        official record
                      </a>{" "}
                      {url}
                    </li>
                  ))}
                </ul>
              )}
              {provider.notes.length > 0 && (
                <ul className="space-y-1 text-muted-foreground">
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
              <p className="text-muted-foreground">
                nodes {fleetCapabilities.total_nodes} | total_cpu {fleetCapabilities.hardware_summary.total_cpus} | total_memory_gb{" "}
                {fleetCapabilities.hardware_summary.total_memory_gb} | gpu_nodes {fleetCapabilities.hardware_summary.gpu_capable_nodes}
              </p>
              <p className="text-muted-foreground">
                executors{" "}
                {Object.entries(fleetCapabilities.executors)
                  .map(([name, data]) => `${name}(${data.node_count})`)
                  .join(", ") || "none"}
              </p>
              <p className="text-muted-foreground">
                tools{" "}
                {Object.entries(fleetCapabilities.tools)
                  .map(([name, data]) => `${name}(${data.node_count})`)
                  .join(", ") || "none"}
              </p>
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
        <p className="text-muted-foreground">threshold_ratio {alerts.threshold_ratio}</p>
        <ul className="space-y-2">
          {alerts.alerts.map((alert) => (
            <li key={alert.id} className="rounded-xl border border-border/20 bg-background/40 p-3 flex justify-between gap-3">
              <span>
                {alert.provider} | {alert.metric_id} | {alert.severity}
              </span>
              <span className="text-muted-foreground">{alert.message}</span>
            </li>
          ))}
          {(alerts?.alerts?.length ?? 0) === 0 && <li className="text-muted-foreground">No capacity alerts.</li>}
        </ul>
      </section>

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
