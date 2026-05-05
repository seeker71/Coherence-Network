// Shared inline-link helper for prose paragraphs.
//
// The codebase declares `prose` and `prose-a:text-amber-*` Tailwind
// classes throughout, but @tailwindcss/typography isn't installed —
// those classes are inert. This component gives every cross-link in
// body copy a consistent amber treatment with hover, underline-offset,
// and decoration shading. Use it inside prose paragraphs anywhere a
// next/link would otherwise render unstyled.
//
// Pattern:
//   <p>Read more at <L href="/one-sheet">/one-sheet</L>.</p>

import Link from "next/link";
import type { ReactNode } from "react";

interface InlineLinkProps {
  href: string;
  children: ReactNode;
  /** Override the default amber styling if a different surface needs a tone. */
  className?: string;
}

const DEFAULT_CLASS =
  "text-amber-500 hover:text-amber-400 dark:text-amber-400 dark:hover:text-amber-300 underline-offset-4 underline decoration-amber-500/40 hover:decoration-amber-400/70 transition-colors";

export function L({ href, children, className }: InlineLinkProps) {
  // External links (mailto:, https://) get a regular <a>; anything else uses
  // next/link for client-side navigation.
  if (
    href.startsWith("mailto:") ||
    href.startsWith("http://") ||
    href.startsWith("https://")
  ) {
    return (
      <a
        href={href}
        className={className ?? DEFAULT_CLASS}
        target={href.startsWith("http") ? "_blank" : undefined}
        rel={href.startsWith("http") ? "noopener noreferrer" : undefined}
      >
        {children}
      </a>
    );
  }
  return (
    <Link href={href} className={className ?? DEFAULT_CLASS}>
      {children}
    </Link>
  );
}
