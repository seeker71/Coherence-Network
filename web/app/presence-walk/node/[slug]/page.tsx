import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, ArrowRight, Compass, ExternalLink } from "lucide-react";

import { resolveRequestLocale } from "@/lib/request-locale";
import { formatPresenceCopy, getPresenceWalk } from "../../data";
import {
  getPresenceNode,
  getPresenceNodeNeighbors,
  getPresenceBranding,
  getPresenceBrandClasses,
  getPresenceCompositionClasses,
  getPresenceLineage,
  getPresenceMotifLayers,
  getPresenceNodeDetailSections,
  getPresenceNodePageCopy,
  getPresencePresentation,
  getPresenceSiblings,
  getPresenceSourceVisual,
  type PresenceBranding,
  type PresencePresentation,
  type PresenceSourceVisual,
} from "../../nodes";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const lang = await resolveRequestLocale();
  const copy = getPresenceNodePageCopy(lang);
  const node = getPresenceNode(slug, lang);
  if (!node) return { title: copy.metadataFallbackTitle };
  return {
    title: formatPresenceCopy(copy.metadataTitleTemplate, {
      name: node.name,
    }),
    description: node.lens,
  };
}

export default async function PresenceNodePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const lang = await resolveRequestLocale();
  const copy = getPresenceNodePageCopy(lang);
  const detailSections = getPresenceNodeDetailSections(lang);
  const compositionClasses = getPresenceCompositionClasses(lang);
  const brandClasses = getPresenceBrandClasses(lang);
  const motifLayers = getPresenceMotifLayers(lang);
  const node = getPresenceNode(slug, lang);
  if (!node) notFound();

  const walk = getPresenceWalk(node.kind, lang);
  if (!walk) notFound();

  const { previous, next } = getPresenceNodeNeighbors(node.slug, lang);
  const presentation = getPresencePresentation(node.slug, lang);
  const branding = getPresenceBranding(node.slug, lang);
  const lineage = getPresenceLineage(node.slug, lang);
  const siblings = getPresenceSiblings(node.slug, lang);
  const sourceVisual = getPresenceSourceVisual(node.slug, lang);
  const backgroundImage = branding.image ?? node.image;
  const Icon = walk.Icon;

  return (
    <main className="min-h-screen bg-stone-950 text-stone-50">
      {sourceVisual ? (
        <SourceVisualHero
          nodeName={node.name}
          copy={copy}
          sourceHref={node.sourceHref}
          visual={sourceVisual}
        />
      ) : (
      <section className="relative min-h-screen overflow-hidden">
        <img
          src={node.image}
          alt=""
          className="absolute inset-0 h-full w-full object-cover opacity-35"
        />
        <img
          src={backgroundImage}
          alt=""
          className={`absolute inset-0 h-full w-full ${brandImageClass(branding, brandClasses)}`}
          style={{ objectPosition: branding.imagePosition ?? "center center" }}
        />
        <div className={`absolute inset-0 ${brandSideScrimClass(branding, brandClasses)}`} />
        <div className={`absolute inset-0 ${brandBaseScrimClass(branding, brandClasses)}`} />
        <PresenceMotif motif={presentation.motif} motifLayers={motifLayers} />

        <div className="relative z-10 mx-auto flex min-h-screen max-w-6xl flex-col px-4 py-7 sm:px-6 lg:px-8">
          <nav
            className="flex flex-wrap items-center gap-2 text-xs"
            aria-label={copy.navigationAriaLabel}
          >
            <Link
              href={`/presence-walk/${node.kind}`}
              className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-stone-950/35 px-3 py-1.5 text-stone-200 transition-colors hover:border-white/35 hover:bg-white/10"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              {formatPresenceCopy(copy.lensBackTemplate, {
                label: walk.label,
              })}
            </Link>
            <Link
              href={`/presence-walk/node/${previous.slug}`}
              className="rounded-full border border-white/15 bg-stone-950/35 px-3 py-1.5 text-stone-300 transition-colors hover:border-white/35 hover:bg-white/10"
            >
              {previous.name}
            </Link>
            <Link
              href={`/presence-walk/node/${next.slug}`}
              className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-stone-950/35 px-3 py-1.5 text-stone-300 transition-colors hover:border-white/35 hover:bg-white/10"
            >
              {next.name}
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </nav>

          <div className={`flex flex-1 py-8 ${compositionClasses[presentation.composition].shell}`}>
            <div className={`max-w-4xl space-y-5 ${compositionClasses[presentation.composition].text}`}>
              <span className="inline-flex h-12 w-12 items-center justify-center rounded-full border border-white/20 bg-stone-950/35 backdrop-blur">
                <Icon className={`h-5 w-5 ${walk.accent}`} />
              </span>
              {branding.logoImage ? (
                <img
                  src={branding.logoImage}
                  alt={formatPresenceCopy(copy.brandMarkAltTemplate, {
                    name: node.name,
                  })}
                  className={`max-h-16 max-w-[19rem] object-contain drop-shadow-[0_18px_50px_rgba(0,0,0,0.65)] ${brandLogoToneClass(
                    branding,
                    brandClasses,
                  )} ${compositionClasses[presentation.composition].brandMark}`}
                />
              ) : branding.brandName ? (
                <p
                  className={`text-sm font-semibold uppercase tracking-[0.28em] text-white/85 ${walk.accent}`}
                >
                  {branding.brandName}
                </p>
              ) : null}
              <div>
                <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${walk.accent}`}>
                  {formatPresenceCopy(copy.presenceEyebrowTemplate, {
                    label: walk.label,
                    role: node.role,
                  })}
                </p>
                <h1 className="mt-3 max-w-5xl text-5xl font-light leading-[0.95] tracking-tight text-white sm:text-7xl lg:text-8xl">
                  {node.name}
                </h1>
              </div>
              <p className="max-w-3xl text-2xl font-light leading-tight text-stone-50 sm:text-4xl">
                {branding.phrase}
              </p>
              <p className="max-w-2xl text-sm font-medium uppercase tracking-[0.24em] text-stone-300">
                {branding.focus}
              </p>
              <p className="max-w-3xl text-lg font-light leading-relaxed text-stone-100 sm:text-xl">
                {presentation.invitation}
              </p>
              <div className={`flex flex-wrap gap-3 pt-2 ${compositionClasses[presentation.composition].buttons}`}>
                {node.sourceHref ? (
                  <Link
                    href={node.sourceHref}
                    className="inline-flex items-center gap-2 rounded-md bg-white px-4 py-2 text-sm font-medium text-stone-950 transition-opacity hover:opacity-90"
                  >
                    {node.sourceLabel ?? copy.sourceFallbackLabel}
                    <ExternalLink className="h-4 w-4" />
                  </Link>
                ) : null}
                <Link
                  href={`/presence-walk/${node.kind}`}
                  className="inline-flex items-center gap-2 rounded-md border border-white/25 bg-stone-950/25 px-4 py-2 text-sm font-medium text-white backdrop-blur transition-colors hover:bg-white/10"
                >
                  <Compass className="h-4 w-4" />
                  {formatPresenceCopy(copy.walkMoreTemplate, {
                    labelLower: walk.label.toLowerCase(),
                  })}
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>
      )}

      <section className="border-t border-white/10 bg-stone-950 px-4 py-12 sm:px-6 lg:px-8">
        <div className="mx-auto grid max-w-6xl gap-10 lg:grid-cols-[minmax(0,0.85fr)_minmax(340px,1.15fr)]">
          <div className="space-y-7">
            <div>
              <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${walk.accent}`}>
                {copy.lineageLabel}
              </p>
              <h2 className="mt-3 text-2xl font-light text-white">
                {formatPresenceCopy(copy.lineageHeadingTemplate, {
                  name: node.name,
                })}
              </h2>
              <p className="mt-4 text-base leading-relaxed text-stone-200">
                {lineage.voice}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {lineage.roots.map((root) => (
                <span
                  key={root}
                  className="rounded-full border border-white/12 bg-white/[0.04] px-3 py-1 text-xs uppercase tracking-[0.16em] text-stone-300"
                >
                  {root}
                </span>
              ))}
            </div>
            <section className="border-t border-white/10 pt-5">
              <h3 className="text-xs font-semibold uppercase tracking-[0.2em] text-stone-400">
                {copy.visualAlignmentLabel}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-stone-300">
                {node.visualWhy}
              </p>
            </section>
          </div>

          <div>
            <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${walk.accent}`}>
              {copy.naturalSiblingsLabel}
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {siblings.map((sibling) => {
                const siblingBranding = getPresenceBranding(sibling.slug, lang);
                const siblingImage = siblingBranding.image ?? sibling.image;
                return (
                  <Link
                    key={sibling.slug}
                    href={`/presence-walk/node/${sibling.slug}`}
                    className="group relative min-h-[13rem] overflow-hidden rounded-md border border-white/10 bg-stone-900 transition-colors hover:border-white/30"
                  >
                    <img
                      src={siblingImage}
                      alt=""
                      className={`absolute inset-0 h-full w-full transition-transform duration-500 group-hover:scale-[1.03] ${
                        siblingBranding.fit === "contain"
                          ? "object-contain p-6 opacity-90"
                          : "object-cover opacity-85"
                      }`}
                      style={{ objectPosition: siblingBranding.imagePosition ?? "center center" }}
                    />
                    <div className="absolute inset-0 bg-[linear-gradient(0deg,rgba(10,10,9,0.9)_0%,rgba(10,10,9,0.16)_64%,rgba(10,10,9,0.4)_100%)]" />
                    <div className="relative z-10 flex min-h-[13rem] flex-col justify-end p-4">
                      {siblingBranding.logoImage ? (
                        <img
                          src={siblingBranding.logoImage}
                          alt={formatPresenceCopy(copy.brandMarkAltTemplate, {
                            name: sibling.name,
                          })}
                          className={`mb-3 max-h-10 max-w-[12rem] object-contain drop-shadow-[0_10px_30px_rgba(0,0,0,0.75)] ${brandLogoToneClass(
                            siblingBranding,
                            brandClasses,
                          )}`}
                        />
                      ) : null}
                      <p className="text-lg font-light text-white">{sibling.name}</p>
                      <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-stone-300">
                        {siblingBranding.phrase}
                      </p>
                    </div>
                  </Link>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      <section className="border-t border-white/10 bg-stone-950 px-4 py-12 sm:px-6 lg:px-8">
        <div className="mx-auto grid max-w-6xl gap-8 lg:grid-cols-[minmax(0,0.72fr)_minmax(320px,1fr)]">
          <div>
            <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${walk.accent}`}>
              {copy.storyAfterEntryLabel}
            </p>
            <h2 className="mt-3 text-2xl font-light text-white">
              {copy.storyAfterEntryHeading}
            </h2>
          </div>
          <div className="grid gap-5 sm:grid-cols-2">
            {detailSections.map((section) => (
              <section key={section.field} className="border-t border-white/10 pt-4">
                <h3 className="text-xs font-semibold uppercase tracking-[0.2em] text-stone-400">
                  {section.label}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-stone-300">
                  {node[section.field]}
                </p>
              </section>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}

function SourceVisualHero({
  nodeName,
  copy,
  sourceHref,
  visual,
}: {
  nodeName: string;
  copy: ReturnType<typeof getPresenceNodePageCopy>;
  sourceHref?: string;
  visual: PresenceSourceVisual;
}) {
  switch (visual.template) {
    case "curved-portrait-offer":
      return (
        <CurvedPortraitOfferHero
          sourceHref={sourceHref}
          visual={visual}
        />
      );
    case "patterned-release-page":
      return (
        <PatternedReleasePageHero
          nodeName={nodeName}
          copy={copy}
          visual={visual}
        />
      );
  }
  return null;
}

function CurvedPortraitOfferHero({
  sourceHref,
  visual,
}: {
  sourceHref?: string;
  visual: Extract<PresenceSourceVisual, { template: "curved-portrait-offer" }>;
}) {
  return (
    <section className="relative min-h-screen overflow-hidden bg-[#fbfaf8] text-[#183f45]">
      <div className="relative z-20 mx-auto max-w-6xl px-4 pb-3 pt-7 sm:px-6 lg:px-8">
        <div className="hidden justify-center gap-10 text-xs font-semibold uppercase tracking-[0.32em] text-[#16162a] md:flex">
          {visual.navItems.map((item) => (
            <span key={item}>{item}</span>
          ))}
        </div>
        <div className="mt-4 hidden justify-center md:flex">
          <Link
            href={sourceHref ?? "#"}
            className="border-x border-[#f55c58]/50 px-6 py-3 text-xs font-semibold uppercase tracking-[0.32em] text-[#f55c58]"
          >
            {visual.accountLabel}
          </Link>
        </div>
      </div>

      <div className="relative h-[43vh] min-h-[330px] overflow-hidden">
        <img
          src={visual.image}
          alt=""
          className="h-full w-full object-cover"
          style={{ objectPosition: visual.imagePosition ?? "center center" }}
        />
      </div>

      <div className="relative z-10 bg-[#fbfaf8] px-4 pb-12 sm:px-6 lg:px-8">
        <div className="absolute -top-24 left-[-10%] h-44 w-[120%] rounded-[50%] bg-[#fbfaf8]" />
        <div className="pointer-events-none absolute left-8 top-10 h-44 w-44 rounded-full border-[42px] border-[#f6dedd]/45" />
        <div className="relative mx-auto grid max-w-6xl gap-10 pt-16 lg:grid-cols-[0.72fr_1.28fr]">
          <aside className="max-w-md self-end">
            <p className="text-xs font-medium uppercase tracking-[0.32em] text-[#183f45]">
              {visual.offerKicker}
            </p>
            <p className="mt-4 text-2xl font-semibold leading-tight text-[#183f45] sm:text-3xl">
              {visual.offerText}
            </p>
            <Link
              href={sourceHref ?? "#"}
              className="mt-8 inline-flex w-full max-w-sm items-center justify-center rounded-full bg-[#f55c58] px-7 py-4 text-sm font-semibold uppercase tracking-[0.22em] text-white transition-opacity hover:opacity-90"
            >
              {visual.offerCta}
            </Link>
          </aside>

          <div className="max-w-2xl">
            <p className="text-sm font-semibold uppercase tracking-[0.24em] text-[#f55c58]">
              {visual.overline}
            </p>
            <h1 className="mt-4 text-4xl font-medium uppercase leading-tight tracking-normal text-[#244a50] sm:text-5xl">
              {visual.headline}
            </h1>
            <div className="mt-7 space-y-5 text-lg leading-relaxed text-[#173d43]">
              {visual.paragraphs.map((paragraph) => (
                <p key={paragraph}>{paragraph}</p>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function PatternedReleasePageHero({
  nodeName,
  copy,
  visual,
}: {
  nodeName: string;
  copy: ReturnType<typeof getPresenceNodePageCopy>;
  visual: Extract<PresenceSourceVisual, { template: "patterned-release-page" }>;
}) {
  return (
    <section className="relative min-h-screen overflow-hidden bg-[#dff5fb] text-[#0e2a44]">
      <img
        src={visual.backgroundImage}
        alt=""
        className="absolute inset-0 h-full w-full object-cover opacity-70"
      />
      <div className="absolute inset-0 bg-white/18" />

      <header
        className="relative z-10 bg-cover bg-center shadow-[0_10px_22px_rgba(28,91,140,0.42)]"
        style={{ backgroundImage: `url(${visual.headerImage})` }}
      >
        <div className="mx-auto flex h-[8.1rem] max-w-5xl flex-col items-center justify-end px-4 pb-2">
          <img
            src={visual.logoImage}
            alt={formatPresenceCopy(copy.brandMarkAltTemplate, {
              name: nodeName,
            })}
            className="h-auto w-[19rem] max-w-[78vw] object-contain drop-shadow-[0_8px_18px_rgba(14,42,68,0.4)]"
          />
          <nav
            className="mt-2 flex flex-wrap justify-center gap-x-5 gap-y-1 text-xs font-medium uppercase tracking-normal text-white drop-shadow-[0_1px_3px_rgba(14,42,68,0.9)]"
            aria-label={formatPresenceCopy(
              copy.sourceNavigationAriaTemplate,
              { name: nodeName },
            )}
          >
            {visual.navItems.map((item) => (
              <span key={item}>{item}</span>
            ))}
          </nav>
        </div>
      </header>

      <div className="relative z-10 mx-auto min-h-[calc(100vh-8.1rem)] max-w-[56rem] px-5 py-12 sm:px-8">
        <div className="bg-white/42 px-6 py-7 shadow-[inset_22px_0_38px_rgba(255,255,255,0.36),inset_-22px_0_38px_rgba(255,255,255,0.36)] backdrop-blur-[1px] sm:px-10">
          {visual.paragraphs.map((paragraph, index) => (
            <RichTextParagraph
              key={index}
              segments={paragraph}
            />
          ))}
        </div>

        <div className="mt-6 h-px bg-[#1c5d8a]/70 shadow-[0_1px_0_rgba(255,255,255,0.65)]" />
        <section className="mt-5 text-center">
          <h1 className="text-3xl font-light tracking-normal text-[#102744]">
            {visual.releaseHeading}
          </h1>
          <div className="mt-6 grid grid-cols-3 gap-4 sm:gap-6">
            {visual.releases.map((release) => (
              <div
                key={release.image}
                className="border-4 border-white bg-white/40 shadow-[0_14px_32px_rgba(14,42,68,0.18)]"
              >
                <img
                  src={release.image}
                  alt={release.alt}
                  className="aspect-square w-full object-cover"
                />
              </div>
            ))}
          </div>
        </section>
      </div>
    </section>
  );
}

function RichTextParagraph({
  segments,
}: {
  segments: Extract<PresenceSourceVisual, { template: "patterned-release-page" }>["paragraphs"][number];
}) {
  return (
    <p className="text-base leading-relaxed text-[#102744] sm:text-lg">
      {segments.map((segment, index) =>
        segment.strong ? (
          <strong key={`${segment.text}-${index}`}>{segment.text}</strong>
        ) : (
          <span key={`${segment.text}-${index}`}>{segment.text}</span>
        ),
      )}
    </p>
  );
}

function brandImageClass(
  branding: PresenceBranding,
  brandClasses: ReturnType<typeof getPresenceBrandClasses>,
): string {
  if (branding.surface === "album-art") {
    return brandClasses.image.albumArt;
  }
  if (branding.surface === "source-logo") {
    return brandClasses.image.sourceLogo;
  }
  if (branding.fit === "contain") {
    return brandClasses.image.fitContain;
  }
  return brandClasses.image.default;
}

function brandSideScrimClass(
  branding: PresenceBranding,
  brandClasses: ReturnType<typeof getPresenceBrandClasses>,
): string {
  if (branding.surface === "album-art") {
    return brandClasses.sideScrim.albumArt;
  }
  if (branding.surface === "source-portrait") {
    return brandClasses.sideScrim.sourcePortrait;
  }
  return brandClasses.sideScrim.default;
}

function brandBaseScrimClass(
  branding: PresenceBranding,
  brandClasses: ReturnType<typeof getPresenceBrandClasses>,
): string {
  if (branding.surface === "album-art") {
    return brandClasses.baseScrim.albumArt;
  }
  if (branding.surface === "source-portrait") {
    return brandClasses.baseScrim.sourcePortrait;
  }
  return brandClasses.baseScrim.default;
}

function brandLogoToneClass(
  branding: PresenceBranding,
  brandClasses: ReturnType<typeof getPresenceBrandClasses>,
): string {
  return branding.logoTone === "invert"
    ? brandClasses.logoTone.invert
    : brandClasses.logoTone.default;
}

function PresenceMotif({
  motif,
  motifLayers,
}: {
  motif: PresencePresentation["motif"];
  motifLayers: ReturnType<typeof getPresenceMotifLayers>;
}) {
  return (
    <>
      {motifLayers[motif].map((className) => (
        <div key={className} className={className} />
      ))}
    </>
  );
}
