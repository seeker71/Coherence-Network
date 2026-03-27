import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Vision Roadmap",
  description:
    "Product vision and near-term roadmap for Coherence Network, focused on reliable delivery and measurable value flow.",
};

type RoadmapStep = {
  phase: string;
  outcome: string;
  why: string;
};

const ROADMAP: RoadmapStep[] = [
  {
    phase: "Foundation",
    outcome: "Prove end-to-end value lineage from idea to implementation to usage.",
    why: "Trust starts with verifiable execution, not claims.",
  },
  {
    phase: "Execution Efficiency",
    outcome: "Increase task throughput while reducing retries and manual intervention.",
    why: "Sustained progress requires predictable, observable delivery loops.",
  },
  {
    phase: "Network Effect",
    outcome: "Expand cross-instance collaboration and contributor attribution.",
    why: "Ideas realize more value when review, build, and funding can federate.",
  },
];

export default function VisionRoadmapPage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 lg:px-8 space-y-10">
      <header className="space-y-3">
        <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Coherence Network</p>
        <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight">Vision Roadmap</h1>
        <p className="max-w-3xl text-foreground/90 leading-relaxed">
          The goal is simple: ideas should not disappear. Coherence Network maps idea flow from
          origin to impact and keeps attribution visible at each step.
        </p>
      </header>

      <section className="rounded-2xl border border-border/50 bg-card/40 p-6 sm:p-8">
        <h2 className="text-xl font-medium mb-3">What we are building</h2>
        <p className="text-foreground/90 leading-relaxed">
          A shared system where contributors can publish, review, implement, and fund ideas with a
          transparent lineage trail. Progress is measured by coherence and outcomes, not hype.
        </p>
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-medium">Roadmap phases</h2>
        <div className="grid gap-4">
          {ROADMAP.map((step) => (
            <article key={step.phase} className="rounded-xl border border-border/40 bg-background/70 p-5">
              <h3 className="font-medium text-lg">{step.phase}</h3>
              <p className="mt-1 text-foreground/90">{step.outcome}</p>
              <p className="mt-2 text-sm text-muted-foreground">Why it matters: {step.why}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="pt-2">
        <p className="text-sm text-foreground/90">
          Want implementation-level detail? Explore live execution surfaces in{" "}
          <Link href="/tasks" className="underline underline-offset-4 hover:text-foreground">
            Pipeline
          </Link>{" "}
          and{" "}
          <Link href="/specs" className="underline underline-offset-4 hover:text-foreground">
            Specs
          </Link>
          .
        </p>
      </section>
    </div>
  );
}
