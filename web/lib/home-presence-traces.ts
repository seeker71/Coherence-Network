import { getPresenceContent, type HomePresenceTrace } from "@/app/presence-walk/data";
import {
  getPresenceBranding,
  getPresenceNode,
  getPresenceSourceVisual,
  type PresenceNode,
  type PresenceSourceVisual,
} from "@/app/presence-walk/nodes";
import { DEFAULT_LOCALE, type LocaleCode } from "@/lib/locales";

export type HomePresenceTraceCard = PresenceNode &
  HomePresenceTrace & {
    href: string;
    entityId: string;
    image: string;
  };

export function getHomePresenceTraceCards(
  lang: LocaleCode = DEFAULT_LOCALE,
): HomePresenceTraceCard[] {
  const homePresence = getPresenceContent(lang).homePresence;
  if (!homePresence) return [];

  const cards: HomePresenceTraceCard[] = [];

  for (const slug of homePresence.order) {
    const node = getPresenceNode(slug, lang);
    const trace = homePresence.traces[slug];
    if (!node || !trace) continue;

    const branding = getPresenceBranding(slug, lang);
    const sourceVisual = getPresenceSourceVisual(slug, lang);
    const image = trace.image ?? getSourceVisualImage(sourceVisual) ?? branding.image ?? node.image;

    cards.push({
      ...node,
      ...trace,
      image,
      imagePosition: trace.imagePosition ?? branding.imagePosition,
      href: `/people/${node.slug}`,
      entityId: `presence:${node.slug}`,
    });
  }

  return cards;
}

function getSourceVisualImage(sourceVisual: PresenceSourceVisual | undefined): string | undefined {
  if (!sourceVisual) return undefined;
  if (sourceVisual.template === "patterned-release-page") return sourceVisual.backgroundImage;
  return sourceVisual.image;
}
