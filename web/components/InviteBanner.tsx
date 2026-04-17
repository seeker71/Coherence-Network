"use client";

/**
 * InviteBanner — "X invited you" warmth on first arrival.
 *
 * Reads ?from=<inviter>&name=<recipient>&invited_by=<id> from the URL.
 *
 * First-time arrival (no identity stored yet):
 *   • Writes `name` into `cc-reaction-author-name` so she is now
 *     "pre-registered" — able to react, voice, comment without
 *     seeing a registration screen.
 *   • Writes `invited_by` into `cc-invited-by` for the kin graph.
 *   • Records first-seen timestamp in `cc-last-visit-at` so the
 *     next visit's SinceLastVisit counts from now.
 *   • Shows a personalized banner: "Welcome, <name> — <inviter>
 *     invited you to meet this."
 *
 * Returning arrival (identity already stored):
 *   • Does not overwrite stored name — the device's identity wins.
 *   • Shows a "Welcome back" variant if the URL still carries the
 *     invite params (she followed the original link again).
 *   • Still records the invite-by attribution if not yet set.
 *
 * Dismiss: a small × hides for this session. Auto-hides when the
 * search params are cleared (e.g. after navigation without ?from).
 */

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useT } from "@/components/MessagesProvider";

const NAME_KEY = "cc-reaction-author-name";
const CONTRIBUTOR_KEY = "cc-contributor-id";
const INVITED_BY_KEY = "cc-invited-by";
const LAST_VISIT_KEY = "cc-last-visit-at";
const DISMISS_KEY = "cc-invite-banner-dismissed";

type Mode = "welcome" | "welcomeBack" | null;

export function InviteBanner() {
  const t = useT();
  const searchParams = useSearchParams();
  const [from, setFrom] = useState<string | null>(null);
  const [recipientName, setRecipientName] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const fromParam = (searchParams?.get("from") || "").trim().slice(0, 80);
    const nameParam = (searchParams?.get("name") || "").trim().slice(0, 80);
    const invitedByParam = (searchParams?.get("invited_by") || "").trim().slice(0, 200);

    // No invite params — nothing to do.
    if (!fromParam && !nameParam) {
      setVisible(false);
      return;
    }

    let storedName = "";
    let storedContributorId = "";
    let dismissed = "";
    try {
      storedName = localStorage.getItem(NAME_KEY) || "";
      storedContributorId = localStorage.getItem(CONTRIBUTOR_KEY) || "";
      dismissed = sessionStorage.getItem(DISMISS_KEY) || "";
    } catch {
      /* ignore */
    }

    const hasIdentity = Boolean(storedName.trim() || storedContributorId.trim());

    // First-time arrival: pre-register with the name the inviter chose.
    if (!hasIdentity && nameParam) {
      try {
        localStorage.setItem(NAME_KEY, nameParam);
        // Seed the return-visit memory so "since last visit" counts
        // forward from this first touch.
        if (!localStorage.getItem(LAST_VISIT_KEY)) {
          localStorage.setItem(LAST_VISIT_KEY, new Date().toISOString());
        }
      } catch {
        /* ignore */
      }
      setRecipientName(nameParam);
      setMode("welcome");
    } else if (hasIdentity) {
      // Returning — honor the stored name. If URL also carries a
      // name, prefer the stored one for the greeting (device wins).
      const display = storedName.trim() || nameParam;
      setRecipientName(display || null);
      setMode("welcomeBack");
    } else {
      // No stored identity and no recipient name — just the generic
      // "X invited you" banner (backwards-compatible with Cycle H).
      setMode("welcome");
    }

    if (invitedByParam) {
      try {
        // Always record who sent the door — even for returning
        // visitors — if not yet set.
        if (!localStorage.getItem(INVITED_BY_KEY)) {
          localStorage.setItem(INVITED_BY_KEY, invitedByParam);
        }
      } catch {
        /* ignore */
      }
    } else if (fromParam) {
      // Fallback attribution by inviter display name.
      try {
        if (!localStorage.getItem(INVITED_BY_KEY)) {
          localStorage.setItem(INVITED_BY_KEY, fromParam);
        }
      } catch {
        /* ignore */
      }
    }

    setFrom(fromParam || null);
    setVisible(!dismissed);
  }, [searchParams]);

  function dismiss() {
    try {
      sessionStorage.setItem(DISMISS_KEY, "1");
    } catch {
      /* ignore */
    }
    setVisible(false);
  }

  if (!visible || !mode) return null;
  if (!from && !recipientName) return null;

  // Compose the greeting from whatever pieces we have.
  const greeting = (() => {
    if (mode === "welcomeBack" && recipientName) {
      // "Welcome back, <name>."
      return t("inviteBanner.welcomeBackNamed").replace("{name}", recipientName);
    }
    if (recipientName && from) {
      // "Welcome, <name> — <inviter> invited you."
      return t("inviteBanner.welcomeNamedFrom")
        .replace("{name}", recipientName)
        .replace("{from}", from);
    }
    if (recipientName) {
      return t("inviteBanner.welcomeNamed").replace("{name}", recipientName);
    }
    if (from) {
      return `${from} ${t("inviteBanner.inviting")}`;
    }
    return t("inviteBanner.inviting");
  })();

  return (
    <section
      className="relative max-w-3xl mx-3 sm:mx-auto mt-3 px-4 py-3 rounded-xl border border-teal-700/40 bg-teal-950/20 text-sm text-teal-100 flex items-start gap-3"
      aria-label={t("inviteBanner.ariaLabel")}
    >
      <span className="text-lg" aria-hidden="true">🌿</span>
      <div className="flex-1 min-w-0">
        <p className="leading-relaxed">
          {mode === "welcomeBack" && recipientName ? (
            <>
              <span className="text-teal-300 font-medium">{recipientName}</span>
              {greeting.slice(recipientName.length)}
            </>
          ) : recipientName && from ? (
            // Highlight both names
            <>
              {t("inviteBanner.welcomeLead")}{" "}
              <span className="text-teal-300 font-medium">{recipientName}</span>
              {" — "}
              <span className="text-teal-300 font-medium">{from}</span>{" "}
              {t("inviteBanner.invitedYou")}
            </>
          ) : from ? (
            <>
              <span className="text-teal-300 font-medium">{from}</span>{" "}
              {t("inviteBanner.inviting")}
            </>
          ) : (
            greeting
          )}
        </p>
      </div>
      <button
        type="button"
        onClick={dismiss}
        className="text-teal-400/60 hover:text-teal-200 shrink-0"
        aria-label={t("inviteBanner.dismiss")}
      >
        ×
      </button>
    </section>
  );
}
