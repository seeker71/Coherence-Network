import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getApiBase } from "@/lib/api";
import {
  buildRuntimeSummarySearchParams,
  buildSystemLineageSearchParams,
} from "@/lib/egress";
import { fetchJsonOrNull } from "@/lib/fetch";

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

const LANDING_PATHS: Array<{
  title: string;
  description: string;
  links: Array<{ href: string; label: string }>;
}> = [
  {
    title: "Start Exploring",
    description: "Understand where value and uncertainty are concentrated before picking work.",
    links: [
      { href: "/ideas", label: "High-upside ideas" },
      { href: "/search", label: "Project search" },
      { href: "/flow", label: "System flow map" },
    ],
  },
  {
    title: "Contribute With Context",
    description: "Use one guided contribution chain so each change maps to measurable system value.",
    links: [
      { href: "/contribute", label: "Contribution console" },
      { href: "/portfolio", label: "Portfolio governance" },
      { href: "/tasks", label: "Execution tasks" },
    ],
  },
  {
    title: "Operate Reliably",
    description: "Monitor runtime, automation, and deployment gates without hunting across pages.",
    links: [
      { href: "/usage", label: "Runtime usage" },
      { href: "/automation", label: "Automation readiness" },
      { href: "/gates", label: "Gate status" },
    ],
  },
];

const ADVANCED_SURFACES: Array<{ href: string; label: string }> = [
  { href: "/specs", label: "Specs" },
  { href: "/friction", label: "Friction" },
  { href: "/contributors", label: "Contributors" },
  { href: "/contributions", label: "Contributions" },
  { href: "/assets", label: "Assets" },
  { href: "/agent", label: "Agent" },
  { href: "/api-coverage", label: "API Coverage" },
  { href: "/import", label: "Import" },
  { href: "/api-health", label: "API Health" },
  { href: "/remote-ops", label: "Remote Ops" },
];

const WELCOME_SIGNALS: Array<{ label: string; value: string }> = [
  {
    label: "Always visible",
    value: "Home and the core actions to explore, collaborate, and ship",
  },
  {
    label: "In menus",
    value: "Specialized pages for deeper operational and governance work",
  },
  {
    label: "For deep work",
    value: "Context links stay nearby without crowding the page",
  },
];

export const revalidate = 90;

async function loadIdeas(): Promise<IdeasResponse | null> {
  const data = await fetchJsonOrNull<IdeasResponse>(`${getApiBase()}/api/ideas`, {}, 5000);
  if (!data) {
    return null;
  }
  return data;
}

async function loadInventory(): Promise<InventoryResponse | null> {
  const params = buildSystemLineageSearchParams();
  const data = await fetchJsonOrNull<InventoryResponse>(
    `${getApiBase()}/api/inventory/system-lineage?${params.toString()}`,
    undefined,
    5000,
  );
  if (!data) {
    return null;
  }
  return data;
}

async function loadRuntimeSummary(): Promise<RuntimeSummaryResponse | null> {
  const params = buildRuntimeSummarySearchParams();
  const data = await fetchJsonOrNull<RuntimeSummaryResponse>(
    `${getApiBase()}/api/runtime/ideas/summary?${params.toString()}`,
    undefined,
    5000,
  );
  if (!data) {
    return null;
  }
  return data;
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
        <section className="relative overflow-hidden rounded-2xl border border-border/70 bg-gradient-to-br from-card via-background to-accent/20 p-6 md:p-10">
          <div className="absolute -right-12 -top-14 h-44 w-44 rounded-full bg-primary/20 blur-3xl" />
          <div className="absolute -left-8 bottom-0 h-36 w-36 rounded-full bg-chart-2/20 blur-3xl" />

          <div className="relative grid gap-5">
            <p className="text-sm text-muted-foreground">Collaborative open source workspace</p>
            <h1 className="text-3xl md:text-5xl font-semibold leading-tight tracking-tight max-w-4xl">
              Find meaningful work, build together, and see real impact.
            </h1>
            <p className="max-w-3xl text-muted-foreground">
              Coherence Network helps people discover where help is needed, connect work across teams, and follow each
              contribution from intention to outcome.
            </p>

            <div className="flex flex-wrap gap-3 pt-1">
              <Button asChild>
                <Link href="/contribute">Join the Workspace</Link>
              </Button>
              <Button asChild variant="secondary">
                <Link href="/ideas">Explore Opportunities</Link>
              </Button>
              <Button asChild variant="outline">
                <a href={`${getApiBase()}/docs`} target="_blank" rel="noopener noreferrer">
                  Developer Docs
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
            <p className="text-sm text-muted-foreground">Shared Journey</p>
            <h2 className="text-xl font-semibold">A clear path from intention to impact</h2>
            <p className="text-sm text-muted-foreground">
              Each contribution follows one easy story: identify a need, align on a plan, build it, then see how it helps.
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
            <p className="text-sm text-muted-foreground">Getting Started</p>
            <h2 className="text-xl font-semibold">A calm first path for new contributors</h2>
            <ol className="space-y-2 text-sm text-muted-foreground list-decimal list-inside">
              <li>Set up your profile and share what you like to work on.</li>
              <li>Choose one idea where your help can create momentum.</li>
              <li>Ship a change and keep attribution connected to the result.</li>
            </ol>
            <div className="flex gap-2 flex-wrap">
              <Link href="/contribute" className="text-sm underline text-muted-foreground hover:text-foreground">
                Open contribution console
              </Link>
              <Link href="/portfolio" className="text-sm underline text-muted-foreground hover:text-foreground">
                Open portfolio
              </Link>
              <Link href="/tasks" className="text-sm underline text-muted-foreground hover:text-foreground">
                Open tasks
              </Link>
            </div>
          </article>

          <article className="rounded-xl border bg-background/60 p-5 space-y-3">
            <p className="text-sm text-muted-foreground">Simple By Default</p>
            <h2 className="text-xl font-semibold">Keep the essentials visible, tuck depth into menus</h2>
            <div className="space-y-2 text-sm text-muted-foreground">
              {WELCOME_SIGNALS.map((signal) => (
                <p key={signal.label}>
                  <span className="font-medium text-foreground">{signal.label}:</span> {signal.value}
                </p>
              ))}
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

        <section className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          {LANDING_PATHS.map((path) => (
            <article key={path.title} className="rounded-lg border bg-background/60 p-4 space-y-3">
              <h3 className="font-semibold">{path.title}</h3>
              <p className="text-sm text-muted-foreground">{path.description}</p>
              <div className="flex flex-wrap gap-2">
                {path.links.map((link) => (
                  <Link key={link.href} href={link.href} className="rounded border px-2 py-1 text-sm hover:bg-accent">
                    {link.label}
                  </Link>
                ))}
              </div>
            </article>
          ))}
        </section>

        <section className="rounded-xl border bg-background/60 p-4">
          <details>
            <summary className="cursor-pointer text-sm text-muted-foreground hover:text-foreground">
              Advanced surfaces (show all)
            </summary>
            <div className="mt-3 flex flex-wrap gap-2">
              {ADVANCED_SURFACES.map((item) => (
                <Link key={item.href} href={item.href} className="rounded border px-2 py-1 text-sm hover:bg-accent">
                  {item.label}
                </Link>
              ))}
            </div>
          </details>
        </section>
      </section>
    </main>
  );
}
