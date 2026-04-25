import {
  API_REVALIDATE_SECONDS,
  CompactUsageMetric,
  CompactUsageResponse,
  DailySummary,
  DailySummaryProviderRow,
  DEFAULT_DAILY_SUMMARY,
  DEFAULT_RUNTIME,
  FETCH_TIMEOUT_MS,
  PROVIDER_SNAPSHOT_FALLBACK_TIMEOUT_MS,
  DAILY_SUMMARY_TIMEOUT_MS,
  RUNTIME_EVENTS_FALLBACK_TIMEOUT_MS,
  RUNTIME_SUMMARY_TIMEOUT_MS,
  RuntimeEvent,
  RuntimeIdeaRow,
  RuntimeSlice,
  RuntimeSummaryResponse,
  VIEW_PERFORMANCE_TIMEOUT_MS,
  WebViewPerformanceReport,
} from "./types";
import { UI_RUNTIME_SUMMARY_WINDOW } from "@/lib/egress";

export function normalizeValue(raw: string | string[] | undefined): string {
  if (Array.isArray(raw)) return (raw[0] || "").trim();
  return (raw || "").trim();
}

export function parsePositiveInt(raw: string | string[] | undefined, fallback: number): number {
  const parsed = Number.parseInt(normalizeValue(raw), 10);
  if (!Number.isFinite(parsed) || parsed < 1) return fallback;
  return parsed;
}

export async function fetchJsonOrNull<T>(
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
    const res = await fetch(url, {
      next: { revalidate: API_REVALIDATE_SECONDS },
      ...init,
      signal: controller.signal,
    });
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

function pickProviderMetric(metrics: CompactUsageMetric[] | undefined): CompactUsageMetric | null {
  if (!Array.isArray(metrics) || metrics.length === 0) return null;
  const quota = metrics.find((m) => m.limit != null || m.remaining != null);
  return quota ?? metrics[0];
}

export async function loadRuntimeSlice(
  apiBase: string,
  pageSize: number,
  offset: number,
): Promise<RuntimeSlice> {
  const warnings: string[] = [];
  const attempts = [UI_RUNTIME_SUMMARY_WINDOW];
  for (const seconds of attempts) {
    const params = new URLSearchParams({
      seconds: String(seconds),
      limit: String(pageSize),
      offset: String(offset),
    });
    const payload = await fetchJsonOrNull<RuntimeSummaryResponse>(
      `${apiBase}/api/runtime/ideas/summary?${params.toString()}`,
      RUNTIME_SUMMARY_TIMEOUT_MS,
    );
    if (payload && Array.isArray(payload.ideas)) {
      return { runtime: payload, hasMore: payload.ideas.length >= pageSize, warnings };
    }
    warnings.push(`runtime summary (${seconds}s)`);
  }

  const fallbackEvents = await fetchJsonOrNull<RuntimeEvent[]>(
    `${apiBase}/api/runtime/events?limit=${Math.max(150, pageSize * 6)}`,
    RUNTIME_EVENTS_FALLBACK_TIMEOUT_MS,
  );
  if (fallbackEvents && Array.isArray(fallbackEvents)) {
    const fallback = summarizeRuntimeEvents(fallbackEvents, pageSize, offset);
    warnings.push("runtime summary fallback to recent runtime events");
    return { runtime: fallback.runtime, hasMore: fallback.hasMore, warnings };
  }

  warnings.push("runtime telemetry unavailable");
  return {
    runtime: { ...DEFAULT_RUNTIME, offset, limit: pageSize },
    hasMore: false,
    warnings,
  };
}

async function loadCompactProviderRows(apiBase: string): Promise<DailySummaryProviderRow[]> {
  const usage = await fetchJsonOrNull<CompactUsageResponse>(
    `${apiBase}/api/automation/usage?compact=true`,
    PROVIDER_SNAPSHOT_FALLBACK_TIMEOUT_MS,
  );
  if (!usage || !Array.isArray(usage.providers)) return [];
  return usage.providers.map((row) => {
    const metric = pickProviderMetric(row.metrics);
    return {
      provider: row.provider,
      status: row.status || "unknown",
      data_source: row.data_source || "snapshot",
      usage: metric
        ? {
            label: metric.label || "usage",
            used: Number(metric.used || 0),
            unit: metric.unit || "units",
            remaining: metric.remaining ?? null,
            limit: metric.limit ?? null,
            window: metric.window ?? null,
            validation_state: metric.validation_state ?? null,
            validation_detail: metric.validation_detail ?? null,
            evidence_source: metric.evidence_source ?? null,
          }
        : null,
      notes: Array.isArray(row.notes) ? row.notes : [],
    };
  });
}

export async function loadDailySummary(
  apiBase: string,
): Promise<{ summary: DailySummary; warnings: string[] }> {
  const summary = await fetchJsonOrNull<DailySummary>(
    `${apiBase}/api/automation/usage/daily-summary?window_hours=24&top_n=8`,
    DAILY_SUMMARY_TIMEOUT_MS,
  );
  if (summary) return { summary, warnings: [] };
  const compactProviders = await loadCompactProviderRows(apiBase);
  if (compactProviders.length > 0) {
    return {
      summary: {
        ...DEFAULT_DAILY_SUMMARY,
        generated_at: new Date().toISOString(),
        providers: compactProviders,
      },
      warnings: ["daily usage summary unavailable (using compact provider snapshots)"],
    };
  }
  return { summary: DEFAULT_DAILY_SUMMARY, warnings: ["daily usage summary unavailable"] };
}

export async function loadViewPerformance(
  apiBase: string,
): Promise<WebViewPerformanceReport | null> {
  const params = new URLSearchParams({
    seconds: String(UI_RUNTIME_SUMMARY_WINDOW),
    limit: "12",
  });
  return fetchJsonOrNull<WebViewPerformanceReport>(
    `${apiBase}/api/runtime/web/views/summary?${params.toString()}`,
    VIEW_PERFORMANCE_TIMEOUT_MS,
  );
}
