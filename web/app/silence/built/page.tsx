import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";
import { cookies } from "next/headers";
import { loadPublicWebConfig } from "@/lib/app-config";
import { createTranslator, type Translator } from "@/lib/i18n";
import {
  DEFAULT_LOCALE,
  isSupportedLocale,
  type LocaleCode,
} from "@/lib/locales";

const _WEB_UI = loadPublicWebConfig().webUiBaseUrl;
const ROOT = "/silence/2026-05-04-brahmavihara";
const BOARD = `${ROOT}/presentation/coherent-native-flow-board.png`;

async function resolveLocale(): Promise<LocaleCode> {
  const cookieStore = await cookies();
  const cookieLang = cookieStore.get("NEXT_LOCALE")?.value;
  return isSupportedLocale(cookieLang) ? cookieLang : DEFAULT_LOCALE;
}

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveLocale();
  const t = createTranslator(lang);
  return {
    title: t("silenceBuilt.metaTitle"),
    description: t("silenceBuilt.metaDescription"),
    openGraph: {
      title: t("silenceBuilt.metaTitle"),
      description: t("silenceBuilt.ogDescription"),
      url: `${_WEB_UI}/silence/built`,
      images: [{ url: BOARD }],
    },
    twitter: {
      card: "summary_large_image",
      title: t("silenceBuilt.metaTitle"),
      description: t("silenceBuilt.twitterDescription"),
      images: [BOARD],
    },
  };
}

interface KeyValueItem {
  label?: string;
  value?: string;
  name?: string;
  use?: string;
  body?: string;
  title?: string;
}

function getArray(t: Translator, key: string): KeyValueItem[] {
  // The translator only returns strings, so to read an array we go via
  // direct JSON access. Re-resolving against the bundle is the simplest
  // way to support arrays in our minimal i18n layer.
  const raw = t(key);
  // If the value came back as the raw key, the path is missing.
  if (raw === key) return [];
  try {
    // The translator stringifies arrays/objects when the path resolves
    // to a non-string. We don't have that today; fall back to indexed
    // lookups by reading individual entries via t(`${key}.${i}.field`).
    // Empty array signals to the caller to read items by index.
    return [];
  } catch {
    return [];
  }
}

function FactStrip({ t }: { t: Translator }) {
  const items: { label: string; value: string }[] = [];
  for (let i = 0; i < 5; i++) {
    const label = t(`silenceBuilt.facts.${i}.label`);
    const value = t(`silenceBuilt.facts.${i}.value`);
    if (label !== `silenceBuilt.facts.${i}.label`) {
      items.push({ label, value });
    }
  }
  return (
    <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      {items.map(({ label, value }) => (
        <div
          key={label}
          className="border-l border-stone-300/70 bg-white/45 px-4 py-3 dark:border-stone-700 dark:bg-stone-950/20"
        >
          <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-stone-400">
            {label}
          </p>
          <p className="mt-2 text-lg font-light text-stone-950 dark:text-stone-100">
            {value}
          </p>
        </div>
      ))}
    </div>
  );
}

function Section({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="mt-16">
      <p className="text-xs uppercase tracking-[0.22em] text-amber-700 dark:text-amber-300">
        {eyebrow}
      </p>
      <h2 className="mt-3 max-w-4xl text-3xl font-light tracking-tight text-stone-950 dark:text-stone-100 sm:text-4xl">
        {title}
      </h2>
      {children}
    </section>
  );
}

// Read N indexed items from a translation array, where each item has
// the same set of subkeys (e.g. moments[i].title / .body).
function readArray(
  t: Translator,
  base: string,
  fields: string[],
  max = 12,
): Record<string, string>[] {
  const out: Record<string, string>[] = [];
  for (let i = 0; i < max; i++) {
    const probe = t(`${base}.${i}.${fields[0]}`);
    if (probe === `${base}.${i}.${fields[0]}`) break;
    const entry: Record<string, string> = {};
    for (const f of fields) entry[f] = t(`${base}.${i}.${f}`);
    out.push(entry);
  }
  return out;
}

function ViewSequence({ t }: { t: Translator }) {
  const moments = readArray(t, "silenceBuilt.viewSequence.moments", ["title", "body"]);
  return (
    <Section
      eyebrow={t("silenceBuilt.viewSequence.eyebrow")}
      title={t("silenceBuilt.viewSequence.title")}
    >
      <p className="mt-5 max-w-4xl text-base leading-relaxed text-stone-700 dark:text-stone-300">
        {t("silenceBuilt.viewSequence.lead")}
      </p>
      <figure className="mt-7 overflow-hidden rounded-lg border border-stone-300/70 bg-white/65 dark:border-stone-700 dark:bg-stone-950/30">
        <Image
          src={BOARD}
          alt={t("silenceBuilt.viewSequence.boardAlt")}
          width={1680}
          height={960}
          className="h-auto w-full"
          sizes="100vw"
        />
        <figcaption className="border-t border-stone-300/70 p-4 text-sm leading-relaxed text-stone-700 dark:border-stone-700 dark:text-stone-300">
          {t("silenceBuilt.viewSequence.boardCaption")}
        </figcaption>
      </figure>
      <div className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {moments.map((m) => (
          <article
            key={m.title}
            className="rounded-lg border border-stone-300/70 bg-white/60 p-5 dark:border-stone-700 dark:bg-stone-950/30"
          >
            <h3 className="text-lg font-medium text-stone-950 dark:text-stone-100">
              {m.title}
            </h3>
            <p className="mt-3 text-sm leading-relaxed text-stone-700 dark:text-stone-300">
              {m.body}
            </p>
          </article>
        ))}
      </div>
    </Section>
  );
}

export default async function SilenceBuiltPage() {
  void getArray; // satisfy unused-import lint until needed
  const lang = await resolveLocale();
  const t = createTranslator(lang);
  const spaces = readArray(t, "silenceBuilt.spatial.spaces", ["name", "body"]);
  const weather: string[] = [];
  for (let i = 0; i < 12; i++) {
    const v = t(`silenceBuilt.climate.weather.${i}`);
    if (v === `silenceBuilt.climate.weather.${i}`) break;
    weather.push(v);
  }
  const atmosphere = readArray(t, "silenceBuilt.atmosphere.items", ["title", "body"]);
  const materials = readArray(t, "silenceBuilt.materials.items", ["name", "use"]);

  return (
    <main id="main-content" className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <p className="text-xs uppercase tracking-widest text-muted-foreground">
        <Link
          href="/silence"
          className="text-muted-foreground/80 hover:text-amber-500"
        >
          {t("silenceBuilt.breadcrumbBack")}
        </Link>{" "}
        · {t("silenceBuilt.retreatLabel")} · 2026-05-04
      </p>

      <section className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1fr)_380px] lg:items-start">
        <div>
          <p className="text-sm uppercase tracking-[0.18em] text-amber-700 dark:text-amber-300">
            {t("silenceBuilt.compoundEyebrow")}
          </p>
          <h1 className="mt-4 max-w-4xl text-5xl font-light tracking-tight text-stone-950 dark:text-stone-100">
            {t("silenceBuilt.h1")}
          </h1>
          <p className="mt-6 max-w-3xl text-xl leading-relaxed text-stone-700 dark:text-stone-300">
            {t("silenceBuilt.lead")}
          </p>
          <FactStrip t={t} />
        </div>

        <figure className="overflow-hidden rounded-lg border border-stone-300/70 bg-stone-950 dark:border-stone-700">
          <Image
            src={`${ROOT}/8-mandala.jpg`}
            alt={t("silenceBuilt.mandalaAlt")}
            width={4000}
            height={2252}
            className="h-auto w-full"
            priority
            sizes="(max-width: 1024px) 100vw, 380px"
          />
          <figcaption className="bg-white px-4 py-3 text-xs leading-relaxed text-stone-700 dark:bg-stone-950 dark:text-stone-300">
            {t("silenceBuilt.sourceCaption")}
          </figcaption>
        </figure>
      </section>

      <ViewSequence t={t} />

      <Section
        eyebrow={t("silenceBuilt.spatial.eyebrow")}
        title={t("silenceBuilt.spatial.title")}
      >
        <p className="mt-5 max-w-4xl text-base leading-relaxed text-stone-700 dark:text-stone-300">
          {t("silenceBuilt.spatial.lead")}
        </p>
        <div className="mt-7 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {spaces.map((space) => (
            <article
              key={space.name}
              className="rounded-lg border border-stone-300/70 bg-white/60 p-5 dark:border-stone-700 dark:bg-stone-950/30"
            >
              <h3 className="text-xl font-light text-stone-950 dark:text-stone-100">
                {space.name}
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-stone-700 dark:text-stone-300">
                {space.body}
              </p>
            </article>
          ))}
        </div>
      </Section>

      <Section
        eyebrow={t("silenceBuilt.climate.eyebrow")}
        title={t("silenceBuilt.climate.title")}
      >
        <div className="mt-7 grid gap-8 lg:grid-cols-[0.9fr_1.1fr] lg:items-start">
          <p className="text-base leading-relaxed text-stone-700 dark:text-stone-300">
            {t("silenceBuilt.climate.lead")}
          </p>
          <ul className="grid gap-3 text-sm leading-relaxed text-stone-700 dark:text-stone-300 sm:grid-cols-2">
            {weather.map((item) => (
              <li
                key={item}
                className="rounded-lg border border-stone-300/70 bg-white/60 p-4 dark:border-stone-700 dark:bg-stone-950/30"
              >
                {item}
              </li>
            ))}
          </ul>
        </div>
      </Section>

      <Section
        eyebrow={t("silenceBuilt.atmosphere.eyebrow")}
        title={t("silenceBuilt.atmosphere.title")}
      >
        <p className="mt-5 max-w-4xl text-sm leading-relaxed text-stone-700 dark:text-stone-300">
          {t("silenceBuilt.atmosphere.lead")}
        </p>
        <div className="mt-7 grid gap-4 md:grid-cols-3">
          {atmosphere.map((item) => (
            <article
              key={item.title}
              className="rounded-lg border border-stone-300/70 bg-white/60 p-5 dark:border-stone-700 dark:bg-stone-950/30"
            >
              <h3 className="text-xl font-light text-stone-950 dark:text-stone-100">
                {item.title}
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-stone-700 dark:text-stone-300">
                {item.body}
              </p>
            </article>
          ))}
        </div>
      </Section>

      <Section
        eyebrow={t("silenceBuilt.materials.eyebrow")}
        title={t("silenceBuilt.materials.title")}
      >
        <div className="mt-7 overflow-hidden rounded-lg border border-stone-300/70 dark:border-stone-700">
          {materials.map((m) => (
            <div
              key={m.name}
              className="grid gap-2 border-b border-stone-300/60 bg-white/55 px-4 py-4 last:border-b-0 dark:border-stone-700 dark:bg-stone-950/25 md:grid-cols-[0.7fr_1.3fr]"
            >
              <p className="font-medium text-stone-950 dark:text-stone-100">
                {m.name}
              </p>
              <p className="text-sm text-stone-700 dark:text-stone-300">
                {m.use}
              </p>
            </div>
          ))}
        </div>
      </Section>

      <section className="mt-16 rounded-lg border border-amber-500/35 bg-amber-500/10 p-6">
        <h2 className="text-2xl font-light tracking-tight text-stone-950 dark:text-stone-100">
          {t("silenceBuilt.schematic.h2")}
        </h2>
        <p className="mt-4 max-w-4xl text-sm leading-relaxed text-stone-800 dark:text-stone-200">
          {t("silenceBuilt.schematic.lead")}
        </p>
        <p className="mt-4 text-sm">
          <Link
            href="/silence/built/design-log"
            className="text-amber-700 hover:text-amber-600 dark:text-amber-300"
          >
            {t("silenceBuilt.schematic.openLink")}
          </Link>
        </p>
      </section>
    </main>
  );
}
