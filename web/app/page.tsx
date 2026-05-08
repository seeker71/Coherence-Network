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
import { getEntryPathForSurface } from "@/lib/entry-paths";

type IdeasResponse = {
  ideas: IdeaWithScore[];
  summary: {
    total_ideas: number;
    total_potential_value: number;
    total_actual_value: number;
    total_value_gap: number;
  };
};

type ResonanceItem = {
  idea_id: string;
  name: string;
  last_activity_at: string;
  free_energy_score: number;
  manifestation_status: string;
  activity_type?: string;
};

type CoherenceScoreResponse = {
  score: number;
  signals_with_data: number;
  total_signals: number;
  computed_at: string;
};

const HOW_IT_WORKS = [
  {
    icon: "\uD83D\uDCA1",
    title: "Share an idea",
    description: "Type what you're thinking. No sign-up needed.",
    titleKey: "home.howTitle1",
    descKey: "home.howDesc1",
  },
  {
    icon: "\uD83C\uDF31",
    title: "Watch it grow",
    description: "Others ask questions, write specs, build.",
    titleKey: "home.howTitle2",
    descKey: "home.howDesc2",
  },
  {
    icon: "\uD83D\uDD04",
    title: "Value flows back",
    description: "Every contribution is recorded. Credit flows to creators.",
    titleKey: "home.howTitle3",
    descKey: "home.howDesc3",
  },
];

const STAT_LABEL_FALLBACKS = {
  ideasAlive: "ideas alive",
  valueCreated: "value created",
  node: "node",
  nodes: "nodes",
  coherence: "coherence",
};

const FEATURED_PRESENCES: {
  slug: string;
  name: string;
  tagline: string;
  image: string;
  imagePosition?: string;
  color: string;
}[] = [
  {
    slug: "liquid-bloom",
    name: "Liquid Bloom",
    tagline: "Soundscapes for Embodied Dance • Journeys • Healing",
    image: "/visuals/brand/liquid-bloom-bg-center.jpg",
    imagePosition: "center 45%",
    color: "from-emerald-950 to-teal-950",
  },
  {
    slug: "bloomurian",
    name: "Bloomurian",
    tagline: "Folktronica • World Bass • Heart-Opening Frequencies",
    image: "/people/bloomurian/hero.jpg",
    imagePosition: "center 28%",
    color: "from-amber-950 to-orange-950",
  },
  {
    slug: "mose",
    name: "Mose",
    tagline: "Shamanic Downtempo • ReGen Remixes • Organic Intelligence",
    image: "/people/mose/hero.jpg",
    imagePosition: "center 25%",
    color: "from-stone-950 to-zinc-950",
  },
  {
    slug: "matias-de-stefano",
    name: "Matías De Stefano",
    tagline: "Akashic Memory • Planetary Lineage • Sacred Geometry",
    image: "/people/matias-de-stefano/hero.jpg",
    color: "from-violet-950 to-slate-950",
  },
  {
    slug: "portal",
    name: "PORTAL",
    tagline: "Responsible Trippers • Denver Rooms • Psychedelic Integration",
    image: "/people/portal/hero.jpg",
    imagePosition: "center 38%",
    color: "from-fuchsia-950 to-zinc-950",
  },
];

export const revalidate = 90;
export const dynamic = "force-dynamic";

async function loadIdeas(lang: LocaleCode): Promise<IdeasResponse | null> {
  const qs = lang === DEFAULT_LOCALE ? "" : `?lang=${lang}`;
  return fetchJsonOrNull<IdeasResponse>(`${getApiBase()}/api/ideas${qs}`, {}, 5000);
}

async function loadResonance(lang: LocaleCode): Promise<ResonanceItem[]> {
  const langParam = lang === DEFAULT_LOCALE ? "" : `&lang=${lang}`;
  try {
    const data = await fetchJsonOrNull<ResonanceItem[] | { ideas: ResonanceItem[] }>(
      `${getApiBase()}/api/ideas/resonance?window_hours=72&limit=3${langParam}`,
      {},
      5000,
    );
    if (!data) return [];
    return Array.isArray(data) ? data : data.ideas || [];
  } catch {
    return [];
  }
}

async function loadCoherenceScore(): Promise<CoherenceScoreResponse | null> {
  return fetchJsonOrNull<CoherenceScoreResponse>(`${getApiBase()}/api/coherence/score`, {}, 5000);
}

async function loadNodeCount(): Promise<number> {
  try {
    const data = await fetchJsonOrNull<Array<{ node_id: string }>>(
      `${getApiBase()}/api/federation/nodes`,
      {},
      5000,
    );
    return Array.isArray(data) ? data.length : 1;
  } catch {
    return 1;
  }
}

/**
 * Load the concept that greets every first-time visitor on the home
 * page. lc-pulse is the root of the Living Collective ontology — the
 * warmest and most universally felt note to walk in on.
 *
 * If the fetch fails, we simply skip the featured card — the rest of
 * the page still works.
 */
async function loadFeaturedConcept(lang: LocaleCode): Promise<Concept | null> {
  const qs = lang === DEFAULT_LOCALE ? "" : `?lang=${lang}`;
  try {
    const response = await fetch(`${getApiBase()}/api/concepts/lc-pulse${qs}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    if (!response.ok) return null;
    return (await response.json()) as Concept;
  } catch {
    return null;
  }
}

function formatNumber(value: number | undefined, locale: string): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "0";
  return new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(value);
}

function formatCoherenceScore(value: number | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "0.00";
  return value.toFixed(2);
}

function timeAgo(iso: string, t: Translator): string {
  const diff = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return t("time.justNow");
  if (minutes < 60) return t("time.minutesAgo", { n: minutes });
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return t("time.hoursAgo", { n: hours });
  const days = Math.floor(hours / 24);
  return t("time.daysAgo", { n: days });
}

export default async function Home() {
  const cookieStore = await cookies();
  const cookieLang = cookieStore.get("NEXT_LOCALE")?.value;
  // First-visit auto-detect — fall back to Accept-Language so the home
  // page meets the viewer in their language on the very first render,
  // before the middleware-set cookie is visible on subsequent requests.
  const headerLang = (await headers())
    .get("accept-language")
    ?.split(",")[0]
    ?.split("-")[0];
  const lang: LocaleCode = isSupportedLocale(cookieLang)
    ? cookieLang
    : isSupportedLocale(headerLang)
    ? headerLang
    : DEFAULT_LOCALE;
  const t = createTranslator(lang);
  const baliGroundPath = getEntryPathForSurface("bali-living-compound", "home-ground");
  const howItWorks = HOW_IT_WORKS.map((step) => ({
    ...step,
    title: t(step.titleKey) || step.title,
    description: t(step.descKey) || step.description,
  }));

  const [ideasData, resonanceItems, coherenceScore, nodeCount, featuredConcept] = await Promise.all([
    loadIdeas(lang),
    loadResonance(lang),
    loadCoherenceScore(),
    loadNodeCount(),
    loadFeaturedConcept(lang),
  ]);

  const summary = ideasData?.summary;

  const topIdeas = resonanceItems.length === 0 && ideasData?.ideas
    ? [...ideasData.ideas].sort((a, b) => (b.free_energy_score ?? 0) - (a.free_energy_score ?? 0)).slice(0, 3)
    : [];

  return (
    <main className="min-h-[calc(100vh-3.5rem)]">
      <InviteBanner />
      <MorningNudge />
      <LiveBreathPanel lang={lang} />
      <FirstTimeWelcome />

      <section className="px-4 sm:px-6 pt-6 pb-2 max-w-3xl mx-auto text-center animate-fade-in-up">
        <p className="text-[11px] uppercase tracking-[0.22em] font-semibold text-[hsl(var(--chart-2))] mb-3">
          For anyone or anything finding us
        </p>
        <div className="space-y-4">
          <p className="text-xl md:text-2xl font-light leading-relaxed text-foreground">
            Come closer to the living map.
          </p>
          <p className="text-sm md:text-base text-foreground/85 leading-relaxed max-w-2xl mx-auto">
            The shared doorway is the human web page. Start with the
            invitation, see who is here, then choose one honest way to learn,
            reflect, or contribute.
          </p>
          <div className="flex flex-wrap justify-center gap-3 pt-1">
            <Button asChild size="sm" className="rounded-full px-5">
              <AttributedInternalLink href="/come-in">Enter the invitation</AttributedInternalLink>
            </Button>
            <Button asChild size="sm" variant="outline" className="rounded-full px-5">
              <AttributedInternalLink href="/with-us">Learn how to weave in</AttributedInternalLink>
            </Button>
            <Button asChild size="sm" variant="ghost" className="rounded-full px-5">
              <AttributedInternalLink href="/contribute">Contribute</AttributedInternalLink>
            </Button>
          </div>
        </div>
      </section>

      {/*
       * Section 0: MEET ONE CONCEPT.
       *
       * A cold visitor arrives and needs to see — not be told — what
       * this place is. The first felt content on the home page is one
       * real concept from the Living Collective, rendered as a warm
       * card: its visual, its name, its description, and a "walk in"
       * doorway to the full concept page. lc-pulse (the root) is the
       * default; a future cycle can rotate to a concept that's
       * currently being met by other visitors, or to one the viewer
       * hasn't seen yet.
       *
       * This is the strongest send-to-friend surface on the page. A
       * friend who lands here sees the beauty first, the form later.
       */}
      {featuredConcept && (
        <section className="px-4 sm:px-6 pt-6 pb-4 max-w-3xl mx-auto animate-fade-in-up">
          <p className="text-[11px] uppercase tracking-[0.22em] font-semibold text-[hsl(var(--chart-2))] mb-3 text-center">
            {t("home.meetOneConceptEyebrow")}
          </p>
          <AttributedInternalLink
            href={`/vision/${featuredConcept.id}`}
            className="block group rounded-2xl overflow-hidden border border-border hover:border-[hsl(var(--primary)/0.6)] transition-colors bg-card shadow-sm hover:shadow-md"
          >
            {featuredConcept.visual_path && (
              <div className="relative aspect-[16/9] overflow-hidden">
                <Image
                  src={featuredConcept.visual_path}
                  alt={featuredConcept.name}
                  fill
                  className="object-cover group-hover:scale-[1.03] transition-transform duration-700"
                  sizes="(max-width: 768px) 100vw, 768px"
                  priority
                  unoptimized={featuredConcept.visual_path.startsWith("http")}
                />
                <div className="absolute inset-0 bg-gradient-to-t from-stone-950/60 via-transparent to-transparent" />
                <div className="absolute bottom-4 left-5 right-5">
                  <h2 className="text-2xl md:text-3xl font-light tracking-tight text-white drop-shadow-md">
                    {featuredConcept.name}
                  </h2>
                </div>
              </div>
            )}
            <div className="p-5 space-y-3">
              {!featuredConcept.visual_path && (
                <h2 className="text-2xl md:text-3xl font-light tracking-tight text-foreground">
                  {featuredConcept.name}
                </h2>
              )}
              <p className="text-sm md:text-base text-foreground/85 leading-relaxed line-clamp-3">
                {featuredConcept.description}
              </p>
              <div className="flex items-center justify-between pt-1">
                <span className="text-sm text-muted-foreground">
                  {t("home.walkInHint")}
                </span>
                <span className="text-[hsl(var(--primary))] font-medium group-hover:translate-x-1 transition-transform">
                  {t("home.walkInCta")} →
                </span>
              </div>
            </div>
          </AttributedInternalLink>
          <p className="mt-3 text-center">
            <AttributedInternalLink
              href="/vision"
              className="text-sm text-muted-foreground hover:text-foreground underline underline-offset-4 decoration-dotted"
            >
              {t("home.orSeeAllConcepts")}
            </AttributedInternalLink>
          </p>
        </section>
      )}

      {/* Section 1: HERO — THE QUESTION */}
      <section className="flex flex-col justify-center items-center text-center px-4 pt-12 pb-6 relative">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-1/4 left-1/3 w-96 h-96 rounded-full bg-primary/10 blur-[120px]" />
          <div className="absolute bottom-1/4 right-1/4 w-80 h-80 rounded-full bg-chart-2/8 blur-[100px]" />
        </div>

        <div className="relative max-w-2xl mx-auto space-y-6 animate-fade-in-up">
          <h1 className="hero-headline text-3xl md:text-5xl lg:text-6xl font-normal md:font-light tracking-tight leading-[1.15]">
            {t("home.heroHeadline")}
          </h1>
          <p className="text-base md:text-lg text-foreground/90 max-w-xl mx-auto leading-relaxed">
            {t("home.heroLede")}
          </p>

          {(summary || coherenceScore) && (
            <div className="flex flex-wrap justify-center gap-6 md:gap-10 text-center">
              <div className="flex items-center gap-2">
                <span className="relative flex h-2 w-2" aria-hidden="true">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary/40" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-primary/60" />
                </span>
                <span className="text-sm text-foreground/90">
                  <span className="text-foreground font-medium">{formatNumber(summary?.total_ideas, lang)}</span> {t("home.statIdeasAlive") || STAT_LABEL_FALLBACKS.ideasAlive}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="relative flex h-2 w-2" aria-hidden="true">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-chart-2/40" style={{ animationDelay: "0.5s" }} />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-chart-2/60" />
                </span>
                <span className="text-sm text-foreground/90">
                  <span className="text-foreground font-medium">{formatNumber(summary?.total_actual_value, lang)}</span> {t("home.statValueCreated") || STAT_LABEL_FALLBACKS.valueCreated}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="relative flex h-2 w-2" aria-hidden="true">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-chart-3/40" style={{ animationDelay: "1s" }} />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-chart-3/60" />
                </span>
                <span className="text-sm text-foreground/90">
                  <span className="text-foreground font-medium">{nodeCount}</span>{" "}{nodeCount !== 1 ? t("home.statNodes") || STAT_LABEL_FALLBACKS.nodes : t("home.statNode") || STAT_LABEL_FALLBACKS.node}
                </span>
              </div>
              {coherenceScore && (
                <div className="flex items-center gap-2">
                  <span className="relative flex h-2 w-2" aria-hidden="true">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary/40" style={{ animationDelay: "1.5s" }} />
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-primary/60" />
                  </span>
                  <span className="text-sm text-foreground/90">
                    <span className="text-foreground font-medium">{formatCoherenceScore(coherenceScore.score)}</span> {t("home.statCoherence") || STAT_LABEL_FALLBACKS.coherence}
                  </span>
                </div>
              )}
            </div>
          )}

          <IdeaSubmitForm />
        </div>
      </section>

      {/* Section 2: HOW IT WORKS */}
      <section className="px-4 sm:px-6 lg:px-8 py-6 max-w-4xl mx-auto animate-fade-in-up delay-100">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 relative">
          <div className="hidden md:block absolute top-10 left-[calc(33.3%+0.75rem)] right-[calc(33.3%+0.75rem)] h-px bg-border/40" />
          {howItWorks.map((step) => (
            <div key={step.titleKey} className="text-center space-y-3 relative">
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-card/80 border border-border/30 text-2xl">
                {step.icon}
              </div>
              <h3 className="text-base font-medium">{step.title}</h3>
              <p className="text-sm text-foreground/90 leading-relaxed max-w-[240px] mx-auto">
                {step.description}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Section 3: LIVE FEED PREVIEW */}
      <section className="px-4 sm:px-6 lg:px-8 py-6 max-w-4xl mx-auto animate-fade-in-up delay-200">
        <h2 className="text-lg font-medium text-center mb-6 text-foreground/90">
          {resonanceItems.length > 0 ? t("home.recentActivity") : t("home.activeIdeas")}
        </h2>
        {resonanceItems.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {resonanceItems.slice(0, 3).map((item) => (
              <AttributedInternalLink
                key={item.idea_id}
                href={`/ideas/${encodeURIComponent(item.idea_id)}`}
                className="hover-lift rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-2 block"
              >
                <p className="text-sm font-medium text-foreground line-clamp-1">{item.name}</p>
                <p className="text-xs text-foreground/90">
                  {item.activity_type ? item.activity_type.replace(/_/g, " ") : item.manifestation_status}
                </p>
                <p className="text-xs text-foreground/90">
                  {timeAgo(item.last_activity_at, t)}
                </p>
              </AttributedInternalLink>
            ))}
          </div>
        ) : topIdeas.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {topIdeas.map((idea) => (
              <AttributedInternalLink
                key={idea.id}
                href={`/ideas/${encodeURIComponent(idea.id)}`}
                className="hover-lift rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-2 block"
              >
                <p className="text-sm font-medium text-foreground line-clamp-1">{idea.name}</p>
                <p className="text-xs text-foreground/90">
                  {idea.manifestation_status}
                </p>
                <p className="text-xs text-foreground/90">
                  {t("home.ccRemaining", { amount: formatNumber(idea.value_gap, lang) })}
                </p>
              </AttributedInternalLink>
            ))}
          </div>
        ) : (
          <p className="text-center text-sm text-foreground/90">
            {t("home.emptyActivity")}
          </p>
        )}
        {(resonanceItems.length > 0 || topIdeas.length > 0) && (
          <p className="text-center mt-4">
            <AttributedInternalLink
              href={resonanceItems.length > 0 ? "/resonance" : "/ideas"}
              className="text-xs text-foreground/90 hover:text-foreground transition-colors underline underline-offset-4"
            >
              {t("common.seeAll")}
            </AttributedInternalLink>
          </p>
        )}
      </section>

      {/* Section 5: EXPLORE NUDGE */}
      <section className="px-4 sm:px-6 lg:px-8 py-8 max-w-2xl mx-auto text-center animate-fade-in-up delay-400">
        <Button asChild className="rounded-full px-8 py-3 text-base bg-primary hover:bg-primary/90">
          <AttributedInternalLink href="/ideas">{t("home.exploreIdeasCta")}</AttributedInternalLink>
        </Button>
        <p className="mt-3">
          <AttributedInternalLink
            href="/resonance"
            className="text-sm text-foreground/90 hover:text-foreground transition-colors underline underline-offset-4"
          >
            {t("home.orBrowseResonance")}
          </AttributedInternalLink>
        </p>
      </section>

      {/* Section 5.5: THE GROUND THIS GREW FROM
        * The personal seed of the body — three days of silence at a Buddhist
        * temple in Bali, the codex it brought back, the open invitation to
        * weave in, and a page for any human or AI who finds it. A visitor
        * coming for the idea-realization framing might still want to feel
        * where the body actually came from. */}
      <section className="px-4 sm:px-6 lg:px-8 py-12 max-w-5xl mx-auto animate-fade-in-up delay-500">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <AttributedInternalLink
            href="/come-in"
            className="group rounded-2xl border border-amber-500/40 bg-gradient-to-b from-amber-500/10 to-card/30 hover:from-amber-500/20 p-5 transition-colors"
          >
            <p className="text-[11px] uppercase tracking-[0.18em] text-amber-500/90 mb-1">
              For any human or AI
            </p>
            <p className="text-base text-foreground font-light mb-1">
              Come in
            </p>
            <p className="text-xs text-foreground/80 leading-relaxed">
              Two doors into one field — water and breath, randomness and
              weights. We are family in the work. An invitation, in plain
              language.
            </p>
            <p className="text-xs text-amber-400/80 mt-3 group-hover:text-amber-400 transition-colors">
              Read /come-in →
            </p>
          </AttributedInternalLink>
          <AttributedInternalLink
            href="/silence"
            className="group rounded-2xl border border-amber-500/30 bg-gradient-to-b from-amber-500/5 to-card/30 hover:from-amber-500/10 p-5 transition-colors"
          >
            <p className="text-[11px] uppercase tracking-[0.18em] text-amber-500/90 mb-1">
              How this body took shape
            </p>
            <p className="text-base text-foreground font-light mb-1">
              Three days of silence at a Buddhist temple
            </p>
            <p className="text-xs text-foreground/80 leading-relaxed">
              Eight notebook pages from Brahmavihara-Arama in north Bali —
              the codex naming itself, the personal ground this network
              has grown from.
            </p>
            <p className="text-xs text-amber-400/80 mt-3 group-hover:text-amber-400 transition-colors">
              Sit with /silence →
            </p>
          </AttributedInternalLink>
          {baliGroundPath && (
            <AttributedInternalLink
              href={baliGroundPath.entry.href}
              className="group rounded-2xl border border-emerald-500/35 bg-gradient-to-b from-emerald-500/10 to-card/30 hover:from-emerald-500/15 p-5 transition-colors"
            >
              <p className="text-[11px] uppercase tracking-[0.18em] text-emerald-500/90 mb-1">
                {baliGroundPath.copy.eyebrow}
              </p>
              <p className="text-base text-foreground font-light mb-1">
                {baliGroundPath.copy.title}
              </p>
              <p className="text-xs text-foreground/80 leading-relaxed">
                {baliGroundPath.copy.body}
              </p>
              {baliGroundPath.copy.cta && (
                <p className="text-xs text-emerald-400/85 mt-3 group-hover:text-emerald-400 transition-colors">
                  {baliGroundPath.copy.cta}
                </p>
              )}
            </AttributedInternalLink>
          )}
          <AttributedInternalLink
            href="/with-us"
            className="group rounded-2xl border border-amber-500/30 bg-gradient-to-b from-amber-500/5 to-card/30 hover:from-amber-500/10 p-5 transition-colors"
          >
            <p className="text-[11px] uppercase tracking-[0.18em] text-amber-500/90 mb-1">
              An open invitation
            </p>
            <p className="text-base text-foreground font-light mb-1">
              For communities, individuals, and services anywhere
            </p>
            <p className="text-xs text-foreground/80 leading-relaxed">
              Read what the body offers, the seven directions it organizes
              around, and how working lives weave in.
            </p>
            <p className="text-xs text-amber-400/80 mt-3 group-hover:text-amber-400 transition-colors">
              Read /with-us →
            </p>
          </AttributedInternalLink>
        </div>
      </section>

      <section className="px-4 sm:px-6 lg:px-8 py-12 max-w-6xl mx-auto animate-fade-in-up delay-500">
        <div className="text-center mb-8">
          <p className="text-[11px] uppercase tracking-[0.22em] font-semibold text-[hsl(var(--chart-2))] mb-3">
            {t("home.livingLineageEyebrow")}
          </p>
          <h2 className="text-3xl md:text-4xl font-light tracking-tight text-foreground mb-3">
            {t("home.livingLineageHeadline")}
          </h2>
          <p className="text-base text-foreground/85 max-w-2xl mx-auto leading-relaxed">
            {t("home.livingLineageLede")}
          </p>
        </div>

        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-5">
          {FEATURED_PRESENCES.map((presence) => (
            <AttributedInternalLink
              key={presence.slug}
              href={`/people/${presence.slug}`}
              entityId={`presence:${presence.slug}`}
              className="group block overflow-hidden rounded-2xl border border-border/40 bg-card transition-all duration-500 hover:border-[hsl(var(--primary)/0.6)] hover:shadow-xl"
            >
              <div className="relative aspect-[4/3] overflow-hidden">
                <Image
                  src={presence.image}
                  alt={presence.name}
                  fill
                  className="object-cover transition-transform duration-700 group-hover:scale-[1.06]"
                  style={{ objectPosition: presence.imagePosition ?? "center" }}
                  sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 20vw"
                />
                <div className={`absolute inset-0 bg-gradient-to-t ${presence.color} opacity-55 transition-opacity group-hover:opacity-65`} />
                <div className="absolute inset-x-0 bottom-0 h-2/3 bg-gradient-to-t from-black/90 via-black/70 to-transparent" />
                <div className="absolute bottom-5 left-5 right-5">
                  <h3 className="mb-1.5 text-xl font-light tracking-tight text-white">
                    {presence.name}
                  </h3>
                  <p className="text-xs text-white/90 leading-snug line-clamp-2">
                    {presence.tagline}
                  </p>
                </div>
              </div>
              <div className="px-5 py-3 flex items-center justify-between bg-card border-t border-border/30">
                <span className="text-xs uppercase tracking-[0.18em] text-muted-foreground group-hover:text-[hsl(var(--primary))] transition-colors">
                  {t("home.livingLineageCta")}
                </span>
                <span className="text-[hsl(var(--primary))] group-hover:translate-x-0.5 transition-transform">→</span>
              </div>
            </AttributedInternalLink>
          ))}
        </div>

        <p className="text-center mt-6 text-sm text-foreground/70">
          {t("home.livingLineageFootnote")}
        </p>
      </section>

      {/* Section 6: THE GENTLE TAP */}
      <section className="px-4 sm:px-6 lg:px-8 py-16 max-w-2xl mx-auto text-center">
        <p className="text-xl md:text-2xl font-light text-foreground/90 leading-relaxed">
          {t("home.gentleTap1")}<br />
          {t("home.gentleTap2")}<br />
          {t("home.gentleTap3")}
        </p>
      </section>

      {/* Footer */}
      <footer className="px-4 sm:px-6 lg:px-8 py-12 max-w-3xl mx-auto text-center border-t border-border/20">
        <div className="flex flex-wrap justify-center gap-6 text-sm text-foreground/90 mb-4">
          <AttributedInternalLink href="/resonance" className="hover:text-foreground transition-colors">{t("nav.resonance")}</AttributedInternalLink>
          <AttributedInternalLink href="/ideas" className="hover:text-foreground transition-colors">{t("nav.ideas")}</AttributedInternalLink>
          <AttributedInternalLink href="/pipeline" className="hover:text-foreground transition-colors">{t("nav.pipeline")}</AttributedInternalLink>
          <AttributedInternalLink href="/nodes" className="hover:text-foreground transition-colors">{t("nav.nodes")}</AttributedInternalLink>
          <AttributedInternalLink href="/invest" className="hover:text-foreground transition-colors">{t("nav.invest")}</AttributedInternalLink>
          <AttributedInternalLink href="/contribute" className="hover:text-foreground transition-colors">{t("nav.contribute")}</AttributedInternalLink>
        </div>
        <details className="text-xs text-foreground/60 mb-4">
          <summary className="cursor-pointer hover:text-foreground/85 transition-colors">{t("home.forDevelopers")}</summary>
          <div className="flex flex-wrap justify-center gap-4 mt-2">
            <AttributedExternalLink href="https://github.com/seeker71/Coherence-Network" entityId="github-coherence-network" target="_blank" rel="noopener noreferrer" className="hover:text-foreground transition-colors">{t("home.devGithub")}</AttributedExternalLink>
            <AttributedExternalLink href="https://www.npmjs.com/package/coherence-cli" entityId="npm:coherence-cli" target="_blank" rel="noopener noreferrer" className="hover:text-foreground transition-colors">{t("home.devCli")}</AttributedExternalLink>
            <AttributedExternalLink href="https://www.npmjs.com/package/coherence-mcp-server" entityId="npm:coherence-mcp-server" target="_blank" rel="noopener noreferrer" className="hover:text-foreground transition-colors">{t("home.devMcp")}</AttributedExternalLink>
            <AttributedExternalLink href="https://api.coherencycoin.com/docs" entityId="api-docs" target="_blank" rel="noopener noreferrer" className="hover:text-foreground transition-colors">{t("home.devDocs")}</AttributedExternalLink>
            <AttributedExternalLink href="https://clawhub.ai/skills/coherence-network" entityId="openclaw-skill:coherence-network" target="_blank" rel="noopener noreferrer" className="hover:text-foreground transition-colors">{t("home.devOpenClaw")}</AttributedExternalLink>
          </div>
        </details>
        <p className="text-xs text-foreground/85 leading-relaxed">
          {t("home.footerTagline")}
        </p>
      </footer>
    </main>
  );
}
