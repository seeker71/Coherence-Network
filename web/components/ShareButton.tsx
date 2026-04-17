"use client";

/**
 * ShareButton — tiny share affordance that uses the native sheet
 * (navigator.share) when available, otherwise copies the URL to the
 * clipboard and acknowledges.
 */

import { useState } from "react";
import { useT } from "@/components/MessagesProvider";

interface Props {
  /** Absolute URL to share. Falls back to current window.location.href. */
  url?: string;
  /** Title to accompany the share payload. */
  title?: string;
  /** Short description accompanying the share payload. */
  text?: string;
  /** Optional className overriding the default pill styling. */
  className?: string;
}

export function ShareButton({ url, title, text, className = "" }: Props) {
  const t = useT();
  const [status, setStatus] = useState<"idle" | "copied" | "shared" | "error">("idle");

  async function onShare() {
    const shareUrl = url || (typeof window !== "undefined" ? window.location.href : "");
    const payload = {
      url: shareUrl,
      title: title || (typeof document !== "undefined" ? document.title : ""),
      text: text || "",
    };
    try {
      if (typeof navigator !== "undefined" && typeof navigator.share === "function") {
        await navigator.share(payload);
        setStatus("shared");
        setTimeout(() => setStatus("idle"), 2000);
        return;
      }
      if (typeof navigator !== "undefined" && navigator.clipboard) {
        await navigator.clipboard.writeText(shareUrl);
        setStatus("copied");
        setTimeout(() => setStatus("idle"), 2000);
        return;
      }
      setStatus("error");
      setTimeout(() => setStatus("idle"), 2000);
    } catch {
      // User cancelled the native sheet — treat as idle.
      setStatus("idle");
    }
  }

  const label =
    status === "copied"
      ? t("share.copied")
      : status === "shared"
      ? t("share.shared")
      : status === "error"
      ? t("share.error")
      : t("share.action");

  return (
    <button
      type="button"
      onClick={onShare}
      className={
        className ||
        "inline-flex items-center gap-1.5 rounded-full border border-border/40 bg-background/60 hover:bg-accent/40 text-sm px-3 py-1 transition-colors"
      }
      aria-label={t("share.action")}
    >
      <span aria-hidden="true">↗</span>
      <span>{label}</span>
    </button>
  );
}
