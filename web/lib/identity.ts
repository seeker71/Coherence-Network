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
export const EMAIL_KEY = "cc-email";

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
  email: string;
} {
  let name = "";
  let contributorId = "";
  let invitedBy = "";
  let email = "";
  try {
    name = localStorage.getItem(NAME_KEY) || "";
    contributorId = localStorage.getItem(CONTRIBUTOR_KEY) || "";
    invitedBy = localStorage.getItem(INVITED_BY_KEY) || "";
    email = localStorage.getItem(EMAIL_KEY) || "";
    // Bridge to the legacy crypto-flow namespace: if cc-contributor-id
    // is empty but the crypto /join flow wrote coherence_contributor_id,
    // adopt it so MeButton + MePage recognize the visitor. One-way
    // copy — we prefer the cc-* namespace going forward.
    if (!contributorId) {
      const legacy = localStorage.getItem("coherence_contributor_id") || "";
      if (legacy) {
        contributorId = legacy;
        try {
          localStorage.setItem(CONTRIBUTOR_KEY, legacy);
        } catch {
          /* ignore */
        }
      }
    }
  } catch {
    /* ignore */
  }
  const fingerprint = ensureFingerprint();
  return { name, contributorId, fingerprint, invitedBy, email };
}

/**
 * Ensure the caller has a real contributor_id. When they already
 * have one, returns it unchanged. When they don't, calls the
 * graduate endpoint with their known identity claims and persists
 * the returned id. Idempotent — safe to call repeatedly.
 *
 * Multi-provider: when an email is available in localStorage the
 * graduate call is email-keyed, so the same visitor on their phone
 * and laptop resolves to one contributor. When only a name +
 * fingerprint is available (quick reactions before a sign-in), the
 * call falls back to the legacy per-device soft path.
 */
export async function ensureContributorId(
  apiBase: string,
): Promise<string | null> {
  const { name, contributorId, fingerprint, invitedBy, email } = readIdentity();
  if (contributorId) return contributorId;
  if (!name.trim()) return null;
  try {
    const body: Record<string, string> = {
      author_name: name.trim(),
      device_fingerprint: fingerprint,
    };
    if (email.trim()) body.email = email.trim();
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
        if (data.email) localStorage.setItem(EMAIL_KEY, data.email);
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


export type IdentityClaim = {
  email?: string;
  public_key?: string;
  wallet_address?: string;
};


export type ClaimedProfile = {
  contributor_id: string;
  author_display_name: string | null;
  locale: string | null;
  resonant_roles: string[];
  invited_by: string | null;
  email: string | null;
  public_key: string | null;
  wallet_address: string | null;
  matched_provider: string;
};


/**
 * Cross-device recovery. Opens the app on a new phone/laptop with
 * nothing in localStorage — the visitor asserts an identity claim
 * (most commonly the email they registered with) and we look up
 * their contributor node on the backend. On success we rehydrate
 * every cc-* key from the server state so MeButton and MePage
 * recognize them instantly.
 *
 * Returns null with no writes when the identity doesn't match any
 * contributor — the caller can then route to /vision/join to
 * register fresh.
 */
export async function claimByIdentity(
  apiBase: string,
  claim: IdentityClaim,
): Promise<ClaimedProfile | null> {
  // Skip the call when the caller sent nothing — the backend would
  // 400 but we can save the round-trip.
  if (!claim.email?.trim() && !claim.public_key?.trim() && !claim.wallet_address?.trim()) {
    return null;
  }
  try {
    const res = await fetch(`${apiBase}/api/contributors/claim-by-identity`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(claim),
    });
    if (!res.ok) return null;
    const data: ClaimedProfile = await res.json();
    if (!data.contributor_id) return null;
    // Rehydrate every cc-* key from the authoritative backend state.
    // The visitor's footprint (voices, reactions, proposals) is keyed
    // by contributor_id server-side, so these writes restore their
    // full presence without the old fingerprint ever mattering.
    try {
      localStorage.setItem(CONTRIBUTOR_KEY, data.contributor_id);
      if (data.author_display_name) {
        localStorage.setItem(NAME_KEY, data.author_display_name);
      }
      if (data.email) localStorage.setItem(EMAIL_KEY, data.email);
      if (data.invited_by) localStorage.setItem(INVITED_BY_KEY, data.invited_by);
      // Signal other mounted components (the MeButton header door)
      // that identity just arrived, so they re-read without a manual
      // reload. StorageEvent ctor is wrapped — Safari is picky.
      try {
        window.dispatchEvent(new StorageEvent("storage", { key: CONTRIBUTOR_KEY }));
      } catch {
        /* non-fatal */
      }
    } catch {
      /* localStorage unavailable — claim still stands in memory */
    }
    return data;
  } catch {
    return null;
  }
}


/**
 * Forget everything about this visitor on this device. Backend
 * state is untouched — the contributor node, edges, voices, and
 * reactions stay where they are in the graph, so signing back in
 * on another device (or this one, with claimByIdentity) restores
 * the full presence.
 */
export function clearLocalIdentity(): void {
  try {
    localStorage.removeItem(NAME_KEY);
    localStorage.removeItem(CONTRIBUTOR_KEY);
    localStorage.removeItem(FINGERPRINT_KEY);
    localStorage.removeItem(INVITED_BY_KEY);
    localStorage.removeItem(EMAIL_KEY);
    // Belt + suspenders — any cc-* accretion (chat drafts, dismissed
    // nudges, presence caches) washes out too.
    const toRemove: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && k.startsWith("cc-")) toRemove.push(k);
    }
    toRemove.forEach((k) => localStorage.removeItem(k));
    // Also clear the legacy crypto-flow namespace so a stale
    // coherence_contributor_id doesn't leak back in on next read.
    localStorage.removeItem("coherence_contributor_id");
    localStorage.removeItem("coherence_public_key");
    localStorage.removeItem("coherence_fingerprint");
  } catch {
    /* ignore */
  }
}
