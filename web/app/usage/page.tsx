import Link from "next/link";

import { getApiBase } from "@/lib/api";
import {
  DEFAULT_DAILY_SUMMARY,
  DEFAULT_PAGE_SIZE,
  MAX_PAGE_SIZE,
  type UsageSearchParams,
} from "./types";
import { loadDailySummary, loadRuntimeSlice, loadViewPerformance, parsePositiveInt } from "./data";
import {
  FrictionSection,
  HostRunnerSection,
  NavLinksSection,
  ProvidersSection,
  QualityAwarenessSection,
  RuntimeCostSection,
  TopToolsAttentionSection,
  ViewPerformanceSection,
} from "./sections";

type ProviderStatsEntry = {
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

type ProviderStatsAlert = {
  provider: string;
  metric: string;
  value: number;
  threshold: number;
  message: string;
};

type ProviderStatsSummary = {
  total_providers: number;
  healthy_providers: number;
  attention_needed: number;
  total_measurements: number;
};

type ProviderStatsResponse = {
  providers: Record<string, ProviderStatsEntry>;
  task_types: Record<string, { providers: Record<string, ProviderStatsEntry> }>;
  alerts: ProviderStatsAlert[];
  summary: ProviderStatsSummary;
};

async function loadProviderStats(api: string): Promise<ProviderStatsResponse | null> {
  try {
    const res = await fetch(`${api}/api/providers/stats`, { next: { revalidate: 60 } });
    if (!res.ok) return null;
    return (await res.json()) as ProviderStatsResponse;
  } catch {
    return null;
  }
}

export const revalidate = 60;

export default async function UsagePage({ searchParams }: { searchParams: UsageSearchParams }) {
  const resolved = await searchParams;
  const pageSize = Math.max(
    1,
    Math.min(parsePositiveInt(resolved.page_size, DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE),
  );
  const page = parsePositiveInt(resolved.page, 1);
  const offset = (page - 1) * pageSize;

  const API = getApiBase();
  const [runtimeSlice, dailySummaryResult, viewPerformance, providerStats] = await Promise.all([
    loadRuntimeSlice(API, pageSize, offset),
    loadDailySummary(API),
    loadViewPerformance(API),
    loadProviderStats(API),
  ]);

  const runtime = runtimeSlice.runtime;
  const dailySummary = dailySummaryResult.summary;
  const friction = dailySummary.friction ?? DEFAULT_DAILY_SUMMARY.friction;
  const qualityAwareness =
    dailySummary.quality_awareness ?? DEFAULT_DAILY_SUMMARY.quality_awareness;
  const toolUsage = dailySummary.tool_usage ?? DEFAULT_DAILY_SUMMARY.tool_usage;
  const workerFailedRaw = Number(
    (toolUsage.worker_failed_events_raw ?? toolUsage.worker_failed_events) || 0,
  );
  const workerFailedRecoverable = Number(toolUsage.worker_failed_events_recoverable || 0);
  const workerFailedActive = Math.max(workerFailedRaw - workerFailedRecoverable, 0);
  const recoveryStreakTarget = Number(toolUsage.recovery_success_streak_target || 3);
  const warnings = [...runtimeSlice.warnings, ...dailySummaryResult.warnings];

  const ideas = [...runtime.ideas].sort(
    (a, b) => b.runtime_cost_estimate - a.runtime_cost_estimate,
  );
  const providerRows = [...(dailySummary.providers || [])];
  const topTools = [...(toolUsage.top_tools || [])].slice(0, 8);
  const topAttentionRows = [...(dailySummary.top_attention_areas || [])].slice(0, 8);
  const hostTaskTypeRows = Object.entries(
    dailySummary.host_runner?.by_task_type || {},
  ).slice(0, 10);
  const viewRows = [...(viewPerformance?.rows || [])]
    .sort((a, b) => b.average_api_runtime_cost_estimate - a.average_api_runtime_cost_estimate)
    .slice(0, 10);

  const hasPrevious = page > 1;
  const hasNext = runtimeSlice.hasMore;
  const previousHref = `/usage?page=${Math.max(1, page - 1)}&page_size=${pageSize}`;
  const nextHref = `/usage?page=${page + 1}&page_size=${pageSize}`;

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8">
      <div className="mx-auto w-full max-w-7xl space-y-8">
        <section className="space-y-2">
          <h1 className="text-3xl font-bold tracking-tight">
            Usage
          </h1>
          <p className="max-w-2xl text-muted-foreground leading-relaxed">
            A transparent view of how resources flow through the network. Runtime telemetry, friction signals, and provider health in one place.
          </p>
          {warnings.length > 0 ? (
            <p className="text-xs uppercase tracking-[0.12em] text-muted-foreground">
              Partial data mode: unavailable {warnings.join(", ")}.
            </p>
          ) : null}
        </section>

        <NavLinksSection />

        <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3">
          <h2 className="text-xl font-semibold">Provider Health</h2>
          {providerStats ? (
            <>
              <p className="text-sm text-muted-foreground">
                {providerStats.summary.healthy_providers}/{providerStats.summary.total_providers} providers healthy, {providerStats.summary.total_measurements} measurements
              </p>
              {providerStats.alerts.length > 0 && (
                <ul className="space-y-1">
                  {providerStats.alerts.map((alert, i) => (
                    <li
                      key={`prov-alert-${alert.provider}-${alert.metric}-${i}`}
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
                      <th className="pb-2 pr-4">Provider</th>
                      <th className="pb-2 pr-4">Overall Rate</th>
                      <th className="pb-2 pr-4">Last 5</th>
                      <th className="pb-2 pr-4">Avg Speed</th>
                      <th className="pb-2">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(providerStats.providers)
                      .sort(([a], [b]) => a.localeCompare(b))
                      .map(([name, entry]) => (
                        <tr key={`prov-row-${name}`} className="border-b border-border/30">
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
                {Object.entries(providerStats.providers)
                  .sort(([a], [b]) => a.localeCompare(b))
                  .map(([name, entry]) => (
                    <div key={`prov-mobile-${name}`} className="rounded-xl border border-border/20 bg-background/40 p-3 space-y-1">
                      <p className="font-medium text-sm">{name}</p>
                      <div className="grid grid-cols-3 gap-2 text-xs">
                        <div>
                          <p className="text-muted-foreground">Overall</p>
                          <p>{(entry.success_rate * 100).toFixed(0)}%</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Last 5</p>
                          <p className={entry.last_5_rate < 0.5 ? "text-red-600 dark:text-red-400" : entry.last_5_rate < 0.8 ? "text-amber-600 dark:text-amber-400" : ""}>
                            {(entry.last_5_rate * 100).toFixed(0)}%
                          </p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Status</p>
                          <p>{entry.blocked ? "blocked" : entry.needs_attention ? "attention" : "ok"}</p>
                        </div>
                      </div>
                    </div>
                  ))}
              </div>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">Provider stats are not available right now. Check back once the API is connected.</p>
          )}
        </section>

        <FrictionSection friction={friction} />

        <HostRunnerSection
          dailySummary={dailySummary}
          workerFailedRaw={workerFailedRaw}
          workerFailedRecoverable={workerFailedRecoverable}
          workerFailedActive={workerFailedActive}
          recoveryStreakTarget={recoveryStreakTarget}
          hostTaskTypeRows={hostTaskTypeRows}
        />

        <QualityAwarenessSection qualityAwareness={qualityAwareness} />

        <ProvidersSection providerRows={providerRows} />

        <TopToolsAttentionSection
          topTools={topTools}
          topAttentionRows={topAttentionRows}
          recoveryStreakTarget={recoveryStreakTarget}
        />

        <RuntimeCostSection
          ideas={ideas}
          runtime={runtime}
          page={page}
          hasPrevious={hasPrevious}
          hasNext={hasNext}
          previousHref={previousHref}
          nextHref={nextHref}
        />

        <ViewPerformanceSection viewRows={viewRows} />

        {/* Where to go next */}
        <nav className="py-8 text-center space-y-2 border-t border-border/20" aria-label="Where to go next">
          <p className="text-xs text-muted-foreground/60 uppercase tracking-wider">Where to go next</p>
          <div className="flex flex-wrap justify-center gap-4 text-sm">
            <Link href="/automation" className="text-amber-600 dark:text-amber-400 hover:underline">Automation</Link>
            <Link href="/flow" className="text-amber-600 dark:text-amber-400 hover:underline">Flow</Link>
            <Link href="/ideas" className="text-amber-600 dark:text-amber-400 hover:underline">Ideas</Link>
          </div>
        </nav>
      </div>
    </main>
  );
}
