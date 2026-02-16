import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getApiBase } from "@/lib/api";

type IdeaQuestion = {
  question: string;
  value_to_whole: number;
  estimated_cost: number;
  answer?: string | null;
  measured_delta?: number | null;
};

type IdeaWithScore = {
  id: string;
  name: string;
  description: string;
  potential_value: number;
  actual_value: number;
  estimated_cost: number;
  confidence: number;
  manifestation_status: string;
  open_questions: IdeaQuestion[];
  free_energy_score: number;
  value_gap: number;
};

type IdeasResponse = {
  ideas: IdeaWithScore[];
  summary: {
    total_ideas: number;
    total_potential_value: number;
    total_actual_value: number;
    total_value_gap: number;
  };
};

type LineageValuation = {
  measured_value_total: number;
  estimated_cost: number;
  roi_ratio: number;
  event_count: number;
};

type InventoryResponse = {
  implementation_usage?: {
    lineage_links?: Array<{
      lineage_id: string;
      idea_id: string;
      spec_id: string;
      valuation?: LineageValuation | null;
    }>;
  };
};

type RuntimeSummaryResponse = {
  ideas: Array<{
    idea_id: string;
    event_count: number;
    average_runtime_ms: number;
  }>;
};

type OpportunityIdea = IdeaWithScore & {
  estimated_collective_upside: number;
};

const API_NAV_CARDS: Array<{ href: string; title: string; description: string }> = [
  {
    href: "/search",
    title: "Search",
    description: "Find projects, then drill into per-project runtime and coherence signals.",
  },
  {
    href: "/portfolio",
    title: "Portfolio",
    description: "ROI-first governance: questions, costs, signals, and next actions.",
  },
  {
    href: "/flow",
    title: "Flow",
    description: "See how ideas, contributors, contributions, and assets connect.",
  },
  {
    href: "/ideas",
    title: "Ideas",
    description: "Browse high-upside ideas and unresolved questions.",
  },
  {
    href: "/specs",
    title: "Specs",
    description: "Specs discovered from system lineage inventory.",
  },
  {
    href: "/usage",
    title: "Usage",
    description: "Runtime telemetry and friction signals.",
  },
  {
    href: "/friction",
    title: "Friction",
    description: "Inspect blockers and delay-cost hotspots in the execution pipeline.",
  },
  {
    href: "/contributors",
    title: "Contributors",
    description: "Register contributors and track who created value.",
  },
  {
    href: "/contributions",
    title: "Contributions",
    description: "Trace contributor work to assets, specs, and realized impact.",
  },
  {
    href: "/assets",
    title: "Assets",
    description: "Track code/docs/endpoints as measurable system assets.",
  },
  {
    href: "/tasks",
    title: "Tasks",
    description: "Track active and queued execution items with ownership and status.",
  },
  {
    href: "/gates",
    title: "Gates",
    description: "Validate merge/deploy contracts and endpoint traceability coverage.",
  },
  {
    href: "/import",
    title: "Import",
    description: "Analyze dependency manifests and identify coherence risk.",
  },
  {
    href: "/api-health",
    title: "API Health",
    description: "Monitor API readiness and web/API version alignment.",
  },
];

async function loadIdeas(): Promise<IdeasResponse | null> {
  try {
    const res = await fetch(`${getApiBase()}/api/ideas`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as IdeasResponse;
  } catch {
    return null;
  }
}

async function loadInventory(): Promise<InventoryResponse | null> {
  try {
    const res = await fetch(`${getApiBase()}/api/inventory/system-lineage?runtime_window_seconds=86400`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as InventoryResponse;
  } catch {
    return null;
  }
}

async function loadRuntimeSummary(): Promise<RuntimeSummaryResponse | null> {
  try {
    const res = await fetch(`${getApiBase()}/api/runtime/ideas/summary?seconds=86400`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as RuntimeSummaryResponse;
  } catch {
    return null;
  }
}

function formatNumber(value: number | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "0";
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value);
}

export default async function Home() {
  const [ideasData, inventoryData, runtimeData] = await Promise.all([
    loadIdeas(),
    loadInventory(),
    loadRuntimeSummary(),
  ]);

  const topOpportunityIdeas: OpportunityIdea[] = (ideasData?.ideas ?? [])
    .map((idea) => {
      const cost = Math.max(idea.estimated_cost, 0.0001);
      return {
        ...idea,
        estimated_collective_upside: (Math.max(idea.potential_value - idea.actual_value, 0) * idea.confidence) / cost,
      };
    })
    .sort((a, b) => b.estimated_collective_upside - a.estimated_collective_upside)
    .slice(0, 5);

  const topAchievements = (inventoryData?.implementation_usage?.lineage_links ?? [])
    .filter((row) => row.valuation && row.valuation.event_count > 0)
    .sort((a, b) => {
      const aValue = (a.valuation?.measured_value_total ?? 0) + (a.valuation?.roi_ratio ?? 0);
      const bValue = (b.valuation?.measured_value_total ?? 0) + (b.valuation?.roi_ratio ?? 0);
      return bValue - aValue;
    })
    .slice(0, 5);

  const topRuntimeActivity = (runtimeData?.ideas ?? [])
    .sort((a, b) => b.event_count - a.event_count)
    .slice(0, 5);

  const summary = ideasData?.summary;

  return (
    <main className="min-h-[calc(100vh-3.5rem)] px-4 md:px-8 py-10">
      <section className="mx-auto max-w-6xl grid gap-8">
        <section className="relative overflow-hidden rounded-2xl border bg-gradient-to-br from-background via-background to-muted/40 p-6 md:p-10">
          <div className="absolute -right-16 -top-16 h-44 w-44 rounded-full bg-primary/10 blur-2xl" />
          <div className="absolute -left-10 bottom-0 h-36 w-36 rounded-full bg-emerald-400/15 blur-2xl" />

          <div className="relative grid gap-5">
            <p className="text-sm text-muted-foreground">Collective intelligence operating system</p>
            <h1 className="text-3xl md:text-5xl font-semibold leading-tight tracking-tight max-w-4xl">
              Turn ideas into measurable collective value.
            </h1>
            <p className="max-w-3xl text-muted-foreground">
              Coherence Network links ideas to specs, implementations, runtime usage, and contributor attribution so new
              contributors can see where help is needed and where impact is highest.
            </p>

            <div className="flex flex-wrap gap-3 pt-1">
              <Button asChild>
                <Link href="/contributors">Start Contributing</Link>
              </Button>
              <Button asChild variant="secondary">
                <Link href="/ideas">Pick a High-Upside Idea</Link>
              </Button>
              <Button asChild variant="outline">
                <a href={`${getApiBase()}/docs`} target="_blank" rel="noopener noreferrer">
                  API For Machines
                </a>
              </Button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2 text-sm">
              <div className="rounded-lg border bg-background/80 p-3">
                <p className="text-muted-foreground">Ideas tracked</p>
                <p className="text-xl font-semibold">{formatNumber(summary?.total_ideas)}</p>
              </div>
              <div className="rounded-lg border bg-background/80 p-3">
                <p className="text-muted-foreground">Estimated total potential value</p>
                <p className="text-xl font-semibold">{formatNumber(summary?.total_potential_value)}</p>
              </div>
              <div className="rounded-lg border bg-background/80 p-3">
                <p className="text-muted-foreground">Remaining value gap</p>
                <p className="text-xl font-semibold">{formatNumber(summary?.total_value_gap)}</p>
              </div>
            </div>
          </div>
        </section>

        <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <article className="rounded-xl border p-5 space-y-3">
            <p className="text-sm text-muted-foreground">Main Idea</p>
            <h2 className="text-xl font-semibold">One walkable chain from idea to realized value</h2>
            <p className="text-sm text-muted-foreground">
              Every contribution should be traceable through the same chain: idea to spec to process to implementation
              to usage to measurable value.
            </p>
            <div className="flex flex-wrap gap-2 text-xs">
              {[
                "Idea",
                "Spec",
                "Process",
                "Implementation",
                "Runtime Usage",
                "Value Attribution",
              ].map((step) => (
                <span key={step} className="rounded-full border px-2 py-1 bg-muted/40">
                  {step}
                </span>
              ))}
            </div>
          </article>

          <article className="rounded-xl border p-5 space-y-3">
            <p className="text-sm text-muted-foreground">Contributor Onboarding</p>
            <h2 className="text-xl font-semibold">Best first path for a new contributor</h2>
            <ol className="space-y-2 text-sm text-muted-foreground list-decimal list-inside">
              <li>Register in the contributor registry and declare your role.</li>
              <li>Pick one high-upside idea or unanswered question.</li>
              <li>Create a spec/task link so your implementation is attributable.</li>
            </ol>
            <div className="flex gap-2 flex-wrap">
              <Link href="/contributors" className="text-sm underline text-muted-foreground hover:text-foreground">
                Open contributors
              </Link>
              <Link href="/portfolio" className="text-sm underline text-muted-foreground hover:text-foreground">
                Open portfolio
              </Link>
              <Link href="/tasks" className="text-sm underline text-muted-foreground hover:text-foreground">
                Open tasks
              </Link>
            </div>
          </article>
        </section>

        <section className="grid grid-cols-1 xl:grid-cols-3 gap-4">
          <article className="rounded-xl border p-5 xl:col-span-2 space-y-3">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-lg font-semibold">Highest Estimated Collective Benefit</h2>
              <Link href="/ideas" className="text-sm text-muted-foreground hover:text-foreground underline">
                View all ideas
              </Link>
            </div>
            {topOpportunityIdeas.length === 0 ? (
              <p className="text-sm text-muted-foreground">No idea data available right now.</p>
            ) : (
              <ul className="space-y-2">
                {topOpportunityIdeas.map((idea) => (
                  <li key={idea.id} className="rounded-lg border p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <Link href={`/ideas/${encodeURIComponent(idea.id)}`} className="font-medium hover:underline">
                        {idea.name}
                      </Link>
                      <span className="text-xs rounded-full border px-2 py-1 bg-muted/40">{idea.manifestation_status}</span>
                    </div>
                    <p className="text-sm text-muted-foreground mt-1">{idea.description}</p>
                    <p className="text-xs text-muted-foreground mt-2">
                      upside score {idea.estimated_collective_upside.toFixed(2)} | value gap {idea.value_gap.toFixed(2)} |
                      cost est {idea.estimated_cost.toFixed(2)}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </article>

          <article className="rounded-xl border p-5 space-y-3">
            <h2 className="text-lg font-semibold">Recent Achievements</h2>
            {topAchievements.length === 0 ? (
              <p className="text-sm text-muted-foreground">No measured usage achievements yet.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {topAchievements.map((row) => (
                  <li key={row.lineage_id} className="rounded-lg border p-3">
                    <p className="font-medium">{row.idea_id}</p>
                    <p className="text-xs text-muted-foreground">spec {row.spec_id}</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      value {formatNumber(row.valuation?.measured_value_total)} | ROI {formatNumber(row.valuation?.roi_ratio)} |
                      events {formatNumber(row.valuation?.event_count)}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </article>
        </section>

        <section className="rounded-xl border bg-background/60 p-5 space-y-4">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <h2 className="text-lg font-semibold">Search Projects</h2>
            <p className="text-sm text-muted-foreground">
              Try <code className="rounded bg-muted px-1 py-0.5">react</code>,{" "}
              <code className="rounded bg-muted px-1 py-0.5">fastapi</code>,{" "}
              <code className="rounded bg-muted px-1 py-0.5">neo4j</code>
            </p>
          </div>
          <form action="/search" method="GET" className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-2">
            <Input name="q" placeholder="Search projects..." autoComplete="off" className="h-11 bg-background" />
            <Button type="submit" className="h-11">
              Search
            </Button>
          </form>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 text-sm">
            {topRuntimeActivity.map((row) => (
              <div key={row.idea_id} className="rounded border p-2">
                <p className="font-medium">{row.idea_id}</p>
                <p className="text-xs text-muted-foreground">
                  24h events {formatNumber(row.event_count)} | avg runtime {formatNumber(row.average_runtime_ms)}ms
                </p>
              </div>
            ))}
            {topRuntimeActivity.length === 0 && (
              <p className="text-sm text-muted-foreground">No runtime activity captured in the last 24 hours.</p>
            )}
          </div>
        </section>

        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {API_NAV_CARDS.map((card) => (
            <Link
              key={card.href}
              href={card.href}
              className="rounded-lg border bg-background/60 p-4 hover:bg-background/80 transition-colors"
            >
              <div className="flex items-center justify-between gap-3">
                <h3 className="font-semibold">{card.title}</h3>
                <span className="text-muted-foreground text-sm">→</span>
              </div>
              <p className="text-sm text-muted-foreground mt-2">{card.description}</p>
            </Link>
          ))}
        </section>
      </section>
    </main>
  );
}
