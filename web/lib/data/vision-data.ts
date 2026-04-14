/**
 * Static data maps for the Living Collective vision pages.
 *
 * Extracted from vision-utils.ts so that data is editable without
 * touching utility functions. All exports are re-exported through
 * vision-utils.ts — existing consumers are unaffected.
 */

/* ── Frequency → color ──────────────────────────────────────────────── */

export const HZ_COLORS: Record<number, string> = {
  174: "text-rose-300/80",
  285: "text-rose-200/70",
  396: "text-orange-300/80",
  417: "text-yellow-300/70",
  432: "text-amber-300/80",
  528: "text-teal-300/80",
  639: "text-emerald-300/70",
  741: "text-violet-300/80",
  852: "text-indigo-300/70",
  963: "text-fuchsia-300/70",
};

/* ── Edge type → display label ──────────────────────────────────────── */

export const EDGE_LABELS: Record<string, string> = {
  "resonates-with": "resonates with",
  "analogous-to": "resonates with",
  "emerges-from": "emerges from",
  "enables": "enables",
  "embodies": "embodies",
  "instantiates": "gives form to",
  "complements": "complements",
  "fractal-scaling": "fractal of",
  "transforms-into": "transforms into",
  "catalyzes": "catalyzes",
  "parent-of": "unfolds into",
};

/* ── Resource type → icon ───────────────────────────────────────────── */

export const RESOURCE_ICONS: Record<string, string> = {
  blueprint: "\u{1F4D0}",
  guide: "\u{1F4D6}",
  video: "\u25B6\uFE0F",
  course: "\u{1F393}",
  community: "\u{1F3D8}\uFE0F",
  book: "\u{1F4D5}",
  wiki: "\u{1F310}",
  tool: "\u{1F527}",
  dataset: "\u{1F4CA}",
};

/* ── Climate zone → label + color ───────────────────────────────────── */

export const CLIMATE_LABELS: Record<string, { label: string; color: string }> = {
  temperate: { label: "Temperate", color: "bg-emerald-500/10 text-emerald-400/80 border-emerald-500/20" },
  tropical: { label: "Tropical", color: "bg-amber-500/10 text-amber-400/80 border-amber-500/20" },
  arid: { label: "Arid", color: "bg-orange-500/10 text-orange-400/80 border-orange-500/20" },
  coastal: { label: "Coastal", color: "bg-sky-500/10 text-sky-400/80 border-sky-500/20" },
  alpine: { label: "Alpine", color: "bg-indigo-500/10 text-indigo-400/80 border-indigo-500/20" },
};

/* ── Place name → internal community page slug ──────────────────────── */

export const PLACE_TO_COMMUNITY: Record<string, string> = {
  auroville: "community-auroville",
  findhorn: "community-findhorn",
  "findhorn foundation": "community-findhorn",
  "findhorn ecovillage": "community-findhorn",
  tamera: "community-tamera",
  damanhur: "community-damanhur",
  gaviotas: "community-gaviotas",
  earthship: "community-earthship",
  "earthship biotecture": "community-earthship",
  "new earth": "community-new-earth-micronation",
  "new earth micronation": "community-new-earth-micronation",
  "new earth horizon": "community-new-earth-horizon",
  "new earth exchange": "community-new-earth-exchange",
};

/* ── Level labels + colors ──────────────────────────────────────────── */

export const LEVEL_LABELS: Record<number, string> = {
  0: "Root Pulse",
  1: "System / Flow",
  2: "Living Expression",
  3: "Vocabulary",
};

export const LEVEL_COLORS: Record<number, string> = {
  0: "border-amber-500/40 text-amber-300/90",
  1: "border-teal-500/40 text-teal-300/90",
  2: "border-violet-500/40 text-violet-300/90",
  3: "border-stone-500/40 text-stone-400",
};
