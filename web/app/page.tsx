import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const CARDS: Array<{ href: string; title: string; description: string }> = [
  {
    href: "/portfolio",
    title: "Portfolio",
    description: "ROI-first governance: questions, cost signals, and next actions.",
  },
  {
    href: "/ideas",
    title: "Ideas",
    description: "Browse the idea graph: value gap, confidence, and open questions.",
  },
  {
    href: "/specs",
    title: "Specs",
    description: "Specs discovered from system lineage inventory (what exists, what’s missing).",
  },
  {
    href: "/usage",
    title: "Usage",
    description: "Runtime telemetry and friction signals rendered for human inspection.",
  },
  {
    href: "/import",
    title: "Import Stack",
    description: "Upload a lockfile and inspect risk/coherence of your dependency tree.",
  },
  {
    href: "/gates",
    title: "Gates",
    description: "Deployment validation contracts and PR-to-public checks.",
  },
  {
    href: "/friction",
    title: "Friction",
    description: "Cost-without-gain ledger: blockers, tool failures, and energy loss estimates.",
  },
  {
    href: "/contributors",
    title: "Contributors",
    description: "People and agents registered as value-producing entities in the system.",
  },
  {
    href: "/assets",
    title: "Assets",
    description: "Trackable artifacts with cost and contribution attribution (code, docs, endpoints).",
  },
];

export default function Home() {
  return (
    <main className="min-h-[calc(100vh-3.5rem)] px-4 md:px-8 py-10">
      <section className="mx-auto max-w-6xl grid gap-10">
        <div className="grid gap-4">
          <p className="text-sm text-muted-foreground">
            Open source intelligence graph
          </p>
          <h1 className="text-4xl md:text-5xl font-semibold leading-tight tracking-tight">
            Search, measure, and attribute value across the OSS ecosystem.
          </h1>
          <p className="text-muted-foreground max-w-3xl">
            Coherence Network connects projects, ideas, specs, implementations, usage, and contributors into one
            inspectable operating model.
          </p>
        </div>

        <section className="rounded-lg border bg-background/60 p-4 md:p-6 grid gap-4">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <h2 className="font-semibold">Search packages</h2>
            <p className="text-sm text-muted-foreground">
              Examples: <code className="rounded bg-muted px-1 py-0.5">react</code>,{" "}
              <code className="rounded bg-muted px-1 py-0.5">fastapi</code>,{" "}
              <code className="rounded bg-muted px-1 py-0.5">neo4j</code>
            </p>
          </div>
          <form action="/search" method="GET" className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-2">
            <Input name="q" placeholder="Search projects…" autoComplete="off" className="h-11 bg-background" />
            <Button type="submit" className="h-11">
              Search
            </Button>
          </form>
          <p className="text-sm text-muted-foreground">
            If you already know the project path, open a project page directly:{" "}
            <code className="rounded bg-muted px-1 py-0.5">/project/npm/react</code>.
          </p>
        </section>

        <section className="grid gap-4">
          <div className="flex items-end justify-between gap-3 flex-wrap">
            <h2 className="text-xl font-semibold">Console</h2>
            <Link href="/portfolio" className="text-sm text-muted-foreground hover:text-foreground underline">
              Open operating cockpit
            </Link>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {CARDS.map((c) => (
              <Link
                key={c.href}
                href={c.href}
                className="rounded-lg border bg-background/60 p-4 hover:bg-background/80 transition-colors"
              >
                <div className="flex items-center justify-between gap-3">
                  <h3 className="font-semibold">{c.title}</h3>
                  <span className="text-muted-foreground text-sm">→</span>
                </div>
                <p className="text-sm text-muted-foreground mt-2">{c.description}</p>
              </Link>
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}
