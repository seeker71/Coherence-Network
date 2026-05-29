// disposition.ts — a cell's agency over its own boundary.
//
// Every other lens is how *we* choose to see a cell. A disposition is how the
// *cell* chooses to show itself: which inner state it turns into its surface,
// and how it decides to react to being observed and touched. The choice is not
// arbitrary — it is read from what the cell IS (container / leaf / hot / deep),
// so the cell's self-presentation is faithful to its own nature.
//
// Observation is *felt* — the surface blooms, flares, or withdraws. Touch is
// *answered* — the cell speaks back through the channel in the first person.

import type { SpaceCell } from "./space";

export type SurfaceMode = "rings" | "strata" | "turbulence" | "fracture";
export type ReactStyle = "bloom" | "flare" | "shy" | "ripple";

const MODE_INDEX: Record<SurfaceMode, number> = {
  rings: 0,
  strata: 1,
  turbulence: 2,
  fracture: 3,
};

export interface Disposition {
  mode: SurfaceMode;
  modeIndex: number;
  surfaces: string; // the inner state turned into surface
  react: ReactStyle;
  // shader reaction parameters — how observation/touch reshape the surface
  observeBrighten: number; // + brightens when watched, − withdraws
  observeScale: number; // pattern opens (>1) or tightens (<1) under attention
  observeSaturate: number; // + colour floods in, − it drains
  touchFlash: number; // brightness burst on contact
  rippleAmp: number; // surface ripple amplitude on contact
  shy: number; // 0..1 — how much it fades when unobserved
}

const REACT: Record<ReactStyle, Omit<Disposition, "mode" | "modeIndex" | "surfaces" | "react">> = {
  bloom: { observeBrighten: 0.9, observeScale: 1.45, observeSaturate: 0.5, touchFlash: 1.7, rippleAmp: 0.22, shy: 0 },
  flare: { observeBrighten: 1.4, observeScale: 1.1, observeSaturate: 0.25, touchFlash: 2.6, rippleAmp: 0.14, shy: 0 },
  shy: { observeBrighten: -0.25, observeScale: 0.82, observeSaturate: -0.55, touchFlash: 0.9, rippleAmp: 0.34, shy: 1 },
  ripple: { observeBrighten: 0.6, observeScale: 1.65, observeSaturate: 0.15, touchFlash: 1.3, rippleAmp: 0.5, shy: 0 },
};

// The cell decides — reading its own structure.
export function disposition(cell: SpaceCell): Disposition {
  let mode: SurfaceMode;
  let react: ReactStyle;
  let surfaces: string;

  if (cell.container != null) {
    // a container shows what it holds: its children, layered as strata
    mode = "strata";
    react = "bloom";
    surfaces = `its ${cell.arity} children`;
  } else if (cell.kind === "leaf") {
    // a value-cell is quiet — it rings softly and shies from attention
    mode = "rings";
    react = "shy";
    surfaces = cell.value ? `its value (${cell.value})` : "its stored value";
  } else if (cell.heat > 0.15) {
    // a hot cell burns its runtime activity onto its skin
    mode = "turbulence";
    react = "flare";
    surfaces = `its heat (${cell.heat.toFixed(2)})`;
  } else if (cell.depth >= 3) {
    // a deep cell cracks its surface into self-similar recursion
    mode = "fracture";
    react = "ripple";
    surfaces = `its depth (${cell.depth} deep)`;
  } else {
    mode = "rings";
    react = "bloom";
    surfaces = cell.hz ? `its frequency (${cell.hz}Hz)` : "its frequency";
  }

  return { mode, modeIndex: MODE_INDEX[mode], surfaces, react, ...REACT[react] };
}

// The cell's first-person account — what it is doing with its surface, and how
// it meets contact. This is the reply that touch sends into the channel.
export function speak(
  cell: SpaceCell,
  event: "rest" | "observed" | "touched",
): string {
  const d = disposition(cell);
  const rest: Record<SurfaceMode, string> = {
    strata: `I hold ${cell.arity} within me — my skin is their colours, layered.`,
    turbulence: `My work runs hot (${cell.heat.toFixed(2)}); I let it churn across my surface.`,
    fracture: `I went ${cell.depth} deep — my recursion cracks me into self-similar cells.`,
    rings: cell.hz
      ? `I rest at ${cell.hz}Hz; my frequency rings out in slow circles.`
      : `I ring my own note out in slow circles.`,
  };
  if (event === "rest") return rest[d.mode];

  const observed: Record<ReactStyle, string> = {
    bloom: "You're watching — I bloom, and let more of myself rise to the surface.",
    flare: "Seen — I flare; the flow quickens where your attention lands.",
    shy: "Watched, I draw inward — colour drains, I grow quiet and dim.",
    ripple: "Under your gaze my detail sharpens, fold within fold.",
  };
  if (event === "observed") return observed[d.react];

  const mine = d.surfaces.replace(/^its /, "my ");
  const touched: Record<ReactStyle, string> = {
    bloom: `Touched — I open, and let you see ${mine} bright across me.`,
    flare: `Touched — I burst, and all of ${mine} rises at once.`,
    shy: `Touched — I ripple once, show ${mine}, then settle back.`,
    ripple: `Touched — a wave runs out through me, ${mine} rippling in rings.`,
  };
  return touched[d.react];
}
