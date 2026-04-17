"use client";

/**
 * FirstTimeWelcome — what this place is, in one sentence and one tap.
 *
 * Dismissed by clicking the "X" (writes a flag to localStorage so
 * returning visitors don't see it again). Does not hide on its own —
 * a viewer who ignores it sees it again on next visit, until they
 * dismiss explicitly or click through to a concept.
 *
 * Shown above the main hero so a first-time visitor (a mother, a
 * friend, anyone arriving from a WhatsApp link) gets "what is this
 * place?" answered before they scroll.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { useT } from "@/components/MessagesProvider";

const DISMISS_KEY = "cc-welcome-dismissed";

export function FirstTimeWelcome() {
  const t = useT();
  const [visible, setVisible] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      const dismissed = localStorage.getItem(DISMISS_KEY);
      setVisible(!dismissed);
    } catch {
      setVisible(true);
    }
    setHydrated(true);
  }, []);

  if (!hydrated || !visible) return null;

  function dismiss() {
    try {
      localStorage.setItem(DISMISS_KEY, "1");
    } catch {
      /* ignore */
    }
    setVisible(false);
  }

  return (
    <section
      className="relative max-w-3xl mx-auto mt-4 mx-3 sm:mx-auto px-4 sm:px-6 py-5 rounded-2xl border border-amber-700/30 bg-gradient-to-br from-amber-950/30 via-stone-900/40 to-teal-950/20"
      aria-label={t("welcome.ariaLabel")}
    >
      <button
        type="button"
        onClick={dismiss}
        className="absolute top-2 right-2 text-stone-500 hover:text-stone-300 w-8 h-8 rounded-full flex items-center justify-center"
        aria-label={t("welcome.dismiss")}
      >
        ×
      </button>
      <p className="text-xs uppercase tracking-widest text-amber-300/90 mb-2">
        {t("welcome.eyebrow")}
      </p>
      <h2 className="text-lg md:text-xl font-light text-stone-100 leading-snug mb-2">
        {t("welcome.headline")}
      </h2>
      <p className="text-sm text-stone-300 leading-relaxed mb-4">
        {t("welcome.lede")}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <Link
          href="/meet/concept/lc-nourishing"
          className="inline-flex items-center gap-1.5 rounded-full bg-amber-700/80 hover:bg-amber-600/90 text-stone-950 px-4 py-2 text-sm font-medium transition-colors"
          onClick={dismiss}
        >
          {t("welcome.startCta")} →
        </Link>
        <Link
          href="/explore/concept"
          className="inline-flex items-center gap-1.5 rounded-full border border-border/40 hover:bg-accent/40 text-sm text-stone-300 px-4 py-2 transition-colors"
          onClick={dismiss}
        >
          {t("welcome.walkCta")}
        </Link>
      </div>
    </section>
  );
}
