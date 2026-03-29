import type { Metadata } from "next";
import { Suspense } from "react";

import type { UsageSearchParams } from "@/app/usage/types";

import PipelineDashboard from "./pipeline-dashboard";
import RemoteOpsPanel from "./remote-ops-panel";
import { UsageMetricsSection } from "./usage-metrics-section";

export const metadata: Metadata = {
  title: "Pipeline",
  description: "Live execution, usage telemetry, and remote operations in one place.",
};

export const revalidate = 60;

export default function PipelinePage({ searchParams }: { searchParams: UsageSearchParams }) {
  return (
    <main className="min-h-screen">
      <PipelineDashboard />
      <Suspense fallback={<div className="px-4 py-8 text-muted-foreground">Loading usage metrics…</div>}>
        <UsageMetricsSection searchParams={searchParams} />
      </Suspense>
      <RemoteOpsPanel />
    </main>
  );
}
