"use client";

/**
 * MeButton — visible only to viewers with a stored identity.
 *
 * Reads `cc-contributor-id` / `cc-reaction-author-name` from localStorage
 * and renders a small avatar-ish affordance that opens a pop-up with
 * links to the viewer's personal surfaces: profile, corner feed,
 * notifications, contributions.
 *
 * When there is no identity, the component renders a "Sign in" pill
 * linking to /vision/join instead — so the header always carries the
 * right invitation.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { useT } from "@/components/MessagesProvider";

const CONTRIBUTOR_KEY = "cc-contributor-id";
const NAME_KEY = "cc-reaction-author-name";

export function MeButton() {
  const t = useT();
  const [contributorId, setContributorId] = useState<string | null>(null);
  const [authorName, setAuthorName] = useState<string>("");
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

  if (!ready) return null;

  // No identity yet — offer the gentle door
  if (!contributorId && !authorName.trim()) {
    return (
      <Link
        href="/vision/join"
        className="rounded-full border border-teal-700/40 bg-teal-950/20 hover:bg-teal-950/40 text-teal-200 px-3 py-1 text-xs font-medium transition-colors"
      >
        {t("me.stepIn")}
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
            {t("me.heading")}
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
        </div>
      </div>
    </details>
  );
}
