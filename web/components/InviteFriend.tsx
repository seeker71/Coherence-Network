"use client";

/**
 * InviteFriend — a small "bring someone in" block.
 *
 * Generates a warm shareable link: the current site with a soft
 * ?from= parameter carrying the inviter's author name. Copies to
 * clipboard (or opens the native share sheet on mobile) with a
 * suggested message in the inviter's language.
 *
 * The landing pages don't need to parse ?from= yet — that's a later
 * cycle. For now the link already works (it just lands on the home
 * page) and the inviter gets a proud affordance.
 */

import { useEffect, useState } from "react";
import { useT, useLocale } from "@/components/MessagesProvider";

const NAME_KEY = "cc-reaction-author-name";

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
  const [name, setName] = useState<string>("");
  const [copied, setCopied] = useState<"idle" | "copied" | "shared">("idle");

  useEffect(() => {
    try {
      setName(localStorage.getItem(NAME_KEY) || "");
    } catch {
      /* ignore */
    }
  }, []);

  function buildUrl(): string {
    const base = siteBase();
    const url = new URL(targetPath, base);
    if (name.trim()) url.searchParams.set("from", name.trim());
    return url.toString();
  }

  async function onInvite() {
    const url = buildUrl();
    const message = name.trim()
      ? t("invite.messageWithName").replace("{name}", name.trim())
      : t("invite.message");
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

  return (
    <section
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
      <button
        type="button"
        onClick={onInvite}
        className="inline-flex items-center gap-2 rounded-full bg-teal-700/80 hover:bg-teal-600/90 text-stone-950 px-4 py-2 text-sm font-medium transition-colors"
      >
        <span aria-hidden="true">🌿</span>
        <span>{label}</span>
      </button>
    </section>
  );
}
