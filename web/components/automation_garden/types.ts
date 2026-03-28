/** Serializable props for Automation Garden (server → client). */

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

export type ProviderExecStatsResponse = {
  providers: Record<string, ProviderExecStatsEntry>;
  task_types: Record<string, { providers: Record<string, ProviderExecStatsEntry> }>;
  alerts: Array<{ provider: string; metric: string; value: number; threshold: number; message: string }>;
  summary: {
    total_providers: number;
    healthy_providers: number;
    attention_needed: number;
    total_measurements: number;
  };
};

export type NetworkNodeInfo = {
  hostname: string;
  os_type: string;
  status: string;
  last_seen_at: string;
};

export type NetworkStatsResponse = {
  nodes: Record<string, NetworkNodeInfo>;
  providers: Record<
    string,
    {
      node_count: number;
      total_samples: number;
      total_successes: number;
      total_failures: number;
      overall_success_rate: number;
      avg_duration_s: number;
      per_node: Record<
        string,
        { success_rate: number; samples: number; avg_duration_s: number }
      >;
    }
  >;
  alerts: Array<{ provider: string; message: string }>;
  window_days: number;
  total_measurements: number;
};

export type FederationNode = {
  node_id: string;
  hostname: string;
  os_type: string;
  providers: string[];
  capabilities?: {
    executors?: string[];
    tools?: string[];
    models_by_executor?: Record<string, string[]>;
    probed_at?: string;
  };
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

export type AutomationGardenPayload = {
  usage: AutomationUsageResponse;
  alerts: UsageAlertResponse;
  readiness: ProviderReadinessResponse;
  validation: ProviderValidationResponse;
  execStats: ProviderExecStatsResponse | null;
  networkStats: NetworkStatsResponse | null;
  federationNodes: FederationNode[];
  fleetCapabilities: FleetCapabilitiesResponse | null;
};
