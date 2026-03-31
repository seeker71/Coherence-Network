import { getApiBase } from "@/lib/api";

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

export type AutomationUsageResponse = {
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

export type UsageAlert = {
  id: string;
  provider: string;
  metric_id: string;
  severity: string;
  message: string;
  remaining_ratio?: number | null;
  created_at: string;
};

export type UsageAlertResponse = {
  generated_at: string;
  threshold_ratio: number;
  alerts: UsageAlert[];
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

export type ProviderReadinessResponse = {
  generated_at: string;
  required_providers: string[];
  all_required_ready: boolean;
  blocking_issues: string[];
  recommendations: string[];
  providers: ProviderReadinessRow[];
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

export type ProviderExecStatsAlert = {
  provider: string;
  metric: string;
  value: number;
  threshold: number;
  message: string;
};

export type ProviderExecStatsSummary = {
  total_providers: number;
  healthy_providers: number;
  attention_needed: number;
  total_measurements: number;
};

export type ProviderExecStatsResponse = {
  providers: Record<string, ProviderExecStatsEntry>;
  task_types: Record<string, { providers: Record<string, ProviderExecStatsEntry> }>;
  alerts: ProviderExecStatsAlert[];
  summary: ProviderExecStatsSummary;
};

export type NetworkNodeInfo = {
  hostname: string;
  os_type: string;
  status: string;
  last_seen_at: string;
};

export type NetworkProviderNode = {
  success_rate: number;
  samples: number;
  avg_duration_s: number;
};

export type NetworkProvider = {
  node_count: number;
  total_samples: number;
  total_successes: number;
  total_failures: number;
  overall_success_rate: number;
  avg_duration_s: number;
  per_node: Record<string, NetworkProviderNode>;
};

export type NetworkStatsResponse = {
  nodes: Record<string, NetworkNodeInfo>;
  providers: Record<string, NetworkProvider>;
  alerts: Array<{ provider: string; message: string }>;
  window_days: number;
  total_measurements: number;
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

export type FleetCapabilitiesResponse = {
  total_nodes: number;
  executors: Record<string, { node_count: number; node_ids: string[] }>;
  tools: Record<string, { node_count: number }>;
  hardware_summary: {
    total_cpus: number;
    total_memory_gb: number;
    gpu_capable_nodes: number;
  };
};

export type ProviderValidationRow = {
  provider: string;
  configured: boolean;
  readiness_status: string;
  usage_events: number;
  successful_events: number;
  validated_execution: boolean;
  last_event_at?: string | null;
  notes: string[];
};

export type ProviderValidationResponse = {
  generated_at: string;
  required_providers: string[];
  runtime_window_seconds: number;
  min_execution_events: number;
  all_required_validated: boolean;
  blocking_issues: string[];
  providers: ProviderValidationRow[];
};

export type AutomationPagePayload = {
  usage: AutomationUsageResponse;
  alerts: UsageAlertResponse;
  readiness: ProviderReadinessResponse;
  validation: ProviderValidationResponse;
  execStats: ProviderExecStatsResponse | null;
  networkStats: NetworkStatsResponse | null;
  federationNodes: FederationNode[];
  fleetCapabilities: FleetCapabilitiesResponse | null;
};

export async function loadAutomationData(): Promise<AutomationPagePayload> {
  const api = getApiBase();
  const [
    usageRes,
    alertsRes,
    readinessRes,
    validationRes,
    execStatsRes,
    networkStatsRes,
    federationNodesRes,
    fleetCapsRes,
  ] = await Promise.all([
    fetch(`${api}/api/automation/usage?force_refresh=true`, { cache: "no-store" }),
    fetch(`${api}/api/automation/usage/alerts?threshold_ratio=0.2`, { cache: "no-store" }).catch(() => null),
    fetch(`${api}/api/automation/usage/readiness?force_refresh=true`, { cache: "no-store" }).catch(() => null),
    fetch(
      `${api}/api/automation/usage/provider-validation?runtime_window_seconds=86400&min_execution_events=1&force_refresh=true`,
      { cache: "no-store" },
    ).catch(() => null),
    fetch(`${api}/api/providers/stats`, { cache: "no-store" }).catch(() => null),
    fetch(`${api}/api/federation/nodes/stats`, { cache: "no-store" }).catch(() => null),
    fetch(`${api}/api/federation/nodes`, { cache: "no-store" }).catch(() => null),
    fetch(`${api}/api/federation/nodes/capabilities`, { cache: "no-store" }).catch(() => null),
  ]);
  if (!usageRes.ok) {
    throw new Error(`automation usage HTTP ${usageRes.status}`);
  }
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
    alerts: alertsRes?.ok
      ? ((await alertsRes.json()) as UsageAlertResponse)
      : ({ alerts: [], generated_at: "", threshold_ratio: 0.2 } as UsageAlertResponse),
    readiness: readinessRes?.ok
      ? ((await readinessRes.json()) as ProviderReadinessResponse)
      : ({
          providers: [],
          all_required_ready: true,
          generated_at: "",
          required_providers: [],
          blocking_issues: [],
          recommendations: [],
        } as ProviderReadinessResponse),
    validation: validationRes?.ok
      ? ((await validationRes.json()) as ProviderValidationResponse)
      : ({
          providers: [],
          generated_at: "",
          required_providers: [],
          runtime_window_seconds: 86400,
          min_execution_events: 1,
          all_required_validated: false,
          blocking_issues: [],
        } as ProviderValidationResponse),
    execStats,
    networkStats,
    federationNodes,
    fleetCapabilities,
  };
}

export type BrookItem = {
  id: string;
  at: string;
  title: string;
  detail: string;
  accent: "pulse" | "alert" | "node" | "metric";
};

/** Build chronological stream items for the activity brook (newest first). */
export function buildActivityBrookItems(payload: AutomationPagePayload): BrookItem[] {
  const { usage, alerts, readiness, validation, execStats, networkStats, federationNodes } = payload;
  const items: BrookItem[] = [];

  items.push({
    id: "usage-snapshot",
    at: usage.generated_at,
    title: "Meadow refreshed",
    detail: `${usage.tracked_providers} provider track${usage.tracked_providers === 1 ? "" : "s"} · ${usage.unavailable_providers.length} unavailable`,
    accent: "pulse",
  });

  if (readiness.generated_at) {
    items.push({
      id: "readiness-snapshot",
      at: readiness.generated_at,
      title: "Readiness scan",
      detail: readiness.all_required_ready ? "All required providers ready" : `${readiness.blocking_issues.length} blocking issue(s)`,
      accent: "metric",
    });
  }

  if (validation.generated_at) {
    items.push({
      id: "validation-snapshot",
      at: validation.generated_at,
      title: "Validation contract",
      detail: validation.all_required_validated ? "Execution validated" : `${validation.blocking_issues.length} blocking issue(s)`,
      accent: "metric",
    });
  }

  if (execStats?.summary) {
    items.push({
      id: "exec-summary",
      at: usage.generated_at,
      title: "Execution pulse",
      detail: `${execStats.summary.healthy_providers}/${execStats.summary.total_providers} healthy · ${execStats.summary.total_measurements} measurements`,
      accent: "metric",
    });
  }

  for (const a of alerts.alerts) {
    items.push({
      id: `alert-${a.id}`,
      at: a.created_at || alerts.generated_at || usage.generated_at,
      title: `${a.provider} · ${a.severity}`,
      detail: a.message,
      accent: "alert",
    });
  }

  for (const node of federationNodes) {
    items.push({
      id: `node-${node.node_id}`,
      at: node.last_seen_at,
      title: `Node ${node.hostname}`,
      detail: `${node.status} · last seen`,
      accent: "node",
    });
  }

  if (networkStats) {
    for (const [id, n] of Object.entries(networkStats.nodes)) {
      items.push({
        id: `net-node-${id}`,
        at: n.last_seen_at,
        title: `Network ${n.hostname}`,
        detail: `${n.status} · ${id.slice(0, 8)}…`,
        accent: "node",
      });
    }
  }

  const t = (s: string) => {
    const x = Date.parse(s);
    return Number.isFinite(x) ? x : 0;
  };

  return items.sort((a, b) => t(b.at) - t(a.at)).slice(0, 28);
}
