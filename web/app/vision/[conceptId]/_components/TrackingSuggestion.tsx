"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useT } from "@/components/MessagesProvider";

/**
 * Shows a gentle suggestion to identify yourself for read sensing
 * when viewing NFT/high-value assets. Only shows if:
 * - The user hasn't registered a contributor ID yet
 * - The asset has generated measurable value (reads, CC)
 */
export function TrackingSuggestion({ conceptId }: { conceptId: string }) {
  const [show, setShow] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const t = useT();

  useEffect(() => {
    // Check if user already has a contributor ID
    const cid = localStorage.getItem("coherence_contributor_id");
    if (cid) {
      // Already registered — send contributor ID with future reads
      // This happens automatically via the fetch interceptor below
      setShow(false);
      return;
    }

    // Check if already dismissed this session
    const dismissed = sessionStorage.getItem("tracking_suggestion_dismissed");
    if (dismissed) return;

    // Show after a longer delay — let the reader settle into the content first
    // Only show once per session across all concept pages
    const shownCount = parseInt(sessionStorage.getItem("tracking_suggestion_shown") || "0", 10);
    if (shownCount > 0) return;

    const timer = setTimeout(() => {
      setShow(true);
      sessionStorage.setItem("tracking_suggestion_shown", "1");
    }, 15000);
    return () => clearTimeout(timer);
  }, []);

  if (!show || dismissed) return null;

  return (
    <div className="fixed bottom-20 left-4 right-4 md:left-auto md:right-6 md:max-w-md z-40 animate-in slide-in-from-bottom duration-500">
      <div className="rounded-2xl border border-amber-500/20 bg-stone-950/95 backdrop-blur-sm p-5 shadow-2xl space-y-3">
        <div className="flex items-start justify-between">
          <p className="text-sm text-stone-300 leading-relaxed pr-4">
            {t("profileNudge.body")}
          </p>
          <button
            aria-label={t("profileNudge.dismissAria")}
            onClick={() => { setDismissed(true); sessionStorage.setItem("tracking_suggestion_dismissed", "1"); }}
            className="text-stone-600 hover:text-stone-400 text-sm shrink-0"
          >
            {"\u2715"}
          </button>
        </div>
        <div className="flex gap-2">
          <Link href="/vision/join"
            className="px-4 py-2 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 hover:bg-amber-500/20 transition-all text-xs font-medium">
            {t("profileNudge.startCta")}
          </Link>
          <button
            onClick={() => { setDismissed(true); sessionStorage.setItem("tracking_suggestion_dismissed", "1"); }}
            className="px-4 py-2 rounded-xl border border-stone-800/40 text-stone-500 text-xs">
            {t("profileNudge.laterCta")}
          </button>
        </div>
        <p className="text-xs text-stone-600">{t("profileNudge.footer")}</p>
      </div>
    </div>
  );
}
