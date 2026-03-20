import Link from "next/link";

import { Button } from "@/components/ui/button";
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

const THREE_PATHS = [
  {
    title: "Share an Insight",
    description:
      "You noticed something. A pattern, a gap, a better way. Publish it \u2014 even a two-sentence idea can spark something real.",
    href: "/ideas",
    label: "Share an idea",
  },
  {
    title: "Build Something Real",
    description:
      "Pick up an idea someone shared. Spec it, test it, ship it. Your work stays connected to the insight that inspired it.",
    href: "/tasks",
    label: "Find work",
  },
  {
    title: "Back What Matters",
    description:
      "Stake your belief in ideas that resonate. When they create real value, the credit traces back to everyone involved.",
    href: "/contribute",
    label: "Contribute",
  },
];

const FLOW_STEPS = ["Idea", "Review", "Spec", "Build", "Ship", "Impact"];

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

  // Retained for future use (achievements section planned for later pass)
  void inventoryData;
  void runtimeData;

  const summary = ideasData?.summary;

  return (
    <main className="min-h-[calc(100vh-3.5rem)]">
      {/* Section 1: THE INVITATION */}
      <section className="min-h-[80vh] flex flex-col justify-center items-center text-center px-4 py-20 relative">
        {/* Soft ambient glow */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-1/4 left-1/3 w-96 h-96 rounded-full bg-primary/10 blur-[120px]" />
          <div className="absolute bottom-1/4 right-1/4 w-80 h-80 rounded-full bg-chart-2/8 blur-[100px]" />
        </div>

        <div className="relative max-w-3xl mx-auto space-y-8 animate-fade-in-up">
          <h1 className="text-4xl md:text-6xl lg:text-7xl font-normal md:font-light tracking-tight leading-[1.1]">
            Ideas deserve to<br />
            <span className="text-primary">become real</span>
          </h1>
          <p className="text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto leading-relaxed">
            Share what you see. Build what matters. Every contribution traced
            from thought to impact — openly, fairly, together.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center pt-4">
            <Button asChild className="rounded-full px-8 py-3 text-base">
              <Link href="/ideas">Start Exploring</Link>
            </Button>
            <Link
              href="/demo"
              className="text-muted-foreground hover:text-foreground transition-colors duration-300 underline underline-offset-4 py-3"
            >
              See how it works
            </Link>
          </div>
        </div>
      </section>

      {/* Section 2: THREE PATHS */}
      <section className="px-4 md:px-8 py-16 max-w-6xl mx-auto">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 animate-fade-in-up delay-100">
          {THREE_PATHS.map((path) => (
            <article
              key={path.title}
              className="hover-lift rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-8 space-y-4"
            >
              <h3 className="text-xl font-medium">{path.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {path.description}
              </p>
              <Link
                href={path.href}
                className="inline-block text-sm text-primary hover:text-foreground transition-colors duration-300"
              >
                {path.label} &rarr;
              </Link>
            </article>
          ))}
        </div>
      </section>

      {/* Section 3: THE PULSE */}
      <section className="px-4 md:px-8 py-16 max-w-6xl mx-auto animate-fade-in-up delay-200">
        <h2 className="text-2xl md:text-3xl font-light text-center mb-10">
          What&apos;s Happening Now
        </h2>
        {summary ? (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-8 text-center space-y-2">
              <p className="text-3xl md:text-4xl font-light text-primary">
                {formatNumber(summary.total_ideas)}
              </p>
              <p className="text-sm text-muted-foreground">Ideas being explored</p>
            </div>
            <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-8 text-center space-y-2">
              <p className="text-3xl md:text-4xl font-light text-primary">
                {formatNumber(summary.total_potential_value)}
              </p>
              <p className="text-sm text-muted-foreground">Value created together</p>
            </div>
            <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-8 text-center space-y-2">
              <p className="text-3xl md:text-4xl font-light text-primary">
                {formatNumber(summary.total_value_gap)}
              </p>
              <p className="text-sm text-muted-foreground">Remaining opportunity</p>
            </div>
          </div>
        ) : (
          <p className="text-center text-muted-foreground text-sm">
            The network is warming up. Live metrics appear once the API is connected.
          </p>
        )}
      </section>

      {/* Section 4: THE FLOW */}
      <section className="px-4 md:px-8 py-16 max-w-4xl mx-auto animate-fade-in-up delay-300">
        <h2 className="text-2xl md:text-3xl font-light text-center mb-10">
          The Journey
        </h2>
        <div className="flex items-center justify-between relative">
          {/* Connecting line */}
          <div className="absolute top-1/2 left-0 right-0 h-px bg-border/60 -translate-y-1/2" />
          {FLOW_STEPS.map((step, i) => (
            <div key={step} className="relative flex flex-col items-center gap-2 z-10">
              <div
                className={`w-10 h-10 md:w-12 md:h-12 rounded-full border-2 flex items-center justify-center text-xs md:text-sm font-medium ${
                  i === 0 || i === FLOW_STEPS.length - 1
                    ? "border-primary bg-primary/20 text-primary"
                    : "border-border bg-background text-muted-foreground"
                }`}
              >
                {i + 1}
              </div>
              <span className="text-xs text-muted-foreground">{step}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Section 5: TOP OPPORTUNITIES */}
      <section className="px-4 md:px-8 py-16 max-w-6xl mx-auto animate-fade-in-up delay-300">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-8">
          <h2 className="text-2xl md:text-3xl font-light">
            Where Help Creates the Most Value
          </h2>
          <Link
            href="/ideas"
            className="text-sm text-muted-foreground hover:text-foreground underline underline-offset-4 transition-colors duration-300 shrink-0"
          >
            View all ideas
          </Link>
        </div>
        {topOpportunityIdeas.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No ideas loaded yet. Once the API is running, the highest-value opportunities will appear here.
          </p>
        ) : (
          <div className="grid gap-4">
            {topOpportunityIdeas.map((idea) => (
              <article
                key={idea.id}
                className="hover-lift rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 md:p-8"
              >
                <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                  <Link
                    href={`/ideas/${encodeURIComponent(idea.id)}`}
                    className="text-lg font-medium hover:text-primary transition-colors duration-300"
                  >
                    {idea.name}
                  </Link>
                  <span className="text-xs rounded-full border border-border/40 px-3 py-1 bg-muted/30 text-muted-foreground">
                    {idea.manifestation_status}
                  </span>
                </div>
                <p className="text-sm text-muted-foreground mb-3 line-clamp-2">
                  {idea.description}
                </p>
                <div className="flex items-center gap-3">
                  <div className="flex-1 h-1.5 rounded-full bg-muted/40 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-primary/60"
                      style={{ width: `${Math.min(idea.confidence * 100, 100)}%` }}
                    />
                  </div>
                  <span className="text-xs text-muted-foreground whitespace-nowrap">
                    {(idea.confidence * 100).toFixed(0)}% confidence
                  </span>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      {/* Section 6: FIRST STEPS */}
      <section className="px-4 md:px-8 py-20 max-w-3xl mx-auto text-center animate-fade-in-up delay-400">
        <p className="text-xl md:text-2xl font-light text-muted-foreground mb-12 leading-relaxed">
          You don&apos;t need to know everything.<br />
          Start wherever feels right.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-8 text-left">
          <div className="space-y-2">
            <Link
              href="/ideas"
              className="text-base font-medium hover:text-primary transition-colors duration-300"
            >
              Browse ideas
            </Link>
            <p className="text-sm text-muted-foreground">
              Curious? See what people are working on.
            </p>
          </div>
          <div className="space-y-2">
            <Link
              href="/demo"
              className="text-base font-medium hover:text-primary transition-colors duration-300"
            >
              Watch the demo
            </Link>
            <p className="text-sm text-muted-foreground">
              Want to understand the flow? It takes 5 minutes.
            </p>
          </div>
          <div className="space-y-2">
            <Link
              href="/contribute"
              className="text-base font-medium hover:text-primary transition-colors duration-300"
            >
              Share your first insight
            </Link>
            <p className="text-sm text-muted-foreground">
              Ready to contribute? No setup needed.
            </p>
          </div>
        </div>
      </section>
      {/* Footer note */}
      <footer className="px-4 md:px-8 py-12 max-w-3xl mx-auto text-center border-t border-border/20">
        <p className="text-xs text-muted-foreground/70 leading-relaxed">
          Built on coherence, not control. Every contribution is traced, every
          decision is visible, and the math always checks out.
        </p>
      </footer>
    </main>
  );
}
