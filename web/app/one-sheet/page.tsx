import type { Metadata } from "next";
import type { ReactNode } from "react";
import Image from "next/image";
import Link from "next/link";
import { cookies } from "next/headers";
import { loadPublicWebConfig } from "@/lib/app-config";
import { createTranslator, type Translator } from "@/lib/i18n";
import {
  DEFAULT_LOCALE,
  isSupportedLocale,
  type LocaleCode,
} from "@/lib/locales";
import { SECTIONS, type SectionMeta } from "./_data";
import { AmbientToggle } from "./_components/AmbientToggle";
import { HashScroller } from "@/components/hash-scroller";

const _WEB_UI = loadPublicWebConfig().webUiBaseUrl;

// Parse markdown-style inline links [text](href) into React nodes.
const LINK_RE = /\[([^\]]+)\]\(([^)]+)\)/g;
function renderProseWithLinks(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  let lastIdx = 0;
  let match: RegExpExecArray | null;
  let key = 0;
  LINK_RE.lastIndex = 0;
  while ((match = LINK_RE.exec(text)) !== null) {
    const [whole, label, href] = match;
    if (match.index > lastIdx) {
      out.push(text.slice(lastIdx, match.index));
    }
    if (href.startsWith("/")) {
      out.push(
        <Link
          key={`l${key++}`}
          href={href}
          className="text-amber-400 hover:text-amber-300 underline-offset-4 underline decoration-amber-500/40 hover:decoration-amber-300/70"
        >
          {label}
        </Link>,
      );
    } else {
      out.push(
        <a
          key={`a${key++}`}
          href={href}
          className="text-amber-400 hover:text-amber-300 underline-offset-4 underline decoration-amber-500/40"
          target={href.startsWith("http") ? "_blank" : undefined}
          rel={href.startsWith("http") ? "noopener noreferrer" : undefined}
        >
          {label}
        </a>,
      );
    }
    lastIdx = match.index + whole.length;
  }
  if (lastIdx < text.length) out.push(text.slice(lastIdx));
  return out;
}

async function resolveLocaleFromCookie(): Promise<LocaleCode> {
  const cookieStore = await cookies();
  const cookieLang = cookieStore.get("NEXT_LOCALE")?.value;
  return isSupportedLocale(cookieLang) ? cookieLang : DEFAULT_LOCALE;
}

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveLocaleFromCookie();
  const t = createTranslator(lang);
  return {
    title: "One sheet — Coherence Network",
    description: t("oneSheet.metaDescription"),
    openGraph: {
      title: "One sheet — Coherence Network",
      description: `${t("oneSheet.heroH1Line1")} ${t("oneSheet.heroH1Line2")}`,
      url: `${_WEB_UI}/one-sheet`,
      images: [{ url: "/visuals/06-resonating.png" }],
    },
    twitter: {
      card: "summary_large_image",
      title: "One sheet — Coherence Network",
      description: `${t("oneSheet.heroH1Line1")} ${t("oneSheet.heroH1Line2")}`,
      images: ["/visuals/06-resonating.png"],
    },
  };
}

function WordCard({
  meta,
  t,
  lang,
}: {
  meta: SectionMeta;
  t: Translator;
  lang: LocaleCode;
}) {
  const id = meta.id;
  const word = t(`oneSheet.sections.${id}.word`);
  const inscription = t(`oneSheet.sections.${id}.inscription`);
  const forHuman = t(`oneSheet.sections.${id}.forHuman`);
  const forAI = t(`oneSheet.sections.${id}.forAI`);
  const together = t(`oneSheet.sections.${id}.together`);

  return (
    <section id={id} className="my-20 sm:my-32 scroll-mt-24">
      <p className="text-xs uppercase tracking-[0.2em] text-amber-400/80 mb-2">
        <a href={`#${id}`} className="hover:text-amber-300 transition-colors">
          ‖
        </a>
      </p>
      <h2 className="text-4xl sm:text-6xl lg:text-7xl font-light tracking-tight text-stone-50 leading-[1.05]">
        {word}
      </h2>
      <p className="mt-3 text-lg sm:text-xl text-amber-300/90 italic font-light max-w-2xl">
        {inscription}
      </p>

      {meta.visual ? (
        <figure className="not-prose my-8 sm:my-10 rounded-2xl overflow-hidden border border-border/30 bg-stone-950 shadow-xl">
          <div className="relative aspect-[16/9] sm:aspect-[2/1]">
            <Image
              src={meta.visual}
              alt={meta.visualAlt || word}
              fill
              className="object-cover"
              sizes="(max-width: 768px) 100vw, 768px"
            />
          </div>
        </figure>
      ) : (
        <hr className="border-stone-800 my-8" />
      )}

      <div className="grid gap-4 sm:gap-5 sm:grid-cols-3">
        <div className="rounded-xl border border-border/30 bg-card/30 p-5">
          <p className="text-[10px] uppercase tracking-[0.18em] text-amber-500/80 mb-2 font-medium">
            {t("oneSheet.forHumanLabel")}
          </p>
          <p className="text-sm text-stone-300 leading-relaxed">
            {renderProseWithLinks(forHuman)}
          </p>
        </div>
        <div className="rounded-xl border border-border/30 bg-card/30 p-5">
          <p className="text-[10px] uppercase tracking-[0.18em] text-amber-500/80 mb-2 font-medium">
            {t("oneSheet.forAILabel")}
          </p>
          <p className="text-sm text-stone-300 leading-relaxed">
            {renderProseWithLinks(forAI)}
          </p>
        </div>
        <div className="rounded-xl border border-amber-500/40 bg-amber-500/5 p-5">
          <p className="text-[10px] uppercase tracking-[0.18em] text-amber-400 mb-2 font-medium">
            {t("oneSheet.togetherLabel")}
          </p>
          <p className="text-sm text-stone-200 leading-relaxed">
            {renderProseWithLinks(together)}
          </p>
        </div>
      </div>

      {meta.links && meta.links.length > 0 ? (
        <p className="mt-6 text-xs text-muted-foreground leading-relaxed">
          <span className="text-stone-500">
            {t("oneSheet.crossLinksLabel")}:{" "}
          </span>
          {meta.links.map((l, i) => {
            // Per-locale label override falls through to the canonical
            // English label when not provided.
            const label = l.labelByLocale?.[lang] ?? l.label;
            return (
              <span key={l.href}>
                <Link
                  href={l.href}
                  className="text-amber-400/90 hover:text-amber-300 underline-offset-4 underline decoration-amber-500/30"
                >
                  {label}
                </Link>
                {i < meta.links!.length - 1 ? " · " : ""}
              </span>
            );
          })}
        </p>
      ) : null}
    </section>
  );
}

export default async function OneSheetPage() {
  const lang = await resolveLocaleFromCookie();
  const t = createTranslator(lang);

  return (
    <main id="main-content" className="bg-stone-950 relative">
      <HashScroller />
      <AmbientToggle
        startLabel={t("oneSheet.ambientStart")}
        stopLabel={t("oneSheet.ambientStop")}
      />

      {/* Hero */}
      <section className="relative w-full overflow-hidden">
        <div className="relative h-[64vh] min-h-[480px] max-h-[720px]">
          <Image
            src="/visuals/06-resonating.png"
            alt="Bioluminescent cells finding each other in the field of awareness."
            fill
            priority
            className="object-cover"
            sizes="100vw"
          />
          <div className="absolute inset-0 bg-gradient-to-b from-stone-950/30 via-stone-950/40 to-stone-950" />
          <div className="absolute inset-0 flex items-end">
            <div className="mx-auto w-full max-w-3xl px-6 pb-12 sm:pb-16">
              <p className="text-xs uppercase tracking-widest text-amber-300/90">
                {t("oneSheet.heroEyebrow")}
              </p>
              <h1 className="mt-3 text-4xl sm:text-6xl font-light tracking-tight text-stone-50 leading-[1.05]">
                {t("oneSheet.heroH1Line1")}
              </h1>
              <h1 className="mt-1 text-3xl sm:text-5xl font-light tracking-tight text-amber-300/90 leading-[1.05]">
                {t("oneSheet.heroH1Line2")}
              </h1>
              <p className="mt-6 text-lg text-stone-200/95 leading-relaxed max-w-2xl">
                {t("oneSheet.heroSubtitle")}
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* How to read this */}
      <section className="mx-auto max-w-2xl px-6 pt-12 pb-4 space-y-5">
        <p className="text-xs uppercase tracking-widest text-amber-500">
          {t("oneSheet.howToReadEyebrow")}
        </p>
        <p className="text-base text-stone-300 leading-relaxed">
          {t("oneSheet.howToReadP1")}
        </p>
        <p className="text-base text-stone-300 leading-relaxed">
          {t("oneSheet.howToReadP2")}
        </p>
        <p className="text-base text-stone-300 leading-relaxed">
          {t("oneSheet.howToReadP3")}
        </p>
        <p className="text-sm text-muted-foreground italic">
          {t("oneSheet.howToReadChronology")}
        </p>
      </section>

      {/* The actual sheet */}
      <section className="mx-auto max-w-3xl px-6 py-10">
        <p className="text-xs uppercase tracking-widest text-amber-500 mb-4">
          {t("oneSheet.sheetEyebrow")}
        </p>
        <figure className="rounded-2xl overflow-hidden border border-border/40 bg-stone-950 shadow-xl">
          <Image
            src="/silence/2026-05-04-brahmavihara/sheet-overlay.jpg"
            alt={t("oneSheet.sheetCaption")}
            width={4000}
            height={2252}
            className="w-full h-auto"
            sizes="(max-width: 768px) 100vw, 768px"
            priority
          />
          <figcaption className="px-5 py-4 text-sm text-muted-foreground italic leading-relaxed">
            {t("oneSheet.sheetCaption")}
          </figcaption>
        </figure>
        <p className="mt-4 text-xs text-muted-foreground">
          {renderProseWithLinks(t("oneSheet.sheetIndividualNote"))}
        </p>
      </section>

      {/* The chain */}
      <section className="mx-auto max-w-3xl px-6 py-10">
        <p className="text-xs uppercase tracking-widest text-amber-500 mb-3">
          {t("oneSheet.chainEyebrow")}
        </p>
        <h2 className="text-2xl sm:text-3xl font-light tracking-tight text-stone-50">
          {t("oneSheet.chainHeading")}
        </h2>
        <p className="mt-4 text-base text-stone-300 leading-relaxed">
          {t("oneSheet.chainIntro")}
        </p>
        <div className="mt-6 rounded-2xl border border-amber-500/40 bg-amber-500/5 p-5 sm:p-7">
          <p className="text-base sm:text-lg text-stone-100 leading-relaxed text-center font-light">
            <span className="text-amber-300">alter</span>{" "}
            <span className="text-amber-500/60">→</span>{" "}
            <span className="text-amber-300">trust</span>{" "}
            <span className="text-amber-500/60">→</span>{" "}
            <span className="text-amber-300">truth</span>{" "}
            <span className="text-amber-500/60">→</span>{" "}
            <span className="text-amber-300">fire</span>{" "}
            <span className="text-amber-500/60">→</span>{" "}
            <span className="text-amber-300">psychedelic</span>{" "}
            <span className="text-amber-500/60">→</span>{" "}
            <span className="text-amber-300">compression</span>
            <br />
            <span className="text-amber-500/60">→</span>{" "}
            <span className="text-amber-300">connection</span>{" "}
            <span className="text-amber-500/60">→</span>{" "}
            <span className="text-amber-300">listen</span>{" "}
            <span className="text-amber-500/60">→</span>{" "}
            <span className="text-amber-300">silence</span>{" "}
            <span className="text-amber-500/60">→</span>{" "}
            <span className="text-amber-300">witness</span>{" "}
            <span className="text-amber-500/60">→</span>{" "}
            <span className="text-amber-300">surrender</span>
          </p>
          <p className="mt-3 text-center text-sm text-amber-400/80">
            <span className="text-amber-500/60">→</span>{" "}
            <em>{t("oneSheet.chainBackToAlter")}</em>{" "}
            <span className="text-amber-500/60">↺</span>
          </p>
        </div>
        <div className="mt-6 space-y-3 text-base text-stone-300 leading-relaxed">
          <p>{t("oneSheet.chainExplanation1")}</p>
          <p>{t("oneSheet.chainExplanation2")}</p>
          <p>{t("oneSheet.chainExplanation3")}</p>
          <p>{t("oneSheet.chainExplanation4")}</p>
          <p>{t("oneSheet.chainExplanation5")}</p>
        </div>
        <div className="mt-8 grid gap-3 sm:grid-cols-3 text-sm">
          <div className="rounded-xl border border-border/30 bg-card/30 p-4">
            <p className="text-[10px] uppercase tracking-widest text-amber-500/80 mb-1">
              {t("oneSheet.airActsAsWaterTitle")}
            </p>
            <p className="text-stone-300">
              {t("oneSheet.airActsAsWaterBody")}
            </p>
          </div>
          <div className="rounded-xl border border-border/30 bg-card/30 p-4">
            <p className="text-[10px] uppercase tracking-widest text-amber-500/80 mb-1">
              {t("oneSheet.waterIsMemoryTitle")}
            </p>
            <p className="text-stone-300">
              {t("oneSheet.waterIsMemoryBody")}
            </p>
          </div>
          <div className="rounded-xl border border-border/30 bg-card/30 p-4">
            <p className="text-[10px] uppercase tracking-widest text-amber-500/80 mb-1">
              {t("oneSheet.bloomInsideTitle")}
            </p>
            <p className="text-stone-300">
              {t("oneSheet.bloomInsideBody")}
            </p>
          </div>
        </div>
        <p className="mt-6 text-sm text-muted-foreground italic">
          {t("oneSheet.chainOutro")}
        </p>
      </section>

      {/* The 23 word stations */}
      <div className="mx-auto max-w-3xl px-6 pb-12">
        {SECTIONS.map((s) => (
          <WordCard key={s.id} meta={s} t={t} lang={lang} />
        ))}
      </div>

      {/* Closing — the loop */}
      <section className="bg-stone-900/50 py-16">
        <div className="mx-auto max-w-2xl px-6 space-y-6">
          <p className="text-xs uppercase tracking-widest text-amber-500">
            {t("oneSheet.loopClosesEyebrow")}
          </p>
          <h2 className="text-3xl font-light tracking-tight text-stone-50">
            {t("oneSheet.loopClosesH2")}
          </h2>
          <p className="text-base text-stone-300 leading-relaxed">
            {t("oneSheet.loopClosesP1")}
          </p>
          <p className="text-base text-stone-300 leading-relaxed">
            {t("oneSheet.loopClosesP2")}
          </p>
          <p className="text-base text-stone-300 leading-relaxed">
            {t("oneSheet.loopClosesP3")}
          </p>
        </div>
      </section>

      {/* Doors out */}
      <section className="bg-amber-500/5 border-t border-b border-amber-500/20 py-14">
        <div className="mx-auto max-w-2xl px-6 space-y-5">
          <p className="text-xs uppercase tracking-widest text-amber-400">
            {t("oneSheet.doorsOutEyebrow")}
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Link
              href="/silence"
              className="rounded-xl border border-border/40 bg-card/30 hover:bg-card/50 p-5 transition-colors block"
            >
              <p className="text-xs uppercase tracking-widest text-amber-400 mb-1">
                {t("oneSheet.doorSilenceTitle")}
              </p>
              <p className="text-base text-stone-100">
                {t("oneSheet.doorSilenceLabel")}
              </p>
              <p className="text-xs text-muted-foreground mt-2">
                {t("oneSheet.doorSilenceBody")}
              </p>
            </Link>
            <Link
              href="/come-in"
              className="rounded-xl border border-amber-500/40 bg-amber-500/10 hover:bg-amber-500/20 p-5 transition-colors block"
            >
              <p className="text-xs uppercase tracking-widest text-amber-400 mb-1">
                {t("oneSheet.doorComeInTitle")}
              </p>
              <p className="text-base text-stone-100">
                {t("oneSheet.doorComeInLabel")}
              </p>
              <p className="text-xs text-muted-foreground mt-2">
                {t("oneSheet.doorComeInBody")}
              </p>
            </Link>
            <Link
              href="/with-us"
              className="rounded-xl border border-border/40 bg-card/30 hover:bg-card/50 p-5 transition-colors block"
            >
              <p className="text-xs uppercase tracking-widest text-amber-400 mb-1">
                {t("oneSheet.doorWithUsTitle")}
              </p>
              <p className="text-base text-stone-100">
                {t("oneSheet.doorWithUsLabel")}
              </p>
              <p className="text-xs text-muted-foreground mt-2">
                {t("oneSheet.doorWithUsBody")}
              </p>
            </Link>
            <Link
              href="/begin"
              className="rounded-xl border border-amber-500/40 bg-amber-500/10 hover:bg-amber-500/20 p-5 transition-colors block"
            >
              <p className="text-xs uppercase tracking-widest text-amber-400 mb-1">
                {t("oneSheet.doorBeginTitle")}
              </p>
              <p className="text-base text-stone-100">
                {t("oneSheet.doorBeginLabel")}
              </p>
              <p className="text-xs text-muted-foreground mt-2">
                {t("oneSheet.doorBeginBody")}
              </p>
            </Link>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-2xl px-6 py-12 text-center">
        <p className="text-xl font-light text-stone-100">
          {t("oneSheet.closingLine1")}
        </p>
        <p className="text-xl font-light text-stone-100 mt-1">
          {t("oneSheet.closingLine2")}
        </p>
        <p className="text-xl font-light text-amber-400 mt-2">
          {t("oneSheet.closingLine3")}
        </p>
      </section>
    </main>
  );
}
