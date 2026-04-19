/**
 * Per-provider brand tokens.
 *
 * Every platform carries its own frequency. The presence row pulls
 * from here so each button *looks* like the platform it points to
 * rather than a uniform chip. Colors are kept in HSL-friendly hex so
 * callers can drop them directly into inline styles, and each entry
 * has an optional gradient for platforms whose brand is a gradient.
 */

export type BrandTone = {
  label: string;
  bg: string;
  fg: string;
  gradient?: string;
};

export const PROVIDER_BRAND: Record<string, BrandTone> = {
  bandcamp: { label: "Bandcamp", bg: "#1da0c3", fg: "#ffffff" },
  spotify: { label: "Spotify", bg: "#1ed760", fg: "#000000" },
  youtube: { label: "YouTube", bg: "#ff0000", fg: "#ffffff" },
  soundcloud: { label: "SoundCloud", bg: "#ff5500", fg: "#ffffff" },
  "apple-music": {
    label: "Apple Music",
    bg: "#fa243c",
    fg: "#ffffff",
    gradient: "linear-gradient(135deg,#fa243c,#a445b2)",
  },
  substack: { label: "Substack", bg: "#ff6719", fg: "#ffffff" },
  patreon: { label: "Patreon", bg: "#f96854", fg: "#ffffff" },
  instagram: {
    label: "Instagram",
    bg: "#e1306c",
    fg: "#ffffff",
    gradient: "linear-gradient(135deg,#f09433,#e6683c,#dc2743,#cc2366,#bc1888)",
  },
  tiktok: {
    label: "TikTok",
    bg: "#000000",
    fg: "#ffffff",
    gradient: "linear-gradient(135deg,#25f4ee,#000000 45%,#fe2c55)",
  },
  x: { label: "X", bg: "#000000", fg: "#ffffff" },
  twitter: { label: "X", bg: "#000000", fg: "#ffffff" },
  facebook: { label: "Facebook", bg: "#1877f2", fg: "#ffffff" },
  linktree: { label: "Linktree", bg: "#43e660", fg: "#0b1711" },
  wikipedia: { label: "Wikipedia", bg: "#000000", fg: "#ffffff" },
  web: { label: "Site", bg: "#3f3f46", fg: "#ffffff" },
};

export function brandFor(provider: string | null | undefined): BrandTone {
  if (!provider) return PROVIDER_BRAND.web;
  return PROVIDER_BRAND[provider] || { ...PROVIDER_BRAND.web, label: provider };
}
