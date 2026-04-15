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
  description: "A creative economy where every contributor earns, every flow is verifiable, and the math is the proof.",
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
              Every contributor earns. Every flow is verifiable. The math is the proof.
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
          <h2 className="text-lg font-light text-stone-300">How CC Flows</h2>
          <div className="font-mono text-xs text-stone-500 leading-loose space-y-1 overflow-x-auto">
            <div className="text-amber-400/70">Creator</div>
            <div>  │ creates asset (article, blueprint, 3D model, image, research)</div>
            <div>  │ asset registered on Story Protocol → immutable attribution</div>
            <div>  │ content stored on Arweave → permanent, content-addressed</div>
            <div>  ▼</div>
            <div className="text-teal-400/70">Reader</div>
            <div>  │ reads freely (no paywall, no subscription, no ads)</div>
            <div>  │ voluntarily identifies → X-Contributor-Id header</div>
            <div>  │ reading history builds frequency profile (vector, not score)</div>
            <div>  ▼</div>
            <div className="text-violet-400/70">Reader Contributes</div>
            <div>  │ creates their own asset → generates CC</div>
            <div>  │ 15% of generated CC flows back through reading history</div>
            <div>  │ weighted by resonance (cosine similarity of frequency profiles)</div>
            <div>  ▼</div>
            <div className="text-emerald-400/70">Creator Receives</div>
            <div>  │ CC arrives proportional to how their work resonated</div>
            <div>  │ the blueprint creator, the renderer builder, the host → all earn</div>
            <div>  │ every flow is hashed daily, signed weekly, publicly verifiable</div>
            <div>  ▼</div>
            <div className="text-amber-400/70">Verification</div>
            <div>  │ daily SHA-256 hash chains per asset (tamper-evident)</div>
            <div>  │ weekly Ed25519 signed snapshots (non-repudiable)</div>
            <div>  │ public API → anyone can recompute and verify</div>
            <div>  └─ the math is the proof</div>
          </div>
        </section>

        {/* Story Content */}
        {concept?.story_content && (
          <StoryContent content={concept.story_content} conceptId="lc-economy" nameMap={nameMap} />
        )}

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
