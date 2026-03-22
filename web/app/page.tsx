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
    title: "Notice Something",
    description:
      "A two-sentence thought can change everything. Share what you see and let it find the people who care about the same thing.",
    href: "/contribute",
    label: "Share a thought",
  },
  {
    title: "Join the Flow",
    description:
      "Ideas are evolving right now. See what has momentum, ask a question, write a spec, or just watch it unfold.",
    href: "/resonance",
    label: "See what\u2019s alive",
  },
  {
    title: "Invest Your Attention",
    description:
      "When you put energy behind an idea, real work happens. Your belief becomes compute, specs, implementations \u2014 and the credit traces back.",
    href: "/invest",
    label: "Back an idea",
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
      {/* Section 1: THE QUESTION */}
      <section className="min-h-[80vh] flex flex-col justify-center items-center text-center px-4 py-20 relative">
        {/* Soft ambient glow */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-1/4 left-1/3 w-96 h-96 rounded-full bg-primary/10 blur-[120px]" />
          <div className="absolute bottom-1/4 right-1/4 w-80 h-80 rounded-full bg-chart-2/8 blur-[100px]" />
        </div>

        <div className="relative max-w-2xl mx-auto space-y-10 animate-fade-in-up">
          <h1 className="text-3xl md:text-5xl lg:text-6xl font-normal md:font-light tracking-tight leading-[1.15]">
            What idea are you holding?
          </h1>
          <p className="text-base md:text-lg text-muted-foreground max-w-xl mx-auto leading-relaxed">
            A pattern you noticed. A gap that needs filling. A better way.
            Share it — someone out there is looking for exactly this.
          </p>

          {/* The text box */}
          <form action="/api/share" method="GET" className="space-y-4">
            <textarea
              name="idea"
              rows={3}
              placeholder="I think there should be a way to..."
              className="w-full rounded-2xl border border-border/40 bg-card/60 backdrop-blur-sm px-6 py-4 text-base md:text-lg placeholder:text-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/40 resize-none transition-all duration-300"
            />
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <Button asChild className="rounded-full px-8 py-3 text-base">
                <Link href="/contribute">Share your idea</Link>
              </Button>
              <Link
                href="/resonance"
                className="text-muted-foreground hover:text-foreground transition-colors duration-300 underline underline-offset-4 py-3 text-sm"
              >
                or see what others are working on
              </Link>
            </div>
          </form>
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

      {/* Section 6: THE GENTLE TAP */}
      <section className="px-4 md:px-8 py-20 max-w-2xl mx-auto text-center animate-fade-in-up delay-400">
        <p className="text-xl md:text-2xl font-light text-muted-foreground leading-relaxed">
          You don&apos;t need permission.<br />
          You don&apos;t need to know everything.<br />
          You just need one thought worth sharing.
        </p>
      </section>
      {/* Footer */}
      <footer className="px-4 md:px-8 py-12 max-w-3xl mx-auto text-center border-t border-border/20">
        <div className="flex flex-wrap justify-center gap-6 text-sm text-muted-foreground/60 mb-4">
          <Link href="/resonance" className="hover:text-foreground transition-colors">Resonance</Link>
          <Link href="/ideas" className="hover:text-foreground transition-colors">Ideas</Link>
          <Link href="/invest" className="hover:text-foreground transition-colors">Invest</Link>
          <Link href="/flow" className="hover:text-foreground transition-colors">Flow</Link>
          <Link href="/automation" className="hover:text-foreground transition-colors">Automation</Link>
        </div>
        <p className="text-xs text-muted-foreground/50 leading-relaxed">
          Ideas into realization — through attention, curiosity, and collaboration.
        </p>
      </footer>
    </main>
  );
}
