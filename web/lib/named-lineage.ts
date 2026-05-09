// named-lineage — slugs of the load-bearing humans in the lineage,
// in roughly the chronological order they entered the body's arc.
// Single source of truth so /people can surface them above the
// alphabetic flood of book authors and auto-resolved channels, and
// any future surface that wants "the figures who actually shaped
// this work" reads from one list.
//
// Order matches /people/urs/lineage prose: childhood transmissions →
// foundation collaborator → bridge listening → current era streams →
// Ubud cluster → present connections. A figure earns inclusion here
// only when /people/{slug} renders a curated h1 (not a thin
// auto-resolved stub) — verified live before authoring.

export const LINEAGE_FIGURE_SLUGS: readonly string[] = [
  // Era 1 — the keystone (~1984 – ~1990)
  "michael-ende",
  "james-fenimore-cooper",
  // Era 2 — foundation (1991 – 2000)
  "steve-bjorg",
  // Era 6 — Qualcomm listening (2009 – 2022)
  "lex-fridman",
  // Era 7 — bridge years (Jan 2022 – 2024) and current devotional substrate
  "anne-tucker",
  "mose",
  "liquid-bloom",
  // Streams that ran alongside
  "michael-levin",
  "robert-edward-grant",
  // Era 8 — Coherence Network present
  "aubrey-marcus",
  "bloomurian",
  // Ubud cluster — transmission node (Sunday-Wednesday rhythm)
  "ilena",
  "vasudev-baba",
  "elios",
  // Current connections
  "aly-constantine",
];

const RANK = new Map(
  LINEAGE_FIGURE_SLUGS.map((slug, i) => [slug, i] as const),
);

// Returns 0..N-1 for lineage figures (lower = earlier in the arc),
// or null when the slug is not a named lineage figure.
export function lineageFigureRank(slug: string | undefined | null): number | null {
  if (!slug) return null;
  const r = RANK.get(slug);
  return r === undefined ? null : r;
}

export function isLineageFigure(slug: string | undefined | null): boolean {
  return lineageFigureRank(slug) !== null;
}
