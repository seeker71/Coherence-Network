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
  RBlock,
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

// dataType — the leaf's trivial flavor, used to pick geometry + surface so an
// int reads as a faceted gem, a float as a droplet, a string as a tablet, a
// bool as a coin, null as a hollow shell. Recipes carry "" (their shape is the
// room, not the object).
export type DataType =
  | "int"
  | "float"
  | "string"
  | "bool"
  | "null"
  | "";

// container — recipes whose children have a known logical layout. A LIST is an
// ordered spine; a LET binding is a (name → value) pair; a BLOCK/DO is a
// sequence of statements. Other recipes leave children on the depth ring.
export type Container = "list" | "binding" | "sequence" | null;

export interface SpaceCell {
  id: string; // nodeKey — stable identity
  node: NodeID;
  kind: "recipe" | "leaf";
  arm: string; // RBasic arm name (recipes) or trivial type name (leaves)
  dataType: DataType; // leaf flavor — drives object geometry + surface
  container: Container; // logical child layout for known blueprint shapes
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
  hz?: number; // resonant frequency, when the cell carries one (vision concepts)
  note?: string; // optional sourced description (presence/field cells)
}

export interface KernelSpace {
  root: string;
  cells: Record<string, SpaceCell>;
  order: string[]; // discovery order (stable, deterministic)
  parentOf: Record<string, string | null>; // first-seen parent — drill pop-out
  trace: LocalFormTrace;
  armHeat: Record<string, number>; // arm name → normalized walk share
  result: string;
  stdout: string;
  stderr: string;
  framebuffer: { width: number; height: number; rgba: Uint8Array; tiles: number };
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

function dataTypeOf(n: NodeID): DataType {
  switch (n.type) {
    case Triv.INT:
    case Triv.INT64:
    case Triv.INT8:
    case Triv.INT16:
    case Triv.UINT8:
    case Triv.UINT16:
    case Triv.UINT32:
    case Triv.UINT64:
      return "int";
    case Triv.FLOAT32:
    case Triv.FLOAT64:
      return "float";
    case Triv.STRING:
      return "string";
    case Triv.BOOL:
      return "bool";
    case Triv.NULL:
      return "null";
    default:
      return "";
  }
}

function containerOf(category: NodeID): Container {
  if (category.type === RBasic.LIST) return "list";
  if (category.type === RBasic.BLOCK) {
    return category.inst === RBlock.LET ? "binding" : "sequence";
  }
  return null;
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
): { width: number; height: number; rgba: Uint8Array; tiles: number } {
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
  return { width: size, height: size, rgba, tiles: cols };
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
  const parentOf: Record<string, string | null> = { [nodeKey(root)]: null };
  const queue: Array<{ node: NodeID; depth: number; parent: string | null }> = [
    { node: root, depth: 0, parent: null },
  ];
  let recipes = 0;
  let leaves = 0;
  let maxDepth = 0;

  while (queue.length > 0) {
    const { node, depth, parent } = queue.shift()!;
    const id = nodeKey(node);
    if (parentOf[id] === undefined) parentOf[id] = parent;
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
        dataType: dataTypeOf(node),
        container: null,
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
      dataType: "",
      container: containerOf(recipe.category),
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
    for (const c of kids) queue.push({ node: c, depth: depth + 1, parent: id });
  }

  return {
    root: nodeKey(root),
    cells,
    order,
    parentOf,
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
  spine: boolean; // true ⇒ a compact object inside a parent's logical layout
  index: number; // position within the parent's child order (spine ordering)
}

// layoutSpace — place the subtree rooted at `rootId` (default the whole space).
// Re-rooting is the drill mechanic: entering a recipe lays out only its subtree,
// so a detail becomes the world. Ring cells (ordinary recipes) sit on depth
// rings along the into-axis; the children of a container cell (list / binding /
// sequence) instead lay out as an ordered spine in front of their parent, so a
// list reads as a list and a binding reads as name → value.
export function layoutSpace(
  space: KernelSpace,
  rootId: string = space.root,
): Record<string, CellLayout> {
  const out: Record<string, CellLayout> = {};
  if (!space.cells[rootId]) return out;

  // BFS from rootId — depth + traversal parent over the static child edges.
  const depthOf: Record<string, number> = { [rootId]: 0 };
  const tParent: Record<string, string | null> = { [rootId]: null };
  const orderBfs: string[] = [];
  const seen = new Set<string>([rootId]);
  const q: string[] = [rootId];
  while (q.length) {
    const id = q.shift()!;
    orderBfs.push(id);
    const cell = space.cells[id];
    if (!cell) continue;
    for (const c of cell.childIds) {
      if (seen.has(c) || !space.cells[c]) continue;
      seen.add(c);
      depthOf[c] = (depthOf[id] ?? 0) + 1;
      tParent[c] = id;
      q.push(c);
    }
  }

  const parentContainerOf = (id: string): Container => {
    const p = tParent[id];
    return p != null ? (space.cells[p]?.container ?? null) : null;
  };
  const isSpine = (id: string) => parentContainerOf(id) != null;

  // Ring cells — reachable, not laid out as a spine child. Depth → Z ring.
  const ringByDepth: Record<number, string[]> = {};
  for (const id of orderBfs) {
    if (isSpine(id)) continue;
    (ringByDepth[depthOf[id] ?? 0] ??= []).push(id);
  }
  const ringGap = 16;
  const radiusBase = 9;
  for (const [dStr, ids] of Object.entries(ringByDepth)) {
    const z = -Number(dStr) * ringGap;
    const n = ids.length;
    if (n === 1) {
      out[ids[0]!] = { id: ids[0]!, position: [0, 0, z], spine: false, index: 0 };
      continue;
    }
    const radius = radiusBase + n * 1.2;
    ids.forEach((id, i) => {
      const a = (i / n) * Math.PI * 2;
      out[id] = {
        id,
        position: [Math.cos(a) * radius, Math.sin(a) * (radius * 0.35), z],
        spine: false,
        index: i,
      };
    });
  }

  // Spine children — ordered line in front of and below their container parent,
  // in the exact child order the recipe carries. BFS order means a parent is
  // already placed before we lay out its children (lists can nest in lists).
  const spacing = 3.4;
  for (const parentId of orderBfs) {
    const parent = space.cells[parentId];
    if (!parent || parent.container == null) continue;
    const base = out[parentId]?.position;
    if (!base) continue;
    const kids = parent.childIds.filter((c) => seen.has(c));
    const n = kids.length;
    kids.forEach((cid, i) => {
      if (out[cid]) return;
      const offset = (i - (n - 1) / 2) * spacing;
      out[cid] = {
        id: cid,
        position: [base[0] + offset, base[1] - 4.6, base[2] + 4],
        spine: true,
        index: i,
      };
    });
  }

  return out;
}
