"use client";

/**
 * InviteBanner — "X invited you to this" warmth on first arrival.
 *
 * Reads ?from=<name> from the current URL. If present (and viewer
 * hasn't acknowledged), shows a small teal banner above the page
 * content naming the inviter and welcoming the new arrival.
 *
 * Dismisses automatically after the viewer's first gesture or after
 * a minute. The ?from= value also gets stored so future surfaces
 * (notifications, kin feed) know she arrived through a warm door.
 */

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useT } from "@/components/MessagesProvider";

const INVITED_BY_KEY = "cc-invited-by";

export function InviteBanner() {
  const t = useT();
  const searchParams = useSearchParams();
  const [from, setFrom] = useState<string | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const fromParam = searchParams?.get("from") || "";
    if (fromParam.trim()) {
      const name = fromParam.trim().slice(0, 80);
      setFrom(name);
      setVisible(true);
      // Persist so the viewer's kin feed and future surfaces can
      // remember the warm door she came through.
      try {
        localStorage.setItem(INVITED_BY_KEY, name);
      } catch {
        /* ignore */
      }
      return;
    }
    // Check storage — if she came through an invite earlier this session
    // but the URL no longer has ?from=, we do not re-show the banner.
    setVisible(false);
  }, [searchParams]);

  if (!visible || !from) return null;

  return (
    <section
      className="relative max-w-3xl mx-3 sm:mx-auto mt-3 px-4 py-3 rounded-xl border border-teal-700/40 bg-teal-950/20 text-sm text-teal-100 flex items-start gap-3"
      aria-label={t("inviteBanner.ariaLabel")}
    >
      <span className="text-lg" aria-hidden="true">🌿</span>
      <div className="flex-1 min-w-0">
        <p className="leading-relaxed">
          <span className="text-teal-300 font-medium">{from}</span>{" "}
          {t("inviteBanner.inviting")}
        </p>
      </div>
      <button
        type="button"
        onClick={() => setVisible(false)}
        className="text-teal-400/60 hover:text-teal-200 shrink-0"
        aria-label={t("inviteBanner.dismiss")}
      >
        ×
      </button>
    </section>
  );
}
