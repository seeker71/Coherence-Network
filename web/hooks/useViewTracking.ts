"use client";

import { useEffect } from "react";
import { usePathname, useSearchParams } from "next/navigation";

import { getApiBase } from "@/lib/api";

const SESSION_KEY = "coherence_session_fingerprint";
const CONTRIBUTOR_KEY = "coherence_contributor_id";

function getOrCreateSessionFingerprint(): string {
  if (typeof window === "undefined") return "";
  let fingerprint = sessionStorage.getItem(SESSION_KEY);
  if (!fingerprint) {
    fingerprint = crypto.randomUUID();
    sessionStorage.setItem(SESSION_KEY, fingerprint);
  }
  return fingerprint;
}

function getContributorId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(CONTRIBUTOR_KEY);
}

/**
 * Tracks page views by attaching identifying headers to subsequent
 * fetch requests and firing an explicit view event to the runtime
 * events endpoint.
 *
 * Headers set on each page load:
 *   X-Contributor-Id       — from localStorage
 *   X-Session-Fingerprint  — generated once per session
 *   X-Page-Route           — current pathname
 *   X-Referrer-Contributor-Id — from ?ref= query param
 */
export function useViewTracking() {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  useEffect(() => {
    if (typeof window === "undefined") return;

    const contributorId = getContributorId();
    const sessionFingerprint = getOrCreateSessionFingerprint();
    const referrerId = searchParams?.get("ref") ?? null;

    const payload: Record<string, string> = {
      event: "page_view",
      route: pathname ?? "/",
      session_fingerprint: sessionFingerprint,
      timestamp: new Date().toISOString(),
    };

    if (contributorId) payload.contributor_id = contributorId;
    if (referrerId) payload.referrer_contributor_id = referrerId;

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (contributorId) headers["X-Contributor-Id"] = contributorId;
    headers["X-Session-Fingerprint"] = sessionFingerprint;
    headers["X-Page-Route"] = pathname ?? "/";
    if (referrerId) headers["X-Referrer-Contributor-Id"] = referrerId;

    // Fire explicit view event (best-effort, failures are silent)
    fetch(`${getApiBase()}/api/runtime/events`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      keepalive: true,
    }).catch(() => {
      // View tracking is observational; failures are acceptable
    });
  }, [pathname, searchParams]);
}
