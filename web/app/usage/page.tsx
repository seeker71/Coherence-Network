import Link from "next/link";

import { getApiBase } from "@/lib/api";
import {
  UI_RUNTIME_SUMMARY_WINDOW,
} from "@/lib/egress";

export const revalidate = 15;

type RuntimeIdeaRow = {
  idea_id: string;
  event_count: number;
  total_runtime_ms: number;
  average_runtime_ms: number;
  runtime_cost_estimate: number;
  by_source: Record<string, number>;
};

type RuntimeSummaryResponse = {
  window_seconds: number;
  limit?: number;
  offset?: number;
  ideas: RuntimeIdeaRow[];
};

type FrictionReportRow = {
  key: string;
  count: number;
  energy_loss: number;
  cost_of_delay?: number;
};

type FrictionEntryPoint = {
  key: string;
  event_count: number;
  energy_loss: number;
  cost_of_delay: number;
  status: string;
};

type RuntimeEvent = {
  id: string;
  idea_id?: string | null;
  origin_idea_id?: string | null;
  source: string;
  runtime_ms: number;
  runtime_cost_estimate: number;
};

type WebViewPerformanceRow = {
  route: string;
  views: number;
  p50_render_ms: number;
  p95_render_ms: number;
  average_api_call_count: number;
  average_api_endpoint_count: number;
  average_api_runtime_ms: number;
  average_api_runtime_cost_estimate: number;
};

type WebViewPerformanceReport = {
  window_seconds: number;
  rows: WebViewPerformanceRow[];
};

type DailySummaryProviderRow = {
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

type DailySummaryTopTool = {
  tool: string;
  events: number;
  failed: number;
};

type DailySummaryAttentionRow = {
  endpoint: string;
  events: number;
  attention_score: number;
  runtime_cost_estimate: number;
  friction_event_count: number;
};

type DailySummaryQualityHotspot = {
  kind: string;
  path: string;
  line_count?: number;
  line?: number;
  function?: string;
  forbidden_import?: string;
  detail: string;
};

type DailySummaryQualityTask = {
  task_id: string;
  title: string;
  priority: string;
  roi_estimate: number;
  direction: string;
};

type DailySummary = {
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

type UsageSearchParams = Promise<{
  page?: string | string[];
  page_size?: string | string[];
}>;

type RuntimeSlice = {
  runtime: RuntimeSummaryResponse;
  hasMore: boolean;
  warnings: string[];
};

const FETCH_TIMEOUT_MS = 12000;
const DEFAULT_PAGE_SIZE = 20;
const MAX_PAGE_SIZE = 50;

const DEFAULT_RUNTIME: RuntimeSummaryResponse = {
  window_seconds: UI_RUNTIME_SUMMARY_WINDOW,
  ideas: [],
};

const DEFAULT_DAILY_SUMMARY: DailySummary = {
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

function normalizeValue(raw: string | string[] | undefined): string {
  if (Array.isArray(raw)) return (raw[0] || "").trim();
  return (raw || "").trim();
}

function parsePositiveInt(raw: string | string[] | undefined, fallback: number): number {
  const parsed = Number.parseInt(normalizeValue(raw), 10);
  if (!Number.isFinite(parsed) || parsed < 1) return fallback;
  return parsed;
}

async function fetchJsonOrNull<T>(
  url: string,
  initOrTimeout: RequestInit | number = {},
  timeoutMs = FETCH_TIMEOUT_MS,
): Promise<T | null> {
  const init = typeof initOrTimeout === "number" ? {} : initOrTimeout;
  const effectiveTimeoutMs = typeof initOrTimeout === "number" ? initOrTimeout : timeoutMs;
  const controller = new AbortController();
  const timeoutId = setTimeout(
    () => controller.abort(new DOMException("Request timed out", "TimeoutError")),
    effectiveTimeoutMs,
  );
  try {
    const res = await fetch(url, { cache: "force-cache", ...init, signal: controller.signal });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  } finally {
    clearTimeout(timeoutId);
  }
}

function summarizeRuntimeEvents(
  rows: RuntimeEvent[],
  pageSize: number,
  offset: number,
): { runtime: RuntimeSummaryResponse; hasMore: boolean } {
  const grouped = new Map<string, RuntimeIdeaRow>();
  for (const row of rows) {
    const key = String(row.idea_id || row.origin_idea_id || "unmapped").trim() || "unmapped";
    const existing = grouped.get(key) || {
      idea_id: key,
      event_count: 0,
      total_runtime_ms: 0,
      average_runtime_ms: 0,
      runtime_cost_estimate: 0,
      by_source: {},
    };
    existing.event_count += 1;
    existing.total_runtime_ms += Number(row.runtime_ms || 0);
    existing.runtime_cost_estimate += Number(row.runtime_cost_estimate || 0);
    existing.by_source[row.source] = (existing.by_source[row.source] || 0) + 1;
    grouped.set(key, existing);
  }

  const sorted = [...grouped.values()]
    .map((entry) => ({
      ...entry,
      total_runtime_ms: Number(entry.total_runtime_ms.toFixed(4)),
      runtime_cost_estimate: Number(entry.runtime_cost_estimate.toFixed(8)),
      average_runtime_ms:
        entry.event_count > 0 ? Number((entry.total_runtime_ms / entry.event_count).toFixed(4)) : 0,
    }))
    .sort((a, b) => b.runtime_cost_estimate - a.runtime_cost_estimate);

  const sliced = sorted.slice(offset, offset + pageSize);
  return {
    runtime: {
      window_seconds: 3600,
      offset,
      limit: pageSize,
      ideas: sliced,
    },
    hasMore: offset + pageSize < sorted.length,
  };
}

async function loadRuntimeSlice(apiBase: string, pageSize: number, offset: number): Promise<RuntimeSlice> {
  const warnings: string[] = [];
  const attempts = [UI_RUNTIME_SUMMARY_WINDOW, 3600, 900];
  for (const seconds of attempts) {
    const params = new URLSearchParams({
      seconds: String(seconds),
      limit: String(pageSize),
      offset: String(offset),
    });
    const payload = await fetchJsonOrNull<RuntimeSummaryResponse>(
      `${apiBase}/api/runtime/ideas/summary?${params.toString()}`,
      9000,
    );
    if (payload && Array.isArray(payload.ideas)) {
      return {
        runtime: payload,
        hasMore: payload.ideas.length >= pageSize,
        warnings,
      };
    }
    warnings.push(`runtime summary (${seconds}s)`);
  }

  const fallbackEvents = await fetchJsonOrNull<RuntimeEvent[]>(
    `${apiBase}/api/runtime/events?limit=${Math.max(200, pageSize * 8)}`,
    7000,
  );
  if (fallbackEvents && Array.isArray(fallbackEvents)) {
    const fallback = summarizeRuntimeEvents(fallbackEvents, pageSize, offset);
    warnings.push("runtime summary fallback to recent runtime events");
    return {
      runtime: fallback.runtime,
      hasMore: fallback.hasMore,
      warnings,
    };
  }

  warnings.push("runtime telemetry unavailable");
  return {
    runtime: {
      ...DEFAULT_RUNTIME,
      offset,
      limit: pageSize,
    },
    hasMore: false,
    warnings,
  };
}

async function loadDailySummary(apiBase: string): Promise<{ summary: DailySummary; warnings: string[] }> {
  const summary = await fetchJsonOrNull<DailySummary>(
    `${apiBase}/api/automation/usage/daily-summary?window_hours=24&top_n=8`,
    { cache: "no-store" },
    10000,
  );
  if (summary) {
    return { summary, warnings: [] };
  }
  return { summary: DEFAULT_DAILY_SUMMARY, warnings: ["daily usage summary unavailable"] };
}

async function loadViewPerformance(apiBase: string): Promise<WebViewPerformanceReport | null> {
  const params = new URLSearchParams({
    seconds: String(UI_RUNTIME_SUMMARY_WINDOW),
    limit: "12",
  });
  return fetchJsonOrNull<WebViewPerformanceReport>(
    `${apiBase}/api/runtime/web/views/summary?${params.toString()}`,
    { cache: "no-store" },
    7000,
  );
}

export default async function UsagePage({ searchParams }: { searchParams: UsageSearchParams }) {
  const resolved = await searchParams;
  const pageSize = Math.max(1, Math.min(parsePositiveInt(resolved.page_size, DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE));
  const page = parsePositiveInt(resolved.page, 1);
  const offset = (page - 1) * pageSize;

  const API = getApiBase();
  const [runtimeSlice, dailySummaryResult, viewPerformance] = await Promise.all([
    loadRuntimeSlice(API, pageSize, offset),
    loadDailySummary(API),
    loadViewPerformance(API),
  ]);

  const runtime = runtimeSlice.runtime;
  const dailySummary = dailySummaryResult.summary;
  const friction = dailySummary.friction ?? DEFAULT_DAILY_SUMMARY.friction;
  const qualityAwareness = dailySummary.quality_awareness ?? DEFAULT_DAILY_SUMMARY.quality_awareness;
  const warnings = [
    ...runtimeSlice.warnings,
    ...dailySummaryResult.warnings,
  ];

  const ideas = [...runtime.ideas].sort((a, b) => b.runtime_cost_estimate - a.runtime_cost_estimate);
  const providerRows = [...(dailySummary.providers || [])];
  const topTools = [...(dailySummary.tool_usage?.top_tools || [])].slice(0, 8);
  const topAttentionRows = [...(dailySummary.top_attention_areas || [])].slice(0, 8);
  const hostTaskTypeRows = Object.entries(dailySummary.host_runner?.by_task_type || {}).slice(0, 10);
  const viewRows = [...(viewPerformance?.rows || [])]
    .sort((a, b) => b.average_api_runtime_cost_estimate - a.average_api_runtime_cost_estimate)
    .slice(0, 10);

  const hasPrevious = page > 1;
  const hasNext = runtimeSlice.hasMore;
  const previousHref = `/usage?page=${Math.max(1, page - 1)}&page_size=${pageSize}`;
  const nextHref = `/usage?page=${page + 1}&page_size=${pageSize}`;

  return (
    <main className="min-h-screen p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Home
        </Link>
        <Link href="/portfolio" className="text-muted-foreground hover:text-foreground">
          Portfolio
        </Link>
        <Link href="/ideas" className="text-muted-foreground hover:text-foreground">
          Ideas
        </Link>
        <Link href="/specs" className="text-muted-foreground hover:text-foreground">
          Specs
        </Link>
        <Link href="/flow" className="text-muted-foreground hover:text-foreground">
          Flow
        </Link>
        <Link href="/contributors" className="text-muted-foreground hover:text-foreground">
          Contributors
        </Link>
        <Link href="/contributions" className="text-muted-foreground hover:text-foreground">
          Contributions
        </Link>
        <Link href="/assets" className="text-muted-foreground hover:text-foreground">
          Assets
        </Link>
        <Link href="/tasks" className="text-muted-foreground hover:text-foreground">
          Tasks
        </Link>
        <Link href="/agent" className="text-muted-foreground hover:text-foreground">
          Agent
        </Link>
        <Link href="/gates" className="text-muted-foreground hover:text-foreground">
          Gates
        </Link>
      </div>

      <h1 className="text-2xl font-bold">Usage</h1>
      <p className="text-muted-foreground">Runtime telemetry + friction summary (machine data rendered for humans).</p>
      {warnings.length > 0 ? (
        <p className="text-sm text-muted-foreground">Partial data mode: unavailable {warnings.join(", ")}.</p>
      ) : null}

      <section className="rounded border p-4 space-y-2 text-sm">
        <h2 className="font-semibold">Friction (24h)</h2>
        <p className="text-muted-foreground">total_events {friction.total_events} | open {friction.open_events}</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="rounded border p-3">
            <p className="font-medium mb-2">Top block types</p>
            <ul className="space-y-1">
              {friction.top_block_types.slice(0, 8).map((row) => (
                <li key={row.key} className="flex justify-between">
                  <Link href="/friction" className="underline hover:text-foreground">
                    {row.key}
                  </Link>
                  <span className="text-muted-foreground">{row.count}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded border p-3">
            <p className="font-medium mb-2">Top stages</p>
            <ul className="space-y-1">
              {friction.top_stages.slice(0, 8).map((row) => (
                <li key={row.key} className="flex justify-between">
                  <span>{row.key}</span>
                  <span className="text-muted-foreground">{row.count}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
        <div className="rounded border p-3">
          <p className="font-medium mb-2">Top entry points</p>
          <ul className="space-y-1">
            {friction.entry_points.slice(0, 8).map((row) => (
              <li key={row.key} className="flex justify-between gap-2">
                <span className="truncate">{row.key}</span>
                <span className="text-muted-foreground">
                  events {row.event_count} | {row.status}
                </span>
              </li>
            ))}
            {friction.entry_points.length === 0 ? (
              <li className="text-muted-foreground">No friction entry points in the selected window.</li>
            ) : null}
          </ul>
        </div>
      </section>

      <section className="rounded border p-4 space-y-2 text-sm">
        <h2 className="font-semibold">Host Runner (24h)</h2>
        <p className="text-muted-foreground">
          runs {dailySummary.host_runner.total_runs} | failed {dailySummary.host_runner.failed_runs} | completed{" "}
          {dailySummary.host_runner.completed_runs} | tool events {dailySummary.tool_usage.worker_events} | tool failures{" "}
          {dailySummary.tool_usage.worker_failed_events}
        </p>
        <ul className="space-y-2">
          {hostTaskTypeRows.map(([taskType, counts]) => (
            <li key={taskType} className="rounded border p-2 flex flex-wrap justify-between gap-2">
              <span className="font-medium">{taskType}</span>
              <span className="text-muted-foreground">
                total {Number(counts.total || 0)} | completed {Number(counts.completed || 0)} | failed{" "}
                {Number(counts.failed || 0)}
              </span>
            </li>
          ))}
          {hostTaskTypeRows.length === 0 ? <li className="text-muted-foreground">No host-runner task-type data yet.</li> : null}
        </ul>
        {dailySummary.contract_gaps.length > 0 ? (
          <div className="rounded border p-3">
            <p className="font-medium mb-1">Telemetry Contract Gaps</p>
            <ul className="list-disc pl-5 space-y-1 text-muted-foreground">
              {dailySummary.contract_gaps.map((gap) => (
                <li key={gap}>{gap}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </section>

      <section className="rounded border p-4 space-y-2 text-sm">
        <h2 className="font-semibold">Code Quality Awareness (Guidance)</h2>
        <p className="text-muted-foreground">
          intent {qualityAwareness.intent_focus.join(", ")} | severity {qualityAwareness.summary.severity} | risk score{" "}
          {qualityAwareness.summary.risk_score} | status {qualityAwareness.status}
        </p>
        <p className="text-muted-foreground">
          modules {qualityAwareness.summary.python_module_count} | runtime files {qualityAwareness.summary.runtime_file_count} |
          layer violations {qualityAwareness.summary.layer_violations} | very large modules{" "}
          {qualityAwareness.summary.very_large_modules} | long functions {qualityAwareness.summary.long_functions}
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="rounded border p-3">
            <p className="font-medium mb-2">Hotspots</p>
            <ul className="space-y-1">
              {qualityAwareness.hotspots.slice(0, 6).map((row, idx) => (
                <li key={`${row.path}:${row.kind}:${idx}`} className="flex flex-col">
                  <span>
                    {row.path} [{row.kind}]
                  </span>
                  <span className="text-muted-foreground text-xs">
                    {row.function ? `fn ${row.function} | ` : ""}
                    {row.line_count ? `lines ${row.line_count} | ` : ""}
                    {row.line ? `line ${row.line} | ` : ""}
                    {row.detail}
                  </span>
                </li>
              ))}
              {qualityAwareness.hotspots.length === 0 ? (
                <li className="text-muted-foreground">No current maintainability hotspots in this window.</li>
              ) : null}
            </ul>
          </div>
          <div className="rounded border p-3">
            <p className="font-medium mb-2">Guidance</p>
            <ul className="space-y-1">
              {qualityAwareness.guidance.map((row) => (
                <li key={row} className="text-muted-foreground">
                  {row}
                </li>
              ))}
              {qualityAwareness.guidance.length === 0 ? (
                <li className="text-muted-foreground">No quality guidance available yet.</li>
              ) : null}
            </ul>
          </div>
        </div>
        <div className="rounded border p-3">
          <p className="font-medium mb-2">Recommended self-improvement tasks</p>
          <ul className="space-y-1">
            {qualityAwareness.recommended_tasks.slice(0, 3).map((task) => (
              <li key={task.task_id || task.title} className="flex justify-between gap-2">
                <span className="truncate">{task.title || task.task_id}</span>
                <span className="text-muted-foreground">
                  priority {task.priority} | roi {task.roi_estimate.toFixed(2)}
                </span>
              </li>
            ))}
            {qualityAwareness.recommended_tasks.length === 0 ? (
              <li className="text-muted-foreground">No recommended quality tasks available.</li>
            ) : null}
          </ul>
        </div>
      </section>

      <section className="rounded border p-4 space-y-2 text-sm">
        <h2 className="font-semibold">Providers + Limits</h2>
        <ul className="space-y-2">
          {providerRows.map((row) => (
            <li key={row.provider} className="rounded border p-2">
              <div className="flex flex-wrap justify-between gap-2">
                <span className="font-medium">
                  {row.provider} ({row.status})
                </span>
                <span className="text-muted-foreground">{row.data_source}</span>
              </div>
              <p className="text-muted-foreground">
                {row.usage
                  ? `${row.usage.label}: used ${row.usage.used} ${row.usage.unit}` +
                    (row.usage.limit != null ? ` | limit ${row.usage.limit}` : "") +
                    (row.usage.remaining != null ? ` | remaining ${row.usage.remaining}` : "") +
                    (row.usage.window ? ` | window ${row.usage.window}` : "") +
                    (row.usage.validation_state ? ` | validation ${row.usage.validation_state}` : "") +
                    (row.usage.evidence_source ? ` | evidence ${row.usage.evidence_source}` : "")
                  : "No usage metric yet"}
              </p>
              {row.usage?.validation_detail ? (
                <p className="text-muted-foreground text-xs mt-1">{row.usage.validation_detail}</p>
              ) : null}
            </li>
          ))}
          {providerRows.length === 0 ? <li className="text-muted-foreground">No provider summary rows available.</li> : null}
        </ul>
      </section>

      <section className="rounded border p-4 space-y-2 text-sm">
        <h2 className="font-semibold">Top Tool Usage + Attention (24h)</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="rounded border p-3">
            <p className="font-medium mb-2">Top tools</p>
            <ul className="space-y-1">
              {topTools.map((tool) => (
                <li key={tool.tool} className="flex justify-between">
                  <span>{tool.tool}</span>
                  <span className="text-muted-foreground">
                    events {tool.events} | failed {tool.failed}
                  </span>
                </li>
              ))}
              {topTools.length === 0 ? <li className="text-muted-foreground">No worker tool events in window.</li> : null}
            </ul>
          </div>
          <div className="rounded border p-3">
            <p className="font-medium mb-2">Top attention areas</p>
            <ul className="space-y-1">
              {topAttentionRows.map((row) => (
                <li key={row.endpoint} className="flex justify-between gap-2">
                  <span className="truncate">{row.endpoint}</span>
                  <span className="text-muted-foreground">
                    score {row.attention_score.toFixed(1)} | events {row.events}
                  </span>
                </li>
              ))}
              {topAttentionRows.length === 0 ? <li className="text-muted-foreground">No attention rows in window.</li> : null}
            </ul>
          </div>
        </div>
      </section>

      <section className="rounded border p-4 space-y-2 text-sm">
        <h2 className="font-semibold">Runtime Cost by Idea</h2>
        <p className="text-muted-foreground">window_seconds {runtime.window_seconds} | page {page}</p>
        <div className="flex gap-3 text-muted-foreground">
          {hasPrevious ? (
            <Link href={previousHref} className="underline hover:text-foreground">
              Previous
            </Link>
          ) : (
            <span className="opacity-50">Previous</span>
          )}
          {hasNext ? (
            <Link href={nextHref} className="underline hover:text-foreground">
              Next
            </Link>
          ) : (
            <span className="opacity-50">Next</span>
          )}
        </div>
        <ul className="space-y-2">
          {ideas.map((row) => (
            <li key={row.idea_id} className="flex justify-between rounded border p-2">
              <Link href={`/ideas/${encodeURIComponent(row.idea_id)}`} className="underline hover:text-foreground">
                {row.idea_id}
              </Link>
              <span className="text-muted-foreground">
                events {row.event_count} | runtime {row.total_runtime_ms.toFixed(2)}ms | cost ${row.runtime_cost_estimate.toFixed(6)}
              </span>
            </li>
          ))}
          {ideas.length === 0 ? <li className="text-muted-foreground">No runtime usage found for this page.</li> : null}
        </ul>
      </section>

      <section className="rounded border p-4 space-y-2 text-sm">
        <h2 className="font-semibold">Full View Render + API Cost</h2>
        <p className="text-muted-foreground">
          Measured after data is loaded (`web_view_complete` beacon): render time and summed API runtime/cost per route.
        </p>
        <ul className="space-y-2">
          {viewRows.map((row) => (
            <li key={row.route} className="rounded border p-2 flex flex-wrap justify-between gap-2">
              <Link href={row.route} className="underline hover:text-foreground">
                {row.route}
              </Link>
              <span className="text-muted-foreground">
                views {row.views} | p50 {row.p50_render_ms.toFixed(1)}ms | p95 {row.p95_render_ms.toFixed(1)}ms | api calls {row.average_api_call_count.toFixed(1)} | api runtime {row.average_api_runtime_ms.toFixed(1)}ms | api cost ${row.average_api_runtime_cost_estimate.toFixed(6)}
              </span>
            </li>
          ))}
          {viewRows.length === 0 ? (
            <li className="text-muted-foreground">No full-view telemetry yet. Visit pages and refresh this screen.</li>
          ) : null}
        </ul>
      </section>
    </main>
  );
}
