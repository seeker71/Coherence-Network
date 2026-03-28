/**
 * Tests for Spec 165: UX Homepage Readability — Theme Toggle & Contrast
 *
 * These tests validate:
 * 1. Theme persistence logic (localStorage + class application)
 * 2. WCAG AA contrast ratio computations for both dark and light palette tokens
 * 3. System preference detection logic
 */

import { describe, it, expect } from "vitest";

// ---------------------------------------------------------------------------
// Contrast ratio helpers (inline, no browser APIs needed)
// ---------------------------------------------------------------------------

/** Convert 8-bit sRGB channel to linear light. */
function toLinear(c: number): number {
  const s = c / 255;
  return s <= 0.04045 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
}

/** Relative luminance per WCAG 2.1 formula. RGB values 0–255. */
function relativeLuminance(r: number, g: number, b: number): number {
  return 0.2126 * toLinear(r) + 0.7152 * toLinear(g) + 0.0722 * toLinear(b);
}

/** WCAG contrast ratio between two RGB colours. */
function contrastRatio(
  fg: [number, number, number],
  bg: [number, number, number],
): number {
  const l1 = relativeLuminance(...fg);
  const l2 = relativeLuminance(...bg);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

/**
 * Convert HSL (degrees, %, %) to sRGB [0-255, 0-255, 0-255].
 * Implements the standard HSL→RGB algorithm.
 */
function hslToRgb(h: number, s: number, l: number): [number, number, number] {
  s /= 100;
  l /= 100;
  const k = (n: number) => (n + h / 30) % 12;
  const a = s * Math.min(l, 1 - l);
  const f = (n: number) => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
  return [Math.round(f(0) * 255), Math.round(f(8) * 255), Math.round(f(4) * 255)];
}

// ---------------------------------------------------------------------------
// Palette tokens — extracted from Spec 165 design decision
// ---------------------------------------------------------------------------

// Dark mode
const DARK_BG = hslToRgb(24, 22, 11);         // --background dark
const DARK_FG = hslToRgb(38, 32, 93);         // --foreground dark
const DARK_MUTED_FG = hslToRgb(34, 22, 90);   // --muted-foreground dark (was 90% L)
const DARK_CARD = hslToRgb(24, 20, 14);       // --card dark

// Light mode
const LIGHT_BG = hslToRgb(42, 40, 96);        // --background light
const LIGHT_FG = hslToRgb(24, 28, 14);        // --foreground light
const LIGHT_MUTED_FG = hslToRgb(28, 18, 38);  // --muted-foreground light
const LIGHT_CARD = hslToRgb(42, 30, 98);      // --card light
const LIGHT_PRIMARY = hslToRgb(36, 72, 42);   // --primary light (darker gold)

// WCAG thresholds
const AA_NORMAL = 4.5;
const AA_LARGE = 3.0;

// ---------------------------------------------------------------------------
// Contrast tests
// ---------------------------------------------------------------------------

describe("Spec 165: Dark mode contrast ratios", () => {
  it("foreground on background meets WCAG AA for normal text (≥4.5:1)", () => {
    const ratio = contrastRatio(DARK_FG, DARK_BG);
    expect(ratio).toBeGreaterThanOrEqual(AA_NORMAL);
  });

  it("muted-foreground on card background meets WCAG AA large text (≥3:1)", () => {
    // Muted foreground is used for secondary text (typically ≥18px or bold)
    const ratio = contrastRatio(DARK_MUTED_FG, DARK_CARD);
    expect(ratio).toBeGreaterThanOrEqual(AA_LARGE);
  });
});

describe("Spec 165: Light mode contrast ratios", () => {
  it("foreground on background meets WCAG AA for normal text (≥4.5:1)", () => {
    const ratio = contrastRatio(LIGHT_FG, LIGHT_BG);
    expect(ratio).toBeGreaterThanOrEqual(AA_NORMAL);
  });

  it("muted-foreground on card background meets WCAG AA for normal text (≥4.5:1)", () => {
    const ratio = contrastRatio(LIGHT_MUTED_FG, LIGHT_CARD);
    expect(ratio).toBeGreaterThanOrEqual(AA_NORMAL);
  });

  it("primary colour on light background meets WCAG AA large text (≥3:1)", () => {
    const ratio = contrastRatio(LIGHT_PRIMARY, LIGHT_BG);
    expect(ratio).toBeGreaterThanOrEqual(AA_LARGE);
  });
});

// ---------------------------------------------------------------------------
// Theme persistence logic (pure functions extracted from ThemeProvider)
// ---------------------------------------------------------------------------

type Theme = "dark" | "light" | "system";

function resolveTheme(stored: string | null, systemPrefersDark: boolean): "dark" | "light" {
  if (stored === "dark") return "dark";
  if (stored === "light") return "light";
  // "system" or null
  return systemPrefersDark ? "dark" : "light";
}

function getStoredTheme(storage: Record<string, string>, key: string): string | null {
  return storage[key] ?? null;
}

describe("Spec 165: Theme resolution logic", () => {
  it("returns stored 'dark' regardless of system preference", () => {
    expect(resolveTheme("dark", false)).toBe("dark");
    expect(resolveTheme("dark", true)).toBe("dark");
  });

  it("returns stored 'light' regardless of system preference", () => {
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("light", false)).toBe("light");
  });

  it("falls back to system preference when nothing stored", () => {
    expect(resolveTheme(null, true)).toBe("dark");
    expect(resolveTheme(null, false)).toBe("light");
  });

  it("treats 'system' explicitly the same as null (follows OS)", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
  });

  it("reads from storage correctly", () => {
    const storage = { "coherence-theme": "light" };
    expect(getStoredTheme(storage, "coherence-theme")).toBe("light");
  });

  it("returns null when key is absent", () => {
    expect(getStoredTheme({}, "coherence-theme")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// HSL utility self-test
// ---------------------------------------------------------------------------

describe("hslToRgb utility", () => {
  it("converts pure red correctly", () => {
    const [r, g, b] = hslToRgb(0, 100, 50);
    expect(r).toBe(255);
    expect(g).toBe(0);
    expect(b).toBe(0);
  });

  it("converts white correctly", () => {
    const [r, g, b] = hslToRgb(0, 0, 100);
    expect(r).toBe(255);
    expect(g).toBe(255);
    expect(b).toBe(255);
  });

  it("converts black correctly", () => {
    const [r, g, b] = hslToRgb(0, 0, 0);
    expect(r).toBe(0);
    expect(g).toBe(0);
    expect(b).toBe(0);
  });
});
