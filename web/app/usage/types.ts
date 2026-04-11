import { UI_RUNTIME_SUMMARY_WINDOW } from "@/lib/egress";

export type RuntimeIdeaRow = {
  idea_id: string;
  event_count: number;
  total_runtime_ms: number;
  average_runtime_ms: number;
  runtime_cost_estimate: number;
  by_source: Record<string, number>;
};

export type RuntimeSummaryResponse = {
  window_seconds: number;
  limit?: number;
  offset?: number;
  ideas: RuntimeIdeaRow[];
};

export type FrictionReportRow = {
  key: string;
  count: number;
  energy_loss: number;
  cost_of_delay?: number;
};

export type FrictionEntryPoint = {
  key: string;
  event_count: number;
  energy_loss: number;
  cost_of_delay: number;
  status: string;
};

export type RuntimeEvent = {
  id: string;
  idea_id?: string | null;
  origin_idea_id?: string | null;
  source: string;
  runtime_ms: number;
  runtime_cost_estimate: number;
};

export type WebViewPerformanceRow = {
  route: string;
  views: number;
  p50_render_ms: number;
  p95_render_ms: number;
  average_api_call_count: number;
  average_api_endpoint_count: number;
  average_api_runtime_ms: number;
  average_api_runtime_cost_estimate: number;
};

export type WebViewPerformanceReport = {
  window_seconds: number;
  rows: WebViewPerformanceRow[];
};

export type DailySummaryProviderRow = {
  provider: string;
  status: string;
  data_source: string;
  usage: {
    label: string;
    used: number;
    unit: string;
    remaining?: number | null;
    limit?: number | null;
    window?: string | null;
    validation_state?: string | null;
    validation_detail?: string | null;
    evidence_source?: string | null;
  } | null;
  notes: string[];
};

export type DailySummaryTopTool = {
  tool: string;
  events: number;
  failed: number;
  active_failed?: number;
  recent_success_streak?: number;
  success_streak_target?: number;
  failure_recovered?: boolean;
};

export type DailySummaryAttentionRow = {
  endpoint: string;
  events: number;
  attention_score: number;
  runtime_cost_estimate: number;
  friction_event_count: number;
  needs_attention?: boolean;
  recent_success_streak?: number;
  success_streak_target?: number;
  failure_recovered?: boolean;
};

export type DailySummaryQualityHotspot = {
  kind: string;
  path: string;
  line_count?: number;
  line?: number;
  function?: string;
  forbidden_import?: string;
  detail: string;
};

export type DailySummaryQualityTask = {
  task_id: string;
  title: string;
  priority: string;
  roi_estimate: number;
  direction: string;
};

export type DailySummary = {
  generated_at: string;
  window_hours: number;
  host_runner: {
    total_runs: number;
    failed_runs: number;
    completed_runs: number;
    running_runs: number;
    pending_runs: number;
    by_task_type: Record<string, Record<string, number>>;
  };
  execution: {
    tracked_runs: number;
    failed_runs: number;
    success_runs: number;
    coverage: {
      coverage_rate?: number;
      completed_or_failed_tasks?: number;
      tracked_task_runs?: number;
    };
  };
  tool_usage: {
    worker_events: number;
    worker_failed_events: number;
    worker_failed_events_raw?: number;
    worker_failed_events_recoverable?: number;
    recovery_success_streak_target?: number;
    top_tools: DailySummaryTopTool[];
  };
  friction: {
    total_events: number;
    open_events: number;
    top_block_types: FrictionReportRow[];
    top_stages: FrictionReportRow[];
    entry_points: FrictionEntryPoint[];
  };
  providers: DailySummaryProviderRow[];
  top_attention_areas: DailySummaryAttentionRow[];
  contract_gaps: string[];
  quality_awareness: {
    status: string;
    generated_at: string;
    intent_focus: string[];
    summary: {
      severity: string;
      risk_score: number;
      regression: boolean;
      regression_reasons: string[];
      python_module_count: number;
      runtime_file_count: number;
      layer_violations: number;
      large_modules: number;
      very_large_modules: number;
      long_functions: number;
      placeholder_findings: number;
    };
    hotspots: DailySummaryQualityHotspot[];
    guidance: string[];
    recommended_tasks: DailySummaryQualityTask[];
  };
};

export type CompactUsageMetric = {
  label?: string;
  used?: number;
  unit?: string;
  remaining?: number | null;
  limit?: number | null;
  window?: string | null;
  validation_state?: string | null;
  validation_detail?: string | null;
  evidence_source?: string | null;
};

export type CompactUsageProvider = {
  provider: string;
  status: string;
  data_source: string;
  metrics?: CompactUsageMetric[];
  notes?: string[];
};

export type CompactUsageResponse = {
  providers: CompactUsageProvider[];
};

export type UsageSearchParams = Promise<{
  page?: string | string[];
  page_size?: string | string[];
}>;

export type RuntimeSlice = {
  runtime: RuntimeSummaryResponse;
  hasMore: boolean;
  warnings: string[];
};

import { loadPublicWebConfig } from "@/lib/app-config";

export const API_REVALIDATE_SECONDS = 60;
// Falls back to the shared web config so deploys can tune this via
// NEXT_PUBLIC_FETCH_TIMEOUT_MS or api/config/api.json → web.fetch_defaults.
export const FETCH_TIMEOUT_MS = loadPublicWebConfig().fetchDefaults.timeoutMs;
export const RUNTIME_SUMMARY_TIMEOUT_MS = 2500;
export const RUNTIME_EVENTS_FALLBACK_TIMEOUT_MS = 2500;
export const DAILY_SUMMARY_TIMEOUT_MS = 3500;
export const PROVIDER_SNAPSHOT_FALLBACK_TIMEOUT_MS = 2500;
export const VIEW_PERFORMANCE_TIMEOUT_MS = 3000;
export const DEFAULT_PAGE_SIZE = 20;
export const MAX_PAGE_SIZE = 50;

export const DEFAULT_RUNTIME: RuntimeSummaryResponse = {
  window_seconds: UI_RUNTIME_SUMMARY_WINDOW,
  ideas: [],
};

export const DEFAULT_DAILY_SUMMARY: DailySummary = {
  generated_at: "",
  window_hours: 24,
  host_runner: {
    total_runs: 0,
    failed_runs: 0,
    completed_runs: 0,
    running_runs: 0,
    pending_runs: 0,
    by_task_type: {},
  },
  execution: {
    tracked_runs: 0,
    failed_runs: 0,
    success_runs: 0,
    coverage: {},
  },
  tool_usage: {
    worker_events: 0,
    worker_failed_events: 0,
    top_tools: [],
  },
  friction: {
    total_events: 0,
    open_events: 0,
    top_block_types: [],
    top_stages: [],
    entry_points: [],
  },
  providers: [],
  top_attention_areas: [],
  contract_gaps: [],
  quality_awareness: {
    status: "unavailable",
    generated_at: "",
    intent_focus: ["trust", "clarity", "reuse"],
    summary: {
      severity: "unknown",
      risk_score: 0,
      regression: false,
      regression_reasons: [],
      python_module_count: 0,
      runtime_file_count: 0,
      layer_violations: 0,
      large_modules: 0,
      very_large_modules: 0,
      long_functions: 0,
      placeholder_findings: 0,
    },
    hotspots: [],
    guidance: [],
    recommended_tasks: [],
  },
};
