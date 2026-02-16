import Link from "next/link";

import { getApiBase } from "@/lib/api";

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
  notes: string[];
};

type AutomationUsageResponse = {
  generated_at: string;
  providers: ProviderSnapshot[];
  unavailable_providers: string[];
  tracked_providers: number;
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

async function loadAutomationData(): Promise<{ usage: AutomationUsageResponse; alerts: UsageAlertResponse }> {
  const api = getApiBase();
  const [usageRes, alertsRes] = await Promise.all([
    fetch(`${api}/api/automation/usage?force_refresh=true`, { cache: "no-store" }),
    fetch(`${api}/api/automation/usage/alerts?threshold_ratio=0.2`, { cache: "no-store" }),
  ]);
  if (!usageRes.ok) {
    throw new Error(`automation usage HTTP ${usageRes.status}`);
  }
  if (!alertsRes.ok) {
    throw new Error(`automation alerts HTTP ${alertsRes.status}`);
  }
  return {
    usage: (await usageRes.json()) as AutomationUsageResponse,
    alerts: (await alertsRes.json()) as UsageAlertResponse,
  };
}

export default async function AutomationPage() {
  const { usage, alerts } = await loadAutomationData();
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
      </section>

      <section className="rounded border p-4 space-y-3 text-sm">
        <h2 className="font-semibold">Provider Usage</h2>
        <ul className="space-y-3">
          {providers.map((provider) => (
            <li key={provider.id} className="rounded border p-3 space-y-2">
              <p className="font-medium">
                {provider.provider} | status {provider.status} | kind {provider.kind}
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
