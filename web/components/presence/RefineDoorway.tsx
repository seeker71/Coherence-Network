"use client";

/**
 * RefineDoorway — visible permission and ability to update what
 * this presence carries.
 *
 * Anyone visiting this page can correct, deepen, or refine what's
 * here. The doorway is intentionally calm and ambient: not asking
 * the visitor to "edit" but inviting them to bring this presence
 * into truer alignment. Two paths converge here:
 *
 *   · "this is me"  → claim the page, own the editing
 *   · "refine"      → suggest a refinement as a visitor
 *
 * The data this page renders comes from primary signals on the
 * graph node — image, description, presence URLs across platforms,
 * relationship edges. Refining that primary data is what changes
 * the page; the visitor doesn't edit a frozen bio, they shape the
 * data the bio is composed from.
 */

import Link from "next/link";
import type { PresenceIdentity } from "./PresencePage";

export function RefineDoorway({ identity }: { identity: PresenceIdentity }) {
  // Slug-based edit URL when the graph node carries a slug; else
  // the id form (the route resolves both).
  const idForUrl = encodeURIComponent(identity.id);
  const editHref = identity.slug
    ? `/people/${identity.slug}/edit`
    : `/people/${idForUrl}/edit`;
  return (
    <section>
      <div className="rounded-2xl border border-[hsl(var(--primary)/0.25)] bg-[hsl(var(--primary)/0.04)] p-5">
        <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-[hsl(var(--primary))] mb-1.5">
          Refine this presence
        </p>
        <p className="text-sm text-foreground/85 leading-relaxed">
          Anything here can be corrected. If something doesn&apos;t represent{" "}
          <span className="font-medium">{identity.name}</span> well — image,
          tagline, the relationships, the platforms linked from here — open
          the refinement door and shape it.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Link
            href={editHref}
            className="inline-flex items-center gap-1.5 rounded-full border border-[hsl(var(--primary)/0.45)] bg-[hsl(var(--primary)/0.1)] px-3.5 py-1.5 text-xs font-medium text-[hsl(var(--primary))] hover:bg-[hsl(var(--primary)/0.18)] transition-colors"
          >
            Refine
          </Link>
          {identity.claimed === false && (
            <Link
              href={`/claim/${idForUrl}`}
              className="inline-flex items-center gap-1.5 rounded-full border border-border/50 px-3.5 py-1.5 text-xs text-muted-foreground hover:text-foreground hover:border-border transition-colors"
            >
              this is me →
            </Link>
          )}
        </div>
      </div>
    </section>
  );
}
