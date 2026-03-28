import type { Metadata } from "next";

import { getApiBase } from "@/lib/api";
import { GardenMap } from "@/components/automation/garden-map";
import type {
  FederationNode,
  ProviderSnapshot,
  UsageAlert,
} from "@/components/automation/garden-map";

export const metadata: Metadata = {
  title: "Automation",
  description: "Provider automation readiness and subscription status.",
};

// ─── API response types ───────────────────────────────────────────────────────

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

type FleetCapabilitiesResponse = {
  total_nodes: number;
  executors: Record<string, { node_count: number; node_ids: string[] }>;
  tools: Record<string, { node_count: number }>;
  hardware_summary: {
    total_cpus: number;
    total_memory_gb: number;
    gpu_capable_nodes: number;
  };
};

// ─── Data loader ─────────────────────────────────────────────────────────────

async function loadAutomationData() {
  const api = getApiBase();
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

// ─── Page ─────────────────────────────────────────────────────────────────────

export default async function AutomationPage() {
  const { usage, alerts, readiness, execStats, networkNodes, totalMeasurements, federationNodes } =
    await loadAutomationData();

  const providers = [...usage.providers].sort((a, b) => a.provider.localeCompare(b.provider));

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight mb-1">Automation Garden</h1>
        <p className="text-muted-foreground max-w-xl text-sm leading-relaxed">
          A living view of the automation ecosystem — providers as organisms, nodes as terrain, health as vitality.
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
    </main>
  );
}
