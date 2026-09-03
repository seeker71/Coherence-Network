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
  "skill",
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

  return null;
}
