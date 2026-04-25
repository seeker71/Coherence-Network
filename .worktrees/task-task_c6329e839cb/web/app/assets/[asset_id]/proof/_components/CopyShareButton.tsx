"use client";

import { useState } from "react";

interface Props {
  assetId: string;
}

export function CopyShareButton({ assetId }: Props) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    const url =
      typeof window !== "undefined"
        ? `${window.location.origin}/assets/${assetId}/proof`
        : `/assets/${assetId}/proof`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback: briefly show "Copy failed"; don't crash the page.
      setCopied(false);
    }
  }

  return (
    <button
      onClick={handleCopy}
      className="rounded border border-stone-700 bg-stone-900/50 px-4 py-2 text-sm text-stone-200 hover:border-amber-500/40 transition-colors"
    >
      {copied ? "Copied ✓" : "Share proof"}
    </button>
  );
}
