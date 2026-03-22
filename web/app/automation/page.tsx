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
}> {
  const api = getApiBase();
  const [usageRes, alertsRes, readinessRes, validationRes, execStatsRes] = await Promise.all([
    fetch(`${api}/api/automation/usage?force_refresh=true`, { cache: "no-store" }),
    fetch(`${api}/api/automation/usage/alerts?threshold_ratio=0.2`, { cache: "no-store" }),
    fetch(`${api}/api/automation/usage/readiness?force_refresh=true`, { cache: "no-store" }),
    fetch(`${api}/api/automation/usage/provider-validation?runtime_window_seconds=86400&min_execution_events=1&force_refresh=true`, {
      cache: "no-store",
    }),
    fetch(`${api}/api/providers/stats`, { cache: "no-store" }).catch(() => null),
  ]);
  if (!usageRes.ok) {
    throw new Error(`automation usage HTTP ${usageRes.status}`);
  }
  if (!alertsRes.ok) {
    throw new Error(`automation alerts HTTP ${alertsRes.status}`);
  }
  if (!readinessRes.ok) {
    throw new Error(`automation readiness HTTP ${readinessRes.status}`);
  }
  if (!validationRes.ok) {
    throw new Error(`automation provider validation HTTP ${validationRes.status}`);
  }
  let execStats: ProviderExecStatsResponse | null = null;
  if (execStatsRes && execStatsRes.ok) {
    execStats = (await execStatsRes.json()) as ProviderExecStatsResponse;
  }
  return {
    usage: (await usageRes.json()) as AutomationUsageResponse,
    alerts: (await alertsRes.json()) as UsageAlertResponse,
    readiness: (await readinessRes.json()) as ProviderReadinessResponse,
    validation: (await validationRes.json()) as ProviderValidationResponse,
    execStats,
  };
}

export default async function AutomationPage() {
  const { usage, alerts, readiness, validation, execStats } = await loadAutomationData();
  const providers = [...usage.providers].sort((a, b) => a.provider.localeCompare(b.provider));

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

      <h1 className="text-2xl font-bold">Automation Capacity</h1>
      <p className="text-muted-foreground">
        Real provider adapter usage, normalized capacity metrics, and threshold alerts for automation planning.
      </p>

      <section className="rounded border p-4 text-sm space-y-2">
        <p className="text-muted-foreground">
          providers {usage.tracked_providers} | unavailable {usage.unavailable_providers.length} | alerts {alerts.alerts.length}
        </p>
        <p className="text-muted-foreground">
          required_providers {readiness.required_providers.length} | all_required_ready {readiness.all_required_ready ? "yes" : "no"} |
          blocking {readiness.blocking_issues.length}
        </p>
        <p className="text-muted-foreground">
          validation_required {validation.required_providers.length} | all_required_validated {validation.all_required_validated ? "yes" : "no"} |
          blocking {validation.blocking_issues.length}
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
        <section className="rounded border p-4 space-y-2 text-sm">
          <h2 className="font-semibold">Usage Limit Coverage</h2>
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

      <section className="rounded border p-4 space-y-3 text-sm">
        <h2 className="font-semibold">Provider Validation Contract</h2>
        <p className="text-muted-foreground">
          runtime_window_seconds {validation.runtime_window_seconds} | min_execution_events {validation.min_execution_events}
        </p>
        {validation.blocking_issues.length > 0 && (
          <ul className="space-y-1 text-destructive">
            {validation.blocking_issues.map((item) => (
              <li key={`validation-block-${item}`}>{item}</li>
            ))}
          </ul>
        )}
        <ul className="space-y-2">
          {validation.providers.map((provider) => (
            <li key={`validation-${provider.provider}`} className="rounded border p-2">
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

      <section className="rounded border p-4 space-y-3 text-sm">
        <h2 className="font-semibold">Provider Execution Stats</h2>
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
                    className={`rounded border p-2 ${entry.blocked ? "border-red-500/50 bg-red-500/5" : ""}`}
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

      <section className="rounded border p-4 space-y-3 text-sm">
        <h2 className="font-semibold">Provider Readiness</h2>
        {readiness.blocking_issues.length > 0 && (
          <ul className="space-y-1 text-destructive">
            {readiness.blocking_issues.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        )}
        {readiness.recommendations.length > 0 && (
          <ul className="space-y-1 text-muted-foreground">
            {readiness.recommendations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        )}
        <ul className="space-y-2">
          {readiness.providers.map((provider) => (
            <li key={`ready-${provider.provider}`} className="rounded border p-2">
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

      <section className="rounded border p-4 space-y-3 text-sm">
        <h2 className="font-semibold">Provider Usage</h2>
        <ul className="space-y-3">
          {providers.map((provider) => (
            <li key={provider.id} className="rounded border p-3 space-y-2">
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

      <section className="rounded border p-4 space-y-3 text-sm">
        <h2 className="font-semibold">Capacity Alerts</h2>
        <p className="text-muted-foreground">threshold_ratio {alerts.threshold_ratio}</p>
        <ul className="space-y-2">
          {alerts.alerts.map((alert) => (
            <li key={alert.id} className="rounded border p-2 flex justify-between gap-3">
              <span>
                {alert.provider} | {alert.metric_id} | {alert.severity}
              </span>
              <span className="text-muted-foreground">{alert.message}</span>
            </li>
          ))}
          {alerts.alerts.length === 0 && <li className="text-muted-foreground">No capacity alerts.</li>}
        </ul>
      </section>
    </main>
  );
}
