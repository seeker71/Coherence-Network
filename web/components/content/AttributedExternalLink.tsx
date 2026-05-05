"use client";

import Link from "next/link";
import {
  forwardRef,
  type AnchorHTMLAttributes,
  type ReactNode,
} from "react";

import { getApiBase } from "@/lib/api";
import { markRecentAttributionPing } from "@/lib/attribution-ping-dedupe";
import {
  attributionTargetFromHref,
  type AttributionTarget,
} from "@/lib/attribution-target";

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

function currentSourcePage(sourcePage?: string): string {
  if (sourcePage) return sourcePage;
  if (typeof window === "undefined") return "/";
  return `${window.location.pathname}${window.location.search || ""}`;
}

function pingAttribution(target: AttributionTarget, sourcePage?: string) {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const contributorId = getContributorId();
  const sessionFingerprint = getOrCreateSessionFingerprint();
  if (contributorId) headers["X-Contributor-Id"] = contributorId;
  if (sessionFingerprint) headers["X-Session-Fingerprint"] = sessionFingerprint;

  fetch(`${getApiBase()}/api/views/ping`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      asset_id: target.assetId,
      concept_id: target.conceptId || null,
      entity_type: target.entityType,
      entity_id: target.entityId,
      source_page: currentSourcePage(sourcePage),
    }),
    keepalive: true,
  }).catch(() => {
    /* navigation should never depend on attribution sensing */
  });
}

type AttributedExternalLinkProps = Omit<
  AnchorHTMLAttributes<HTMLAnchorElement>,
  "href" | "children"
> & {
  href: string;
  entityId: string;
  sourcePage?: string;
  children: ReactNode;
};

export const AttributedExternalLink = forwardRef<HTMLAnchorElement, AttributedExternalLinkProps>(function AttributedExternalLink({
  href,
  entityId,
  sourcePage,
  children,
  onClick,
  ...props
}, ref) {
  return (
    <a
      {...props}
      href={href}
      ref={ref}
      onClick={(event) => {
        onClick?.(event);
        if (event.defaultPrevented) return;
        pingAttribution({
          entityType: "asset",
          entityId,
          assetId: entityId,
        }, sourcePage);
      }}
    >
      {children}
    </a>
  );
});

type AttributedInternalLinkProps = Omit<
  AnchorHTMLAttributes<HTMLAnchorElement>,
  "href" | "children"
> & {
  href: string;
  sourcePage?: string;
  entityType?: string;
  entityId?: string;
  assetId?: string;
  children: ReactNode;
};

export const AttributedInternalLink = forwardRef<HTMLAnchorElement, AttributedInternalLinkProps>(function AttributedInternalLink({
  href,
  sourcePage,
  entityType,
  entityId,
  assetId,
  children,
  onClick,
  ...props
}, ref) {
  const inferred = attributionTargetFromHref(href);
  const explicit = entityType && entityId
    ? {
        entityType,
        entityId,
        assetId: assetId || (entityType === "page" ? `page:${entityId}` : entityId),
        conceptId: entityType === "concept" ? entityId : null,
      }
    : null;
  const target = explicit || inferred;

  return (
    <Link
      {...props}
      href={href}
      ref={ref}
      onClick={(event) => {
        onClick?.(event);
        if (event.defaultPrevented) return;
        if (target) {
          pingAttribution(target, sourcePage);
          markRecentAttributionPing(target.assetId);
        }
      }}
    >
      {children}
    </Link>
  );
});
