// lineage-works — chronological order of the load-bearing works in
// Urs Muff's 42-year arc. Single source of truth so the lineage
// page's at-a-glance grid, the per-work prev/next strip, and any
// future works-strip rendering all read the same list.
//
// Order matches /people/urs/lineage page top-to-bottom. Each entry
// carries enough context for a stitching strip (era id + label,
// short title, year). Era ids match the article anchors on the
// lineage page (#era-{eraId}).

export type LineageWork = {
  slug: string;
  short: string;
  year: string;
  eraId: string;
  eraLabel: string;
  hue: string;
};

export const LINEAGE_WORKS: LineageWork[] = [
  { slug: "c64-midi-interface", short: "C64 MIDI · age 13", year: "~1984", eraId: "keystone", eraLabel: "keystone", hue: "hsl(220 60% 65%)" },
  { slug: "schindler-hc11-protocol", short: "Schindler HC11 · 7-layer", year: "~1989", eraId: "keystone", eraLabel: "keystone", hue: "hsl(220 60% 65%)" },
  { slug: "backtracking-model-languages", short: "BML thesis · CU Boulder", year: "2000", eraId: "foundation", eraLabel: "foundation", hue: "hsl(38 80% 60%)" },
  { slug: "quark-virtual-dom", short: "Quark · Virtual DOM", year: "2000–05", eraId: "quark", eraLabel: "Quark Denver", hue: "hsl(195 60% 55%)" },
  { slug: "quark-multi-undo-redo", short: "Quark · Multi-Undo/Redo", year: "2000–05", eraId: "quark", eraLabel: "Quark Denver", hue: "hsl(195 60% 55%)" },
  { slug: "quark-mono-corba", short: "Quark · Mono/CORBA", year: "2000–05", eraId: "quark", eraLabel: "Quark Denver", hue: "hsl(195 60% 55%)" },
  { slug: "mindtouch-wiki-in-a-box", short: "MindTouch · Wiki-in-a-box", year: "2005–07", eraId: "mindtouch", eraLabel: "MindTouch", hue: "hsl(140 55% 55%)" },
  { slug: "trimble-glue-layer", short: "Trimble · Glue layer", year: "2007–09", eraId: "trimble", eraLabel: "Trimble Boulder", hue: "hsl(80 55% 55%)" },
  { slug: "qualcomm-test-automation", short: "Qualcomm · Test Automation", year: "2009–22", eraId: "qualcomm", eraLabel: "Qualcomm Boulder", hue: "hsl(40 70% 55%)" },
  { slug: "qualcomm-hdmi-hdcp", short: "Qualcomm · HDMI/HDCP kernel", year: "2009–22", eraId: "qualcomm", eraLabel: "Qualcomm Boulder", hue: "hsl(40 70% 55%)" },
  { slug: "living-resonance-codex", short: "Living-Resonance-Codex · Python", year: "2023", eraId: "bridge", eraLabel: "bridge", hue: "hsl(140 60% 55%)" },
  { slug: "living-codex-csharp", short: "Living-Codex-CSharp · U-CORE", year: "2024", eraId: "bridge", eraLabel: "bridge", hue: "hsl(140 60% 55%)" },
  { slug: "coherence-network", short: "Coherence-Network · live", year: "2024–now", eraId: "coherence-network", eraLabel: "Coherence Network", hue: "hsl(280 70% 65%)" },
];

export function findLineageWork(slug: string | undefined): {
  index: number;
  work: LineageWork;
  prev: LineageWork | null;
  next: LineageWork | null;
} | null {
  if (!slug) return null;
  const i = LINEAGE_WORKS.findIndex((w) => w.slug === slug);
  if (i < 0) return null;
  return {
    index: i,
    work: LINEAGE_WORKS[i],
    prev: i > 0 ? LINEAGE_WORKS[i - 1] : null,
    next: i < LINEAGE_WORKS.length - 1 ? LINEAGE_WORKS[i + 1] : null,
  };
}
