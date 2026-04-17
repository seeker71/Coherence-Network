"use client";

/**
 * InviteFriend — a small "bring someone in" block.
 *
 * The inviter types the recipient's name (first name is enough), and
 * optionally the concept / idea they want to share. The generated link
 * carries both the inviter's name and the recipient's name:
 *
 *   /meet/.../?from=<inviter>&name=<recipient>&invited_by=<contributor-id>
 *
 * When the recipient taps the link, InviteBanner writes `name` into
 * `cc-reaction-author-name` so she arrives already carrying a soft
 * identity — no registration screen, no private key, no friction.
 * She can react, voice, comment immediately. Phone/email/wallet can
 * follow at her pace via the incremental profile card.
 *
 * If the recipient has been here before (any identity already stored),
 * we do not overwrite — her device's identity wins over URL claims.
 * Uses Web Share API when available, clipboard as fallback.
 */

import { useEffect, useState } from "react";
import { useT, useLocale } from "@/components/MessagesProvider";

const NAME_KEY = "cc-reaction-author-name";
const CONTRIBUTOR_KEY = "cc-contributor-id";

interface Props {
  /** Which page to land them on. Defaults to /meet/concept/lc-nourishing —
   *  the warmest first touch. */
  targetPath?: string;
  className?: string;
}

function siteBase(): string {
  if (typeof window === "undefined") return "https://coherencycoin.com";
  return `${window.location.protocol}//${window.location.host}`;
}

export function InviteFriend({
  targetPath = "/meet/concept/lc-nourishing",
  className = "",
}: Props) {
  const t = useT();
  const locale = useLocale();
  const [inviterName, setInviterName] = useState<string>("");
  const [inviterId, setInviterId] = useState<string>("");
  const [recipientName, setRecipientName] = useState<string>("");
  const [copied, setCopied] = useState<"idle" | "copied" | "shared">("idle");

  useEffect(() => {
    try {
      setInviterName(localStorage.getItem(NAME_KEY) || "");
      setInviterId(localStorage.getItem(CONTRIBUTOR_KEY) || "");
    } catch {
      /* ignore */
    }
  }, []);

  function buildUrl(): string {
    const base = siteBase();
    const url = new URL(targetPath, base);
    if (inviterName.trim()) url.searchParams.set("from", inviterName.trim());
    if (recipientName.trim()) url.searchParams.set("name", recipientName.trim().slice(0, 80));
    if (inviterId.trim()) url.searchParams.set("invited_by", inviterId.trim());
    // Hint the UI to the inviter's language so the banner greets in
    // a tongue the sender chose. The receiver's browser detection
    // still wins if different and supported.
    if (locale) url.searchParams.set("lang", locale);
    return url.toString();
  }

  async function onInvite() {
    const url = buildUrl();
    const rName = recipientName.trim();
    const iName = inviterName.trim();
    // Pick the warmest localized line we have
    let message: string;
    if (rName && iName) {
      message = t("invite.messageWithBoth")
        .replace("{recipient}", rName)
        .replace("{name}", iName);
    } else if (iName) {
      message = t("invite.messageWithName").replace("{name}", iName);
    } else {
      message = t("invite.message");
    }
    const payload = {
      title: t("invite.title"),
      text: message,
      url,
    };
    try {
      if (typeof navigator !== "undefined" && typeof navigator.share === "function") {
        await navigator.share(payload);
        setCopied("shared");
        setTimeout(() => setCopied("idle"), 2500);
        return;
      }
      if (typeof navigator !== "undefined" && navigator.clipboard) {
        await navigator.clipboard.writeText(`${message}\n${url}`);
        setCopied("copied");
        setTimeout(() => setCopied("idle"), 2500);
      }
    } catch {
      /* user cancelled — idle */
    }
  }

  const label =
    copied === "copied"
      ? t("invite.copied")
      : copied === "shared"
      ? t("invite.shared")
      : t("invite.cta");

  const ready = recipientName.trim().length > 0;

  return (
    <section
      id="invite"
      className={
        className ||
        "rounded-xl border border-teal-800/40 bg-teal-950/10 p-5 space-y-3"
      }
    >
      <p className="text-xs uppercase tracking-widest text-teal-300/90">
        {t("invite.eyebrow")}
      </p>
      <h3 className="text-base md:text-lg font-light text-stone-100 leading-snug">
        {t("invite.headline")}
      </h3>
      <p className="text-sm text-stone-400 leading-relaxed">
        {t("invite.lede")}
      </p>
      <div className="space-y-2">
        <label className="block text-xs text-stone-400" htmlFor="invite-recipient">
          {t("invite.recipientLabel")}
        </label>
        <input
          id="invite-recipient"
          type="text"
          value={recipientName}
          onChange={(e) => setRecipientName(e.target.value)}
          placeholder={t("invite.recipientPlaceholder")}
          maxLength={80}
          className="w-full rounded-lg border border-teal-900/50 bg-stone-950/60 px-3 py-2 text-sm text-stone-100 placeholder:text-stone-600 focus:border-teal-600 focus:outline-none"
        />
        <p className="text-[11px] text-stone-500 leading-snug">
          {t("invite.recipientHint")}
        </p>
      </div>
      <button
        type="button"
        onClick={onInvite}
        disabled={!ready}
        className="inline-flex items-center gap-2 rounded-full bg-teal-700/80 hover:bg-teal-600/90 disabled:bg-stone-800/40 disabled:text-stone-500 disabled:cursor-not-allowed text-stone-950 px-4 py-2 text-sm font-medium transition-colors"
      >
        <span aria-hidden="true">🌿</span>
        <span>{label}</span>
      </button>
    </section>
  );
}
