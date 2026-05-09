import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { cookies } from "next/headers";
import { EditablePageIntro, EditablePageMarkdown } from "@/components/content/EditablePageContent";
import { loadPublicWebConfig } from "@/lib/app-config";
import { createTranslator, type Translator } from "@/lib/i18n";
import {
  DEFAULT_LOCALE,
  isSupportedLocale,
  type LocaleCode,
} from "@/lib/locales";
import { L } from "@/components/inline-link";
import { MarkdownProse, ProseLine } from "@/components/markdown-prose";
import { NOTEBOOK_PAGES } from "./_data";

const _WEB_UI = loadPublicWebConfig().webUiBaseUrl;

async function resolveLocale(): Promise<LocaleCode> {
  const cookieStore = await cookies();
  const cookieLang = cookieStore.get("NEXT_LOCALE")?.value;
  return isSupportedLocale(cookieLang) ? cookieLang : DEFAULT_LOCALE;
}

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveLocale();
  const t = createTranslator(lang);
  return {
    title: t("silence.metaTitle"),
    description: t("silence.metaDescription"),
    openGraph: {
      title: t("silence.metaTitle"),
      description: t("silence.ogDescription"),
      url: `${_WEB_UI}/silence`,
      images: [{ url: "/silence/2026-05-04-brahmavihara/8-mandala.jpg" }],
    },
    twitter: {
      card: "summary_large_image",
      title: t("silence.metaTitle"),
      description: t("silence.twitterDescription"),
      images: ["/silence/2026-05-04-brahmavihara/8-mandala.jpg"],
    },
  };
}

// Render the markdown intro/cross-link prose at the top of the
// "Where this is going" door card list.
function DoorListItem({
  t,
  href,
  titleKey,
  descKey,
}: {
  t: Translator;
  href: string;
  titleKey: string;
  descKey: string;
}) {
  return (
    <li>
      <L href={href}>
        <strong>{t(titleKey)}</strong>
      </L>{" "}
      — <ProseLine text={t(descKey)} />
    </li>
  );
}

export default async function SilencePage() {
  const lang = await resolveLocale();
  const t = createTranslator(lang);
  const date = t("silence.retreat.date");
  const location = t("silence.retreat.location");
  const retreatTitle = t("silence.retreat.title");
  const retreatIntro = t("silence.retreat.intro");

  return (
    <main
      id="main-content"
      className="mx-auto max-w-2xl px-4 sm:px-6 py-12 prose prose-stone dark:prose-invert prose-headings:tracking-tight prose-a:text-amber-600 dark:prose-a:text-amber-400 max-w-none"
    >
      <EditablePageIntro
        pageId="silence"
        sourcePage="/silence"
        eyebrow={`${t("silence.retreat.location") ? "Silence" : "Silence"} · ${date} · ${location}`}
        title={retreatTitle}
        description={retreatIntro}
        className="not-prose"
        eyebrowClassName="text-xs uppercase tracking-widest text-muted-foreground"
        titleClassName="mt-4 text-3xl font-light tracking-tight"
        descriptionClassName="mt-6 text-muted-foreground text-lg leading-relaxed"
        showMarkdown={false}
      />
      <EditablePageMarkdown
        pageId="silence"
        className="not-prose mt-8 space-y-4 text-stone-300 leading-relaxed"
      />

      <hr className="border-border/30 my-8" />

      <h2 className="text-2xl font-light">{t("silence.wholeArcH2")}</h2>

      <p>
        <ProseLine text={t("silence.wholeArcP1")} />
      </p>

      <p>
        {t("silence.arcReadsLabel")}{" "}
        <em>{t("silence.retreat.arc")}</em>
      </p>

      <p className="not-prose rounded-md border-l-2 border-amber-500/40 bg-amber-500/5 px-4 py-3 text-sm text-stone-300 italic">
        {t("silence.retreat.held")}
      </p>

      <p>
        <ProseLine text={t("silence.pages45")} />
      </p>

      <p>{t("silence.eachPageBelow")}</p>

      <ul className="text-sm">
        {NOTEBOOK_PAGES.map((p) => (
          <li key={p.slug}>
            <L href={`/silence/${p.slug}`}>
              {String(p.n).padStart(2, "0")} ·{" "}
              {t(`silence.notebook.${p.slug}.shortTitle`)}
            </L>{" "}
            <span className="text-muted-foreground/70">
              — {t(`silence.notebook.${p.slug}.blurb`)}
            </span>
          </li>
        ))}
      </ul>

      <hr className="border-border/30 my-10" />

      {NOTEBOOK_PAGES.map((p) => {
        // Pages 5 (breath) and 6 (organic-intelligence) sat as one open
        // spread in the notebook — the word "Water" arches across the
        // binding. Render them under a single stitched image at the breath
        // slot, and skip organic-intelligence since it's already inside.
        if (p.slug === "organic-intelligence") return null;

        if (p.slug === "breath") {
          const oi = NOTEBOOK_PAGES.find((x) => x.slug === "organic-intelligence")!;
          return (
            <section
              key="breath-organic-intelligence-spread"
              className="my-14 scroll-mt-16"
              id="breath-organic-intelligence-spread"
            >
              <h2 className="text-xl font-medium tracking-tight mb-4">
                <span className="text-muted-foreground/60 font-mono mr-3">
                  {String(p.n).padStart(2, "0")} · {String(oi.n).padStart(2, "0")}
                </span>
                {t("silence.spread.heading")}
              </h2>
              <div className="not-prose my-6 mx-auto max-w-3xl rounded-2xl border border-border/30 overflow-hidden bg-stone-950 shadow-xl">
                <Image
                  src="/silence/2026-05-04-brahmavihara/spread-pages-5-6.jpg"
                  alt={t("silence.spread.alt")}
                  width={8000}
                  height={2252}
                  className="w-full h-auto"
                  sizes="(max-width: 768px) 100vw, 1024px"
                />
              </div>

              <div
                id="breath"
                className="space-y-4 text-stone-300 leading-relaxed mt-8 scroll-mt-16"
              >
                <h3 className="text-lg font-medium tracking-tight">
                  <span className="text-muted-foreground/60 font-mono mr-3">
                    {String(p.n).padStart(2, "0")}
                  </span>
                  {t("silence.notebook.breath.title")}
                </h3>
                <MarkdownProse text={t("silence.notebook.breath.body")} />
                <p className="rounded-md border-l-2 border-amber-500/40 bg-amber-500/5 px-4 py-3 text-sm text-stone-300 italic">
                  <ProseLine text={t("silence.notebook.breath.held")} />
                </p>
                <p className="not-prose text-xs">
                  <Link
                    href="/silence/breath"
                    className="text-amber-500/80 hover:text-amber-400"
                  >
                    {t("silence.holdOnItsOwn")}
                  </Link>
                </p>
              </div>

              <div
                id="organic-intelligence"
                className="space-y-4 text-stone-300 leading-relaxed mt-10 scroll-mt-16"
              >
                <h3 className="text-lg font-medium tracking-tight">
                  <span className="text-muted-foreground/60 font-mono mr-3">
                    {String(oi.n).padStart(2, "0")}
                  </span>
                  {t("silence.notebook.organic-intelligence.title")}
                </h3>
                <MarkdownProse text={t("silence.notebook.organic-intelligence.body")} />
                <p className="rounded-md border-l-2 border-amber-500/40 bg-amber-500/5 px-4 py-3 text-sm text-stone-300 italic">
                  <ProseLine text={t("silence.notebook.organic-intelligence.held")} />
                </p>
                <p className="not-prose text-xs">
                  <Link
                    href="/silence/organic-intelligence"
                    className="text-amber-500/80 hover:text-amber-400"
                  >
                    {t("silence.holdOnItsOwn")}
                  </Link>
                </p>
              </div>
            </section>
          );
        }

        return (
          <section key={p.slug} className="my-14 scroll-mt-16" id={p.slug}>
            <h2 className="text-xl font-medium tracking-tight mb-4">
              <span className="text-muted-foreground/60 font-mono mr-3">
                {String(p.n).padStart(2, "0")}
              </span>
              {t(`silence.notebook.${p.slug}.title`)}
            </h2>
            <div className="not-prose my-6 mx-auto max-w-2xl rounded-2xl border border-border/30 overflow-hidden bg-stone-950 shadow-xl">
              <Link
                href={`/silence/${p.slug}`}
                aria-label={`${t("silence.openLabel")} ${t(`silence.notebook.${p.slug}.title`)}`}
              >
                <Image
                  src={p.image}
                  alt={t(`silence.notebook.${p.slug}.alt`)}
                  width={4000}
                  height={2252}
                  className="w-full h-auto"
                  sizes="(max-width: 768px) 100vw, 768px"
                />
              </Link>
            </div>
            <div className="space-y-4 text-stone-300 leading-relaxed">
              <MarkdownProse text={t(`silence.notebook.${p.slug}.body`)} />
              <p className="rounded-md border-l-2 border-amber-500/40 bg-amber-500/5 px-4 py-3 text-sm text-stone-300 italic">
                <ProseLine text={t(`silence.notebook.${p.slug}.held`)} />
              </p>
              <p className="not-prose text-xs">
                <Link
                  href={`/silence/${p.slug}`}
                  className="text-amber-500/80 hover:text-amber-400"
                >
                  {t("silence.holdOnItsOwn")}
                </Link>
              </p>
            </div>
          </section>
        );
      })}

      <hr className="border-border/30 my-10" />

      <h2 className="text-2xl font-light">{t("silence.whereThisGoingH2")}</h2>

      <p>{t("silence.nextBreath")}</p>

      <ul>
        <DoorListItem
          t={t}
          href="/one-sheet"
          titleKey="silence.doorOneSheetTitle"
          descKey="silence.doorOneSheetDesc"
        />
        <DoorListItem
          t={t}
          href="/come-in"
          titleKey="silence.doorComeInTitle"
          descKey="silence.doorComeInDesc"
        />
        <DoorListItem
          t={t}
          href="/with-us"
          titleKey="silence.doorWithUsTitle"
          descKey="silence.doorWithUsDesc"
        />
        <DoorListItem
          t={t}
          href="/silence/built"
          titleKey="silence.doorBuiltTitle"
          descKey="silence.doorBuiltDesc"
        />
        <DoorListItem
          t={t}
          href="/begin"
          titleKey="silence.doorBeginTitle"
          descKey="silence.doorBeginDesc"
        />
        <DoorListItem
          t={t}
          href="/share"
          titleKey="silence.doorShareTitle"
          descKey="silence.doorShareDesc"
        />
      </ul>
    </main>
  );
}
