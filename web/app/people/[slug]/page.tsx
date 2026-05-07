import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Button } from "@/components/ui/button";
import { AttributedExternalLink } from "@/components/content/AttributedExternalLink";

// Rich, adaptable presence data for the 5 key presences
// This can be expanded to a full CMS or graph-backed system later
const PRESENCES: Record<string, any> = {
  "elon-musk": {
    name: "Elon Musk",
    slug: "elon-musk",
    tagline: "Multiplanetary • xAI • Tesla • SpaceX",
    heroImage: "/presences/elon-musk-hero.jpg", // Replace with real high-res hero
    bio: "Founder of Tesla, SpaceX, xAI, and X. A presence driving humanity toward multiplanetary life and accelerating the understanding of the universe through first-principles thinking and bold execution.",
    resonance: [
      { axis: "Vitality", score: 0.92, note: "Relentless drive toward life-expanding frontiers" },
      { axis: "Organic Intelligence", score: 0.87, note: "First-principles reasoning as living intelligence" },
      { axis: "Expression", score: 0.95, note: "Radical transparency and direct communication" }
    ],
    links: [
      { label: "X / Twitter", href: "https://x.com/elonmusk" },
      { label: "Tesla", href: "https://tesla.com" },
      { label: "SpaceX", href: "https://spacex.com" },
      { label: "xAI", href: "https://x.ai" }
    ],
    type: "human",
    location: "Earth (multiplanetary intent)"
  },
  "liquid-bloom": {
    name: "Liquid Bloom",
    slug: "liquid-bloom",
    tagline: "Soundscapes for Embodied Dance • Journeys • Healing",
    heroImage: "/presences/liquid-bloom-hero.jpg",
    bio: "Visionary world-electronic project of Amani Friend (Desert Dwellers). Creates transcendent soundscapes that serve embodied dance, meditation, wellness, and deep journey work — music as medicine for the collective field.",
    resonance: [
      { axis: "Vitality", score: 0.94, note: "Music that amplifies life force and presence" },
      { axis: "Harmony", score: 0.91, note: "World instrumentation woven into coherent sonic fields" },
      { axis: "Organic Intelligence", score: 0.88, note: "Healing frequencies grown from living tradition" }
    ],
    links: [
      { label: "Instagram", href: "https://www.instagram.com/liquidbloom/" },
      { label: "Bandcamp", href: "https://liquidbloom.bandcamp.com" },
      { label: "Spotify", href: "https://open.spotify.com/artist/liquidbloom" }
    ],
    type: "human",
    location: "Global (Desert Dwellers lineage)"
  },
  "bloomurian": {
    name: "Bloomurian",
    slug: "bloomurian",
    tagline: "Folktronica • World Bass • Heart-Opening Frequencies",
    heroImage: "/presences/bloomurian-hero.jpg",
    bio: "Electronic music & DJ project of Robin Liepman (Bloom). Blends folktronica, world bass, psychedelic bass, and organic house into multidimensional frequencies that cultivate blossoming heart, mind, body, and soul.",
    resonance: [
      { axis: "Vitality", score: 0.93, note: "Heart-opening bass that moves the body" },
      { axis: "Expression", score: 0.89, note: "Live instrumentation + electronic alchemy" },
      { axis: "Harmony", score: 0.90, note: "Polyphonic frequencies for collective resonance" }
    ],
    links: [
      { label: "Website", href: "https://www.bloomurian.com/" },
      { label: "Instagram", href: "https://www.instagram.com/bloomurianmusic/" },
      { label: "Bandcamp", href: "https://bloomurian.bandcamp.com" }
    ],
    type: "human",
    location: "Boulder, Colorado"
  },
  "mose": {
    name: "Mose",
    slug: "mose",
    tagline: "Shamanic Downtempo • ReGen Remixes • Organic Intelligence",
    heroImage: "/presences/mose-hero.jpg",
    bio: "Shamanic electronic musician known for deep, organic, regenerative sound. Creator of the ReGen remix series with Liquid Bloom and collaborator in the conscious music field — frequency work that regenerates the listener.",
    resonance: [
      { axis: "Organic Intelligence", score: 0.95, note: "Regenerative, earth-connected sound design" },
      { axis: "Vitality", score: 0.88, note: "Downtempo that restores nervous system coherence" },
      { axis: "Harmony", score: 0.86, note: "Folktronica roots meeting modern bass" }
    ],
    links: [
      { label: "Spotify", href: "https://open.spotify.com/artist/mose" },
      { label: "Bandcamp", href: "https://mose.bandcamp.com" }
    ],
    type: "human",
    location: "Global (shamanic electronic lineage)"
  },
  "aly-constantine": {
    name: "Aly Constantine",
    slug: "aly-constantine",
    tagline: "Healing Arts • Conscious Sound • Presence",
    heroImage: "/presences/aly-constantine-hero.jpg",
    bio: "Presence in the healing arts and conscious sound field. Works at the intersection of sound, presence, and embodied transformation — helping the field remember itself through voice, vibration, and deep listening.",
    resonance: [
      { axis: "Vitality", score: 0.91, note: "Sound as direct transmission of life force" },
      { axis: "Harmony", score: 0.94, note: "Conscious sound that aligns the field" },
      { axis: "Expression", score: 0.87, note: "Voice and presence as living art" }
    ],
    links: [
      { label: "Instagram", href: "#" },
      { label: "Website", href: "#" }
    ],
    type: "human",
    location: "Global (healing arts)"
  }
};

export async function generateMetadata({ params }: { params: { slug: string } }): Promise<Metadata> {
  const presence = PRESENCES[params.slug];
  if (!presence) return { title: "Presence not found" };
  return {
    title: `${presence.name} — Coherence Network`,
    description: presence.bio,
    openGraph: {
      images: [{ url: presence.heroImage }],
    },
  };
}

export default function PresencePage({ params }: { params: { slug: string } }) {
  const presence = PRESENCES[params.slug];
  if (!presence) notFound();

  return (
    <main className="max-w-4xl mx-auto px-4 sm:px-6 py-12 space-y-12">
      {/* Hero */}
      <div className="relative h-[60vh] min-h-[420px] w-full overflow-hidden rounded-3xl">
        <Image
          src={presence.heroImage}
          alt={presence.name}
          fill
          className="object-cover"
          priority
          unoptimized
        />
        <div className="absolute inset-0 bg-gradient-to-b from-black/60 via-black/40 to-black/80" />
        <div className="absolute bottom-0 left-0 right-0 p-8 md:p-12">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-white/70 mb-3">
              {presence.type} · {presence.location}
            </div>
            <h1 className="text-6xl md:text-7xl font-light tracking-tighter text-white mb-4">
              {presence.name}
            </h1>
            <p className="text-2xl text-white/90 max-w-2xl">
              {presence.tagline}
            </p>
          </div>
        </div>
      </div>

      {/* Bio */}
      <div className="prose prose-lg max-w-none text-foreground/90">
        <p>{presence.bio}</p>
      </div>

      {/* Resonance with the Codex */}
      <section>
        <div className="flex items-center gap-3 mb-6">
          <div className="text-xs uppercase tracking-[0.18em] font-semibold text-[hsl(var(--primary))]">Resonance with the Living Collective</div>
          <div className="flex-1 h-px bg-border" />
        </div>
        
        <div className="grid gap-4 md:grid-cols-3">
          {presence.resonance.map((r: any, i: number) => (
            <div key={i} className="rounded-2xl border border-border/50 bg-card p-6">
              <div className="flex items-baseline justify-between mb-3">
                <div className="font-medium text-lg">{r.axis}</div>
                <div className="text-sm tabular-nums text-[hsl(var(--primary))] font-mono">{Math.round(r.score * 100)}%</div>
              </div>
              <p className="text-sm text-foreground/80 leading-relaxed">{r.note}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Public Links */}
      <section>
        <div className="text-xs uppercase tracking-[0.18em] font-semibold text-[hsl(var(--primary))] mb-4">Public presence</div>
        <div className="flex flex-wrap gap-3">
          {presence.links.map((link: any, i: number) => (
            <AttributedExternalLink
              key={i}
              href={link.href}
              className="inline-flex items-center gap-2 rounded-full border border-border px-5 py-2 text-sm hover:bg-accent transition-colors"
            >
              {link.label} →
            </AttributedExternalLink>
          ))}
        </div>
      </section>

      {/* Weave in CTA */}
      <div className="pt-8 border-t border-border/50 text-center">
        <p className="text-sm text-muted-foreground mb-4">This presence is part of the Living Collective.</p>
        <Button asChild size="lg" className="rounded-full px-10">
          <Link href="/begin">Weave into the field</Link>
        </Button>
      </div>
    </main>
  );
}
