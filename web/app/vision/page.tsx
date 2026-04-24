import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { cookies } from "next/headers";
import { createTranslator } from "@/lib/i18n";
import { DEFAULT_LOCALE, isSupportedLocale, type LocaleCode } from "@/lib/locales";
import { getApiBase } from "@/lib/api";

type HubSection = {
  id: string;
  concept_id: string;
  image: string;
  title: string;
  body: string;
  note: string;
};

type HubGalleryItem = {
  id?: string;
  image: string;
  label: string;
  href: string;
};

type HubCard = {
  id?: string;
  title: string;
  concept_id: string;
  href: string;
  desc: string;
  tag: string;
};

type VisionHubContent = {
  source: "graph";
  domain: string;
  sections: HubSection[];
  galleries: {
    spaces: HubGalleryItem[];
    practices: HubGalleryItem[];
    people: HubGalleryItem[];
    network: HubGalleryItem[];
  };
  blueprints: HubCard[];
  emerging: HubCard[];
  orientation_words: string[];
  counts: {
    sections: number;
    gallery_items: number;
    blueprints: number;
    emerging: number;
    orientation_words: number;
  };
};

const EMPTY_HUB: VisionHubContent = {
  source: "graph",
  domain: "living-collective",
  sections: [],
  galleries: {
    spaces: [],
    practices: [],
    people: [],
    network: [],
  },
  blueprints: [],
  emerging: [],
  orientation_words: [],
  counts: {
    sections: 0,
    gallery_items: 0,
    blueprints: 0,
    emerging: 0,
    orientation_words: 0,
  },
};

async function fetchVisionHub(): Promise<VisionHubContent> {
  try {
    const res = await fetch(`${getApiBase()}/api/vision/living-collective/hub`, { cache: "no-store" });
    if (!res.ok) return EMPTY_HUB;
    const data = await res.json();
    return {
      ...EMPTY_HUB,
      ...data,
      galleries: {
        ...EMPTY_HUB.galleries,
        ...(data?.galleries || {}),
      },
      counts: {
        ...EMPTY_HUB.counts,
        ...(data?.counts || {}),
      },
    };
  } catch {
    return EMPTY_HUB;
  }
}

export const metadata: Metadata = {
  title: "The Living Collective | Coherence Network",
  description:
    "A frequency-based blueprint for organism-based community. Where cells and the field thrive as one movement.",
  openGraph: {
    title: "The Living Collective",
    description: "What emerges when community is designed from resonance, vitality, and coherence.",
  },
};

function EmptyHubGroup({ label }: { label: string }) {
  return (
    <div className="rounded-xl border border-dashed border-stone-800/60 bg-stone-900/10 p-5 text-sm text-stone-600">
      No {label} records are published in the graph yet.
    </div>
  );
}

function GalleryGrid({
  items,
  wide = false,
}: {
  items: HubGalleryItem[];
  wide?: boolean;
}) {
  if (items.length === 0) return <EmptyHubGroup label="gallery" />;
  return (
    <div className={wide ? "grid grid-cols-1 md:grid-cols-3 gap-3" : "grid grid-cols-2 md:grid-cols-4 gap-3"}>
      {items.map((item) => (
        <Link
          key={item.id || `${item.href}-${item.label}`}
          href={item.href}
          className={`group relative ${wide ? "aspect-[16/9]" : "aspect-[4/3]"} rounded-xl overflow-hidden`}
        >
          {item.image ? (
            <Image
              src={item.image}
              alt={item.label}
              fill
              className="object-cover group-hover:scale-105 transition-transform duration-500"
              sizes={wide ? "33vw" : "25vw"}
            />
          ) : (
            <div className="absolute inset-0 bg-stone-900" />
          )}
          <div className="absolute inset-0 bg-gradient-to-t from-stone-950/80 via-transparent to-transparent" />
          <span className={`absolute ${wide ? "bottom-3 left-4 text-sm" : "bottom-2 left-3 text-xs"} text-stone-200 font-medium`}>
            {item.label}
          </span>
        </Link>
      ))}
    </div>
  );
}

/* ── Page ─────────────────────────────────────────────────────────────── */

export default async function VisionPage() {
  const cookieStore = await cookies();
  const cookieLang = cookieStore.get("NEXT_LOCALE")?.value;
  const lang: LocaleCode = isSupportedLocale(cookieLang) ? cookieLang : DEFAULT_LOCALE;
  const t = createTranslator(lang);
  const hub = await fetchVisionHub();

  return (
    <main className="min-h-screen bg-gradient-to-b from-stone-950 via-stone-950 to-stone-900 text-stone-100">
      {/* Hero */}
      <section className="relative flex flex-col items-center justify-center min-h-[80vh] px-6 text-center">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_rgba(234,179,8,0.08)_0%,_transparent_70%)]" />
        <div className="relative z-10 max-w-3xl space-y-8">
          <p className="text-amber-400/80 text-sm sensing-[0.3em] uppercase">
            {t("visionIndex.heroEyebrow")}
          </p>
          <h1 className="text-5xl md:text-7xl font-extralight tracking-tight leading-[1.1]">
            {t("visionIndex.heroTitle1")}{" "}
            <span className="bg-gradient-to-r from-amber-300 via-teal-300 to-violet-300 bg-clip-text text-transparent">
              {t("visionIndex.heroTitle2")}
            </span>
          </h1>
          <p className="text-xl md:text-2xl text-stone-400 font-light leading-relaxed max-w-2xl mx-auto">
            {t("visionIndex.heroLede")}
          </p>
          <div className="pt-4 text-stone-500 text-sm italic">
            {t("visionIndex.heroTag")}
          </div>
        </div>

        {/* scroll indicator */}
        <div className="absolute bottom-12 animate-bounce text-stone-600">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M12 5v14m0 0l-6-6m6 6l6-6" />
          </svg>
        </div>
      </section>

      {/* How It Knows */}
      <section className="max-w-3xl mx-auto px-6 py-24 text-center space-y-8">
        <h2 className="text-2xl md:text-3xl font-light text-stone-300">{t("visionIndex.knowsHeading")}</h2>
        <div className="grid gap-4 text-left text-stone-400 text-lg leading-relaxed">
          <p>
            {t("visionIndex.knowsBody")}{" "}
            <span className="text-amber-300/80">{t("visionIndex.knowsExpansion")}</span>{" "}
            <span className="text-teal-300/80">{t("visionIndex.knowsContraction")}</span>{" "}
            {t("visionIndex.knowsTail")}
          </p>
        </div>
        <div className="grid md:grid-cols-2 gap-6 text-sm text-stone-500 pt-8">
          <div className="space-y-3 p-5 rounded-2xl border border-stone-800/50 bg-stone-900/30">
            <div className="text-amber-400/60 font-medium">{t("visionIndex.knowsCard1Title")}</div>
            <p>{t("visionIndex.knowsCard1Body")}</p>
          </div>
          <div className="space-y-3 p-5 rounded-2xl border border-stone-800/50 bg-stone-900/30">
            <div className="text-amber-400/60 font-medium">{t("visionIndex.knowsCard2Title")}</div>
            <p>{t("visionIndex.knowsCard2Body")}</p>
          </div>
          <div className="space-y-3 p-5 rounded-2xl border border-stone-800/50 bg-stone-900/30">
            <div className="text-amber-400/60 font-medium">{t("visionIndex.knowsCard3Title")}</div>
            <p>{t("visionIndex.knowsCard3Body")}</p>
          </div>
          <div className="space-y-3 p-5 rounded-2xl border border-stone-800/50 bg-stone-900/30">
            <div className="text-amber-400/60 font-medium">{t("visionIndex.knowsCard4Title")}</div>
            <p>{t("visionIndex.knowsCard4Body")}</p>
          </div>
        </div>
      </section>

      {/* Concept sections */}
      {hub.sections.length === 0 && (
        <section className="max-w-4xl mx-auto px-6 py-20">
          <EmptyHubGroup label="vision section" />
        </section>
      )}
      {hub.sections.map((section, i) => (
        <section
          key={section.id}
          id={section.id}
          className={`relative ${i % 2 === 0 ? "" : ""}`}
        >
          {/* Full-width image */}
          <div className="relative w-full aspect-[16/7] md:aspect-[16/6] overflow-hidden">
            {section.image ? (
              <Image
                src={section.image}
                alt={section.title}
                fill
                className="object-cover"
                sizes="100vw"
                priority={i < 3}
              />
            ) : (
              <div className="absolute inset-0 bg-stone-900" />
            )}
            {/* gradient overlays */}
            <div className="absolute inset-0 bg-gradient-to-t from-stone-950 via-stone-950/30 to-transparent" />
            <div className="absolute inset-0 bg-gradient-to-b from-stone-950/60 via-transparent to-transparent" />
          </div>

          {/* Text overlay at bottom of image */}
          <div className="relative -mt-32 md:-mt-48 z-10 max-w-4xl mx-auto px-6 pb-20 md:pb-28">
            <div className="space-y-4">
              <Link href={`/vision/${section.concept_id}`} className="group">
                <h2 className="text-3xl md:text-5xl font-extralight tracking-tight text-white group-hover:text-amber-200/90 transition-colors">
                  {section.title}
                  <span className="ml-3 text-stone-600 group-hover:text-amber-400/50 text-2xl transition-colors">→</span>
                </h2>
              </Link>
              <p className="text-lg md:text-xl text-stone-300 font-light leading-relaxed max-w-2xl">
                {section.body}
              </p>
              <p className="text-sm text-stone-500 italic leading-relaxed max-w-xl pt-2">
                {section.note}
              </p>
            </div>
          </div>
        </section>
      ))}

      {/* Life in the field — visual galleries */}
      <section className="max-w-5xl mx-auto px-6 py-24 space-y-20">
        {/* Sacred Spaces */}
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-extralight text-stone-300">{t("visionIndex.galleryHeadingSpaces")}</h2>
            <Link href="/vision/lived" className="text-sm text-stone-500 hover:text-amber-300/80 transition-colors">{t("common.seeAll")}</Link>
          </div>
          <GalleryGrid items={hub.galleries.spaces} />
        </div>

        {/* Practices & Ceremonies */}
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-extralight text-stone-300">{t("visionIndex.galleryHeadingPractices")}</h2>
            <Link href="/vision/lived" className="text-sm text-stone-500 hover:text-amber-300/80 transition-colors">{t("common.seeAll")}</Link>
          </div>
          <GalleryGrid items={hub.galleries.practices} />
        </div>

        {/* People, Nature, Animals */}
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-extralight text-stone-300">{t("visionIndex.galleryHeadingPeople")}</h2>
            <Link href="/vision/lived" className="text-sm text-stone-500 hover:text-amber-300/80 transition-colors">{t("common.seeAll")}</Link>
          </div>
          <GalleryGrid items={hub.galleries.people} />
        </div>

        {/* The Network */}
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-extralight text-stone-300">{t("visionIndex.galleryHeadingNetwork")}</h2>
            <Link href="/vision/lc-network" className="text-sm text-stone-500 hover:text-amber-300/80 transition-colors">{t("common.explore")}</Link>
          </div>
          <GalleryGrid items={hub.galleries.network} wide />
        </div>

        {/* Stories CTA */}
        <div className="text-center">
          <Link
            href="/vision/lived"
            className="inline-flex items-center gap-2 px-8 py-3 rounded-xl bg-violet-500/10 border border-violet-500/20 text-violet-300/90 hover:bg-violet-500/20 hover:border-violet-500/30 transition-all font-medium"
          >
            {t("visionIndex.storiesCta")}
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M5 12h14m0 0l-6-6m6 6l-6 6" />
            </svg>
          </Link>
        </div>
      </section>

      {/* Blueprints & Resources — enriched concepts with real building data */}
      <section className="border-t border-stone-800/30">
        <div className="max-w-5xl mx-auto px-6 py-24 space-y-10">
          <div className="text-center space-y-4">
            <h2 className="text-3xl md:text-4xl font-extralight text-stone-300">
              {t("visionIndex.blueprintsHeading")}
            </h2>
            <p className="text-stone-500 text-lg max-w-2xl mx-auto">
              {t("visionIndex.blueprintsLede")}
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
            {hub.blueprints.map((bp) => (
              <Link
                key={bp.id || bp.href}
                href={bp.href}
                className="group p-5 rounded-2xl border border-teal-800/30 bg-teal-900/10 hover:bg-teal-900/20 hover:border-teal-700/40 transition-all duration-300 space-y-2"
              >
                <div className="flex items-center justify-between">
                  <h3 className="text-base font-medium text-teal-300/90 group-hover:text-teal-200 transition-colors">
                    {bp.title}
                  </h3>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-teal-500/10 text-teal-400/70 border border-teal-500/20">
                    {t("visionIndex.blueprintsResourcesTag", { n: parseInt(bp.tag, 10) || 0 })}
                  </span>
                </div>
                <p className="text-xs text-stone-500 leading-relaxed">
                  {bp.desc}
                </p>
              </Link>
            ))}
            {hub.blueprints.length === 0 && <EmptyHubGroup label="blueprint" />}
          </div>

          <div className="text-center pt-4">
            <Link
              href="/concepts/garden?domain=living-collective"
              className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl bg-teal-500/10 border border-teal-500/20 text-teal-300/80 hover:bg-teal-500/20 transition-all text-sm font-medium"
            >
              {t("visionIndex.blueprintsBrowseAll")}
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M5 12h14m0 0l-6-6m6 6l-6 6" />
              </svg>
            </Link>
          </div>
        </div>
      </section>

      {/* Emerging visions */}
      <section className="max-w-4xl mx-auto px-6 py-32 space-y-16">
        <div className="text-center space-y-4">
          <h2 className="text-3xl md:text-4xl font-extralight text-stone-300">
            {t("visionIndex.emergingHeading")}
          </h2>
          <p className="text-stone-500 text-lg max-w-2xl mx-auto">
            {t("visionIndex.emergingLede")}
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          {hub.emerging.map((vision) => (
            <Link
              key={vision.id || vision.href}
              href={vision.href}
              className="group p-6 rounded-2xl border border-stone-800/40 bg-stone-900/20 hover:bg-stone-900/40 hover:border-amber-800/30 transition-all duration-500 space-y-3"
            >
              <h3 className="text-lg font-light text-amber-300/80 group-hover:text-amber-300 transition-colors">
                {vision.title}
                <span className="ml-2 text-stone-700 group-hover:text-amber-500/40 transition-colors">→</span>
              </h3>
              <p className="text-sm text-stone-500 leading-relaxed">
                {vision.desc}
              </p>
            </Link>
          ))}
          {hub.emerging.length === 0 && <EmptyHubGroup label="emerging vision" />}
        </div>

        {/* Explore all concepts */}
      </section>

      {/* Orientation */}
      <section className="border-t border-stone-800/30">
        <div className="max-w-3xl mx-auto px-6 py-24 text-center space-y-10">
          <div className="flex flex-wrap justify-center gap-3 text-sm">
            {hub.orientation_words.map(
              (word) => (
                <span
                  key={word}
                  className="px-4 py-2 rounded-full border border-stone-700/40 text-stone-400 bg-stone-900/30"
                >
                  {word}
                </span>
              ),
            )}
            {hub.orientation_words.length === 0 && <EmptyHubGroup label="orientation word" />}
          </div>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/vision/immerse"
              className="inline-flex items-center gap-2 px-8 py-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 hover:bg-amber-500/20 hover:border-amber-500/30 transition-all font-medium"
            >
              {t("visionIndex.orientationImmerse")}
            </Link>
            <Link
              href="/vision/lived"
              className="inline-flex items-center gap-2 px-8 py-3 rounded-xl bg-violet-500/10 border border-violet-500/20 text-violet-300/90 hover:bg-violet-500/20 hover:border-violet-500/30 transition-all font-medium"
            >
              {t("visionIndex.orientationLived")}
            </Link>
            <Link
              href="/vision/realize"
              className="inline-flex items-center gap-2 px-8 py-3 rounded-xl bg-teal-500/10 border border-teal-500/20 text-teal-300/90 hover:bg-teal-500/20 hover:border-teal-500/30 transition-all font-medium"
            >
              {t("visionIndex.orientationRealize")}
            </Link>
            <Link
              href="/vision/join"
              className="inline-flex items-center gap-2 px-8 py-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 hover:bg-amber-500/20 hover:border-amber-500/30 transition-all font-medium"
            >
              {t("visionIndex.orientationJoin")}
            </Link>
          </div>
          <Link href="/vision/aligned" className="text-sm text-stone-500 hover:text-violet-300/80 transition-colors">
            {t("visionIndex.orientationAligned")}
          </Link>
          <p className="text-stone-600 text-sm pt-6">
            {t("visionIndex.orientationNervous")}
          </p>
          <p className="text-stone-700 text-xs italic">{t("visionIndex.orientationItsAlive")}</p>
          <div className="pt-8">
            <Link
              href="/"
              className="text-sm text-stone-500 hover:text-amber-400/80 transition-colors"
            >
              {t("visionIndex.orientationReturn")}
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
