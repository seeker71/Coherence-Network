// LineageStrip — when the current /people/{slug} page is one of the
// 13 chronological works in Urs Muff's lineage, surface a small
// stitching strip: previous work · era anchor · next work · back to
// lineage. Without this strip, every work page is a dead-end leaf.
// With it, the visitor walks the body's own time.

import Link from "next/link";

import { findLineageWork } from "@/lib/lineage-works";

export function LineageStrip({ slug }: { slug?: string }) {
  const found = findLineageWork(slug);
  if (!found) return null;
  const { index, work, prev, next } = found;

  return (
    <nav
      aria-label="Lineage navigation"
      className="mb-8 flex flex-wrap items-center gap-2 rounded-xl border border-border/40 bg-card/30 px-3 py-2 text-xs"
    >
      <Link
        href={`/people/urs/lineage#era-${work.eraId}`}
        className="rounded-full px-2 py-1 text-foreground/85 hover:text-foreground transition-colors"
        style={{
          backgroundColor: work.hue.replace(")", " / 0.08)"),
          border: `1px solid ${work.hue.replace(")", " / 0.45)")}`,
        }}
      >
        <span style={{ color: work.hue }}>{work.eraLabel}</span>
        <span className="text-muted-foreground/80 ml-1.5 font-mono">{work.year}</span>
      </Link>
      <span className="text-muted-foreground/60 font-mono">
        work {index + 1} of 13
      </span>
      <span className="ml-auto flex items-center gap-2">
        {prev ? (
          <Link
            href={`/people/${prev.slug}`}
            className="text-muted-foreground hover:text-foreground transition-colors"
            title={`Previous: ${prev.short}`}
          >
            ← {prev.short}
          </Link>
        ) : (
          <span className="text-muted-foreground/40">—</span>
        )}
        <Link
          href="/people/urs/lineage"
          className="rounded-full border border-border/40 px-2 py-1 text-muted-foreground hover:text-foreground hover:border-border transition-colors"
        >
          ↑ Lineage
        </Link>
        {next ? (
          <Link
            href={`/people/${next.slug}`}
            className="text-muted-foreground hover:text-foreground transition-colors"
            title={`Next: ${next.short}`}
          >
            {next.short} →
          </Link>
        ) : (
          <span className="text-muted-foreground/40">—</span>
        )}
      </span>
    </nav>
  );
}
