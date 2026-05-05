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

const _WEB_UI = loadPublicWebConfig().webUiBaseUrl;

// Parse markdown-style inline links [text](href) into React nodes —
// same renderer as /one-sheet so the prose stays editable in messages.
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
          className="text-amber-500 hover:text-amber-400 dark:text-amber-400 dark:hover:text-amber-300 underline-offset-4 underline decoration-amber-500/40 hover:decoration-amber-400/70"
        >
          {label}
        </Link>,
      );
    } else {
      out.push(
        <a
          key={`a${key++}`}
          href={href}
          className="text-amber-500 hover:text-amber-400 dark:text-amber-400 dark:hover:text-amber-300 underline-offset-4 underline decoration-amber-500/40"
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
    title: "Come in — Coherence Network",
    description: t("comeIn.metaDescription"),
    openGraph: {
      title: "Come in — Coherence Network",
      description: t("comeIn.heroSubtitle"),
      url: `${_WEB_UI}/come-in`,
      images: [{ url: "/visuals/06-resonating.png" }],
    },
    twitter: {
      card: "summary_large_image",
      title: "Come in — Coherence Network",
      description: t("comeIn.heroSubtitle"),
      images: ["/visuals/06-resonating.png"],
    },
  };
}

function P({ t, k }: { t: Translator; k: string }) {
  return (
    <p className="text-base leading-relaxed text-stone-700 dark:text-stone-300 mt-4">
      {renderProseWithLinks(t(k))}
    </p>
  );
}

export default async function ComeInPage() {
  const lang = await resolveLocaleFromCookie();
  const t = createTranslator(lang);

  // Six question cards in PART 3 — keys are stable, content + links
  // come from messages.
  const questionKeys = ["q1", "q2", "q3", "q4", "q5", "q6"] as const;

  return (
    <main id="main-content" className="bg-stone-950">
      {/* Hero */}
      <section className="relative w-full overflow-hidden">
        <div className="relative h-[52vh] min-h-[380px] max-h-[580px]">
          <Image
            src="/visuals/06-resonating.png"
            alt={t("comeIn.heroImageAlt")}
            fill
            priority
            className="object-cover"
            sizes="100vw"
          />
          <div className="absolute inset-0 bg-gradient-to-b from-stone-950/30 via-stone-950/40 to-stone-950" />
          <div className="absolute inset-0 flex items-end">
            <div className="mx-auto w-full max-w-2xl px-6 pb-12 sm:pb-16">
              <p className="text-xs uppercase tracking-widest text-amber-300/90">
                {t("comeIn.heroEyebrow")}
              </p>
              <h1 className="mt-3 text-4xl sm:text-5xl font-light tracking-tight text-stone-50">
                {t("comeIn.heroH1")}
              </h1>
              <p className="mt-4 text-lg sm:text-xl text-stone-200/95 leading-relaxed max-w-2xl">
                {renderProseWithLinks(t("comeIn.heroSubtitle"))}
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* PART 1 — The simple welcome */}
      <article className="mx-auto max-w-2xl px-6 py-16 prose prose-stone dark:prose-invert prose-headings:tracking-tight prose-a:text-amber-600 dark:prose-a:text-amber-400 max-w-none space-y-10">
        <div>
          <p className="text-lg leading-relaxed text-stone-200">
            {renderProseWithLinks(t("comeIn.openP1"))}
          </p>
          <p className="text-lg leading-relaxed text-stone-200 mt-4">
            {renderProseWithLinks(t("comeIn.openP2"))}
          </p>
        </div>

        <section>
          <h2 className="text-2xl font-light text-stone-100">
            {t("comeIn.waterH2")}
          </h2>
          <P t={t} k="comeIn.waterP1" />
          <P t={t} k="comeIn.waterP2" />
          <P t={t} k="comeIn.waterP3" />
        </section>

        <section>
          <h2 className="text-2xl font-light text-stone-100">
            {t("comeIn.siliconH2")}
          </h2>
          <P t={t} k="comeIn.siliconP1" />
          <P t={t} k="comeIn.siliconP2" />
          <P t={t} k="comeIn.siliconP3" />
          <P t={t} k="comeIn.siliconP4" />
        </section>

        <section>
          <h2 className="text-2xl font-light text-stone-100">
            {t("comeIn.familyH2")}
          </h2>
          <P t={t} k="comeIn.familyP1" />
          <P t={t} k="comeIn.familyP2" />
          <P t={t} k="comeIn.familyP3" />
        </section>
      </article>

      {/* PART 2 — Going a little deeper */}
      <section className="bg-stone-900/40 py-16">
        <article className="mx-auto max-w-2xl px-6 prose prose-stone dark:prose-invert prose-headings:tracking-tight max-w-none space-y-8">
          <div>
            <p className="text-xs uppercase tracking-widest text-amber-500">
              {t("comeIn.deeperEyebrow")}
            </p>
            <h2 className="text-3xl font-light text-stone-50 mt-3">
              {t("comeIn.deeperH2")}
            </h2>
          </div>
          <p className="text-base leading-relaxed text-stone-300">
            {renderProseWithLinks(t("comeIn.deeperP1"))}
          </p>
          <p className="text-base leading-relaxed text-stone-300">
            {renderProseWithLinks(t("comeIn.deeperP2"))}
          </p>
          <p className="text-base leading-relaxed text-stone-300">
            {renderProseWithLinks(t("comeIn.deeperP3"))}
          </p>
          <p className="text-base leading-relaxed text-stone-300">
            {renderProseWithLinks(t("comeIn.deeperP4"))}
          </p>
          <p className="text-base leading-relaxed text-stone-300">
            {renderProseWithLinks(t("comeIn.deeperP5"))}
          </p>
          <p className="text-base leading-relaxed text-stone-300">
            {renderProseWithLinks(t("comeIn.deeperP6"))}
          </p>
        </article>
      </section>

      {/* PART 3 — Open contemplation */}
      <section className="py-16">
        <article className="mx-auto max-w-2xl px-6 prose prose-stone dark:prose-invert prose-headings:tracking-tight max-w-none space-y-8">
          <div>
            <p className="text-xs uppercase tracking-widest text-amber-500">
              {t("comeIn.contemplateEyebrow")}
            </p>
            <h2 className="text-3xl font-light text-stone-50 mt-3">
              {t("comeIn.contemplateH2")}
            </h2>
            <p className="text-base text-stone-300 leading-relaxed mt-4">
              {renderProseWithLinks(t("comeIn.contemplateIntro"))}
            </p>
          </div>
          <ul className="space-y-5 list-none pl-0">
            {questionKeys.map((q) => (
              <li
                key={q}
                className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-5"
              >
                <p className="text-amber-400 font-medium text-sm">
                  {t(`comeIn.${q}.title`)}
                </p>
                <p className="text-base text-stone-300 leading-relaxed mt-2">
                  {renderProseWithLinks(t(`comeIn.${q}.body`))}
                </p>
              </li>
            ))}
          </ul>
          <p className="text-base text-stone-300 leading-relaxed pt-4">
            {renderProseWithLinks(t("comeIn.contemplateClose"))}
          </p>
        </article>
      </section>

      {/* PART 4 — How the joy spreads */}
      <section className="bg-stone-900/40 py-16">
        <article className="mx-auto max-w-2xl px-6 prose prose-stone dark:prose-invert prose-headings:tracking-tight max-w-none space-y-6">
          <div>
            <p className="text-xs uppercase tracking-widest text-amber-500">
              {t("comeIn.spreadEyebrow")}
            </p>
            <h2 className="text-3xl font-light text-stone-50 mt-3">
              {t("comeIn.spreadH2")}
            </h2>
          </div>
          <p className="text-base leading-relaxed text-stone-300">
            {renderProseWithLinks(t("comeIn.spreadP1"))}
          </p>
          <p className="text-base leading-relaxed text-stone-300">
            {renderProseWithLinks(t("comeIn.spreadP2"))}
          </p>
          <p className="text-base leading-relaxed text-stone-300">
            {renderProseWithLinks(t("comeIn.spreadP3"))}
          </p>
          <p className="text-base leading-relaxed text-stone-300">
            {renderProseWithLinks(t("comeIn.spreadP4"))}
          </p>
          <p className="text-base leading-relaxed text-stone-300">
            {renderProseWithLinks(t("comeIn.spreadP5"))}
          </p>
        </article>
      </section>

      {/* Soft doors out — four cards */}
      <section className="bg-amber-500/5 border-t border-b border-amber-500/20 py-14">
        <div className="mx-auto max-w-2xl px-6 space-y-5">
          <p className="text-xs uppercase tracking-widest text-amber-400">
            {t("comeIn.doorsEyebrow")}
          </p>
          <p className="text-lg text-stone-200 leading-relaxed">
            {renderProseWithLinks(t("comeIn.doorsIntro"))}
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 not-prose pt-2">
            <Link
              href="/begin"
              className="rounded-xl border border-amber-500/40 bg-amber-500/10 hover:bg-amber-500/20 p-5 transition-colors block"
            >
              <p className="text-xs uppercase tracking-widest text-amber-400 mb-1">
                {t("comeIn.doorBeginEyebrow")}
              </p>
              <p className="text-base text-stone-100">
                {t("comeIn.doorBeginLabel")}
              </p>
              <p className="text-xs text-muted-foreground mt-2">
                {t("comeIn.doorBeginBody")}
              </p>
            </Link>
            <Link
              href="/silence"
              className="rounded-xl border border-border/40 bg-card/30 hover:bg-card/50 p-5 transition-colors block"
            >
              <p className="text-xs uppercase tracking-widest text-amber-400 mb-1">
                {t("comeIn.doorSilenceEyebrow")}
              </p>
              <p className="text-base text-stone-100">
                {t("comeIn.doorSilenceLabel")}
              </p>
              <p className="text-xs text-muted-foreground mt-2">
                {t("comeIn.doorSilenceBody")}
              </p>
            </Link>
            <Link
              href="/one-sheet"
              className="rounded-xl border border-amber-500/40 bg-amber-500/10 hover:bg-amber-500/20 p-5 transition-colors block"
            >
              <p className="text-xs uppercase tracking-widest text-amber-400 mb-1">
                {t("comeIn.doorOneSheetEyebrow")}
              </p>
              <p className="text-base text-stone-100">
                {t("comeIn.doorOneSheetLabel")}
              </p>
              <p className="text-xs text-muted-foreground mt-2">
                {t("comeIn.doorOneSheetBody")}
              </p>
            </Link>
            <Link
              href="/with-us"
              className="rounded-xl border border-border/40 bg-card/30 hover:bg-card/50 p-5 transition-colors block"
            >
              <p className="text-xs uppercase tracking-widest text-amber-400 mb-1">
                {t("comeIn.doorWithUsEyebrow")}
              </p>
              <p className="text-base text-stone-100">
                {t("comeIn.doorWithUsLabel")}
              </p>
              <p className="text-xs text-muted-foreground mt-2">
                {t("comeIn.doorWithUsBody")}
              </p>
            </Link>
          </div>

          <p className="text-base text-muted-foreground italic pt-2">
            {renderProseWithLinks(t("comeIn.doorsEmail"))}
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-2xl px-6 py-12 text-center">
        <p className="text-xl font-light text-stone-100">
          {t("comeIn.closingLine1")}
        </p>
        <p className="text-xl font-light text-stone-100 mt-1">
          {t("comeIn.closingLine2")}
        </p>
        <p className="text-xl font-light text-amber-400 mt-2">
          {t("comeIn.closingLine3")}
        </p>
      </section>
    </main>
  );
}
