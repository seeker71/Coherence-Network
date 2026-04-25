import type { Metadata } from "next";
import Link from "next/link";
import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "Ontology Garden — Coherence Network",
  description:
    "Extend the ontology in plain language. No graph theory required — share ideas, tag domains, and the system finds where they fit.",
};

export const dynamic = "force-dynamic";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type GardenConcept = {
  id: string;
  title: string;
  plain_text: string;
  domains: string[];
  status: "pending" | "placed" | "orphan";
  garden_position: { cluster: string; x: number; y: number };
  relationship_count: number;
  core_concept_match: string | null;
  contributor_id: string;
};

type GardenCluster = {
  name: string;
  size: number;
  members: GardenConcept[];
};

type GardenResponse = {
  clusters: GardenCluster[];
  concepts: GardenConcept[];
  total: number;
  contributor_count: number;
  domain_count: number;
  placement_rate: number;
};

type StatsResponse = {
  total_contributions: number;
  placed_count: number;
  pending_count: number;
  orphan_count: number;
  placement_rate: number;
  top_domains: { domain: string; count: number }[];
  recent_contributors: string[];
  inferred_edges_count: number;
};

// ---------------------------------------------------------------------------
// Server-side data fetchers
// ---------------------------------------------------------------------------

async function fetchGarden(): Promise<GardenResponse> {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/ontology/garden?limit=200`, {
      next: { revalidate: 30 },
    });
    if (!res.ok) {
      return {
        clusters: [],
        concepts: [],
        total: 0,
        contributor_count: 0,
        domain_count: 0,
        placement_rate: 0,
      };
    }
    return res.json();
  } catch {
    return {
      clusters: [],
      concepts: [],
      total: 0,
      contributor_count: 0,
      domain_count: 0,
      placement_rate: 0,
    };
  }
}

async function fetchStats(): Promise<StatsResponse> {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/ontology/stats`, {
      next: { revalidate: 30 },
    });
    if (!res.ok) {
      return {
        total_contributions: 0,
        placed_count: 0,
        pending_count: 0,
        orphan_count: 0,
        placement_rate: 0,
        top_domains: [],
        recent_contributors: [],
        inferred_edges_count: 0,
      };
    }
    return res.json();
  } catch {
    return {
      total_contributions: 0,
      placed_count: 0,
      pending_count: 0,
      orphan_count: 0,
      placement_rate: 0,
      top_domains: [],
      recent_contributors: [],
      inferred_edges_count: 0,
    };
  }
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: string }) {
  const colours: Record<string, string> = {
    placed: "bg-green-100 text-green-800 border-green-200",
    pending: "bg-yellow-100 text-yellow-800 border-yellow-200",
    orphan: "bg-gray-100 text-gray-600 border-gray-200",
  };
  const labels: Record<string, string> = {
    placed: "Placed in graph",
    pending: "Being placed…",
    orphan: "New territory",
  };
  return (
    <span
      className={`inline-block text-xs px-2 py-0.5 rounded-full border font-medium ${
        colours[status] ?? "bg-gray-100 text-gray-600"
      }`}
    >
      {labels[status] ?? status}
    </span>
  );
}

function ConceptCard({ concept }: { concept: GardenConcept }) {
  return (
    <div className="border border-gray-200 rounded-xl p-4 bg-white shadow-sm hover:shadow-md transition-shadow flex flex-col gap-2">
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-semibold text-gray-900 text-sm leading-snug">
          {concept.title}
        </h3>
        <StatusBadge status={concept.status} />
      </div>
      <p className="text-xs text-gray-600 line-clamp-2">{concept.plain_text}</p>
      <div className="flex flex-wrap gap-1 mt-1">
        {concept.domains.map((d) => (
          <span
            key={d}
            className="text-xs bg-blue-50 text-blue-700 border border-blue-100 rounded-full px-2 py-0.5"
          >
            {d}
          </span>
        ))}
      </div>
      <div className="flex items-center justify-between mt-auto pt-1 text-xs text-gray-400">
        <span>by {concept.contributor_id}</span>
        {concept.relationship_count > 0 && (
          <span>{concept.relationship_count} connection{concept.relationship_count !== 1 ? "s" : ""}</span>
        )}
        {concept.core_concept_match && (
          <Link
            href={`/concepts?highlight=${concept.core_concept_match}`}
            className="text-indigo-500 hover:underline"
          >
            → {concept.core_concept_match}
          </Link>
        )}
      </div>
    </div>
  );
}

function ClusterSection({ cluster }: { cluster: GardenCluster }) {
  return (
    <section>
      <h2 className="text-lg font-bold text-gray-800 mb-3 flex items-center gap-2">
        <span className="capitalize">{cluster.name}</span>
        <span className="text-sm font-normal text-gray-400">
          {cluster.size} concept{cluster.size !== 1 ? "s" : ""}
        </span>
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {cluster.members.map((c) => (
          <ConceptCard key={c.id} concept={c} />
        ))}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default async function OntologyGardenPage() {
  const [garden, stats] = await Promise.all([fetchGarden(), fetchStats()]);

  const placementPct = Math.round(stats.placement_rate * 100);

  return (
    <main className="max-w-6xl mx-auto px-4 py-10">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Ontology Garden</h1>
        <p className="text-gray-500 max-w-2xl">
          You don&apos;t need to understand graph theory to add a concept. Share an idea
          in plain language — the system finds where it fits, infers connections, and
          surfaces your contribution as a card in the garden.
        </p>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
        {[
          { label: "Contributions", value: stats.total_contributions },
          { label: "Placed in graph", value: stats.placed_count },
          { label: "Inferred connections", value: stats.inferred_edges_count },
          { label: "Placement rate", value: `${placementPct}%` },
        ].map(({ label, value }) => (
          <div key={label} className="bg-white border border-gray-200 rounded-xl p-4 text-center">
            <div className="text-2xl font-bold text-indigo-600">{value}</div>
            <div className="text-xs text-gray-500 mt-1">{label}</div>
          </div>
        ))}
      </div>

      {/* Contribute CTA */}
      <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-5 mb-8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="font-semibold text-indigo-900">Add your concept</h2>
          <p className="text-sm text-indigo-700 mt-0.5">
            Describe it in plain language — any domain, any level of abstraction.
          </p>
        </div>
        <Link
          href="/ontology/contribute"
          className="shrink-0 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-5 py-2.5 rounded-lg transition-colors"
        >
          Share an idea →
        </Link>
      </div>

      {/* Domain tags */}
      {stats.top_domains.length > 0 && (
        <div className="mb-6 flex flex-wrap gap-2 items-center">
          <span className="text-xs text-gray-500 font-medium mr-1">Top domains:</span>
          {stats.top_domains.slice(0, 8).map(({ domain, count }) => (
            <Link
              key={domain}
              href={`/ontology?domain=${encodeURIComponent(domain)}`}
              className="text-xs bg-white border border-gray-200 rounded-full px-3 py-1 text-gray-700 hover:bg-gray-50 transition-colors"
            >
              {domain} <span className="text-gray-400">({count})</span>
            </Link>
          ))}
        </div>
      )}

      {/* Garden clusters */}
      {garden.clusters.length === 0 ? (
        <div className="text-center py-20 text-gray-400">
          <p className="text-4xl mb-4">🌱</p>
          <p className="font-medium">The garden is empty.</p>
          <p className="text-sm mt-1">Be the first to contribute a concept.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-10">
          {garden.clusters.map((cluster) => (
            <ClusterSection key={cluster.name} cluster={cluster} />
          ))}
        </div>
      )}

      {/* Footer nav */}
      <div className="mt-12 pt-6 border-t border-gray-200 flex gap-4 text-sm text-gray-500">
        <Link href="/concepts" className="hover:text-gray-700">
          Technical graph view →
        </Link>
        <Link href="/ontology/stats" className="hover:text-gray-700">
          Contribution stats →
        </Link>
      </div>
    </main>
  );
}
