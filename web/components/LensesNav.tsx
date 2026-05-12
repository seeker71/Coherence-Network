import Link from "next/link";

/**
 * LensesNav — surfaces the same body through different perspectives.
 *
 * The network has multiple ways to look at "who is here": the
 * directory (every presence by kind), contributors (paged by
 * registration), creators (through the contribution economy), peers
 * (resonance-matched to your frequency), the guided presence walk.
 * Each is a different lens on the same field, not a duplicate.
 *
 * Per Urs's directive on the doorway-walk: these lenses stay; what
 * was missing was that they didn't see each other. This component
 * renders a slim row showing the sibling lenses so a visitor on any
 * one can step sideways to another and feel the same body through a
 * different shape of attention.
 *
 * The current lens renders quietly (highlighted but not a link) so
 * the visitor knows where they are.
 */

export type LensKey =
  | "presences"
  // Legacy alias kept for surfaces still using "people" as the lens
  // identifier — they still highlight the directory lens correctly.
  | "people"
  | "contributors"
  | "creators"
  | "peers"
  | "presence-walk";

const LENSES: Array<{
  key: LensKey;
  href: string;
  label: string;
  desc: string;
}> = [
  {
    key: "presences",
    href: "/presences",
    label: "Presences",
    desc: "Every cell, place, gathering, practice, and work the body holds",
  },
  {
    key: "contributors",
    href: "/contributors",
    label: "Contributors",
    desc: "Paged through the body's registration",
  },
  {
    key: "creators",
    href: "/creators",
    label: "Creators",
    desc: "Through the contribution-economy lens",
  },
  {
    key: "peers",
    href: "/peers",
    label: "Peers",
    desc: "Resonance-matched to your frequency",
  },
  {
    key: "presence-walk",
    href: "/presence-walk",
    label: "Guided walk",
    desc: "Through each kind of presence in turn",
  },
];

export function LensesNav({ current }: { current: LensKey }) {
  return (
    <nav
      aria-label="Lenses on the same body"
      className="rounded-xl border border-border/30 bg-card/30 px-4 py-3"
    >
      <p className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground/80 mb-2">
        Lenses — the same body through different perspectives
      </p>
      <ul className="flex flex-wrap items-center gap-1.5">
        {LENSES.map((l) => {
          const isCurrent = l.key === current;
          if (isCurrent) {
            return (
              <li key={l.key}>
                <span
                  className="inline-flex flex-col rounded-lg border border-[hsl(var(--primary))]/40 bg-[hsl(var(--primary))]/5 px-3 py-1.5"
                  aria-current="page"
                >
                  <span className="text-xs font-medium text-[hsl(var(--primary))]">
                    {l.label}
                  </span>
                  <span className="text-[10px] text-[hsl(var(--primary))]/70 leading-tight">
                    {l.desc}
                  </span>
                </span>
              </li>
            );
          }
          return (
            <li key={l.key}>
              <Link
                href={l.href}
                className="group inline-flex flex-col rounded-lg border border-border/40 bg-card/40 hover:bg-card/65 hover:border-border px-3 py-1.5 transition-colors"
              >
                <span className="text-xs text-foreground/85 group-hover:text-foreground">
                  {l.label}
                </span>
                <span className="text-[10px] text-muted-foreground/85 leading-tight">
                  {l.desc}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
