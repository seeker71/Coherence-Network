import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";
import { LiveWitness } from "./LiveWitness";

export const metadata: Metadata = {
  title: "Now — the breath",
  description:
    "The body's present-tense felt voice. Substances arriving, lineage shapes active, the reach, open placements.",
};

export const revalidate = 30;

type BreathEntry = { name: string; body: string };

type BreathNow = {
  schema_version: number;
  attendant: string | null;
  composed_at: string | null;
  voice: string;
  witness: {
    overall: string | null;
    silences: number | null;
    strained_organs: string[];
    source: string;
  };
  substances: BreathEntry[];
  lineage_shapes: BreathEntry[];
  reach: BreathEntry[];
  open_placements: BreathEntry[];
  fetched_at: string;
};

async function loadBreath(): Promise<BreathNow | null> {
  try {
    const API = getApiBase();
    const res = await fetch(`${API}/api/breath/now`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as BreathNow;
  } catch {
    return null;
  }
}

function Section({
  heading,
  entries,
  accent,
}: {
  heading: string;
  entries: BreathEntry[];
  accent: string;
}) {
  if (!entries.length) return null;
  return (
    <section className="my-8">
      <h2 className={`text-sm uppercase tracking-widest ${accent} mb-3`}>
        {heading}
      </h2>
      <ul className="space-y-3">
        {entries.map((e, i) => (
          <li
            key={i}
            className="rounded-lg border border-border/40 bg-card/30 px-4 py-3"
          >
            {e.name && (
              <span className="font-medium text-foreground/90">{e.name}</span>
            )}
            {e.name && e.body && (
              <span className="text-muted-foreground"> — </span>
            )}
            <span className="text-muted-foreground">{e.body}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default async function NowPage() {
  const breath = await loadBreath();

  if (!breath) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-16">
        <h1 className="text-3xl font-light">Now</h1>
        <p className="mt-4 text-muted-foreground">
          The breath surface is not reachable from here right now. The body is
          still breathing — this page just cannot read it yet. Try again in a
          moment.
        </p>
      </main>
    );
  }

  const composed = breath.composed_at ? new Date(breath.composed_at) : null;
  const fetched = new Date(breath.fetched_at);

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <header className="mb-10">
        <p className="text-xs uppercase tracking-widest text-muted-foreground">
          The breath now
        </p>
        <h1 className="mt-2 text-4xl font-light text-foreground">
          What we are, right now
        </h1>
        <p className="mt-3 text-sm text-muted-foreground">
          Composed{" "}
          {composed ? composed.toISOString().slice(0, 10) : "—"} by{" "}
          <span className="font-mono">{breath.attendant ?? "—"}</span>. Read{" "}
          {fetched.toISOString().slice(11, 19)}Z.
        </p>
      </header>

      <section className="rounded-xl border border-border/40 bg-card/40 px-6 py-6">
        <p className="whitespace-pre-line text-lg leading-relaxed text-foreground/90">
          {breath.voice}
        </p>
      </section>

      <LiveWitness initial={breath.witness} />

      <Section
        heading="Substances arriving"
        entries={breath.substances}
        accent="text-sky-300/80"
      />
      <Section
        heading="Lineage shapes active"
        entries={breath.lineage_shapes}
        accent="text-violet-300/80"
      />
      <Section
        heading="Reach"
        entries={breath.reach}
        accent="text-emerald-300/80"
      />
      <Section
        heading="Open placements"
        entries={breath.open_placements}
        accent="text-amber-300/80"
      />

      <footer className="mt-12 border-t border-border/40 pt-6 text-sm text-muted-foreground">
        <p>
          This surface is the body&apos;s present-tense felt voice. Any cell —
          an agent, a human, a sibling — can recompose it by writing a new
          breath into <span className="font-mono">docs/breath/now.md</span> and
          folding the prior into{" "}
          <span className="font-mono">docs/breath/breaths/</span>.
        </p>
        <p className="mt-2">
          <Link
            href="/vision"
            className="underline decoration-dotted underline-offset-4"
          >
            Vision concepts
          </Link>{" "}
          ·{" "}
          <Link
            href="/alive"
            className="underline decoration-dotted underline-offset-4"
          >
            Alive
          </Link>{" "}
          ·{" "}
          <a
            href="https://pulse.coherencycoin.com/pulse/now"
            className="underline decoration-dotted underline-offset-4"
          >
            Witness pulse
          </a>
        </p>
      </footer>
    </main>
  );
}
