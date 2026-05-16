import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { getApiBase } from "@/lib/api";
import { fetchJsonOrNull } from "@/lib/fetch";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import {
  pickLocaleContent,
  toPersonProfileContent,
  type PresenceContent,
  type PresenceContentByLocale,
} from "@/lib/presence-content";

/**
 * /people/urs — the central cell, rendered from one canonical graph node.
 *
 * `contributor:seeker71` is the canonical node: it carries every
 * `contributes-to` / `inspired-by` / `resonates-with` edge (315 in
 * total), its slug is `urs-muff` (the canonical handle), and its
 * `aliases` list names `urs` / `urs-muff` / `seeker71` / `ursmuff` —
 * every handle this cell answers to, all alive. After today's
 * reconcile, this is THE node for the urs cell; `contributor:urs`
 * remains a placeholder for a handful of code references that still
 * name it directly, waiting for retuning in a separate breath.
 *
 * Both content and edges now load from the same node. One source of
 * truth — the URL is just the public doorway.
 */

export const dynamic = "force-dynamic";

const CANONICAL_NODE_ID = "contributor:seeker71";

async function fetchPresenceContent(
  lang: string,
): Promise<PresenceContent | null> {
  const base = getApiBase();
  const node = await fetchJsonOrNull<Record<string, unknown>>(
    `${base}/api/graph/nodes/${encodeURIComponent(CANONICAL_NODE_ID)}`,
    {},
    5000,
  );
  const raw = node && (node as Record<string, unknown>).presence_content;
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as Record<string, unknown>;
  const looksLikeEnvelope =
    typeof obj.en === "object" ||
    typeof obj.de === "object" ||
    typeof obj.es === "object" ||
    typeof obj.id === "object";
  if (looksLikeEnvelope) {
    return pickLocaleContent(obj as PresenceContentByLocale, lang);
  }
  if (typeof obj.hero === "object" && obj.hero) {
    return obj as unknown as PresenceContent;
  }
  return null;
}

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  const presence = await fetchPresenceContent(lang);
  if (!presence) {
    return {
      title: "Urs Muff — Founder | Coherence Network",
      description:
        "Founder and primary shepherd of Coherence Network.",
    };
  }
  return presence.metadata ?? {};
}

export default async function UrsProfilePage() {
  const lang = await resolveRequestLocale();
  const presence = await fetchPresenceContent(lang);
  if (!presence) {
    // The graph node should always carry presence_content; if it
    // doesn't, something's wrong upstream. notFound() is honest:
    // we have nothing to render rather than a sparse fallback.
    notFound();
  }
  return (
    <PersonProfileTemplate
      content={toPersonProfileContent(presence)}
      lang={lang}
      graphSlug={CANONICAL_NODE_ID}
    />
  );
}
