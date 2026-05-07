/**
 * Spectrum colors for the seven canonical edge-type families.
 *
 * Every relationship in this body carries a frequency. Ontological
 * edges paint violet (the ground of being); operational edges paint
 * gold (the warm hand of giving); knowledge edges paint blue (the
 * crystalline architecture); and so on across the seven families.
 * The palette is the visible spectrum of the connection.
 *
 * Edge type families come from `api/app/config/edge_types.py` —
 * the single source of truth for relationship types in the network.
 * Adding a new family means: new entry here + new entry there.
 *
 * Each family declares hue/saturation/lightness for both light and
 * dark themes. The chip and the link inherit the family's color
 * with reduced saturation for the surface and full saturation for
 * the text and the connecting line.
 */

export type EdgeFamilySlug =
  | "ontological"
  | "process"
  | "knowledge"
  | "scale"
  | "temporal"
  | "tension"
  | "attribution";

export type EdgeFamilyTone = {
  /** Hue in degrees (0–360). The single number that carries the family. */
  hue: number;
  /** Saturation/lightness for the chip text + connecting line. Bright. */
  saturation: number;
  lightness: number;
  /** Slightly dimmer values for the chip background fill. Soft. */
  bgSaturation: number;
  bgLightness: number;
};

export type EdgeFamily = {
  slug: EdgeFamilySlug;
  /** Display label for the family heading. */
  name: string;
  /** A felt-sense description of what this family of relationships
   *  carries. Shown as a tooltip on the family heading. */
  feeling: string;
  light: EdgeFamilyTone;
  dark: EdgeFamilyTone;
};

export const EDGE_FAMILIES: readonly EdgeFamily[] = [
  {
    slug: "ontological",
    name: "Being",
    feeling:
      "Resonance and emergence — what this presence is in relation to other forms of being.",
    light: { hue: 270, saturation: 50, lightness: 55, bgSaturation: 55, bgLightness: 92 },
    dark: { hue: 270, saturation: 70, lightness: 70, bgSaturation: 50, bgLightness: 22 },
  },
  {
    slug: "process",
    name: "Transformation",
    feeling:
      "Catalysts and changes — what this presence enables, blocks, amplifies, or transforms.",
    light: { hue: 25, saturation: 75, lightness: 50, bgSaturation: 75, bgLightness: 92 },
    dark: { hue: 25, saturation: 80, lightness: 65, bgSaturation: 60, bgLightness: 22 },
  },
  {
    slug: "knowledge",
    name: "Structure",
    feeling:
      "Architecture — what this presence implements, extends, refines, or stands in tension with as a structure of thought.",
    light: { hue: 215, saturation: 60, lightness: 50, bgSaturation: 65, bgLightness: 92 },
    dark: { hue: 215, saturation: 70, lightness: 70, bgSaturation: 50, bgLightness: 22 },
  },
  {
    slug: "scale",
    name: "Scale",
    feeling:
      "Fractals and aggregates — how this presence composes, decomposes, and repeats across scales.",
    light: { hue: 145, saturation: 50, lightness: 45, bgSaturation: 55, bgLightness: 92 },
    dark: { hue: 145, saturation: 60, lightness: 60, bgSaturation: 50, bgLightness: 22 },
  },
  {
    slug: "temporal",
    name: "Time",
    feeling:
      "Sequence and cause — what precedes, follows, triggers, resolves, or co-occurs with this presence.",
    light: { hue: 240, saturation: 55, lightness: 50, bgSaturation: 60, bgLightness: 92 },
    dark: { hue: 240, saturation: 65, lightness: 70, bgSaturation: 50, bgLightness: 22 },
  },
  {
    slug: "tension",
    name: "Tension",
    feeling:
      "Productive friction — paradoxes held, polarities bridged, integrations earned.",
    light: { hue: 340, saturation: 65, lightness: 55, bgSaturation: 70, bgLightness: 92 },
    dark: { hue: 340, saturation: 75, lightness: 70, bgSaturation: 55, bgLightness: 22 },
  },
  {
    slug: "attribution",
    name: "Attribution",
    feeling:
      "The warm hand — what this presence contributes to, is rooted in, is inspired by, depends on.",
    light: { hue: 40, saturation: 75, lightness: 48, bgSaturation: 80, bgLightness: 92 },
    dark: { hue: 40, saturation: 80, lightness: 65, bgSaturation: 60, bgLightness: 22 },
  },
] as const;

const FAMILY_BY_SLUG: Record<EdgeFamilySlug, EdgeFamily> = Object.fromEntries(
  EDGE_FAMILIES.map((f) => [f.slug, f]),
) as Record<EdgeFamilySlug, EdgeFamily>;

/**
 * Map of canonical edge type → family slug. Mirrors the families
 * in `api/app/config/edge_types.py`. Synced manually; if a new
 * canonical edge type is introduced there it must also land here.
 */
export const EDGE_TYPE_TO_FAMILY: Record<string, EdgeFamilySlug> = {
  // ontological
  "resonates-with": "ontological",
  "emerges-from": "ontological",
  "transcends": "ontological",
  "instantiates": "ontological",
  "embodies": "ontological",
  "reflects": "ontological",
  // process
  "transforms-into": "process",
  "enables": "process",
  "blocks": "process",
  "catalyzes": "process",
  "stabilizes": "process",
  "amplifies": "process",
  "dampens": "process",
  // knowledge
  "implements": "knowledge",
  "extends": "knowledge",
  "refines": "knowledge",
  "generalises": "knowledge",
  "contradicts": "knowledge",
  "complements": "knowledge",
  "subsumes": "knowledge",
  // scale
  "fractal-scaling": "scale",
  "composes-from": "scale",
  "decomposes-into": "scale",
  "aggregates": "scale",
  "specialises": "scale",
  // temporal
  "precedes": "temporal",
  "follows": "temporal",
  "co-occurs-with": "temporal",
  "triggers": "temporal",
  "resolves": "temporal",
  "iterates": "temporal",
  // tension
  "paradox-resolution": "tension",
  "polarity-of": "tension",
  "tension-with": "tension",
  "bridges": "tension",
  "integrates": "tension",
  // attribution
  "contributes-to": "attribution",
  "funded-by": "attribution",
  "inspired-by": "attribution",
  "referenced-by": "attribution",
  "challenges": "attribution",
  "validates": "attribution",
  "invalidates": "attribution",
  "analogous-to": "attribution",
  "depends-on": "attribution",
  "precondition-of": "attribution",
  "at-place": "attribution",
};

/**
 * Convert a family tone into an `hsl(h s% l%)` CSS string.
 * Use the bg variant for surface fills, the main variant for text
 * and connector lines.
 */
export function hsl(tone: EdgeFamilyTone, surface: "fg" | "bg" = "fg"): string {
  const s = surface === "bg" ? tone.bgSaturation : tone.saturation;
  const l = surface === "bg" ? tone.bgLightness : tone.lightness;
  return `hsl(${tone.hue} ${s}% ${l}%)`;
}

export function familyForEdgeType(edgeType: string): EdgeFamily {
  const slug = EDGE_TYPE_TO_FAMILY[edgeType];
  // Unknown edge types fall to the attribution family — the warm
  // default, since most ad-hoc relationships are credit-shaped.
  return FAMILY_BY_SLUG[slug ?? "attribution"];
}

/**
 * Display label for a canonical edge type. Replaces hyphens with
 * spaces and renders sentence-case. "resonates-with" → "Resonates with".
 */
export function edgeTypeLabel(edgeType: string): string {
  if (!edgeType) return "";
  const words = edgeType.replace(/-/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}
