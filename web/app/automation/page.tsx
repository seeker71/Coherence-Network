import type { Metadata } from "next";

import { AutomationGarden } from "@/components/automation/automation_garden";
import { GardenMap } from "@/components/automation/garden-map";
import { getApiBase } from "@/lib/api";
import { loadAutomationData } from "@/lib/automation-page-data";

export const metadata: Metadata = {
  title: "Automation",
  description: "Provider automation readiness and subscription status.",
};

export default async function AutomationPage() {
  const payload = await loadAutomationData();
  const { usage, alerts, readiness, execStats, networkStats, federationNodes } = payload;
  const providers = [...usage.providers].sort((a, b) => a.provider.localeCompare(b.provider));
  const apiBase = getApiBase();

  return (
    <main className="min-h-screen px-4 py-8 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <div>
          <h1 className="mb-1 text-3xl font-bold tracking-tight">Automation Garden</h1>
          <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
            Provider capacity, execution readiness, and node health shown as a living system first,
            with the raw operating facts one disclosure away.
          </p>
        </div>

        <AutomationGarden payload={payload} apiBase={apiBase} />

        <details
          data-testid="automation-technical-soil"
          className="rounded-3xl border border-border/70 bg-card/70 p-5 shadow-sm"
        >
          <summary className="cursor-pointer list-none text-base font-semibold tracking-tight">
            Technical soil
          </summary>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground">
            This keeps the newer systems view visible without hiding the route-level diagnostics that
            operators need when a provider, node, or quota starts drifting.
          </p>
          <div className="mt-5">
            <GardenMap
              providers={providers}
              readiness={readiness}
              execStats={execStats?.providers ?? null}
              alerts={alerts.alerts}
              federationNodes={federationNodes}
              networkNodes={networkStats?.nodes ?? {}}
              totalMeasurements={networkStats?.total_measurements ?? 0}
              unavailableProviders={usage.unavailable_providers ?? []}
              limitCoverage={usage.limit_coverage ?? null}
              generatedAt={usage.generated_at}
            />
          </div>
        </details>
      </div>
    </main>
  );
}
