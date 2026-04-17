"use client";

/**
 * InviteFriend — a small "bring someone in" block.
 *
 * The inviter types the recipient's name (first name is enough) and
 * picks the language the recipient should arrive in. The generated
 * link:
 *
 *   /meet/.../?from=<inviter>&name=<recipient>&invited_by=<contributor-id>[&lang=<locale>]
 *
 * Language selector defaults to "auto-detect from her browser" (no
 * ?lang= in the URL, middleware picks from Accept-Language). The
 * inviter can override per-invite — e.g. Patrick (browsing in English)
 * wants his German mother to arrive in German without setting his own
 * site to German first.
 *
 * When the recipient taps the link, InviteBanner writes `name` into
 * `cc-reaction-author-name` so she arrives already carrying a soft
 * identity — no registration screen, no private key, no friction.
 *
 * On return visits, InviteBanner honors her device's identity; no
 * duplicates. See InviteBanner for that half of the contract.
 * Uses Web Share API when available, clipboard as fallback.
 */

import { useEffect, useMemo, useState } from "react";
import { useT, useLocale } from "@/components/MessagesProvider";
import { createTranslator } from "@/lib/i18n";
import { LOCALES, type LocaleCode } from "@/lib/locales";

const NAME_KEY = "cc-reaction-author-name";
const CONTRIBUTOR_KEY = "cc-contributor-id";

// Language selection for the invite link.
// "auto" means "no ?lang= in URL" — let middleware pick from the
// recipient's Accept-Language header. This is the safest default
// because it honors her device, not the inviter's.
type InviteLang = "auto" | LocaleCode;

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
  // Default to "auto" — let the recipient's own browser decide.
  // The inviter's own locale is just a UI language for this form,
  // not a claim about what the recipient speaks.
  const [inviteLang, setInviteLang] = useState<InviteLang>("auto");
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
    // Language policy:
    //   "auto" (default) — no ?lang= in URL. The middleware honors
    //     the recipient's browser Accept-Language on first paint.
    //     This is the warmest default: the recipient's own device
    //     decides, not the inviter.
    //   explicit locale — inviter overrides for this recipient,
    //     e.g. Patrick (English UI) inviting his German mother.
    if (inviteLang !== "auto") {
      url.searchParams.set("lang", inviteLang);
    }
    return url.toString();
  }

  // Compose the share message in the recipient's language when the
  // inviter picked one explicitly. For "auto" we fall back to the
  // inviter's UI locale — that's what they'll be reading anyway in
  // the share sheet, and the recipient's device will retranslate
  // the site once she taps through.
  const shareLang: LocaleCode = inviteLang === "auto" ? (locale as LocaleCode) : inviteLang;
  const tShare = useMemo(() => createTranslator(shareLang), [shareLang]);

  async function onInvite() {
    const url = buildUrl();
    const rName = recipientName.trim();
    const iName = inviterName.trim();
    // Pick the warmest localized line we have — in the recipient's language
    let message: string;
    if (rName && iName) {
      message = tShare("invite.messageWithBoth")
        .replace("{recipient}", rName)
        .replace("{name}", iName);
    } else if (iName) {
      message = tShare("invite.messageWithName").replace("{name}", iName);
    } else {
      message = tShare("invite.message");
    }
    const payload = {
      title: tShare("invite.title"),
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
      <div className="space-y-2">
        <label className="block text-xs text-stone-400" htmlFor="invite-lang">
          {t("invite.langLabel")}
        </label>
        <select
          id="invite-lang"
          value={inviteLang}
          onChange={(e) => setInviteLang(e.target.value as InviteLang)}
          className="w-full rounded-lg border border-teal-900/50 bg-stone-950/60 px-3 py-2 text-sm text-stone-100 focus:border-teal-600 focus:outline-none"
        >
          <option value="auto">{t("invite.langAuto")}</option>
          {LOCALES.map((l) => (
            <option key={l.code} value={l.code}>
              {l.nativeName}
            </option>
          ))}
        </select>
        <p className="text-[11px] text-stone-500 leading-snug">
          {t("invite.langHint")}
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
