/** Shared canonical-id, slug, and alias resolution for presence routes. */

import { getApiBase } from "@/lib/api";
import { fetchJsonOrNull } from "@/lib/fetch";

export type PresenceNodeRecord = Record<string, unknown>;

export type PresenceNodeFetcher = (
  path: string,
) => Promise<PresenceNodeRecord | null>;

export const PRESENCE_NODE_TYPES = [
  "contributor",
  "interested-person",
  "event",
  "scene",
  "place",
  "community",
  "network-org",
  "practice",
  "asset",
] as const;

async function fetchPresencePath(
  path: string,
): Promise<PresenceNodeRecord | null> {
  return fetchJsonOrNull<PresenceNodeRecord>(
    `${getApiBase()}${path}`,
    {},
    5000,
  );
}

/**
 * Resolve every public identity shape to its canonical graph node.
 *
 * Presence URLs may carry a stable graph id, a bare contributor id, a human
 * slug, or one of the node's aliases. Display and refinement routes share this
 * resolver so an identity that can be read can always be refined as well.
 */
export async function resolvePresenceGraphNode(
  id: string,
  fetcher: PresenceNodeFetcher = fetchPresencePath,
): Promise<PresenceNodeRecord | null> {
  const direct = await fetcher(`/api/graph/nodes/${encodeURIComponent(id)}`);
  if (direct) return direct;

  if (!id.includes(":")) {
    const prefixed = await fetcher(
      `/api/graph/nodes/${encodeURIComponent(`contributor:${id}`)}`,
    );
    if (prefixed) return prefixed;
  }

  const bareId = id.startsWith("contributor:")
    ? id.slice("contributor:".length)
    : id;
  const lists = await Promise.all(
    PRESENCE_NODE_TYPES.map((type) =>
      fetcher(`/api/graph/nodes?type=${encodeURIComponent(type)}&limit=500`),
    ),
  );
  const humanSlug = Boolean(bareId) && !/^[0-9a-f]{12,}$/.test(bareId);

  for (const list of lists) {
    const items = Array.isArray(list?.items) ? list.items : [];
    for (const candidate of items) {
      if (!candidate || typeof candidate !== "object") continue;
      const node = candidate as PresenceNodeRecord;
      if (humanSlug && node.slug === bareId) return node;
      const aliases = Array.isArray(node.aliases) ? node.aliases : [];
      if (
        aliases.some(
          (alias) => typeof alias === "string" && alias === bareId,
        )
      ) {
        return node;
      }
    }
  }

  return null;
}
