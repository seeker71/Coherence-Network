"use client";

import { useState, useCallback } from "react";

interface IdeaShareProps {
  ideaId: string;
  name: string;
  description: string;
  valueGap: number;
  status: string;
  url: string;
}

function truncate(text: string, max: number): string {
  if (text.length <= max) return text;
  return text.slice(0, max).trimEnd() + "\u2026";
}

export default function IdeaShare({
  ideaId,
  name,
  description,
  valueGap,
  status,
  url,
}: IdeaShareProps) {
  const [copied, setCopied] = useState(false);

  const twitterText = `"${truncate(description, 200)}"\n\nThis idea needs help \u2192\n${url}`;
  const twitterHref = `https://twitter.com/intent/tweet?text=${encodeURIComponent(twitterText)}`;

  const linkedInText = `${name}\n\n${truncate(description, 300)}\n\nValue opportunity: ${valueGap.toFixed(0)} CC | Status: ${status}\n\nSee the full idea and contribute: ${url}`;
  const linkedInHref = `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}&summary=${encodeURIComponent(linkedInText)}`;

  const redditTitle = `${name} \u2014 ${truncate(description, 250)}`;
  const redditHref = `https://www.reddit.com/submit?url=${encodeURIComponent(url)}&title=${encodeURIComponent(redditTitle)}`;

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [url]);

  const btnClass =
    "inline-flex items-center justify-center h-8 w-8 rounded-lg border border-border/30 bg-background/60 text-sm transition-colors duration-200 hover:bg-amber-100 hover:border-amber-300 dark:hover:bg-amber-900/30 dark:hover:border-amber-700";

  return (
    <div className="flex items-center gap-1.5">
      <a
        href={twitterHref}
        target="_blank"
        rel="noopener noreferrer"
        className={btnClass}
        title="Share on X"
        aria-label="Share on X"
      >
        <span className="text-xs font-bold leading-none">{"\uD835\uDD4F"}</span>
      </a>
      <a
        href={linkedInHref}
        target="_blank"
        rel="noopener noreferrer"
        className={btnClass}
        title="Share on LinkedIn"
        aria-label="Share on LinkedIn"
      >
        <span className="text-xs font-bold leading-none">in</span>
      </a>
      <a
        href={redditHref}
        target="_blank"
        rel="noopener noreferrer"
        className={btnClass}
        title="Share on Reddit"
        aria-label="Share on Reddit"
      >
        <span className="text-xs leading-none">r/</span>
      </a>
      <button
        type="button"
        onClick={handleCopy}
        className={btnClass}
        title="Copy link"
        aria-label="Copy link"
      >
        {copied ? (
          <span className="text-xs text-amber-600 dark:text-amber-400 font-medium">{"Copied!"}</span>
        ) : (
          <span className="text-xs leading-none">{"\uD83D\uDD17"}</span>
        )}
      </button>
    </div>
  );
}

/** Compact copy-link-only button for list views. */
export function IdeaCopyLink({ url }: { url: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [url]);

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="inline-flex items-center justify-center h-7 w-7 rounded-md border border-border/30 bg-background/60 text-xs transition-colors duration-200 hover:bg-amber-100 hover:border-amber-300 dark:hover:bg-amber-900/30 dark:hover:border-amber-700"
      title="Copy link"
      aria-label="Copy link"
    >
      {copied ? (
        <span className="text-[10px] text-amber-600 dark:text-amber-400 font-medium">{"\u2713"}</span>
      ) : (
        <span className="text-xs leading-none">{"\uD83D\uDD17"}</span>
      )}
    </button>
  );
}
