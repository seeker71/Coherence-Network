// space.ts — turn a Form run into a walkable 3D scene graph.
//
// The kernel walks a content-addressed recipe tree. This module reads that
// tree back out and shapes it into rooms you can navigate, so "what the
// kernel is doing" becomes a place rather than a log.
//
// The trinity (CLAUDE.md) maps to three visual registers:
//   Recipe (water)    → the room itself + its doorways + the trace-flow that
//                        pulses through them. How the computation HAPPENS.
//   Blueprint (ice)   → a frozen crystal skeleton derived from (level, type).
//                        Two cells with the same Blueprint carry the SAME
//                        crystal — structural equivalence made visible across
//                        rooms, even when the rooms sit far apart.
//   NamedCell (gas)   → a faint haze around identifier/name cells. Where a
//                        thing is diffusely individuated rather than composed.
//
// Doors are the "pointers as windows/doors" idea: each child of a recipe is a
// framed portal in the room wall; walking through it descends into the child
// recipe. A child that resolves to an already-seen cell becomes a loop-back
// portal (recursion and shared sub-shapes show as real architecture).
//
// The substrate lattice rasterizes to an RGBA framebuffer — the same memory
// plane the form-kernel runtime visualizer renders — and is projected as a
// texture onto the floor of the space (the "object surface as texture").

import {
  Frame,
  Kernel,
  Level,
  RBasic,
  RCmp,
  RMath,
  Trace,
  Triv,
  mathOp,
  nodeKey,
  walk,
  type NodeID,
} from "./vendor/kernel.ts";
import { readAll } from "./vendor/reader.ts";
import type { LocalFormTrace } from "./client.ts";

export type RGB = readonly [number, number, number];

// --- vocabulary reverse maps -------------------------------------------------

const RBASIC_NAME: Record<number, string> = {
  [RBasic.UNDEFINED]: "UNDEFINED",
  [RBasic.WITNESS]: "WITNESS",
  [RBasic.BLOCK]: "BLOCK",
  [RBasic.CALL]: "CALL",
  [RBasic.COND]: "COND",
  [RBasic.MATH]: "MATH",
  [RBasic.COMPARE]: "COMPARE",
  [RBasic.LOGIC]: "LOGIC",
  [RBasic.ACCESS]: "ACCESS",
  [RBasic.METHOD]: "METHOD",
  [RBasic.FNDEF]: "FNDEF",
  [RBasic.FNCALL]: "FNCALL",
  [RBasic.IDENT]: "IDENT",
  [RBasic.LIST]: "LIST",
  [RBasic.CHOICE]: "CHOICE",
  [RBasic.QUOTIENT]: "QUOTIENT",
  [RBasic.INDUCTIVE]: "INDUCTIVE",
  [RBasic.CONSTRUCTOR]: "CONSTRUCTOR",
  [RBasic.PROOF]: "PROOF",
  [RBasic.INFERENCE]: "INFERENCE",
  [RBasic.ALIAS]: "ALIAS",
  [RBasic.TRANSMUTE]: "TRANSMUTE",
  [RBasic.BLANKET]: "BLANKET",
  [RBasic.PROJECT]: "PROJECT",
  [RBasic.GENERATIVE]: "GENERATIVE",
  [RBasic.VECTOR]: "VECTOR",
  [RBasic.TILE]: "TILE",
  [RBasic.PARALLELIZE]: "PARALLELIZE",
  [RBasic.VECTORIZE]: "VECTORIZE",
  [RBasic.OBSERVER]: "OBSERVER",
};

const TRIV_NAME: Record<number, string> = {
  [Triv.INT]: "int",
  [Triv.STRING]: "str",
  [Triv.BOOL]: "bool",
  [Triv.NULL]: "null",
  [Triv.INT64]: "i64",
  [Triv.FLOAT32]: "f32",
  [Triv.FLOAT64]: "f64",
  [Triv.INT8]: "i8",
  [Triv.INT16]: "i16",
  [Triv.UINT8]: "u8",
  [Triv.UINT16]: "u16",
  [Triv.UINT32]: "u32",
  [Triv.UINT64]: "u64",
};

const MATH_GLYPH: Record<number, string> = {
  [RMath.PLUS]: "+",
  [RMath.MINUS]: "−",
  [RMath.MUL]: "×",
  [RMath.DIV]: "÷",
  [RMath.MOD]: "%",
};

const CMP_GLYPH: Record<number, string> = {
  [RCmp.EQ]: "=",
  [RCmp.NE]: "≠",
  [RCmp.LT]: "<",
  [RCmp.LE]: "≤",
  [RCmp.GT]: ">",
  [RCmp.GE]: "≥",
};

// --- deterministic NodeID → color (mirrors visualizer.nodeIDToColor) ---------

function mix32(x: number): number {
  x = (x ^ (x >>> 16)) >>> 0;
  x = Math.imul(x, 0x7feb352d) >>> 0;
  x = (x ^ (x >>> 15)) >>> 0;
  x = Math.imul(x, 0x846ca68b) >>> 0;
  x = (x ^ (x >>> 16)) >>> 0;
  return x;
}

function hashU32s(...words: number[]): number {
  let h = 0xc1da_b193 >>> 0;
  for (const w of words) h = mix32((h ^ (w >>> 0)) >>> 0);
  return h >>> 0;
}

function colorFromHash(h: number): RGB {
  return [(h & 0xff) / 255, ((h >>> 8) & 0xff) / 255, ((h >>> 16) & 0xff) / 255];
}

// Instance color — every distinct NodeID a distinct hue.
export function instanceColor(n: NodeID): RGB {
  return colorFromHash(hashU32s(n.pkg, n.level, n.type, n.inst));
}

// Blueprint color — ignores the instance counter. Same shape ⇒ same hue.
// This is the "ice" register: structural identity painted the same everywhere.
export function blueprintColor(n: NodeID): RGB {
  return colorFromHash(hashU32s(n.pkg, n.level, n.type));
}

// --- scene types -------------------------------------------------------------

export interface SpaceCell {
  id: string; // nodeKey — stable identity
  node: NodeID;
  kind: "recipe" | "leaf";
  arm: string; // RBasic arm name (recipes) or trivial type name (leaves)
  label: string; // short human label shown over the room / on the window
  value?: string; // leaf rendered value
  color: RGB; // instance color (water — this exact cell)
  blueprintColor: RGB; // blueprint color (ice — this shape)
  blueprintKey: string; // `${level}.${type}` — identical ⇒ identical crystal
  childIds: string[]; // ordered doors out of this room
  isName: boolean; // gas register — identifier cell
  depth: number; // first-seen depth from root
  heat: number; // 0..1 — share of total walks this arm took at runtime
  arity: number; // number of children
}

export interface KernelSpace {
  root: string;
  cells: Record<string, SpaceCell>;
  order: string[]; // discovery order (stable, deterministic)
  trace: LocalFormTrace;
  armHeat: Record<string, number>; // arm name → normalized walk share
  result: string;
  stdout: string;
  stderr: string;
  framebuffer: { width: number; height: number; rgba: Uint8Array };
  stats: {
    cells: number;
    recipes: number;
    leaves: number;
    maxDepth: number;
    totalWalks: number;
  };
}

// --- labelling ---------------------------------------------------------------

function leafLabel(k: Kernel, n: NodeID): { label: string; isName: boolean } {
  if (n.type === Triv.STRING) {
    try {
      const v = k.trivialValue(n);
      if (v.kind === "str") return { label: v.str, isName: true };
    } catch {
      /* fall through */
    }
    return { label: `str#${n.inst}`, isName: true };
  }
  try {
    const v = k.trivialValue(n);
    switch (v.kind) {
      case "int":
      case "i8":
      case "i16":
      case "u8":
      case "u16":
      case "u32":
        return { label: String(v.int), isName: false };
      case "i64":
      case "u64":
        return { label: String(v.bigint), isName: false };
      case "f32":
      case "f64":
        return { label: String(v.float), isName: false };
      case "bool":
        return { label: v.bool ? "true" : "false", isName: false };
      case "null":
        return { label: "null", isName: false };
    }
  } catch {
    /* fall through */
  }
  return { label: TRIV_NAME[n.type] ?? `t${n.type}`, isName: false };
}

function armLabel(category: NodeID): string {
  const name = RBASIC_NAME[category.type] ?? `arm${category.type}`;
  if (category.type === RBasic.MATH) {
    const glyph = MATH_GLYPH[mathOp(category.inst)];
    if (glyph) return `${name} ${glyph}`;
  }
  if (category.type === RBasic.COMPARE) {
    const glyph = CMP_GLYPH[category.inst];
    if (glyph) return `${name} ${glyph}`;
  }
  return name;
}

// --- framebuffer (lattice → RGBA, blueprint-colored) -------------------------

function renderLattice(
  k: Kernel,
  size = 96,
): { width: number; height: number; rgba: Uint8Array } {
  const cells: NodeID[] = [];
  for (const key of k.byID.keys()) {
    const p = key.split(".");
    if (p.length !== 4) continue;
    cells.push({
      pkg: +(p[0] ?? 0),
      level: +(p[1] ?? 0),
      type: +(p[2] ?? 0),
      inst: +(p[3] ?? 0),
    });
  }
  cells.sort((a, b) =>
    a.level !== b.level
      ? a.level - b.level
      : a.type !== b.type
        ? a.type - b.type
        : a.inst - b.inst,
  );
  const cols = Math.max(1, Math.ceil(Math.sqrt(cells.length)) || 1);
  const rows = cols;
  const rgba = new Uint8Array(size * size * 4);
  for (let i = 0; i < size * size; i++) {
    rgba[i * 4] = 10;
    rgba[i * 4 + 1] = 12;
    rgba[i * 4 + 2] = 18;
    rgba[i * 4 + 3] = 255;
  }
  const tileW = Math.max(1, (size / cols) | 0);
  const tileH = Math.max(1, (size / rows) | 0);
  cells.forEach((node, i) => {
    if (i >= cols * rows) return;
    const [r, g, b] = blueprintColor(node);
    const cx = (i % cols) * tileW;
    const cy = ((i / cols) | 0) * tileH;
    for (let y = cy; y < Math.min(size, cy + tileH); y++) {
      for (let x = cx; x < Math.min(size, cx + tileW); x++) {
        const off = (y * size + x) * 4;
        rgba[off] = (r * 255) | 0;
        rgba[off + 1] = (g * 255) | 0;
        rgba[off + 2] = (b * 255) | 0;
        rgba[off + 3] = 255;
      }
    }
  });
  return { width: size, height: size, rgba };
}

// --- builder -----------------------------------------------------------------

export function buildKernelSpace(source: string): KernelSpace {
  const stdout: string[] = [];
  const stderr: string[] = [];
  const kernel = new Kernel({
    writeStdout: (t) => stdout.push(t),
    writeStderr: (t) => stderr.push(t),
  });
  kernel.trace = new Trace();
  const root = readAll(kernel, source);
  let result = "";
  try {
    result = kernel.render(walk(kernel, root, new Frame(null)));
  } catch (err) {
    stderr.push(String(err instanceof Error ? err.message : err));
  }
  const trace = kernel.trace.toJSON() as LocalFormTrace;

  // arm name → normalized share of total walks (runtime heat per arm).
  const armHeat: Record<string, number> = {};
  const totalWalks = trace.total_walks || 1;
  for (const a of trace.arms) {
    armHeat[a.arm_name] = a.count / totalWalks;
  }

  // Walk the static recipe tree breadth-first from the root. The tree is
  // finite (recursion lives in execution, not structure); content-addressing
  // can make it a DAG, so a shared sub-shape becomes a loop-back door rather
  // than a duplicated room.
  const cells: Record<string, SpaceCell> = {};
  const order: string[] = [];
  const queue: Array<{ node: NodeID; depth: number }> = [
    { node: root, depth: 0 },
  ];
  let recipes = 0;
  let leaves = 0;
  let maxDepth = 0;

  while (queue.length > 0) {
    const { node, depth } = queue.shift()!;
    const id = nodeKey(node);
    if (cells[id]) continue;

    maxDepth = Math.max(maxDepth, depth);
    const recipe = kernel.recipeAt(node);

    if (!recipe) {
      // Trivial leaf — a value-window.
      const { label, isName } = leafLabel(kernel, node);
      leaves++;
      cells[id] = {
        id,
        node,
        kind: "leaf",
        arm: TRIV_NAME[node.type] ?? `t${node.type}`,
        label,
        value: label,
        color: instanceColor(node),
        blueprintColor: blueprintColor(node),
        blueprintKey: `${node.level}.${node.type}`,
        childIds: [],
        isName,
        depth,
        heat: 0,
        arity: 0,
      };
      order.push(id);
      continue;
    }

    recipes++;
    const kids = recipe.children;
    const arm = armLabel(recipe.category);
    const baseArm = RBASIC_NAME[recipe.category.type] ?? arm;
    cells[id] = {
      id,
      node,
      kind: "recipe",
      arm,
      label: arm,
      color: instanceColor(node),
      blueprintColor: blueprintColor(node),
      blueprintKey: `${node.level}.${node.type}`,
      childIds: kids.map((c) => nodeKey(c)),
      isName: recipe.category.type === RBasic.IDENT,
      depth,
      heat: armHeat[baseArm] ?? 0,
      arity: kids.length,
    };
    order.push(id);
    for (const c of kids) queue.push({ node: c, depth: depth + 1 });
  }

  return {
    root: nodeKey(root),
    cells,
    order,
    trace,
    armHeat,
    result,
    stdout: stdout.join(""),
    stderr: stderr.join(""),
    framebuffer: renderLattice(kernel),
    stats: {
      cells: order.length,
      recipes,
      leaves,
      maxDepth,
      totalWalks: trace.total_walks,
    },
  };
}

// --- layout ------------------------------------------------------------------
//
// Place rooms in 3D by depth (the "into-ness" axis) so walking forward is
// walking deeper into the computation. Siblings fan out around their depth
// ring; trivial leaves tuck close to their parents. Deterministic so the same
// Form always lays out the same way.

export interface CellLayout {
  id: string;
  position: readonly [number, number, number];
}

export function layoutSpace(space: KernelSpace): Record<string, CellLayout> {
  const depths: Record<number, string[]> = {};
  for (const id of space.order) {
    const d = space.cells[id]!.depth;
    (depths[d] ??= []).push(id);
  }
  const out: Record<string, CellLayout> = {};
  const ringGap = 16; // distance between depth rings along Z
  const radiusBase = 9;
  for (const [depthStr, ids] of Object.entries(depths)) {
    const depth = Number(depthStr);
    const z = -depth * ringGap;
    const n = ids.length;
    if (n === 1) {
      out[ids[0]!] = { id: ids[0]!, position: [0, 0, z] };
      continue;
    }
    const radius = radiusBase + n * 1.2;
    ids.forEach((id, i) => {
      const a = (i / n) * Math.PI * 2;
      out[id] = {
        id,
        position: [Math.cos(a) * radius, Math.sin(a) * (radius * 0.35), z],
      };
    });
  }
  return out;
}
