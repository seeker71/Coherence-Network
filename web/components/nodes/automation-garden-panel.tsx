import { getApiBase } from "@/lib/api";
import { GardenMap } from "@/components/automation/garden-map";
import type {
  FederationNode,
  ProviderSnapshot,
  UsageAlert,
} from "@/components/automation/garden-map";

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

type ProviderExecStatsResponse = {
  providers: Record<string, ProviderExecStatsEntry>;
  task_types: Record<string, { providers: Record<string, ProviderExecStatsEntry> }>;
  alerts: Array<{ provider: string; metric: string; value: number; threshold: number; message: string }>;
  summary: { total_providers: number; healthy_providers: number; attention_needed: number; total_measurements: number };
};

type NetworkNodeInfo = {
  hostname: string;
  os_type: string;
  status: string;
  last_seen_at: string;
};

type NetworkStatsResponse = {
  nodes: Record<string, NetworkNodeInfo>;
  providers: Record<string, unknown>;
  alerts: Array<{ provider: string; message: string }>;
  window_days: number;
  total_measurements: number;
};

async function loadAutomationGardenData() {
  const api = getApiBase();
  // Manual checks: GET /api/automation/usage/provider-validation
  const [usageRes, alertsRes, readinessRes, execStatsRes, networkStatsRes, federationNodesRes] =
    await Promise.all([
      fetch(`${api}/api/automation/usage?force_refresh=true`, { cache: "no-store" }),
      fetch(`${api}/api/automation/usage/alerts?threshold_ratio=0.2`, { cache: "no-store" }).catch(() => null),
      fetch(`${api}/api/automation/usage/readiness?force_refresh=true`, { cache: "no-store" }).catch(() => null),
      fetch(`${api}/api/providers/stats`, { cache: "no-store" }).catch(() => null),
      fetch(`${api}/api/federation/nodes/stats`, { cache: "no-store" }).catch(() => null),
      fetch(`${api}/api/federation/nodes`, { cache: "no-store" }).catch(() => null),
    ]);

  if (!usageRes.ok) {
    throw new Error(`automation usage HTTP ${usageRes.status}`);
  }

  const usage = (await usageRes.json()) as AutomationUsageResponse;
  const trackedCount = usage.tracked_providers;

  const alerts: UsageAlert[] = alertsRes?.ok
    ? ((await alertsRes.json()) as UsageAlertResponse).alerts ?? []
    : [];

  const readiness: ProviderReadinessResponse = readinessRes?.ok
    ? ((await readinessRes.json()) as ProviderReadinessResponse)
    : { providers: [], all_required_ready: true, blocking_issues: [], recommendations: [], generated_at: "", required_providers: [] };

  let execStats: Record<string, ProviderExecStatsEntry> | null = null;
  if (execStatsRes?.ok) {
    const parsed = (await execStatsRes.json()) as ProviderExecStatsResponse;
    execStats = parsed.providers ?? null;
  }

  let networkNodes: Record<string, NetworkNodeInfo> = {};
  let totalMeasurements = 0;
  if (networkStatsRes?.ok) {
    const ns = (await networkStatsRes.json()) as NetworkStatsResponse;
    networkNodes = ns.nodes ?? {};
    totalMeasurements = ns.total_measurements ?? 0;
  }

  let federationNodes: FederationNode[] = [];
  if (federationNodesRes?.ok) {
    federationNodes = (await federationNodesRes.json()) as FederationNode[];
  }

  return {
    usage,
    alerts,
    readiness,
    execStats,
    networkNodes,
    totalMeasurements,
    federationNodes,
  };
}

/** Provider readiness + automation garden (merged from legacy /automation). */
export async function AutomationGardenPanel() {
  try {
    const { usage, alerts, readiness, execStats, networkNodes, totalMeasurements, federationNodes } =
      await loadAutomationGardenData();

    const providers = [...usage.providers].sort((a, b) => a.provider.localeCompare(b.provider));

    return (
    <section className="space-y-6 border-t border-border/20 pt-10 mt-10" aria-labelledby="automation-garden-heading">
      <div>
        <h2 id="automation-garden-heading" className="text-2xl font-bold tracking-tight mb-1">
          Automation garden
        </h2>
        <p className="text-muted-foreground max-w-xl text-sm leading-relaxed">
          Provider readiness, capacity, and federation terrain — same signals as the former automation page.
        </p>
        <p className="text-xs text-muted-foreground mt-2">
          Tracking {usage.tracked_providers} providers
        </p>
      </div>

      <GardenMap
        providers={providers}
        readiness={readiness}
        execStats={execStats}
        alerts={alerts}
        federationNodes={federationNodes}
        networkNodes={networkNodes}
        totalMeasurements={totalMeasurements}
        unavailableProviders={usage.unavailable_providers ?? []}
        limitCoverage={usage.limit_coverage ?? null}
        generatedAt={usage.generated_at}
      />
    </section>
    );
  } catch {
    return (
      <section className="space-y-4 border-t border-border/20 pt-10 mt-10">
        <h2 className="text-xl font-semibold">Automation garden</h2>
        <p className="text-sm text-muted-foreground">
          Could not load provider readiness and automation usage. Check API connectivity and try again.
        </p>
      </section>
    );
  }
}
