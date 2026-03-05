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
  const [runtimeSlice, dailySummaryResult, viewPerformance] = await Promise.all([
    loadRuntimeSlice(API, pageSize, offset),
    loadDailySummary(API),
    loadViewPerformance(API),
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
    <main className="min-h-screen px-4 pb-8 pt-6 sm:px-6 lg:px-8">
      <div className="mx-auto w-full max-w-7xl space-y-4">
        <section className="space-y-1 px-1">
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
            Usage In Motion
          </h1>
          <p className="max-w-3xl text-sm text-muted-foreground sm:text-base">
            Runtime telemetry + friction summary, rendered with operational context for fast triage.
          </p>
          {warnings.length > 0 ? (
            <p className="text-xs uppercase tracking-[0.12em] text-muted-foreground">
              Partial data mode: unavailable {warnings.join(", ")}.
            </p>
          ) : null}
        </section>

        <NavLinksSection />

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
      </div>
    </main>
  );
}
