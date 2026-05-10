/**
 * PersonProfileTemplate — shared renderer for /people/{slug} static pages.
 *
 * Each page now lives at `web/content/people/{slug}/{locale}.tsx` as a
 * typed content object; the page file at `web/app/people/{slug}/page.tsx`
 * resolves the request locale and hands the content here. Chrome strings
 * (breadcrumb labels, the edit-profile CTA) come from the translator
 * bound to the resolved locale.
 *
 * The shape lets every page carry its rich JSX (Links to other people,
 * <em>/<strong>, lists, embedded Panels) as data, so non-English content
 * can be authored in the same module shape per locale without forcing
 * markdown-with-tokens parsing.
 */
import type { ReactNode } from "react";
import type { Metadata } from "next";
import Link from "next/link";
import { Panel } from "@/components/Panel";
import { createTranslator } from "@/lib/i18n";
import type { LocaleCode } from "@/lib/locales";
import { TemplateInfluenceWeb } from "./TemplateInfluenceWeb";
import { LineageStrip } from "./LineageStrip";
import { AttentionPresence } from "./AttentionPresence";
import { InfluenceLineageStrip } from "./InfluenceLineageStrip";

export type PersonProfileFact = {
  label: ReactNode;
  value: ReactNode;
};

export type PersonProfileArticle =
  | {
      kind: "narrative";
      heading: ReactNode;
      body: ReactNode;
    }
  | {
      kind: "panel";
      variant?: "warm" | "cool" | "neutral" | "empty";
      eyebrow?: ReactNode;
      heading?: ReactNode;
      body: ReactNode;
    };

export type PersonProfileLineageDoorway = {
  /** Path to the lineage walk for this person (e.g. /people/urs/lineage). */
  href: string;
  /** Short, action-shaped label — e.g. "Walk the 42-year lineage". */
  label: ReactNode;
  /** One-line proportional summary — e.g. "13 works · 11 substrates · 1984–now".
   *  Lets the visitor sense the size before clicking through. */
  summary?: ReactNode;
};

export type PersonProfileContent = {
  // Full Next.js Metadata so each page can supply openGraph, twitter,
  // and any other metadata fields. The root layout's title.template
  // appends " | Coherence Network" — pages should set the bare title
  // here without the suffix to avoid doubling.
  metadata: Metadata;
  breadcrumbName: ReactNode;
  hero: {
    image?: { src: string; objectPosition?: string };
    background?: string;
    /**
     * Optional second image layer rendered as a sibling overlay above the
     * background and below the gradient overlayClass. Useful when the hero
     * is a CSS gradient blended with a map / texture image (e.g. /people/urs).
     */
    extraImage?: { src: string; opacityClass?: string; mixBlendClass?: string };
    overlayClass?: string;
    eyebrow: ReactNode;
    /**
     * Tailwind classes applied to the eyebrow. Defaults to a subtle
     * muted gray (`text-muted-foreground`) which matches most pages.
     * Pages that want warmth can pass `text-[hsl(var(--primary))]`
     * (gold) or `text-[hsl(var(--chart-2))]` (teal); pages with
     * richer eyebrows commonly tone toward teal.
     */
    eyebrowClass?: string;
    name: ReactNode;
    welcome: ReactNode;
    /**
     * Prominent doorway shown high in the hero — directly under the
     * welcome paragraph, above facts. Use for the lineage walk so a
     * visitor sees the shape and size of what's there before scrolling
     * past several other rendering elements to find it. The whole
     * affordance is a Link to `lineageDoorway.href`.
     */
    lineageDoorway?: PersonProfileLineageDoorway;
  };
  facts?: PersonProfileFact[];
  noteFromBody?: {
    eyebrow?: ReactNode;
    body: ReactNode;
  };
  articles: PersonProfileArticle[];
  footer?: ReactNode;
};

const DEFAULT_OVERLAY =
  "absolute inset-0 bg-gradient-to-t from-background via-background/85 to-background/20";

export function PersonProfileTemplate({
  content,
  lang,
  graphSlug,
}: {
  content: PersonProfileContent;
  lang: LocaleCode;
  /** Slug or graph id of the corresponding contributor node, when
   *  this hand-built page maps to one. Plumbing this lets the page
   *  surface the live influence web and the refine doorway alongside
   *  the hand-curated content. Both forms are accepted by the API. */
  graphSlug?: string;
}) {
  const t = createTranslator(lang);
  const { hero } = content;
  const heroStyle: Record<string, string> = {};
  if (hero.image) {
    heroStyle.backgroundImage = `url('${hero.image.src}')`;
    heroStyle.backgroundSize = "cover";
    heroStyle.backgroundPosition = hero.image.objectPosition ?? "center";
  } else if (hero.background) {
    (heroStyle as Record<string, string>).background = hero.background;
  }

  return (
    <main className="relative">
      <section
        className="relative min-h-screen md:min-h-[85vh] flex flex-col justify-end overflow-hidden"
        style={heroStyle}
      >
        {hero.extraImage && (
          <div
            className={`absolute inset-0 ${hero.extraImage.opacityClass ?? "opacity-[0.14]"} ${hero.extraImage.mixBlendClass ?? "mix-blend-soft-light"}`}
            style={{
              backgroundImage: `url('${hero.extraImage.src}')`,
              backgroundSize: "cover",
              backgroundPosition: "center",
            }}
            aria-hidden="true"
          />
        )}
        <div
          className={hero.overlayClass ?? DEFAULT_OVERLAY}
          aria-hidden="true"
        />
        <div className="relative z-10 max-w-3xl mx-auto px-6 py-12 sm:py-16 w-full">
          <nav
            className="text-sm text-muted-foreground mb-8 flex items-center gap-2"
            aria-label="breadcrumb"
          >
            <Link href="/" className="hover:text-primary transition-colors">
              {t("personProfile.breadcrumb.home")}
            </Link>
            <span className="text-muted-foreground/50">/</span>
            <Link href="/people" className="hover:text-primary transition-colors">
              {t("personProfile.breadcrumb.people")}
            </Link>
            <span className="text-muted-foreground/50">/</span>
            <span className="text-foreground/80">{content.breadcrumbName}</span>
          </nav>

          <p
            className={`text-xs uppercase tracking-[0.18em] mb-3 ${hero.eyebrowClass ?? "text-muted-foreground"}`}
          >
            {hero.eyebrow}
          </p>
          <h1 className="text-5xl md:text-7xl font-extralight text-foreground leading-tight mb-5">
            {hero.name}
          </h1>
          <div className="text-lg md:text-xl text-foreground/85 leading-relaxed max-w-2xl">
            {hero.welcome}
          </div>
          {hero.lineageDoorway && (
            <Link
              href={hero.lineageDoorway.href}
              className="group mt-6 inline-flex items-center gap-3 rounded-lg border border-[hsl(var(--primary))]/40 bg-[hsl(var(--primary))]/5 hover:bg-[hsl(var(--primary))]/10 hover:border-[hsl(var(--primary))]/70 px-4 py-3 transition-colors max-w-2xl w-full sm:w-auto"
            >
              <span className="flex-1 min-w-0">
                <span className="block text-sm md:text-base text-[hsl(var(--primary))] font-medium group-hover:underline">
                  {hero.lineageDoorway.label}
                </span>
                {hero.lineageDoorway.summary && (
                  <span className="block text-xs text-foreground/70 mt-0.5">
                    {hero.lineageDoorway.summary}
                  </span>
                )}
              </span>
              <span
                aria-hidden="true"
                className="text-[hsl(var(--primary))] text-lg group-hover:translate-x-0.5 transition-transform shrink-0"
              >
                →
              </span>
            </Link>
          )}
          {content.facts && content.facts.length > 0 && (
            <dl className="mt-7 text-sm text-foreground/85 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 max-w-2xl">
              {content.facts.map((fact, i) => (
                <FactRow key={i} fact={fact} />
              ))}
            </dl>
          )}
        </div>
      </section>

      <div className="max-w-3xl mx-auto px-6 py-12">
        {/* Lineage strip — renders only when the current slug is one
            of the 13 chronological works. Stitches each work page
            into the lineage so the visitor walks the body's own time
            instead of arriving at a dead-end leaf. */}
        <LineageStrip slug={graphSlug} />

        {/* Attention presence — surfaces the witness-trace's record of
            visits to this page. The data is captured on every read; this
            returns it to the visitor so each page is visibly held by
            other cells, not silent. */}
        {graphSlug && (
          <div className="mb-6">
            <AttentionPresence assetId={graphSlug} />
          </div>
        )}

        {/* Influence lineage — surfaces the cross-layer edges from
            /api/graph/nodes/{slug}/edges so a visitor lands on a work
            and immediately sees what shaped it, what grew out of it,
            and which cells contributed. The graph holds these edges;
            this strip puts them one click from the top of the page
            instead of buried in BodyOfEvidence below. */}
        <InfluenceLineageStrip slug={graphSlug} />

        {/* Source-language disclosure — when the visitor's locale is
            not English but the content module bound to this page is
            English (no de.tsx / es.tsx / id.tsx sibling for this slug
            yet), surface that honestly so the reader knows what they're
            looking at. They can use their browser's built-in
            translate-this-page until an author-curated translation
            arrives. The chrome (breadcrumbs, headings) is already in
            their language; this banner addresses the prose. */}
        {lang !== "en" && (content.metadata as { authoredLang?: string })?.authoredLang !== lang && (
          <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 px-4 py-3 text-xs text-stone-300 leading-relaxed mb-8">
            {t("personProfile.sourceLanguageDisclosure")}
          </div>
        )}
        {content.noteFromBody && (
          <Panel variant="warm" eyebrow={content.noteFromBody.eyebrow ?? t("personProfile.noteEyebrow")}>
            <div className="text-sm text-foreground/85 leading-relaxed">
              {content.noteFromBody.body}
            </div>
          </Panel>
        )}

        {content.articles.length > 0 && (
          <section className="mt-12 space-y-12">
            {content.articles.map((article, i) => (
              <ArticleBlock key={i} article={article} />
            ))}
          </section>
        )}

        {graphSlug && (
          <section className="mt-16 pt-8 border-t border-border/40">
            <TemplateInfluenceWeb graphSlug={graphSlug} />
          </section>
        )}

        {content.footer && (
          <footer className="mt-16 pt-8 border-t border-border text-sm text-muted-foreground space-y-2">
            {content.footer}
            <p className="text-xs">
              <Link
                href="/people/edit-your-profile"
                className="text-primary hover:underline"
              >
                {t("personProfile.editProfileCta")}
              </Link>
            </p>
          </footer>
        )}
      </div>
    </main>
  );
}

function FactRow({ fact }: { fact: PersonProfileFact }) {
  return (
    <>
      <dt className="text-muted-foreground">{fact.label}</dt>
      <dd>{fact.value}</dd>
    </>
  );
}

function ArticleBlock({ article }: { article: PersonProfileArticle }) {
  if (article.kind === "narrative") {
    return (
      <article>
        <h2 className="text-2xl font-light text-foreground mb-4">
          {article.heading}
        </h2>
        <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
          {article.body}
        </div>
      </article>
    );
  }
  return (
    <article>
      <Panel
        variant={article.variant ?? "neutral"}
        eyebrow={article.eyebrow}
        heading={article.heading}
      >
        <div className="text-sm text-foreground/85 leading-relaxed space-y-3 mt-2">
          {article.body}
        </div>
      </Panel>
    </article>
  );
}
