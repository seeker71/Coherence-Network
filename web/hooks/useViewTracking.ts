"use client";

/**
 * useViewTracking — the ping that lets the body feel who is reading.
 *
 * Fires from the browser on mount with the viewer's contributor id (when
 * graduated) plus a per-session fingerprint. The server records an
 * AssetViewEvent so /me can reflect the reader's own trail back to them,
 * and trending/discovery chains become attributable.
 *
 * We read `cc-contributor-id` (the current namespace) and fall back to
 * the legacy `coherence_contributor_id` key — matching the bridge in
 * lib/identity.ts.
 */

import { useEffect } from "react";

import { getApiBase } from "@/lib/api";

const CURRENT_CONTRIBUTOR_KEY = "cc-contributor-id";
const LEGACY_CONTRIBUTOR_KEY = "coherence_contributor_id";
const SESSION_KEY = "cc-presence-session";

function getOrCreateSessionFingerprint(): string {
  if (typeof window === "undefined") return "";
  try {
    let fingerprint = sessionStorage.getItem(SESSION_KEY);
    if (!fingerprint) {
      fingerprint =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `sess-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
      sessionStorage.setItem(SESSION_KEY, fingerprint);
    }
    return fingerprint;
  } catch {
    return "";
  }
}

function getContributorId(): string {
  if (typeof window === "undefined") return "";
  try {
    return (
      localStorage.getItem(CURRENT_CONTRIBUTOR_KEY) ||
      localStorage.getItem(LEGACY_CONTRIBUTOR_KEY) ||
      ""
    );
  } catch {
    return "";
  }
}

function getReferrerContributorId(): string {
  if (typeof window === "undefined") return "";
  try {
    const params = new URLSearchParams(window.location.search);
    return params.get("ref") || "";
  } catch {
    return "";
  }
}

interface ReadPingOptions {
  /** Concept id the reader is meeting (e.g. lc-sensing). Also used as asset_id. */
  conceptId: string;
  /** The page route the ping is happening on — e.g. /vision/lc-sensing. */
  sourcePage?: string;
}

/**
 * Fires a single read-ping for the given concept when the component
 * mounts. Safe to call on every render; the effect only runs once per
 * (conceptId, sourcePage) pair.
 */
export function useReadPing({ conceptId, sourcePage }: ReadPingOptions) {
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!conceptId) return;

    const contributorId = getContributorId();
    const sessionFingerprint = getOrCreateSessionFingerprint();
    const referrerId = getReferrerContributorId();

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (contributorId) headers["X-Contributor-Id"] = contributorId;
    if (sessionFingerprint) headers["X-Session-Fingerprint"] = sessionFingerprint;
    if (referrerId) headers["X-Referrer-Contributor-Id"] = referrerId;

    const body = {
      asset_id: conceptId,
      concept_id: conceptId.startsWith("lc-") ? conceptId : null,
      source_page: sourcePage ?? window.location.pathname,
    };

    fetch(`${getApiBase()}/api/views/ping`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      keepalive: true,
    }).catch(() => {
      /* read sensing is observational — failures are acceptable */
    });
  }, [conceptId, sourcePage]);
}
