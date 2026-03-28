import type { Metadata } from "next";

import LivePipelineDashboard from "@/components/live/LivePipelineDashboard";
import { getApiBase } from "@/lib/api";
import { fetchJsonOrNull } from "@/lib/fetch";

export const metadata: Metadata = {
  title: "Live pipeline",
  description: "What the network is doing right now: nodes, tasks, providers, and idea motion.",
};

type LivePayload = Record<string, unknown>;

export default async function LivePipelinePage() {
  const apiBase = getApiBase();
  const initial = await fetchJsonOrNull<LivePayload>(`${apiBase}/api/agent/live-pipeline`, { cache: "no-store" }, 8000);

  return (
    <div className="min-h-screen px-4 md:px-8 py-10 max-w-6xl mx-auto space-y-8">
      <section className="space-y-3">
        <p className="text-sm text-muted-foreground">Real-time operations</p>
        <h1 className="text-3xl md:text-4xl font-light tracking-tight">Live pipeline</h1>
        <p className="max-w-3xl text-muted-foreground leading-relaxed">
          See nodes online, work executing, queue depth, provider mix, prompt experiments, and which ideas are moving — in one place.
        </p>
      </section>
      <LivePipelineDashboard initial={initial} />
    </div>
  );
}
