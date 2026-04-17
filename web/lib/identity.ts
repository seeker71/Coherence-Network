/**
 * Soft-identity helpers shared across client surfaces.
 *
 * The Coherence Network uses three localStorage keys to hold a
 * visitor's presence:
 *
 *   · cc-reaction-author-name   — her human display name
 *   · cc-contributor-id         — the slug-id of her contributor
 *                                 graph node (once graduated)
 *   · cc-presence-fingerprint   — a short opaque per-device
 *                                 token so two visitors sharing a
 *                                 display name land on distinct
 *                                 contributor nodes
 *   · cc-invited-by             — the contributor_id of whoever
 *                                 invited her, if any — the root
 *                                 of her invite chain
 *
 * Every write into these keys runs through this module so the
 * surfaces stay consistent.
 */

export const NAME_KEY = "cc-reaction-author-name";
export const CONTRIBUTOR_KEY = "cc-contributor-id";
export const FINGERPRINT_KEY = "cc-presence-fingerprint";
export const INVITED_BY_KEY = "cc-invited-by";

export function ensureFingerprint(): string {
  try {
    const existing = localStorage.getItem(FINGERPRINT_KEY);
    if (existing) return existing;
    const fresh = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
    localStorage.setItem(FINGERPRINT_KEY, fresh);
    return fresh;
  } catch {
    return `anon-${Math.random().toString(36).slice(2, 10)}`;
  }
}

export function readIdentity(): {
  name: string;
  contributorId: string;
  fingerprint: string;
  invitedBy: string;
} {
  let name = "";
  let contributorId = "";
  let invitedBy = "";
  try {
    name = localStorage.getItem(NAME_KEY) || "";
    contributorId = localStorage.getItem(CONTRIBUTOR_KEY) || "";
    invitedBy = localStorage.getItem(INVITED_BY_KEY) || "";
  } catch {
    /* ignore */
  }
  const fingerprint = ensureFingerprint();
  return { name, contributorId, fingerprint, invitedBy };
}

/**
 * Ensure the caller has a real contributor_id. When they already
 * have one, returns it unchanged. When they don't, calls the
 * graduate endpoint with their name + device fingerprint and
 * persists the returned id. Idempotent — safe to call repeatedly.
 *
 * The graduate endpoint is intentionally lightweight: no email,
 * no password, no public key. A contributor by caring enough to
 * share something — the same frequency as the voice-posting
 * auto-graduation.
 */
export async function ensureContributorId(
  apiBase: string,
): Promise<string | null> {
  const { name, contributorId, fingerprint, invitedBy } = readIdentity();
  if (contributorId) return contributorId;
  if (!name.trim()) return null;
  try {
    const body: Record<string, string> = {
      author_name: name.trim(),
      device_fingerprint: fingerprint,
    };
    if (invitedBy.trim()) body.invited_by = invitedBy.trim();
    const res = await fetch(`${apiBase}/api/contributors/graduate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) return null;
    const data = await res.json();
    const id: string = data.contributor_id;
    if (id) {
      try {
        localStorage.setItem(CONTRIBUTOR_KEY, id);
      } catch {
        /* ignore */
      }
      return id;
    }
  } catch {
    /* transient */
  }
  return null;
}
