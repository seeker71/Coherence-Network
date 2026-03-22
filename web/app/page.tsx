import Link from "next/link";

import { Button } from "@/components/ui/button";
import { IdeaSubmitForm } from "@/components/idea_submit_form";
import { getApiBase } from "@/lib/api";
import { fetchJsonOrNull } from "@/lib/fetch";

type IdeaWithScore = {
  id: string;
  name: string;
  description: string;
  potential_value: number;
  actual_value: number;
  estimated_cost: number;
  confidence: number;
  manifestation_status: string;
  open_questions: Array<{
    question: string;
    value_to_whole: number;
    estimated_cost: number;
    answer?: string | null;
    measured_delta?: number | null;
  }>;
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

type ResonanceItem = {
  idea_id: string;
  name: string;
  last_activity_at: string;
  free_energy_score: number;
  manifestation_status: string;
  activity_type?: string;
};

type CoherenceScoreResponse = {
  score: number;
  signals_with_data: number;
  total_signals: number;
  computed_at: string;
};

const HOW_IT_WORKS = [
  {
    icon: "\uD83D\uDCA1",
    title: "Share an idea",
    description: "Type what you're thinking. No sign-up needed.",
  },
  {
    icon: "\uD83C\uDF31",
    title: "Watch it grow",
    description: "Others ask questions, write specs, build.",
  },
  {
    icon: "\uD83D\uDD04",
    title: "Value flows back",
    description: "Every contribution is recorded. Credit flows to creators.",
  },
];

export const revalidate = 90;

async function loadIdeas(): Promise<IdeasResponse | null> {
  return fetchJsonOrNull<IdeasResponse>(`${getApiBase()}/api/ideas`, {}, 5000);
}

async function loadResonance(): Promise<ResonanceItem[]> {
  try {
    const data = await fetchJsonOrNull<ResonanceItem[] | { ideas: ResonanceItem[] }>(
      `${getApiBase()}/api/ideas/resonance?window_hours=72&limit=3`,
      {},
      5000,
    );
    if (!data) return [];
    return Array.isArray(data) ? data : data.ideas || [];
  } catch {
    return [];
  }
}

async function loadCoherenceScore(): Promise<CoherenceScoreResponse | null> {
  return fetchJsonOrNull<CoherenceScoreResponse>(`${getApiBase()}/api/coherence/score`, {}, 5000);
}

function formatNumber(value: number | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "0";
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
}

function formatCoherenceScore(value: number | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "0.00";
  return value.toFixed(2);
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default async function Home() {
  const [ideasData, resonanceItems, coherenceScore] = await Promise.all([
    loadIdeas(),
    loadResonance(),
    loadCoherenceScore(),
  ]);

  const summary = ideasData?.summary;
  // Count unique contributors from contribution ledger, not idea count
  const nodeCount = 1; // Will come from /api/federation/nodes when more nodes join

  return (
    <main className="min-h-[calc(100vh-3.5rem)]">
      {/* Section 1: HERO — THE QUESTION */}
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

          {/* The text box — submits directly to the API */}
          <IdeaSubmitForm />
        </div>
      </section>

      {/* Section 2: PULSE — quiet proof of life */}
      <section className="px-4 md:px-8 py-8 max-w-4xl mx-auto animate-fade-in-up delay-100">
        {summary || coherenceScore ? (
          <div className="flex flex-wrap justify-center gap-8 md:gap-12 text-center">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2 w-2" aria-hidden="true">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary/40" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-primary/60" />
              </span>
              <span className="text-sm text-muted-foreground">
                <span className="text-foreground font-medium">{formatNumber(summary?.total_ideas)}</span> ideas alive
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="relative flex h-2 w-2" aria-hidden="true">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-chart-2/40" style={{ animationDelay: "0.5s" }} />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-chart-2/60" />
              </span>
              <span className="text-sm text-muted-foreground">
                <span className="text-foreground font-medium">{formatNumber(summary?.total_actual_value)}</span> value created
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="relative flex h-2 w-2" aria-hidden="true">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-chart-3/40" style={{ animationDelay: "1s" }} />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-chart-3/60" />
              </span>
              <span className="text-sm text-muted-foreground">
                <span className="text-foreground font-medium">{nodeCount}</span>{" "}node{nodeCount !== 1 ? "s" : ""}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="relative flex h-2 w-2" aria-hidden="true">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary/40" style={{ animationDelay: "1.5s" }} />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-primary/60" />
              </span>
              <span className="text-sm text-muted-foreground">
                <span className="text-foreground font-medium">{formatCoherenceScore(coherenceScore?.score)}</span> coherence
                {coherenceScore && (
                  <span className="text-muted-foreground/70"> ({coherenceScore.signals_with_data}/{coherenceScore.total_signals} signals)</span>
                )}
              </span>
            </div>
          </div>
        ) : (
          <p className="text-center text-muted-foreground/60 text-sm">
            The network is warming up. Live metrics appear once the API is connected.
          </p>
        )}
      </section>

      {/* Section 3: HOW IT WORKS — 3 steps with connecting lines */}
      <section className="px-4 md:px-8 py-8 max-w-4xl mx-auto animate-fade-in-up delay-200">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 relative">
          {/* Connecting lines (desktop only) */}
          <div className="hidden md:block absolute top-10 left-[calc(33.3%+0.75rem)] right-[calc(33.3%+0.75rem)] h-px bg-border/40" />
          {HOW_IT_WORKS.map((step, i) => (
            <div key={step.title} className="text-center space-y-3 relative">
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-card/80 border border-border/30 text-2xl">
                {step.icon}
              </div>
              <h3 className="text-base font-medium">{step.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed max-w-[240px] mx-auto">
                {step.description}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Section 4: LIVE FEED PREVIEW — 3 most recent resonance items */}
      <section className="px-4 md:px-8 py-8 max-w-4xl mx-auto animate-fade-in-up delay-300">
        <h2 className="text-lg font-medium text-center mb-6 text-muted-foreground">
          Recent activity
        </h2>
        {resonanceItems.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {resonanceItems.slice(0, 3).map((item) => (
              <Link
                key={item.idea_id}
                href={`/ideas/${encodeURIComponent(item.idea_id)}`}
                className="hover-lift rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-2 block"
              >
                <p className="text-sm font-medium line-clamp-1">{item.name}</p>
                <p className="text-xs text-muted-foreground">
                  {item.activity_type ? item.activity_type.replace(/_/g, " ") : item.manifestation_status}
                </p>
                <p className="text-xs text-muted-foreground/60">
                  {timeAgo(item.last_activity_at)}
                </p>
              </Link>
            ))}
          </div>
        ) : (
          <p className="text-center text-sm text-muted-foreground/60">
            No recent activity yet. Be the first to share an idea.
          </p>
        )}
        {resonanceItems.length > 0 && (
          <p className="text-center mt-4">
            <Link
              href="/resonance"
              className="text-xs text-muted-foreground/60 hover:text-foreground transition-colors underline underline-offset-4"
            >
              See all activity
            </Link>
          </p>
        )}
      </section>

      {/* Section 5: EXPLORE NUDGE */}
      <section className="px-4 md:px-8 py-8 max-w-2xl mx-auto text-center animate-fade-in-up delay-400">
        <Button asChild className="rounded-full px-8 py-3 text-base bg-primary hover:bg-primary/90">
          <Link href="/ideas">Explore Ideas &rarr;</Link>
        </Button>
        <p className="mt-3">
          <Link
            href="/resonance"
            className="text-sm text-muted-foreground/60 hover:text-foreground transition-colors underline underline-offset-4"
          >
            or browse the resonance feed
          </Link>
        </p>
      </section>

      {/* Section 6: THE GENTLE TAP */}
      <section className="px-4 md:px-8 py-16 max-w-2xl mx-auto text-center">
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
          <Link href="/contribute" className="hover:text-foreground transition-colors">Contribute</Link>
        </div>
        <p className="text-xs text-muted-foreground/50 leading-relaxed">
          Ideas into realization — through attention, curiosity, and collaboration.
        </p>
      </footer>
    </main>
  );
}
