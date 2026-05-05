"use client";

import type { AnchorHTMLAttributes, ReactNode } from "react";

import { getApiBase } from "@/lib/api";

const CURRENT_CONTRIBUTOR_KEY = "cc-contributor-id";
const LEGACY_CONTRIBUTOR_KEY = "coherence_contributor_id";
const SESSION_KEY = "cc-presence-session";

function getContributorId(): string {
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

function getOrCreateSessionFingerprint(): string {
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

function pingExternalAsset(entityId: string, sourcePage: string) {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const contributorId = getContributorId();
  const sessionFingerprint = getOrCreateSessionFingerprint();
  if (contributorId) headers["X-Contributor-Id"] = contributorId;
  if (sessionFingerprint) headers["X-Session-Fingerprint"] = sessionFingerprint;

  fetch(`${getApiBase()}/api/views/ping`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      asset_id: entityId,
      entity_type: "asset",
      entity_id: entityId,
      source_page: sourcePage,
    }),
    keepalive: true,
  }).catch(() => {
    /* external navigation should never depend on attribution sensing */
  });
}

type AttributedExternalLinkProps = Omit<
  AnchorHTMLAttributes<HTMLAnchorElement>,
  "href" | "children" | "onClick"
> & {
  href: string;
  entityId: string;
  sourcePage?: string;
  children: ReactNode;
};

export function AttributedExternalLink({
  href,
  entityId,
  sourcePage = "/",
  children,
  ...props
}: AttributedExternalLinkProps) {
  return (
    <a
      {...props}
      href={href}
      onClick={() => pingExternalAsset(entityId, sourcePage)}
    >
      {children}
    </a>
  );
}
