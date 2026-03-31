import type { Metadata } from "next";
import { getApiBase } from "@/lib/api";
import ConceptGardenClient from "./ConceptGardenClient";

export const metadata: Metadata = {
  title: "Concept Garden — Coherence Network",
  description:
    "Share an idea in plain language and the system finds where it fits in the ontology. No graph theory required.",
};

type GardenCard = {
  id: string;
  name: string;
  description: string;
  level: number;
  domains: string[];
  keywords: string[];
  userDefined: boolean;
  contributor?: string;
};

type GardenResponse = {
  cards: GardenCard[];
  total: number;
  shown: number;
  domain_groups: Record<string, string[]>;
  hint: string;
};

type StatsResponse = {
  concepts: number;
  relationship_types: number;
  axes: number;
  user_edges: number;
  user_concepts: number;
};

async function fetchGarden(): Promise<GardenResponse> {
  const base = getApiBase();
  const res = await fetch(`${base}/api/concepts/garden?limit=120`, {
    next: { revalidate: 30 },
  });
  if (!res.ok)
    return { cards: [], total: 0, shown: 0, domain_groups: {}, hint: "" };
  return res.json();
}

async function fetchStats(): Promise<StatsResponse> {
  const base = getApiBase();
  const res = await fetch(`${base}/api/concepts/stats`, {
    next: { revalidate: 60 },
  });
  if (!res.ok)
    return {
      concepts: 0,
      relationship_types: 0,
      axes: 0,
      user_edges: 0,
      user_concepts: 0,
    };
  return res.json();
}

export default async function ConceptGardenPage() {
  const [garden, stats] = await Promise.all([fetchGarden(), fetchStats()]);

  return (
    <main className="max-w-6xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-3">
          <h1 className="text-3xl font-bold tracking-tight">Concept Garden</h1>
          <a
            href="/concepts"
            className="text-xs text-muted-foreground border rounded px-2 py-1 hover:bg-muted transition-colors"
          >
            Graph view
          </a>
        </div>
        <p className="text-muted-foreground text-sm max-w-2xl">
          You don&apos;t need to understand graph theory to add a concept. Share
          an idea in plain language — the system finds where it fits, or creates
          new space for it.
        </p>
        <div className="flex items-center gap-4 mt-3 text-xs text-muted-foreground">
          <span>{stats.concepts} concepts</span>
          <span>{stats.user_concepts} contributed by community</span>
          <span>{stats.user_edges} connections made</span>
        </div>
      </div>

      {/* Client component handles the submission form + interactive filtering */}
      <ConceptGardenClient
        initialCards={garden.cards}
        domainGroups={garden.domain_groups}
        total={garden.total}
        hint={garden.hint}
      />
    </main>
  );
}
