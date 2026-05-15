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
 * /people/urs — the central cell, rendered from the graph.
 *
 * Content lives in the graph node `contributor:urs` as `presence_content`
 * (synced 2026-05-15 from the previously-static en.tsx). The route file
 * is the binding layer that pins the URL to this graph node and tells
 * the template to walk `contributor:seeker71`'s edges (works, lineage,
 * inspired-by) — the two-node bifurcation lives in the substrate, and
 * naming both ids here is honest about it.
 *
 * The dynamic `/people/[id]` route would also resolve /people/urs to
 * the same node, but this static route file lets us specify the edge-
 * walking node explicitly without baking a special-case into the
 * generic dispatcher.
 */

export const dynamic = "force-dynamic";

const STORY_NODE_ID = "contributor:urs";
const EDGES_NODE_ID = "contributor:seeker71";

async function fetchPresenceContent(
  lang: string,
): Promise<PresenceContent | null> {
  const base = getApiBase();
  const node = await fetchJsonOrNull<Record<string, unknown>>(
    `${base}/api/graph/nodes/${encodeURIComponent(STORY_NODE_ID)}`,
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
      graphSlug={EDGES_NODE_ID}
    />
  );
}
