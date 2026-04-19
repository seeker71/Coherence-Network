"use client";

/**
 * MeButton — the header doorway.
 *
 * Reads `cc-contributor-id` / `cc-reaction-author-name` from localStorage
 * (same keys lib/visitor.ts writes to). Three visual states, one
 * underlying contributor node:
 *
 *   1. No contributor yet — shows "step in" as a plain invitation
 *      linking to /vision/join. First time the visitor touches the
 *      page, they have not yet done anything that minted a node.
 *
 *   2. Provisional contributor (id present, no name) — shows
 *      "step in · N held open" where N is the count of things the
 *      visitor has touched in the graph. The door becomes a mirror
 *      of what they've already contributed; naming themselves doesn't
 *      create anything, it claims what's already theirs.
 *
 *   3. Named contributor — shows the avatar+name dropdown with
 *      links to their corner.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { useT } from "@/components/MessagesProvider";
import { countVisitorFootprint } from "@/lib/visitor";

const CONTRIBUTOR_KEY = "cc-contributor-id";
const NAME_KEY = "cc-reaction-author-name";

export function MeButton() {
  const t = useT();
  const [contributorId, setContributorId] = useState<string | null>(null);
  const [authorName, setAuthorName] = useState<string>("");
  const [footprint, setFootprint] = useState<number>(0);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      setContributorId(localStorage.getItem(CONTRIBUTOR_KEY));
      setAuthorName(localStorage.getItem(NAME_KEY) || "");
    } catch {
      /* ignore */
    }
    setReady(true);
  }, []);

  // When the visitor has a provisional id but no name, show how many
  // things they've touched — the door reflects their own wandering
  // rather than performing a generic welcome.
  useEffect(() => {
    if (!contributorId || authorName.trim()) return;
    let cancelled = false;
    countVisitorFootprint(contributorId).then((n) => {
      if (!cancelled) setFootprint(n);
    });
    return () => {
      cancelled = true;
    };
  }, [contributorId, authorName]);

  if (!ready) return null;

  // No contributor yet — the bare invitation
  if (!contributorId) {
    return (
      <Link
        href="/vision/join"
        className="rounded-full border border-teal-700/40 bg-teal-950/20 hover:bg-teal-950/40 text-teal-200 px-3 py-1 text-xs font-medium transition-colors"
      >
        {t("me.stepIn")}
      </Link>
    );
  }

  // Provisional — show the mirror: step in · N held open
  if (!authorName.trim()) {
    const label =
      footprint === 0
        ? t("me.stepIn")
        : footprint === 1
        ? t("me.stepInCount1")
        : t("me.stepInCountN", { n: footprint });
    return (
      <Link
        href="/vision/join"
        className="rounded-full border border-teal-700/40 bg-teal-950/20 hover:bg-teal-950/40 text-teal-200 px-3 py-1 text-xs font-medium transition-colors"
      >
        {label}
      </Link>
    );
  }

  const display = authorName.trim() || t("me.you");
  const initial = (display[0] || "·").toUpperCase();
  const profileHref = contributorId
    ? `/profile/${encodeURIComponent(contributorId)}`
    : "/feed/you";

  return (
    <details className="relative">
      <summary
        className="list-none cursor-pointer flex items-center gap-2 rounded-full border border-border/40 bg-background/60 px-2 py-1 text-sm hover:border-border hover:bg-accent/40 transition-colors"
        aria-label={t("me.menuLabel")}
      >
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-gradient-to-br from-amber-500/30 to-teal-500/30 text-xs font-medium text-amber-200">
          {initial}
        </span>
        <span className="hidden md:inline max-w-[6rem] truncate text-foreground/90">
          {display}
        </span>
      </summary>
      <div className="absolute right-0 mt-2 w-56 rounded-xl border border-border/50 bg-popover/95 backdrop-blur-md shadow-xl z-50">
        <div className="p-3 space-y-0.5">
          <div className="px-2 py-1 text-[11px] uppercase tracking-wider text-muted-foreground/80">
            {t("me.menuHeading")}
          </div>
          <Link
            href={profileHref}
            className="block rounded-lg px-3 py-2 text-sm hover:bg-accent/60 transition-colors"
          >
            {t("me.viewProfile")}
          </Link>
          <Link
            href="/feed/you"
            className="block rounded-lg px-3 py-2 text-sm hover:bg-accent/60 transition-colors"
          >
            {t("me.myCorner")}
          </Link>
          <Link
            href="/here"
            className="block rounded-lg px-3 py-2 text-sm hover:bg-accent/60 transition-colors"
          >
            {t("me.hereNow")}
          </Link>
          {contributorId && (
            <Link
              href={`/contributors/${encodeURIComponent(contributorId)}/portfolio`}
              className="block rounded-lg px-3 py-2 text-sm hover:bg-accent/60 transition-colors"
            >
              {t("me.portfolio")}
            </Link>
          )}
          {contributorId && (
            <Link
              href={`/profile/${encodeURIComponent(contributorId)}/beliefs`}
              className="block rounded-lg px-3 py-2 text-sm hover:bg-accent/60 transition-colors"
            >
              {t("me.beliefs")}
            </Link>
          )}
          <div className="border-t border-border/30 my-2" />
          <Link
            href="/feed/you#invite"
            className="block rounded-lg px-3 py-2 text-sm text-teal-300 hover:bg-teal-950/30 transition-colors"
          >
            {t("me.inviteFriend")}
          </Link>
        </div>
      </div>
    </details>
  );
}
