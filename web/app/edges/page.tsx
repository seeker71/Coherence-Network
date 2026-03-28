import type { Metadata } from "next";
import { Suspense } from "react";

import EdgeGraphExplorer from "@/components/edge_graph_explorer";

export const metadata: Metadata = {
  title: "Edge graph",
  description:
    "Browse the Coherence graph through Living Codex relationship types — click through connected entities.",
};

function ExplorerFallback() {
  return (
    <div className="animate-pulse rounded-2xl border border-border/40 bg-muted/20 p-8 text-sm text-muted-foreground">
      Loading explorer…
    </div>
  );
}

export default function EdgesPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-10 md:px-8">
      <header className="mb-10">
        <h1 className="text-3xl font-semibold tracking-tight">Edge navigation</h1>
        <p className="mt-2 max-w-2xl text-muted-foreground">
          Every entity connects via typed edges (resonates-with, emerges-from, implements, and 43 more).
          Select an entity to see its relationships; choose an edge to jump to the connected node.
        </p>
      </header>
      <Suspense fallback={<ExplorerFallback />}>
        <EdgeGraphExplorer />
      </Suspense>
    </div>
  );
}
