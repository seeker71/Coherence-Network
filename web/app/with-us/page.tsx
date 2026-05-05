import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";
import { cookies } from "next/headers";
import { EditablePageIntro, EditablePageMarkdown } from "@/components/content/EditablePageContent";
import { loadPublicWebConfig } from "@/lib/app-config";
import { createTranslator, type Translator } from "@/lib/i18n";
import {
  DEFAULT_LOCALE,
  isSupportedLocale,
  type LocaleCode,
} from "@/lib/locales";
import { ProseLine } from "@/components/markdown-prose";

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
    title: t("withUs.metaTitle"),
    description: t("withUs.metaDescription"),
    openGraph: {
      title: t("withUs.metaTitle"),
      description: t("withUs.ogDescription"),
      url: `${_WEB_UI}/with-us`,
      images: [{ url: "/visuals/01-the-pulse.png" }],
    },
    twitter: {
      card: "summary_large_image",
      title: t("withUs.metaTitle"),
      description: t("withUs.twitterDescription"),
      images: ["/visuals/01-the-pulse.png"],
    },
  };
}

interface AxisProps {
  name: string;
  essence: string;
  href?: string;
}

function Axis({ name, essence, href }: AxisProps) {
  const inner = (
    <>
      <p className="text-xs uppercase tracking-widest text-amber-400 mb-1">
        {name}
      </p>
      <p className="text-sm text-stone-200 leading-relaxed">{essence}</p>
    </>
  );
  return href ? (
    <Link
      href={href}
      className="rounded-xl border border-amber-500/30 bg-card/30 hover:bg-amber-500/5 hover:border-amber-500/60 p-5 block transition-colors"
    >
      {inner}
    </Link>
  ) : (
    <div className="rounded-xl border border-border/30 bg-card/30 p-5">
      {inner}
    </div>
  );
}

interface FeelTileProps {
  src: string;
  alt: string;
  title: string;
  body: string;
}

function FeelTile({ src, alt, title, body }: FeelTileProps) {
  return (
    <div className="rounded-2xl overflow-hidden border border-border/30 bg-stone-900/60">
      <div className="relative aspect-[4/3]">
        <Image src={src} alt={alt} fill className="object-cover" sizes="(max-width: 768px) 100vw, 50vw" />
      </div>
      <div className="p-5 space-y-1">
        <p className="text-sm text-amber-400 font-medium">{title}</p>
        <p className="text-sm text-stone-200 leading-relaxed">{body}</p>
      </div>
    </div>
  );
}

interface PracticeTileProps {
  name: string;
  body: string;
  href?: string;
}

function PracticeTile({ name, body, href }: PracticeTileProps) {
  const inner = (
    <>
      <p className="text-sm text-amber-400 font-medium">{name}</p>
      <p className="mt-2 text-sm text-stone-200 leading-relaxed">{body}</p>
    </>
  );
  return href ? (
    <Link
      href={href}
      className="rounded-xl border border-amber-500/30 bg-card/30 hover:bg-amber-500/5 hover:border-amber-500/60 p-5 block transition-colors"
    >
      {inner}
    </Link>
  ) : (
    <div className="rounded-xl border border-border/30 bg-card/30 p-5">
      {inner}
    </div>
  );
}

// Read N indexed items from a translation array.
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

const FEEL_TILE_SRCS = [
  "/visuals/life-shared-meal.png",
  "/visuals/space-hearth-interior.png",
  "/visuals/space-water-temple-interior.png",
  "/visuals/life-ceremony-fire.png",
];

const SPACE_TILE_SRCS = [
  "/visuals/space-nest-ground.png",
  "/visuals/space-stillness-sanctuary.png",
  "/visuals/space-gathering-bowl.png",
  "/visuals/space-movement-ground.png",
];

interface IconListProps {
  items: { label: string; body: string }[];
  renderBody?: (text: string) => ReactNode;
}

function IconList({ items, renderBody }: IconListProps) {
  return (
    <ul className="space-y-3 text-base text-stone-200 leading-relaxed pt-2">
      {items.map((it) => (
        <li key={it.label} className="flex gap-3">
          <span className="text-amber-400 mt-1">·</span>
          <span>
            <strong className="text-stone-100">{it.label}</strong>{" "}
            {renderBody ? renderBody(it.body) : it.body}
          </span>
        </li>
      ))}
    </ul>
  );
}

export default async function WithUsPage() {
  const lang = await resolveLocale();
  const t = createTranslator(lang);
  const feelTiles = readArray(t, "withUs.feelTiles", ["alt", "title", "body"]);
  const axes = readArray(t, "withUs.axes", ["name", "essence", "href"]);
  const spaceTiles = readArray(t, "withUs.spaceTiles", ["alt", "title", "body"]);
  const alreadyItems = readArray(t, "withUs.alreadyItems", ["label", "body"]);
  const practiceTiles = readArray(t, "withUs.practiceTiles", ["name", "body", "href"]);
  const ursOfferItems = readArray(t, "withUs.ursOfferItems", ["label", "body"]);

  return (
    <main id="main-content" className="bg-stone-950">
      {/* Hero — radiant pulse */}
      <section className="relative w-full overflow-hidden">
        <div className="relative h-[64vh] min-h-[480px] max-h-[720px]">
          <Image
            src="/visuals/01-the-pulse.png"
            alt={t("withUs.heroAlt")}
            fill
            priority
            className="object-cover"
            sizes="100vw"
          />
          <div className="absolute inset-0 bg-gradient-to-b from-stone-950/30 via-stone-950/40 to-stone-950" />
          <div className="absolute inset-0 flex items-end">
            <div className="mx-auto w-full max-w-3xl px-6 pb-12 sm:pb-16">
              <EditablePageIntro
                pageId="with-us"
                sourcePage="/with-us"
                eyebrow={t("withUs.heroEyebrow")}
                title={t("withUs.heroTitle")}
                description={t("withUs.heroDescription")}
                eyebrowClassName="text-xs uppercase tracking-widest text-amber-300/90"
                titleClassName="mt-3 text-4xl sm:text-5xl font-light tracking-tight text-stone-50"
                descriptionClassName="mt-4 text-lg sm:text-xl text-stone-200/95 leading-relaxed max-w-2xl"
                showMarkdown={false}
              />
            </div>
          </div>
        </div>
      </section>

      <EditablePageMarkdown
        pageId="with-us"
        className="mx-auto max-w-3xl px-6 pt-12 -mb-4 space-y-4 text-base leading-relaxed text-stone-300"
      />

      {/* Who this is for */}
      <section className="mx-auto max-w-2xl px-6 py-16 space-y-5">
        <p className="text-xs uppercase tracking-widest text-amber-500">
          {t("withUs.whoForEyebrow")}
        </p>
        <p className="text-lg text-stone-200 leading-relaxed">
          <ProseLine text={t("withUs.whoForP1")} />
        </p>
        <p className="text-lg text-stone-200 leading-relaxed">
          <ProseLine text={t("withUs.whoForP2")} />
        </p>
        <p className="text-lg text-stone-200 leading-relaxed">
          <ProseLine text={t("withUs.whoForP3")} />
        </p>
        <p className="text-base text-muted-foreground italic pt-2">
          <ProseLine text={t("withUs.whoForP4")} />
        </p>
      </section>

      {/* What it feels like */}
      <section className="bg-stone-900/40 py-16">
        <div className="mx-auto max-w-5xl px-6 space-y-8">
          <div className="max-w-2xl">
            <p className="text-xs uppercase tracking-widest text-amber-500">
              {t("withUs.feelEyebrow")}
            </p>
            <h2 className="mt-3 text-3xl font-light tracking-tight text-stone-50">
              {t("withUs.feelH2")}
            </h2>
            <p className="mt-4 text-base text-stone-200 leading-relaxed">
              <ProseLine text={t("withUs.feelLead")} />
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            {feelTiles.map((tile, i) => (
              <FeelTile
                key={tile.title}
                src={FEEL_TILE_SRCS[i]}
                alt={tile.alt}
                title={tile.title}
                body={tile.body}
              />
            ))}
          </div>
        </div>
      </section>

      {/* The codex */}
      <section className="relative w-full overflow-hidden">
        <div className="relative h-[36vh] min-h-[260px] max-h-[420px]">
          <Image
            src="/visuals/05-nourishing.png"
            alt={t("withUs.codexSectionAlt")}
            fill
            className="object-cover opacity-80"
            sizes="100vw"
          />
          <div className="absolute inset-0 bg-gradient-to-b from-stone-950/60 via-stone-950/40 to-stone-950" />
        </div>
        <div className="mx-auto max-w-3xl px-6 -mt-32 sm:-mt-40 relative pb-16">
          <p className="text-xs uppercase tracking-widest text-amber-300">
            {t("withUs.codexEyebrow")}
          </p>
          <h2 className="mt-3 text-3xl font-light tracking-tight text-stone-50">
            {t("withUs.codexH2")}
          </h2>
          <p className="mt-4 text-base text-stone-200/95 leading-relaxed max-w-2xl">
            <ProseLine text={t("withUs.codexLead")} />
          </p>

          <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 gap-3">
            {axes.map((a) => (
              <Axis key={a.name} name={a.name} essence={a.essence} href={a.href} />
            ))}
          </div>
        </div>
      </section>

      {/* The silence — personal seed */}
      <section className="bg-stone-900/60 py-16">
        <div className="mx-auto max-w-3xl px-6 space-y-8">
          <div>
            <p className="text-xs uppercase tracking-widest text-amber-500">
              {t("withUs.shapeEyebrow")}
            </p>
            <h2 className="mt-3 text-3xl font-light tracking-tight text-stone-50">
              {t("withUs.shapeH2")}
            </h2>
            <p className="mt-4 text-lg text-stone-200 leading-relaxed">
              {t("withUs.shapeLead")}
            </p>
          </div>

          <figure className="rounded-2xl border border-border/30 overflow-hidden bg-stone-950 shadow-xl">
            <Image
              src="/silence/2026-05-04-brahmavihara/8-mandala.jpg"
              alt={t("withUs.shapeFigureAlt")}
              width={4000}
              height={2252}
              className="w-full h-auto"
              sizes="(max-width: 768px) 100vw, 768px"
            />
            <figcaption className="px-5 py-4 text-sm text-muted-foreground italic">
              {t("withUs.shapeFigureCaption")}
            </figcaption>
          </figure>

          <p className="text-base text-stone-200 leading-relaxed">
            <ProseLine text={t("withUs.shapeClose")} />
          </p>
        </div>
      </section>

      {/* What we'd build with land */}
      <section className="relative w-full overflow-hidden">
        <div className="relative h-[60vh] min-h-[440px] max-h-[640px]">
          <Image
            src="/visuals/nature-architecture-blend.png"
            alt={t("withUs.landSectionAlt")}
            fill
            className="object-cover"
            sizes="100vw"
          />
          <div className="absolute inset-0 bg-gradient-to-b from-stone-950/40 via-stone-950/30 to-stone-950" />
          <div className="absolute inset-0 flex items-end">
            <div className="mx-auto w-full max-w-3xl px-6 pb-12 sm:pb-16 space-y-4">
              <p className="text-xs uppercase tracking-widest text-amber-300/90">
                {t("withUs.landEyebrow")}
              </p>
              <h2 className="text-3xl font-light tracking-tight text-stone-50">
                {t("withUs.landH2")}
              </h2>
              <p className="text-base text-stone-200/95 leading-relaxed max-w-2xl">
                {t("withUs.landLead")}
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* What the spaces look like */}
      <section className="mx-auto max-w-5xl px-6 py-16 space-y-8">
        <div className="max-w-2xl">
          <p className="text-xs uppercase tracking-widest text-amber-500">
            {t("withUs.spacesEyebrow")}
          </p>
          <h2 className="mt-3 text-3xl font-light tracking-tight text-stone-50">
            {t("withUs.spacesH2")}
          </h2>
          <p className="mt-4 text-base text-stone-200 leading-relaxed">
            {t("withUs.spacesLead")}
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          {spaceTiles.map((tile, i) => (
            <FeelTile
              key={tile.title}
              src={SPACE_TILE_SRCS[i]}
              alt={tile.alt}
              title={tile.title}
              body={tile.body}
            />
          ))}
        </div>
      </section>

      {/* What's already here */}
      <section className="bg-stone-900/50 py-16">
        <div className="mx-auto max-w-3xl px-6 space-y-6">
          <p className="text-xs uppercase tracking-widest text-amber-500">
            {t("withUs.alreadyEyebrow")}
          </p>
          <h2 className="text-3xl font-light tracking-tight text-stone-50">
            {t("withUs.alreadyH2")}
          </h2>
          <p className="text-base text-stone-200 leading-relaxed">
            {t("withUs.alreadyLead")}
          </p>
          <IconList
            items={alreadyItems.map((it) => ({ label: it.label, body: it.body }))}
            renderBody={(text) => <ProseLine text={text} />}
          />
        </div>
      </section>

      {/* For practitioners */}
      <section className="mx-auto max-w-3xl px-6 py-16 space-y-8">
        <div>
          <p className="text-xs uppercase tracking-widest text-amber-500">
            {t("withUs.practitionerEyebrow")}
          </p>
          <h2 className="mt-3 text-3xl font-light tracking-tight text-stone-50">
            {t("withUs.practitionerH2")}
          </h2>
          <p className="mt-4 text-base text-stone-200 leading-relaxed">
            <ProseLine text={t("withUs.practitionerLead")} />
          </p>
        </div>

        <div className="space-y-4">
          {practiceTiles.map((tile) => (
            <PracticeTile
              key={tile.name}
              name={tile.name}
              body={tile.body}
              href={tile.href}
            />
          ))}
        </div>

        <p className="text-base text-muted-foreground italic">
          <ProseLine text={t("withUs.practitionerClose")} />
        </p>
      </section>

      {/* What Urs brings */}
      <section className="bg-stone-900/40 py-16">
        <div className="mx-auto max-w-3xl px-6 space-y-6">
          <p className="text-xs uppercase tracking-widest text-amber-500">
            {t("withUs.ursEyebrow")}
          </p>
          <h2 className="text-3xl font-light tracking-tight text-stone-50">
            {t("withUs.ursH2")}
          </h2>
          <p className="text-base text-stone-200 leading-relaxed">
            <ProseLine text={t("withUs.ursIntro")} />
          </p>
          <p className="text-base text-stone-200 leading-relaxed">
            {t("withUs.ursOfferLabel")}
          </p>
          <IconList items={ursOfferItems.map((it) => ({ label: it.label, body: it.body }))} />
          <p className="text-base text-stone-200 leading-relaxed pt-2">
            {t("withUs.ursClose")}
          </p>
        </div>
      </section>

      {/* The invitation */}
      <section className="bg-amber-500/5 border-t border-b border-amber-500/20 py-16">
        <div className="mx-auto max-w-2xl px-6 space-y-6">
          <p className="text-xs uppercase tracking-widest text-amber-400">
            {t("withUs.invitationEyebrow")}
          </p>
          <h2 className="text-3xl font-light tracking-tight text-stone-50">
            {t("withUs.invitationH2")}
          </h2>
          <p className="text-lg text-stone-200 leading-relaxed">
            <ProseLine text={t("withUs.invitationLead")} />
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 not-prose pt-2">
            <Link
              href="/begin"
              className="rounded-xl border border-amber-500/40 bg-amber-500/10 hover:bg-amber-500/20 p-5 transition-colors"
            >
              <p className="text-xs uppercase tracking-widest text-amber-400 mb-1">
                {t("withUs.doorBeginEyebrow")}
              </p>
              <p className="text-base text-stone-100">
                {t("withUs.doorBeginLabel")}
              </p>
              <p className="text-xs text-muted-foreground mt-2">
                {t("withUs.doorBeginBody")}
              </p>
            </Link>
            <Link
              href="/share"
              className="rounded-xl border border-border/40 bg-card/30 hover:bg-card/50 p-5 transition-colors"
            >
              <p className="text-xs uppercase tracking-widest text-amber-400 mb-1">
                {t("withUs.doorShareEyebrow")}
              </p>
              <p className="text-base text-stone-100">
                {t("withUs.doorShareLabel")}
              </p>
              <p className="text-xs text-muted-foreground mt-2">
                {t("withUs.doorShareBody")}
              </p>
            </Link>
          </div>

          <p className="text-lg text-stone-200 leading-relaxed pt-2">
            <ProseLine text={t("withUs.invitationEmail")} />
          </p>
          <p className="text-base text-muted-foreground italic">
            {t("withUs.invitationCommunities")}
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-2xl px-6 py-12">
        <p className="text-xs text-muted-foreground italic">
          {t("withUs.livingDocFooter")}
        </p>
      </section>
    </main>
  );
}
