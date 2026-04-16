import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getApiBase } from "@/lib/api";
import { StoryContent } from "../[conceptId]/_components/StoryContent";
import { LiveProof } from "./_components/LiveProof";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "The Living Economy — The Living Collective",
  description: "A creation economy where nourishing contribution becomes visible, flows stay verifiable, and money becomes sensing rather than scarcity.",
};

async function fetchConcept() {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/concepts/lc-economy`, { next: { revalidate: 30 } });
    if (!res.ok) return null;
    return res.json();
  } catch { return null; }
}

async function fetchAllLC() {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/concepts/domain/living-collective?limit=200`, { next: { revalidate: 60 } });
    if (!res.ok) return [];
    const data = await res.json();
    return data?.items || [];
  } catch { return []; }
}

export default async function EconomyPage() {
  const [concept, allLC] = await Promise.all([fetchConcept(), fetchAllLC()]);

  // Build name map
  const nameMap: Record<string, string> = {};
  for (const c of allLC) {
    if (c.id && c.name) nameMap[c.id] = c.name;
  }

  return (
    <main>
      {/* Hero */}
      <section className="relative w-full h-64 overflow-hidden bg-[radial-gradient(ellipse_at_center,_rgba(234,179,8,0.08)_0%,_transparent_70%)]">
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="text-center space-y-4 px-6">
            <h1 className="text-5xl md:text-6xl font-extralight tracking-tight text-white">
              The Living Economy
            </h1>
            <p className="text-xl text-stone-400 font-light max-w-2xl mx-auto">
              The creator economy was the doorway. The living economy expands it to all creation:
              every nourishing contribution becomes visible, every flow stays verifiable, and money
              becomes a sensing layer rather than a gate. The first organs of that sensing layer are
              already forming in views, discovery rewards, reward policies, and the live energy map.
            </p>
          </div>
        </div>
      </section>

      <div className="max-w-4xl mx-auto px-6 pb-20 -mt-8">
        {/* Breadcrumb */}
        <nav className="text-sm text-stone-500 mb-8 flex items-center gap-2" aria-label="breadcrumb">
          <Link href="/vision" className="hover:text-amber-400/80 transition-colors">The Living Collective</Link>
          <span className="text-stone-700">/</span>
          <span className="text-stone-300">The Living Economy</span>
        </nav>

        {/* Flow Diagram */}
        <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-8 mb-12 space-y-6">
          <h2 className="text-lg font-light text-stone-300">How Creation Flows</h2>
          <div className="font-mono text-xs text-stone-500 leading-loose space-y-1 overflow-x-auto">
            <div className="text-amber-400/70">Creation</div>
            <div>  │ today: article, blueprint, 3D model, image, research</div>
            <div>  │ expanding toward: meal, repair, care work, mediation, land restoration, space holding</div>
            <div>  │ digital assets register first because attribution is easiest there</div>
            <div>  │ first live organs: views, discovery chains, reward policies, energy sensing</div>
            <div>  ▼</div>
            <div className="text-teal-400/70">Receiver</div>
            <div>  │ receives freely (no paywall, no subscription, no ads, no earning access to basics)</div>
            <div>  │ voluntarily identifies → X-Contributor-Id header</div>
            <div>  │ participation history builds frequency profile (vector, not score)</div>
            <div>  ▼</div>
            <div className="text-violet-400/70">Receiver Becomes Contributor</div>
            <div>  │ creates their own offering → generates CC</div>
            <div>  │ 15% of generated CC flows back through reading history</div>
            <div>  │ weighted by resonance (cosine similarity of frequency profiles)</div>
            <div>  ▼</div>
            <div className="text-emerald-400/70">The Field Senses</div>
            <div>  │ CC arrives proportional to how their work resonated</div>
            <div>  │ the blueprint creator, the cook, the repairer, the host, the mediator → all can become legible</div>
            <div>  │ the record exists to show what moved, what restored, and what needs replenishment next</div>
            <div>  ▼</div>
            <div className="text-amber-400/70">Verification</div>
            <div>  │ daily SHA-256 hash chains per tracked asset/flow (tamper-evident)</div>
            <div>  │ weekly Ed25519 signed snapshots (non-repudiable)</div>
            <div>  │ public API → anyone can recompute and verify</div>
            <div>  └─ the math is the proof</div>
          </div>
        </section>

        {/* Story Content */}
        {concept?.story_content && (
          <StoryContent content={concept.story_content} conceptId="lc-economy" nameMap={nameMap} />
        )}

        <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-6 mt-12 mb-12 space-y-3">
          <h2 className="text-lg font-light text-stone-300">First Organs Live</h2>
          <p className="text-sm text-stone-400 leading-relaxed">
            Rebasing onto the latest merge changes the stance of this page. The economy is still far
            from whole, but the organism is already beginning to sense attention, circulation, and
            vitality in software rather than only in language.
          </p>
          <div className="flex flex-wrap gap-4 text-sm">
            <Link href="/analytics" className="text-stone-500 hover:text-amber-300/80 transition-colors">Attention flow</Link>
            <Link href="/energy-flow" className="text-stone-500 hover:text-teal-300/80 transition-colors">Energy map</Link>
            <Link href="/alive" className="text-stone-500 hover:text-violet-300/80 transition-colors">Community pulse</Link>
          </div>
        </section>

        {/* Live Verification Proof */}
        <LiveProof />

        {/* Navigation */}
        <div className="flex gap-4 text-sm pt-12">
          <Link href="/vision" className="text-stone-500 hover:text-amber-300/80 transition-colors">&larr; The Living Collective</Link>
          <Link href="/verify" className="text-stone-500 hover:text-teal-300/80 transition-colors">Verify any asset</Link>
          <Link href="/vision/join" className="text-stone-500 hover:text-teal-300/80 transition-colors">Join</Link>
        </div>
      </div>
    </main>
  );
}
