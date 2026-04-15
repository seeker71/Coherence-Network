/**
 * Shared utilities for Living Collective vision pages.
 *
 * This is the single source of truth for:
 * - Concept ID → display name conversion
 * - Hz frequency → color mapping
 * - Inline markdown → safe HTML conversion
 * - Story visual → static image path resolution
 *
 * Every vision page imports from here. No duplication.
 */

/* ── Display names ────────────────────────────────────────────────────── */

/**
 * Convert a concept ID to a human-readable display name.
 * Uses the nameMap when available, falls back to cleaning the ID.
 *
 * Handles all prefixes: lc-, lc-v-, lc-w-
 */
export function displayName(id: string, nameMap?: Record<string, string>): string {
  if (nameMap?.[id]) return nameMap[id];
  return id
    .replace(/^lc-w-/, "")
    .replace(/^lc-v-/, "")
    .replace(/^lc-/, "")
    .replace(/-/g, " ");
}

/* ── Frequency colors ─────────────────────────────────────────────────── */

const HZ_COLORS: Record<number, string> = {
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

/** Get the CSS color class for a solfeggio frequency. */
export function frequencyColor(hz: number): string {
  return HZ_COLORS[hz] || "text-stone-300";
}

/* ── Inline markdown → safe HTML ──────────────────────────────────────── */

/**
 * Convert inline markdown (bold, italic, links) to sanitized HTML.
 *
 * Escapes raw HTML first to prevent XSS, then applies markdown formatting.
 * Safe for use with dangerouslySetInnerHTML because input is sanitized.
 */
export function inlineMarkdownToHtml(text: string): string {
  return text
    // First: escape any raw HTML to prevent XSS
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    // Then: apply markdown formatting
    .replace(/\*\*([^*]+)\*\*/g, '<strong class="text-stone-300">$1</strong>')
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    .replace(
      /\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-amber-400/70 hover:text-amber-300 border-b border-amber-500/20 hover:border-amber-500/40 transition-colors">$1</a>'
    );
}

/* ── Static image path resolution ─────────────────────────────────────── */

/** Seed constants — must match scripts/kb_common.py */
const SEED_STRIDE = 17;
const STORY_SEED_STRIDE = 13;

/** Deterministic seed from concept ID — matches Python's concept_seed(). */
export function conceptSeed(conceptId: string): number {
  let sum = 0;
  for (let i = 0; i < conceptId.length; i++) {
    sum += conceptId.charCodeAt(i);
  }
  return sum;
}

/** Path to a pre-generated gallery visual. */
export function galleryImagePath(conceptId: string, index: number): string {
  return `/visuals/generated/${conceptId}-${index}.jpg`;
}

/** Path to a pre-generated story visual. */
export function storyImagePath(conceptId: string, index: number): string {
  return `/visuals/generated/${conceptId}-story-${index}.jpg`;
}

/**
 * Fallback Pollinations URL — used ONLY during initial generation
 * before static files exist. The concept page should always prefer
 * the static path. This exists solely for the poster page.
 */
export function pollinationsUrl(prompt: string, seed = 42, width = 1024, height = 576): string {
  return `https://image.pollinations.ai/prompt/${encodeURIComponent(prompt)}?width=${width}&height=${height}&model=flux&nologo=true&seed=${seed}`;
}

/* ── Edge labels ──────────────────────────────────────────────────────── */

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

/* ── Resource icons ───────────────────────────────────────────────────── */

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

/* ── Climate labels ───────────────────────────────────────────────────── */

export const CLIMATE_LABELS: Record<string, { label: string; color: string }> = {
  temperate: { label: "Temperate", color: "bg-emerald-500/10 text-emerald-400/80 border-emerald-500/20" },
  tropical: { label: "Tropical", color: "bg-amber-500/10 text-amber-400/80 border-amber-500/20" },
  arid: { label: "Arid", color: "bg-orange-500/10 text-orange-400/80 border-orange-500/20" },
  coastal: { label: "Coastal", color: "bg-sky-500/10 text-sky-400/80 border-sky-500/20" },
  alpine: { label: "Alpine", color: "bg-indigo-500/10 text-indigo-400/80 border-indigo-500/20" },
};

/* ── Community mapping ────────────────────────────────────────────────── */

const PLACE_TO_COMMUNITY: Record<string, string> = {
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

/** Look up an internal community page link from a place name. */
export function placeToLink(name: string): string | null {
  const key = name.toLowerCase().trim();
  const id = PLACE_TO_COMMUNITY[key];
  if (id) return `/vision/aligned/${id}`;
  for (const [place, cid] of Object.entries(PLACE_TO_COMMUNITY)) {
    if (key.includes(place)) return `/vision/aligned/${cid}`;
  }
  return null;
}
