/**
 * visitor — every visitor is a provisional contributor, from their
 * first action onward.
 *
 * The organism tracks contributions by contributors. There is no
 * such thing as an anonymous contribution — the graph would lose
 * integrity. So when a visitor takes their first action (adding a
 * gathering, leaving a reaction, naming an inspiration), this helper
 * ensures a real contributor node exists for them before the action
 * is written. The node is `claimed: false`, has no display name,
 * carries the auto-generated id in localStorage.
 *
 * When they later "step in" — the header door — they're not signing
 * up. They're naming the contributor they already are: the same
 * node is patched with `claimed: true` and a display name, and
 * every past attribution they've made instantly wears the new name.
 *
 * Keys in localStorage:
 *   · cc-contributor-id    — the provisional / claimed contributor id
 *   · cc-reaction-author-name — the chosen display name once claimed
 *
 * These match the keys the rest of the app already uses so naming
 * on /vision/join flows through without special-casing.
 */

import { getApiBase } from "@/lib/api";

const CONTRIBUTOR_KEY = "cc-contributor-id";
const NAME_KEY = "cc-reaction-author-name";

function shortId(): string {
  const bytes = new Uint8Array(6);
  (crypto || window.crypto).getRandomValues(bytes);
  return Array.from(bytes).map((b) => b.toString(36).padStart(2, "0")).join("").slice(0, 10);
}

export function currentContributorId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(CONTRIBUTOR_KEY);
  } catch {
    return null;
  }
}

export function currentContributorName(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(NAME_KEY) || null;
  } catch {
    return null;
  }
}

/**
 * Ensure a provisional contributor exists for this visitor and
 * return its id. Creates the node on first call if needed; subsequent
 * calls just return the cached id.
 *
 * The node is minimal on purpose — no display name, no email, just
 * `claimed: false`. The stepIn door is what surfaces the invitation
 * to name; this helper only guarantees there's a real node to
 * attribute against.
 */
export async function ensureVisitorContributor(): Promise<string | null> {
  if (typeof window === "undefined") return null;
  const cached = currentContributorId();
  if (cached) return cached;

  const id = `contributor:wanderer-${shortId()}`;
  try {
    const res = await fetch(`${getApiBase()}/api/graph/nodes`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        id,
        type: "contributor",
        name: id.replace(/^contributor:/, ""),
        description: "",
        properties: {
          claimed: false,
          contributor_type: "HUMAN",
          provisional: true,
        },
      }),
    });
    if (!res.ok && res.status !== 409) {
      // If creation failed, don't persist the id — the next action
      // will try again rather than attribute to a non-existent node.
      return null;
    }
  } catch {
    return null;
  }
  try {
    localStorage.setItem(CONTRIBUTOR_KEY, id);
  } catch {
    /* session-only is still fine for the current flow */
  }
  return id;
}

/**
 * Fetch how many things this visitor has touched — contributions,
 * inspired-by links, gatherings added. Used by the MeButton door to
 * show "step in · N held open", turning the invitation into a
 * mirror of what the visitor has already done.
 */
export async function countVisitorFootprint(contributorId: string): Promise<number> {
  if (!contributorId) return 0;
  try {
    const res = await fetch(
      `${getApiBase()}/api/edges?from_id=${encodeURIComponent(contributorId)}&limit=50`,
      { cache: "no-store" },
    );
    if (!res.ok) return 0;
    const body: { items?: unknown[] } = await res.json();
    return Array.isArray(body.items) ? body.items.length : 0;
  } catch {
    return 0;
  }
}
