import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";
import { UI_RUNTIME_WINDOW } from "@/lib/egress";

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
  validation_state?: string | null;
  validation_detail?: string | null;
  evidence_source?: string | null;
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

export const revalidate = 120;
const API_REVALIDATE_SECONDS = 120;
const API_FETCH_TIMEOUT_MS = 3000;

const DEFAULT_USAGE: AutomationUsageResponse = {
  generated_at: "",
  providers: [],
  unavailable_providers: [],
  tracked_providers: 0,
  limit_coverage: {
    providers_considered: 0,
    providers_with_limit_metrics: 0,
    providers_with_remaining_metrics: 0,
    providers_missing_limit_metrics: [],
    providers_partial_limit_metrics: [],
    coverage_ratio: 0,
  },
};

const DEFAULT_ALERTS: UsageAlertResponse = {
  generated_at: "",
  threshold_ratio: 0.2,
  alerts: [],
};

const DEFAULT_READINESS: ProviderReadinessResponse = {
  generated_at: "",
  required_providers: [],
  all_required_ready: false,
  blocking_issues: [],
  recommendations: [],
  providers: [],
};

const DEFAULT_VALIDATION: ProviderValidationResponse = {
  generated_at: "",
  required_providers: [],
  runtime_window_seconds: UI_RUNTIME_WINDOW,
  min_execution_events: 1,
  all_required_validated: false,
  blocking_issues: [],
  providers: [],
};

const PROVIDER_LABELS: Record<string, string> = {
  openai: "OpenAI",
  claude: "Claude",
  cursor: "Cursor",
  gemini: "Gemini",
  "coherence-internal": "Coherence Internal Runtime",
  "db-host": "DB Host (Railway Postgres)",
  railway: "Railway (Host Provider)",
};

const PROVIDER_DESCRIPTIONS: Record<string, string> = {
  "coherence-internal": "Internal task/runtime telemetry from this system (not an external paid provider).",
  "db-host": "Database hosting and egress/load tracking for your Postgres host.",
  railway: "Application hosting/runtime provider checks (API+infrastructure), not an LLM provider.",
  openai: "Includes Codex-routed execution telemetry under one OpenAI provider family.",
  claude: "Includes Anthropic/Claude execution telemetry under one provider family.",
  cursor: "Cursor subscription-window telemetry from runner/runtime signals.",
  gemini: "Google Gemini subscription-window telemetry from runner/runtime signals.",
};

function providerLabel(provider: string): string {
  return PROVIDER_LABELS[provider] ?? provider;
}

function providerDescription(provider: string): string {
  return PROVIDER_DESCRIPTIONS[provider] ?? "";
}

function formatNumber(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "n/a";
  }
  const rounded = Math.round(value * 10) / 10;
  return Number.isInteger(rounded) ? String(Math.trunc(rounded)) : rounded.toFixed(1);
}

function formatTimestamp(value?: string): string {
  if (!value) {
    return "n/a";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function statusBadgeClass(status: string): string {
  if (status === "ok") {
    return "bg-green-100 text-green-800";
  }
  if (status === "degraded") {
    return "bg-amber-100 text-amber-900";
  }
  if (status === "unavailable") {
    return "bg-red-100 text-red-800";
  }
  return "bg-muted text-muted-foreground";
}

function statusLabel(status: string): string {
  if (status === "ok") {
    return "Healthy";
  }
  if (status === "degraded") {
    return "Degraded";
  }
  if (status === "unavailable") {
    return "Unavailable";
  }
  return status;
}

function windowMetricSummary(metric: UsageMetric): string {
  const evidence = String(metric.evidence_source ?? "").toLowerCase();
  const nativePercentWindow =
    metric.limit === 100 &&
    metric.remaining !== null &&
    metric.remaining !== undefined &&
    (metric.id.includes("provider_window") || evidence.includes("provider_api") || evidence.includes("wham_usage"));
  if (nativePercentWindow) {
    return `${formatNumber(metric.used)}% used, ${formatNumber(metric.remaining)}% left`;
  }
  if (metric.limit === null || metric.limit === undefined) {
    if (metric.remaining === null || metric.remaining === undefined) {
      return `${formatNumber(metric.used)} ${metric.unit} used (limit not exposed)`;
    }
    return `${formatNumber(metric.used)} ${metric.unit} used, ${formatNumber(metric.remaining)} left`;
  }
  if (metric.remaining === null || metric.remaining === undefined) {
    return `${formatNumber(metric.used)} / ${formatNumber(metric.limit)} used (remaining not exposed)`;
  }
  return `${formatNumber(metric.used)} / ${formatNumber(metric.limit)} used, ${formatNumber(metric.remaining)} left`;
}

function isLLMWindowMetric(provider: string, metric: UsageMetric): boolean {
  const id = metric.id.toLowerCase();
  const window = String(metric.window ?? "").toLowerCase();
  if (provider === "openai") {
    return (
      id.startsWith("openai_subscription_") ||
      id.startsWith("codex_subscription_") ||
      id.startsWith("codex_provider_window_")
    );
  }
  return id.startsWith(`${provider}_subscription_`) || window.includes("hour") || window.includes("week") || window.includes("7d");
}

function isShortWindow(metric: UsageMetric): boolean {
  const id = metric.id.toLowerCase();
  const window = String(metric.window ?? "").toLowerCase();
  return id.includes("_8h") || id.includes("_5h") || id.includes("primary") || window === "8h" || window === "5h" || window.includes("hourly") || window.includes("rolling_5h");
}

function isWeekWindow(metric: UsageMetric): boolean {
  const id = metric.id.toLowerCase();
  const window = String(metric.window ?? "").toLowerCase();
  return id.includes("_week") || id.includes("secondary") || window === "7d" || window.includes("week") || window.includes("rolling_7d");
}

function pickBestMetric(metrics: UsageMetric[]): UsageMetric | null {
  if (metrics.length === 0) {
    return null;
  }
  const scored = [...metrics].sort((a, b) => {
    const score = (metric: UsageMetric): number => {
      let out = 0;
      if (metric.limit !== null && metric.limit !== undefined) out += 4;
      if (metric.remaining !== null && metric.remaining !== undefined) out += 3;
      if (String(metric.validation_state ?? "").toLowerCase() === "validated") out += 2;
      if (String(metric.evidence_source ?? "").toLowerCase().includes("provider_api")) out += 1;
      return out;
    };
    return score(b) - score(a);
  });
  return scored[0] ?? null;
}

function telemetryQuality(metrics: UsageMetric[]): string {
  if (metrics.length === 0) {
    return "missing";
  }
  const native = metrics.some((metric) => {
    const source = String(metric.evidence_source ?? "").toLowerCase();
    return source.includes("provider_api") || source.includes("wham_usage");
  });
  const validated = metrics.some((metric) => String(metric.validation_state ?? "").toLowerCase() === "validated");
  if (native && validated) {
    return "native";
  }
  if (validated) {
    return "validated";
  }
  return "estimated";
}

function qualityLabel(value: string): string {
  if (value === "native") {
    return "Native";
  }
  if (value === "validated") {
    return "Verified";
  }
  if (value === "estimated") {
    return "Estimated";
  }
  return "No data";
}

function presentIssue(issue: string): string {
  const parts = issue.split(":", 2);
  if (parts.length < 2) {
    return issue;
  }
  const provider = parts[0]?.trim().toLowerCase();
  const detail = parts[1]?.trim().toLowerCase() ?? "";
  const label = providerLabel(provider ?? "");

  if (detail.includes("missing_limit_metrics")) {
    return `${label}: usage window data is missing.`;
  }
  if (detail.includes("missing_remaining_metrics")) {
    return `${label}: remaining window data is missing.`;
  }
  if (detail.includes("limit_telemetry_state=")) {
    return `${label}: window telemetry is incomplete.`;
  }
  if (detail.includes("subscription_windows=")) {
    return `${label}: subscription window data is incomplete.`;
  }
  if (detail.includes("configured=") && detail.includes("successful_events=")) {
    return `${label}: runtime validation evidence is below the required threshold.`;
  }
  return `${label}: ${detail.replaceAll("_", " ")}`;
}

async function fetchJsonOrDefault<T>(url: string, fallback: T): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort("automation_fetch_timeout"), API_FETCH_TIMEOUT_MS);
  try {
    const response = await fetch(url, {
      next: { revalidate: API_REVALIDATE_SECONDS },
      signal: controller.signal,
    });
    if (!response.ok) {
      return fallback;
    }
    return (await response.json()) as T;
  } catch {
    return fallback;
  } finally {
    clearTimeout(timeoutId);
  }
}

async function loadAutomationData(): Promise<{
  usage: AutomationUsageResponse;
  alerts: UsageAlertResponse;
  readiness: ProviderReadinessResponse;
  validation: ProviderValidationResponse;
}> {
  const api = getApiBase();
  const validationParams = new URLSearchParams({
    runtime_window_seconds: String(UI_RUNTIME_WINDOW),
    min_execution_events: "1",
  });
  const [usage, alerts, readiness, validation] = await Promise.all([
    fetchJsonOrDefault<AutomationUsageResponse>(`${api}/api/automation/usage?compact=true`, DEFAULT_USAGE),
    fetchJsonOrDefault<UsageAlertResponse>(`${api}/api/automation/usage/alerts?threshold_ratio=0.2`, DEFAULT_ALERTS),
    fetchJsonOrDefault<ProviderReadinessResponse>(`${api}/api/automation/usage/readiness`, DEFAULT_READINESS),
    fetchJsonOrDefault<ProviderValidationResponse>(
      `${api}/api/automation/usage/provider-validation?${validationParams.toString()}`,
      DEFAULT_VALIDATION,
    ),
  ]);
  return { usage, alerts, readiness, validation };
}

export default async function AutomationPage() {
  const { usage, alerts, readiness, validation } = await loadAutomationData();
  const providers = [...usage.providers].sort((a, b) => a.provider.localeCompare(b.provider));
  const providerByName = new Map(providers.map((provider) => [provider.provider, provider]));
  const readinessByName = new Map(readiness.providers.map((row) => [row.provider, row]));
  const alertCountByProvider = alerts.alerts.reduce<Record<string, number>>((acc, row) => {
    acc[row.provider] = (acc[row.provider] ?? 0) + 1;
    return acc;
  }, {});

  const llmProviders = ["openai", "claude", "cursor", "gemini"];
  const llmCards = llmProviders.map((provider) => {
    const snapshot = providerByName.get(provider);
    const windowMetrics = snapshot?.metrics.filter((metric) => isLLMWindowMetric(provider, metric)) ?? [];
    const status = readinessByName.get(provider)?.status ?? snapshot?.status ?? "unknown";
    const configured = readinessByName.get(provider)?.configured ?? status === "ok";
    const metricShort = pickBestMetric(windowMetrics.filter((metric) => isShortWindow(metric)));
    const metricWeek = pickBestMetric(windowMetrics.filter((metric) => isWeekWindow(metric)));
    return {
      provider,
      snapshot,
      alerts: alertCountByProvider[provider] ?? 0,
      status,
      configured,
      metricShort,
      metricWeek,
      quality: telemetryQuality(windowMetrics),
      windowMetrics,
    };
  });

  const infraProviders = providers.filter((provider) =>
    ["coherence-internal", "railway", "db-host"].includes(provider.provider),
  );
  const coverageRatio = usage.limit_coverage?.coverage_ratio ?? 0;
  const llmWithWindowTelemetry = llmCards.filter((row) => row.metricShort && row.metricWeek).length;
  const llmNativeWindows = llmCards.filter((row) => row.quality === "native").length;
  const llmConnected = llmCards.filter((row) => row.configured).length;
  const attentionItems = Array.from(new Set([...readiness.blocking_issues, ...validation.blocking_issues]));
  const freshness = formatTimestamp(usage.generated_at || readiness.generated_at || validation.generated_at);

  return (
    <main className="min-h-screen p-8 max-w-6xl mx-auto space-y-6">
      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Home
        </Link>
        <Link href="/agent" className="text-muted-foreground hover:text-foreground">
          Agent
        </Link>
        <Link href="/usage" className="text-muted-foreground hover:text-foreground">
          Usage
        </Link>
        <Link href="/tasks" className="text-muted-foreground hover:text-foreground">
          Tasks
        </Link>
      </div>

      <h1 className="text-2xl font-bold">Automation Overview</h1>
      <p className="text-muted-foreground">
        Subscription usage overview for all LLM providers, plus hosting and database health.
      </p>
      <p className="text-xs text-muted-foreground">Last refreshed: {freshness}</p>

      <section className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
        <article className="rounded border p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">LLM Connected</p>
          <p className="mt-1 text-2xl font-semibold">
            {llmConnected}/{llmProviders.length}
          </p>
          <p className="text-sm text-muted-foreground">Providers recognized as configured</p>
        </article>
        <article className="rounded border p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Window Telemetry</p>
          <p className="mt-1 text-2xl font-semibold">
            {llmWithWindowTelemetry}/{llmProviders.length}
          </p>
          <p className="text-sm text-muted-foreground">Providers with clear usage + remaining</p>
        </article>
        <article className="rounded border p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Native Windows</p>
          <p className="mt-1 text-2xl font-semibold">
            {llmNativeWindows}/{llmProviders.length}
          </p>
          <p className="text-sm text-muted-foreground">Provider-native window telemetry</p>
        </article>
        <article className="rounded border p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Coverage</p>
          <p className="mt-1 text-2xl font-semibold">{Math.round(coverageRatio * 100)}%</p>
          <p className="text-sm text-muted-foreground">Overall limit telemetry coverage</p>
        </article>
      </section>

      <section className="rounded border p-4 space-y-3 text-sm">
        <h2 className="font-semibold">LLM Providers</h2>
        <p className="text-muted-foreground">
          Real provider telemetry by subscription window. Native formats are shown as-is.
        </p>
        <div className="overflow-x-auto rounded border">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-muted/40 text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">Provider</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium">Now</th>
                <th className="px-3 py-2 font-medium">7d</th>
                <th className="px-3 py-2 font-medium">Source</th>
                <th className="px-3 py-2 font-medium">Alerts</th>
              </tr>
            </thead>
            <tbody>
              {llmCards.map((card) => {
                return (
                  <tr key={card.provider} className="border-t">
                    <td className="px-3 py-2 font-medium">{providerLabel(card.provider)}</td>
                    <td className="px-3 py-2">
                      <span className={`rounded px-2 py-0.5 text-xs ${statusBadgeClass(card.status)}`}>
                        {statusLabel(card.status)}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      {card.metricShort ? windowMetricSummary(card.metricShort) : <span className="text-muted-foreground">n/a</span>}
                    </td>
                    <td className="px-3 py-2">
                      {card.metricWeek ? windowMetricSummary(card.metricWeek) : <span className="text-muted-foreground">n/a</span>}
                    </td>
                    <td className="px-3 py-2">{qualityLabel(card.quality)}</td>
                    <td className="px-3 py-2">{card.alerts}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded border p-4 space-y-3 text-sm">
        <h2 className="font-semibold">Infrastructure</h2>
        <div className="grid gap-3 md:grid-cols-3">
          {infraProviders.map((provider) => {
            const highlights = provider.metrics.slice(0, 2);
            return (
              <article key={provider.id} className="rounded border p-3 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-medium">{providerLabel(provider.provider)}</p>
                  <span className={`rounded px-2 py-0.5 text-xs ${statusBadgeClass(provider.status)}`}>
                    {statusLabel(provider.status)}
                  </span>
                </div>
                {providerDescription(provider.provider) && (
                  <p className="text-muted-foreground">{providerDescription(provider.provider)}</p>
                )}
                {highlights.length > 0 ? (
                  <ul className="space-y-1">
                    {highlights.map((metric) => (
                      <li key={`${provider.id}-${metric.id}`} className="flex items-center justify-between gap-2">
                        <span className="text-muted-foreground">{metric.label}</span>
                        <span>{windowMetricSummary(metric)}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-muted-foreground">No metrics reported.</p>
                )}
              </article>
            );
          })}
        </div>
      </section>

      <section className="rounded border p-4 space-y-2 text-sm">
        <h2 className="font-semibold">Needs Attention</h2>
        {attentionItems.length === 0 ? (
          <p className="text-muted-foreground">No blocking issues right now.</p>
        ) : (
          <ul className="space-y-1 text-destructive">
            {attentionItems.map((item) => (
              <li key={item}>{presentIssue(item)}</li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded border p-4 space-y-2 text-sm">
        <h2 className="font-semibold">Alerts</h2>
        {alerts.alerts.length === 0 ? (
          <p className="text-muted-foreground">No active capacity alerts.</p>
        ) : (
          <ul className="space-y-1">
            {alerts.alerts.map((alert) => (
              <li key={alert.id} className="flex flex-wrap items-center justify-between gap-2 rounded border p-2">
                <span>
                  {providerLabel(alert.provider)} | {alert.severity}
                </span>
                <span className="text-muted-foreground">{alert.message}</span>
              </li>
            ))}
          </ul>
        )}
        <p className="text-xs text-muted-foreground">
          Alert threshold: {Math.round((alerts.threshold_ratio ?? 0) * 100)}% remaining in a tracked window.
        </p>
      </section>
    </main>
  );
}
