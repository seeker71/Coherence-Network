/**
 * Shared utilities for Living Collective vision pages.
 *
 * This is the single source of truth for:
 * - Concept ID → display name conversion
 * - Hz frequency → color mapping
 * - Inline markdown → safe HTML conversion
 * - Story visual → static image path resolution
 *
 * Static data maps live in ./data/vision-data.ts (editable without
 * touching these functions). Re-exported here for backward compat.
 */

export {
  HZ_COLORS,
  EDGE_LABELS,
  RESOURCE_ICONS,
  CLIMATE_LABELS,
  PLACE_TO_COMMUNITY,
  LEVEL_LABELS,
  LEVEL_COLORS,
} from "./data/vision-data";

import { HZ_COLORS, PLACE_TO_COMMUNITY } from "./data/vision-data";

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

/* ── Community mapping ────────────────────────────────────────────────── */

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
