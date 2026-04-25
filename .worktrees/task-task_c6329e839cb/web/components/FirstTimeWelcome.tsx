"use client";

/**
 * FirstTimeWelcome — what this place is, in one sentence and one tap.
 *
 * Dismissed by clicking the "X" (writes a flag to localStorage so
 * returning visitors don't see it again). Also quietly steps aside
 * for any viewer who already has a stored identity (name) and a
 * last-visit timestamp — she is not new, and the marketplace on
 * her morning home stays quiet for the morning nudge to speak.
 *
 * Shown above the main hero so a truly first-time visitor (a
 * mother, a friend, anyone arriving from a WhatsApp link) gets
 * "what is this place?" answered before they scroll.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { useT } from "@/components/MessagesProvider";
import { Panel } from "@/components/Panel";

const DISMISS_KEY = "cc-welcome-dismissed";
const NAME_KEY = "cc-reaction-author-name";
const CONTRIBUTOR_KEY = "cc-contributor-id";
const LAST_VISIT_KEY = "cc-last-visit-at";

export function FirstTimeWelcome() {
  const t = useT();
  const [visible, setVisible] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      // Gate 1: dismissed previously — stay hidden
      if (localStorage.getItem(DISMISS_KEY)) {
        setVisible(false);
      } else if (
        // Gate 2: has a stored identity AND has been here before — this
        // is a returning visitor, not a new one. The MorningNudge /
        // InviteBanner / personal-corner surfaces are the right welcome
        // for her, not this generic "new here?" card.
        (localStorage.getItem(NAME_KEY) || localStorage.getItem(CONTRIBUTOR_KEY)) &&
        localStorage.getItem(LAST_VISIT_KEY)
      ) {
        setVisible(false);
      } else {
        setVisible(true);
      }
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
    <Panel
      variant="warm"
      ariaLabel={t("welcome.ariaLabel")}
      eyebrow={t("welcome.eyebrow")}
      heading={t("welcome.headline")}
      onDismiss={dismiss}
      dismissLabel={t("welcome.dismiss")}
      className="mt-4"
      cta={
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href="/meet/concept/lc-nourishing"
            className="inline-flex items-center gap-1.5 rounded-full bg-amber-600/90 hover:bg-amber-500/90 text-stone-950 px-4 py-2 text-sm font-medium transition-colors"
            onClick={dismiss}
          >
            {t("welcome.startCta")} →
          </Link>
          <Link
            href="/vision"
            className="inline-flex items-center gap-1.5 rounded-full border border-stone-700/60 hover:bg-stone-800/40 text-sm text-stone-300 px-4 py-2 transition-colors"
            onClick={dismiss}
          >
            {t("welcome.walkCta")}
          </Link>
        </div>
      }
    >
      <p>{t("welcome.lede")}</p>
    </Panel>
  );
}
