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
 *   3. Named contributor — avatar+name button that links straight
 *      to /me, the single You hub. From there the visitor reaches
 *      their feed, public profile, portfolio, and lineage surfaces.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { useT } from "@/components/MessagesProvider";
import { countVisitorFootprint } from "@/lib/visitor";
import { readIdentity } from "@/lib/identity";

export function MeButton() {
  const t = useT();
  const [contributorId, setContributorId] = useState<string | null>(null);
  const [authorName, setAuthorName] = useState<string>("");
  const [footprint, setFootprint] = useState<number>(0);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    // readIdentity bridges the legacy coherence_contributor_id key
    // into the cc-* namespace, so a visitor who joined via the
    // crypto /join flow is recognized here without re-submitting.
    try {
      const { contributorId: cid, name } = readIdentity();
      setContributorId(cid || null);
      setAuthorName(name);
    } catch {
      /* ignore */
    }
    setReady(true);

    // React to identity changes from other components (the join
    // form, the 'sign in on this device' card) so the door
    // re-renders without a manual reload.
    function onStorage(e: StorageEvent) {
      if (!e.key || e.key.startsWith("cc-") || e.key === "coherence_contributor_id") {
        try {
          const { contributorId: cid, name } = readIdentity();
          setContributorId(cid || null);
          setAuthorName(name);
        } catch {
          /* ignore */
        }
      }
    }
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
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

  // Tapping the avatar goes straight to /me — the single You hub.
  // From there the visitor finds their feed, their public profile,
  // their lineage, their portfolio. One door, not five.
  return (
    <Link
      href="/me"
      aria-label={t("me.menuLabel")}
      className="flex items-center gap-2 rounded-full border border-border/40 bg-background/60 px-2 py-1 text-sm hover:border-border hover:bg-accent/40 transition-colors"
    >
      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-gradient-to-br from-amber-500/30 to-teal-500/30 text-xs font-medium text-amber-200">
        {initial}
      </span>
      <span className="hidden md:inline max-w-[6rem] truncate text-foreground/90">
        {display}
      </span>
    </Link>
  );
}
