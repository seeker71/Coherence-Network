// /sense/surface — the node's live world-perception surface. Shows what the node
// senses about the world (heard text + translation, who-can-hear-whom, the room's
// echo, place, what's playing), computed live from the proven world-perception.fk
// recipe. The /sense page is the install door; this is what the installed node sees.
import type { Metadata } from "next";
import Link from "next/link";
import { PerceptionSurface } from "../_components/PerceptionSurface";

export const metadata: Metadata = {
  title: "Sense surface — what the node perceives",
  description:
    "What a node senses about the world — heard text and its translation, who can hear whom, the room's echo, where we are, what's playing — computed live from the four-way-proven world-perception Form recipe.",
};

export const dynamic = "force-dynamic";

export default function SenseSurfacePage() {
  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <nav className="mb-6 text-sm text-stone-500" aria-label="breadcrumb">
        <Link href="/sense" className="transition-colors hover:text-amber-400/80">
          Sense
        </Link>
        <span className="mx-2 text-stone-700">/</span>
        <span className="text-stone-300">Surface</span>
      </nav>

      <header className="mb-8 space-y-4">
        <p className="text-sm uppercase tracking-[0.22em] text-amber-400/80">World perception</p>
        <h1 className="text-3xl font-light tracking-tight text-stone-100 md:text-5xl">
          What this node senses about the world.
        </h1>
        <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground md:text-base">
          One engine, many senses: a transcript of what was heard, its translation a tap away, which
          nodes can hear each other by inaudible ping, the room mapped by echo, whether we are moving,
          and what we are playing — offered to every node that can hear us. Each sense is the same
          channel shape; the surface is a projection over channels. Pick a scene and watch the body
          decide.
        </p>
        <p className="text-sm text-muted-foreground">
          The body:{" "}
          <Link
            href="https://github.com/seeker71/Coherence-Network/blob/main/form/form-stdlib/world-perception.fk"
            className="underline hover:text-amber-400/80"
          >
            world-perception.fk
          </Link>{" "}
          — four-way proven (Go / Rust / TypeScript / fkwu → 255). What you see below is that recipe,
          walked live in your browser.
        </p>
      </header>

      <PerceptionSurface />

      <section className="mt-10 space-y-3 rounded-xl border border-stone-800/40 bg-stone-900/30 p-4 text-sm leading-relaxed text-muted-foreground">
        <h2 className="text-lg font-light text-stone-200">The honest floor</h2>
        <p>
          The <em>logic</em> of every sense here is the body&apos;s — proven four-way and run on the
          real kernel. The <em>scene</em> is a sensed snapshot standing in for the phone&apos;s
          microphone, radios, and camera until those carriers are wired. The on-device transcript is a
          champion-challenger slot: the rented oracle holds it until the native ear clears the floor
          and costs less — which is exactly when the badge turns{" "}
          <span className="text-emerald-300">home</span>. Real cross-tongue word-rendering already
          exists in the body (English ⇄ Indonesian, proven four-way through a language-neutral pivot);
          wiring it live to this tap, and feeding the surface from real phone senses, are the next
          breaths.
        </p>
        <p>
          To make a phone one of these nodes, start at the{" "}
          <Link href="/sense" className="underline hover:text-amber-400/80">
            install door
          </Link>
          .
        </p>
      </section>
    </main>
  );
}
