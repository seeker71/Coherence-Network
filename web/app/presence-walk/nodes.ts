import { DEFAULT_LOCALE, type LocaleCode } from "@/lib/locales";

import { getPresenceContent, type PresenceKind } from "./data";

export type PresenceNode = {
  slug: string;
  kind: PresenceKind;
  name: string;
  nodeType: string;
  role: string;
  lens: string;
  story: string;
  style: string;
  message: string;
  presence: string;
  visualWhy: string;
  image: string;
  sourceHref?: string;
  sourceLabel?: string;
};

export type PresencePresentation = {
  invitation: string;
  composition: "left-low" | "center" | "right" | "wide-low" | "upper-left";
  motif:
    | "quiet-rings"
    | "bass-waves"
    | "network-bloom"
    | "oracle-portal"
    | "center-line"
    | "ceremony-spiral"
    | "shelter-threshold"
    | "floor-lines"
    | "river-field"
    | "body-orbit"
    | "altar-wave"
    | "elemental-breath"
    | "gravity-duet"
    | "question-portal"
    | "geometry-grid"
    | "earth-grid"
    | "sky-circles"
    | "loop-circle"
    | "nexus-grid"
    | "compass-path"
    | "mind-meld"
    | "woven-fire"
    | "seasonal-gate";
};

export type PresenceBranding = {
  image?: string;
  logoImage?: string;
  logoTone?: "invert";
  brandName?: string;
  fit?: "cover" | "contain";
  imagePosition?: string;
  surface?: "default" | "source-portrait" | "source-logo" | "album-art";
  phrase: string;
  focus: string;
};

export type PresenceLineage = {
  voice: string;
  roots: string[];
  siblings: string[];
};

export type PresenceNodeDetailSection = {
  label: string;
  field: "story" | "style" | "message" | "presence";
};

export type PresenceRichTextSegment = {
  text: string;
  strong?: boolean;
};

export type PresenceSourceVisual =
  | {
      template: "curved-portrait-offer";
      image: string;
      imagePosition?: string;
      navItems: string[];
      accountLabel: string;
      overline: string;
      headline: string;
      paragraphs: string[];
      offerKicker: string;
      offerText: string;
      offerCta: string;
    }
  | {
      template: "patterned-release-page";
      backgroundImage: string;
      headerImage: string;
      logoImage: string;
      navItems: string[];
      paragraphs: PresenceRichTextSegment[][];
      releaseHeading: string;
      releases: Array<{
        image: string;
        alt: string;
      }>;
    };

type PresenceNodePageCopy = {
  metadataFallbackTitle: string;
  metadataTitleTemplate: string;
  navigationAriaLabel: string;
  lensBackTemplate: string;
  presenceEyebrowTemplate: string;
  sourceFallbackLabel: string;
  walkMoreTemplate: string;
  brandMarkAltTemplate: string;
  lineageLabel: string;
  lineageHeadingTemplate: string;
  visualAlignmentLabel: string;
  naturalSiblingsLabel: string;
  storyAfterEntryLabel: string;
  storyAfterEntryHeading: string;
  sourceNavigationAriaTemplate: string;
};

type PresenceBrandClasses = {
  image: {
    albumArt: string;
    sourceLogo: string;
    fitContain: string;
    default: string;
  };
  sideScrim: {
    albumArt: string;
    sourcePortrait: string;
    default: string;
  };
  baseScrim: {
    albumArt: string;
    sourcePortrait: string;
    default: string;
  };
  logoTone: {
    invert: string;
    default: string;
  };
};

type PresenceNodeContent = {
  nodePage: {
    copy: PresenceNodePageCopy;
    detailSections: PresenceNodeDetailSection[];
    compositionClasses: Record<
      PresencePresentation["composition"],
      {
        shell: string;
        text: string;
        buttons: string;
        brandMark: string;
      }
    >;
    brandClasses: PresenceBrandClasses;
    motifLayers: Record<PresencePresentation["motif"], string[]>;
  };
  presenceNodes: {
    order: string[];
    nodes: Record<string, PresenceNode>;
    presentations: Record<string, PresencePresentation>;
    branding: Record<string, PresenceBranding>;
    sourceVisuals: Record<string, PresenceSourceVisual>;
    lineages: Record<string, PresenceLineage>;
    fallbacks: {
      presentation: PresencePresentation;
      branding: PresenceBranding;
      lineage: PresenceLineage;
    };
  };
};

export const PRESENCE_NODE_SLUGS = getPresenceNodeSlugs();

export function getPresenceNodePageCopy(
  lang: LocaleCode = DEFAULT_LOCALE,
): PresenceNodePageCopy {
  return nodeContent(lang).nodePage.copy;
}

export function getPresenceNodeDetailSections(
  lang: LocaleCode = DEFAULT_LOCALE,
): PresenceNodeDetailSection[] {
  return nodeContent(lang).nodePage.detailSections;
}

export function getPresenceCompositionClasses(lang: LocaleCode = DEFAULT_LOCALE) {
  return nodeContent(lang).nodePage.compositionClasses;
}

export function getPresenceBrandClasses(lang: LocaleCode = DEFAULT_LOCALE) {
  return nodeContent(lang).nodePage.brandClasses;
}

export function getPresenceMotifLayers(lang: LocaleCode = DEFAULT_LOCALE) {
  return nodeContent(lang).nodePage.motifLayers;
}

export function getPresenceNodeSlugs(lang: LocaleCode = DEFAULT_LOCALE): string[] {
  return nodeContent(lang).presenceNodes.order;
}

export function getPresenceNode(
  slug: string,
  lang: LocaleCode = DEFAULT_LOCALE,
): PresenceNode | undefined {
  return nodeContent(lang).presenceNodes.nodes[slug];
}

export function getPresenceNodesByKind(
  kind: PresenceKind,
  lang: LocaleCode = DEFAULT_LOCALE,
): PresenceNode[] {
  const content = nodeContent(lang).presenceNodes;
  return content.order
    .map((slug) => content.nodes[slug])
    .filter((node): node is PresenceNode => Boolean(node) && node.kind === kind);
}

export function getPresenceNodeNeighbors(
  slug: string,
  lang: LocaleCode = DEFAULT_LOCALE,
): {
  previous: PresenceNode;
  next: PresenceNode;
} {
  const content = nodeContent(lang).presenceNodes;
  const nodes = content.order
    .map((nodeSlug) => content.nodes[nodeSlug])
    .filter((node): node is PresenceNode => Boolean(node));
  const index = nodes.findIndex(({ slug: nodeSlug }) => nodeSlug === slug);
  const safeIndex = index === -1 ? 0 : index;
  return {
    previous: nodes[(safeIndex - 1 + nodes.length) % nodes.length],
    next: nodes[(safeIndex + 1) % nodes.length],
  };
}

export function getPresencePresentation(
  slug: string,
  lang: LocaleCode = DEFAULT_LOCALE,
): PresencePresentation {
  const content = nodeContent(lang).presenceNodes;
  return content.presentations[slug] ?? content.fallbacks.presentation;
}

export function getPresenceBranding(
  slug: string,
  lang: LocaleCode = DEFAULT_LOCALE,
): PresenceBranding {
  const content = nodeContent(lang).presenceNodes;
  return content.branding[slug] ?? content.fallbacks.branding;
}

export function getPresenceSourceVisual(
  slug: string,
  lang: LocaleCode = DEFAULT_LOCALE,
): PresenceSourceVisual | undefined {
  return nodeContent(lang).presenceNodes.sourceVisuals[slug];
}

export function getPresenceLineage(
  slug: string,
  lang: LocaleCode = DEFAULT_LOCALE,
): PresenceLineage {
  const content = nodeContent(lang).presenceNodes;
  return content.lineages[slug] ?? content.fallbacks.lineage;
}

export function getPresenceSiblings(
  slug: string,
  lang: LocaleCode = DEFAULT_LOCALE,
): PresenceNode[] {
  return getPresenceLineage(slug, lang)
    .siblings.map((siblingSlug) => getPresenceNode(siblingSlug, lang))
    .filter((node): node is PresenceNode => Boolean(node));
}

function nodeContent(lang: LocaleCode = DEFAULT_LOCALE): PresenceNodeContent {
  return getPresenceContent(lang) as unknown as PresenceNodeContent;
}
