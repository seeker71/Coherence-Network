import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Vision & Roadmap",
  description: "Clear UX direction for Coherence Network and the next delivery milestones.",
};

const ROADMAP_PHASES = [
  {
    id: "now",
    title: "Now",
    goal: "Reduce friction for first-time contributors.",
    bullets: [
      "Keep navigation consistent across main contributor journeys.",
      "Ensure core pages expose plain-language guidance before advanced controls.",
      "Preserve resilient fallback states for API-dependent surfaces.",
    ],
  },
  {
    id: "next",
    title: "Next",
    goal: "Strengthen orientation and progress clarity.",
    bullets: [
      "Add clearer in-page context for where users are and what action is next.",
      "Standardize compact status strips and avoid stacked top-level bars.",
      "Improve cross-page continuity between ideas, specs, flow, and tasks.",
    ],
  },
  {
    id: "later",
    title: "Later",
    goal: "Scale guided workflows without overwhelming the interface.",
    bullets: [
      "Introduce deeper drill-down layers behind progressive disclosure patterns.",
      "Expand dashboard-style summaries with guardrails for readability.",
      "Measure adoption with task completion and contribution activation metrics.",
    ],
  },
];

export default function VisionRoadmapPage() {
  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-10 max-w-5xl mx-auto space-y-8">
      <header className="space-y-3">
        <p className="text-sm text-muted-foreground">UX Vision Roadmap</p>
        <h1 className="text-3xl md:text-4xl font-light tracking-tight">Build a clearer path from idea to contribution</h1>
        <p className="max-w-3xl text-muted-foreground leading-relaxed">
          This page is the shared product direction for interface quality. The core aim is simple: help new and returning
          users understand where to start, what matters now, and how to contribute without confusion.
        </p>
      </header>

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3">
        <h2 className="text-xl font-medium">Vision</h2>
        <p className="text-sm text-muted-foreground leading-relaxed">
          Coherence Network UX should feel welcoming, legible, and purposeful. Each page should guide a user to one clear
          next action while keeping advanced paths discoverable.
        </p>
      </section>

      <section className="space-y-4">
        {ROADMAP_PHASES.map((phase) => (
          <article key={phase.id} className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-xl font-medium">{phase.title}</h2>
              <span className="text-xs text-muted-foreground uppercase tracking-wide">Phase</span>
            </div>
            <p className="text-sm text-foreground/90">{phase.goal}</p>
            <ul className="list-disc pl-5 space-y-1 text-sm text-muted-foreground">
              {phase.bullets.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>
        ))}
      </section>

      <nav className="py-6 text-center space-y-2 border-t border-border/20" aria-label="Where to go next">
        <p className="text-xs text-muted-foreground/80 uppercase tracking-wider">Where to go next</p>
        <div className="flex flex-wrap justify-center gap-4 text-sm">
          <Link href="/today" className="text-amber-600 dark:text-amber-400 hover:underline">Today</Link>
          <Link href="/flow" className="text-amber-600 dark:text-amber-400 hover:underline">Flow</Link>
          <Link href="/specs" className="text-amber-600 dark:text-amber-400 hover:underline">Specs</Link>
        </div>
      </nav>
    </main>
  );
}
