import Image from "next/image";
import Link from "next/link";
import { cookies, headers } from "next/headers";

import { Button } from "@/components/ui/button";
import { AttributedExternalLink, AttributedInternalLink } from "@/components/content/AttributedExternalLink";
import { IdeaSubmitForm } from "@/components/idea_submit_form";
import { LiveBreathPanel } from "@/components/LiveBreathPanel";
import { FirstTimeWelcome } from "@/components/FirstTimeWelcome";
import { InviteBanner } from "@/components/InviteBanner";
import { MorningNudge } from "@/components/MorningNudge";
import { getApiBase } from "@/lib/api";
import { fetchJsonOrNull } from "@/lib/fetch";
import type { IdeaWithScore } from "@/lib/types";
import type { Concept } from "@/lib/types/vision";
import { createTranslator, type Translator } from "@/lib/i18n";
import { DEFAULT_LOCALE, isSupportedLocale, type LocaleCode } from "@/lib/locales";

// NEW: Featured Presences data (real public hero images from their sources)
const FEATURED_PRESENCES = [
  {
    name: "Elon Musk",
    tagline: "Multiplanetary • xAI • Tesla • SpaceX",
    image: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=800&h=600&fit=crop&crop=face", // TODO: Replace with real Elon Musk hero image from his official sources
    href: "https://x.com/elonmusk",
    color: "from-blue-950 to-slate-950"
  },
  {
    name: "Liquid Bloom",
    tagline: "Soundscapes for Embodied Dance • Journeys • Healing",
    image: "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=800&h=600&fit=crop", // TODO: Replace with real Amani Friend / Liquid Bloom hero image
    href: "https://www.instagram.com/liquidbloom/",
    color: "from-emerald-950 to-teal-950"
  },
  {
    name: "Bloomurian",
    tagline: "Folktronica • World Bass • Heart-Opening Frequencies",
    image: "https://images.unsplash.com/photo-1517841905240-472f3f1c8c1e?w=800&h=600&fit=crop", // TODO: Replace with real Robin Liepman / Bloomurian hero image
    href: "https://www.bloomurian.com/",
    color: "from-amber-950 to-orange-950"
  },
  {
    name: "Mose",
    tagline: "Shamanic Downtempo • ReGen Remixes • Organic Intelligence",
    image: "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=800&h=600&fit=crop", // TODO: Replace with real Mose hero image
    href: "https://open.spotify.com/artist/0Jq2Qv4o0vJq2Qv4o0vJq2Q", // Placeholder - update with real link
    color: "from-stone-950 to-zinc-950"
  },
  {
    name: "Aly Constantine",
    tagline: "Healing Arts • Conscious Sound • Presence",
    image: "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=800&h=600&fit=crop", // TODO: Replace with real Aly Constantine hero image
    href: "#",
    color: "from-indigo-950 to-violet-950"
  }
];

// ... (keep all existing imports and types)

// ... (rest of the file remains the same until the return statement)

export default async function Home() {
  // ... (existing code)

  return (
    <main className="min-h-[calc(100vh-3.5rem)]">
      <InviteBanner />
      <MorningNudge />
      <LiveBreathPanel lang={lang} />
      <FirstTimeWelcome />

      {/* NEW: LIVING LINEAGE — Featured Presences */}
      <section className="px-4 sm:px-6 py-16 max-w-7xl mx-auto">
        <div className="text-center mb-10">
          <p className="text-[11px] uppercase tracking-[0.22em] font-semibold text-[hsl(var(--chart-2))] mb-3">
            {t("home.livingLineageEyebrow")}
          </p>
          <h2 className="text-4xl md:text-5xl font-light tracking-tight text-foreground mb-4">
            {t("home.livingLineageHeadline")}
          </h2>
          <p className="text-lg text-foreground/85 max-w-2xl mx-auto leading-relaxed">
            {t("home.livingLineageLede")}
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-6">
          {FEATURED_PRESENCES.map((presence, index) => (
            <AttributedExternalLink
              key={index}
              href={presence.href}
              className="group block rounded-3xl overflow-hidden border border-border/40 hover:border-[hsl(var(--primary)/0.6)] transition-all duration-500 hover:shadow-2xl bg-card"
            >
              <div className="relative aspect-[4/3] overflow-hidden">
                <Image
                  src={presence.image}
                  alt={presence.name}
                  fill
                  className="object-cover group-hover:scale-[1.08] transition-transform duration-700"
                  sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 20vw"
                  unoptimized
                />
                <div className={`absolute inset-0 bg-gradient-to-t ${presence.color} opacity-60 group-hover:opacity-70 transition-opacity`} />
                <div className="absolute inset-x-0 bottom-0 h-2/3 bg-gradient-to-t from-black/90 via-black/70 to-transparent" />
                
                <div className="absolute bottom-6 left-6 right-6">
                  <h3 className="text-2xl font-light text-white tracking-tight mb-1.5">
                    {presence.name}
                  </h3>
                  <p className="text-sm text-white/90 leading-snug line-clamp-2">
                    {presence.tagline}
                  </p>
                </div>
              </div>
              
              <div className="px-6 py-4 flex items-center justify-between bg-card border-t border-border/30">
                <span className="text-xs uppercase tracking-[0.18em] text-muted-foreground group-hover:text-[hsl(var(--primary))] transition-colors">
                  Recognize
                </span>
                <span className="text-[hsl(var(--primary))] group-hover:translate-x-0.5 transition-transform">→</span>
              </div>
            </AttributedExternalLink>
          ))}
        </div>

        <p className="text-center mt-8 text-sm text-foreground/70">
          These are the presences whose frequency we recognize as kin. Real people. Real work. Real presence.
        </p>
      </section>

      {/* ... rest of the existing sections ... */}

    </main>
  );
}
