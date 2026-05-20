// visualizer — substrate GPU framebuffer rendering, in Form.
//
// Task #5. Reads the substrate's content-addressed lattice and renders cells
// as colored pixels in a 2D grid. Each NodeID is hashed to a deterministic
// RGBA color so structurally-equivalent cells (same Blueprint NodeID — same
// `pkg.level.type` family or same interned recipe shape) share visual
// identity. Recipe trees lay out spatially by composition depth (Level
// hierarchy) when requested.
//
// The substrate is the body. The framebuffer is the surface where the body
// becomes visible at a glance: rows of pixels are the lattice's basic level
// (Level.BASIC) and trivial level (Level.TRIVIAL) cells, color is identity,
// neighborhood is depth. Two cells with the same Blueprint paint to the
// same color regardless of where they live in the grid — sameness is the
// thing the eye picks up.
//
// Three deliverable surfaces:
//
//   1. CPU renderer (`renderToRGBA8`) — synchronous, no dependencies, used
//      as the fallback in environments without WebGPU and as the reference
//      oracle for the GPU path. Produces a Uint8Array of width*height*4
//      bytes laid out R,G,B,A,R,G,B,A,...
//
//   2. Form recipe-tree builder (`renderSubstrate`) — emits a recipe tree
//      that describes the render pipeline as Form code. The tree composes
//      from format-recipes (UINT8 quartet for RGBA channels, FP32 for shader
//      uniforms) once the format-recipes module lands; until then this
//      module composes from RBasic primitives directly (additive — the
//      shape is what matters; the seam is documented).
//
//   3. WGSL emitter (`compileToWGSL`) — turns the render recipe into a
//      WebGPU @compute shader source string. This module ships a small,
//      self-contained WGSL emitter for the visualizer's pipeline that does
//      not depend on the (future) general-purpose WGSL backend; when the
//      general backend lands, `compileToWGSL` switches to delegating
//      arithmetic-shaped sub-recipes to it. The seam is the `WgslEmitter`
//      interface below.
//
// Architecture in one line:
//
//   substrate lattice → cell list → grid layout → recipe tree → WGSL
//                                                            ↘ CPU RGBA8
//
// Everything composes; nothing is destructive. The substrate is read-only
// here. The visualizer adds no nodes to the lattice.

import {
  Kernel,
  Level,
  RBasic,
  RBlock,
  RMath,
  Triv,
  nodeKey,
  type NodeID,
} from "./kernel.ts";

// ---------------------------------------------------------------------------
// Config & types
// ---------------------------------------------------------------------------

export type ColorScheme = "blueprint" | "instance" | "level";

export interface VisualizerConfig {
  readonly width: number; // pixel width of the output framebuffer
  readonly height: number; // pixel height
  readonly gridCols: number; // logical cells across (one cell renders to a tile)
  readonly gridRows: number; // logical cells down
  readonly colorScheme: ColorScheme;
  readonly layout: "instance" | "depth"; // grid layout strategy
  readonly background: RGBA8; // empty-cell color
}

export const DEFAULT_CONFIG: VisualizerConfig = {
  width: 256,
  height: 256,
  gridCols: 64,
  gridRows: 64,
  colorScheme: "blueprint",
  layout: "instance",
  background: [16, 16, 16, 255],
};

// RGBA8 — four u8 channels, the on-wire pixel format. Matches WGSL
// `rgba8unorm` and `Uint8Array` exactly, no endianness games.
export type RGBA8 = readonly [number, number, number, number];

export interface CellPosition {
  readonly node: NodeID;
  readonly col: number;
  readonly row: number;
}

export type CellPositions = readonly CellPosition[];

// ---------------------------------------------------------------------------
// nodeIDToColor — deterministic hash mapping NodeID → 4×u8
// ---------------------------------------------------------------------------
//
// Two cells with identical Blueprint NodeID hash to the same color in
// `blueprint` mode — that's the structural-equivalence seeing-at-a-glance.
// `instance` mode includes the instance counter so siblings are
// distinguishable. `level` mode buckets by Level (trivial vs basic) and
// uses type as the dominant channel, giving the eye a fast read on
// "what kind of node lives here."
//
// The hash is a tiny PCG-ish mix on the packed 4×u32; deterministic across
// runs, no state, no dependencies. Same NodeID → same RGBA always.

function mix32(x: number): number {
  // 32-bit avalanche mix. Same constants as xorshift32 / lowbias32 family.
  x = (x ^ (x >>> 16)) >>> 0;
  x = Math.imul(x, 0x7feb352d) >>> 0;
  x = (x ^ (x >>> 15)) >>> 0;
  x = Math.imul(x, 0x846ca68b) >>> 0;
  x = (x ^ (x >>> 16)) >>> 0;
  return x;
}

function hashU32s(...words: number[]): number {
  let h = 0xc1da_b193 >>> 0;
  for (const w of words) {
    h = mix32((h ^ (w >>> 0)) >>> 0);
  }
  return h >>> 0;
}

export function nodeIDToColor(
  node: NodeID,
  scheme: ColorScheme = "blueprint",
): RGBA8 {
  let h: number;
  switch (scheme) {
    case "blueprint":
      // Identity ignores the instance counter. Same shape ⇒ same color.
      h = hashU32s(node.pkg, node.level, node.type);
      break;
    case "instance":
      // Full 4-tuple — every NodeID distinct.
      h = hashU32s(node.pkg, node.level, node.type, node.inst);
      break;
    case "level":
      // Level dominates the red channel; type drives green; pkg drives
      // blue. Gives a categorical read at a glance.
      return [
        (node.level * 89) & 0xff,
        (node.type * 53) & 0xff,
        (node.pkg * 31) & 0xff,
        255,
      ];
  }
  // Spread 32 bits over three channels with alpha pinned opaque.
  const r = h & 0xff;
  const g = (h >>> 8) & 0xff;
  const b = (h >>> 16) & 0xff;
  return [r, g, b, 255];
}

// ---------------------------------------------------------------------------
// Cell collection — pulls a snapshot of the lattice
// ---------------------------------------------------------------------------
//
// The kernel's internal Map keys are stable strings (`pkg.level.type.inst`).
// We reconstruct NodeIDs by re-parsing those keys. This is the read-only
// substrate read — same idea as a coh substrate stats / annotate call.

export function collectCells(k: Kernel): NodeID[] {
  const out: NodeID[] = [];
  for (const key of k.byID.keys()) {
    const parts = key.split(".");
    if (parts.length !== 4) continue;
    const pkg = parseInt(parts[0] ?? "0", 10);
    const level = parseInt(parts[1] ?? "0", 10);
    const type = parseInt(parts[2] ?? "0", 10);
    const inst = parseInt(parts[3] ?? "0", 10);
    if (
      Number.isFinite(pkg) &&
      Number.isFinite(level) &&
      Number.isFinite(type) &&
      Number.isFinite(inst)
    ) {
      out.push({ pkg, level, type, inst });
    }
  }
  // Stable order — sort by (level, type, inst) so layout is deterministic
  // across runs even if Map iteration order shifts under V8 changes.
  out.sort((a, b) => {
    if (a.level !== b.level) return a.level - b.level;
    if (a.type !== b.type) return a.type - b.type;
    return a.inst - b.inst;
  });
  return out;
}

// ---------------------------------------------------------------------------
// Layout — cells → grid positions
// ---------------------------------------------------------------------------

export function mapCellsToGrid(
  k: Kernel,
  cells: readonly NodeID[],
  cols: number,
  rows: number,
  layout: "instance" | "depth" = "instance",
): CellPositions {
  const cap = cols * rows;
  const positions: CellPosition[] = [];
  if (layout === "instance") {
    // Row-major by collection order. Cells past capacity are dropped from
    // the visible frame (the visualizer is a sampling lens, not a complete
    // archive).
    for (let i = 0; i < cells.length && i < cap; i++) {
      const node = cells[i]!;
      positions.push({ node, col: i % cols, row: (i / cols) | 0 });
    }
    return positions;
  }
  // depth — row index encodes composition depth via children-count proxy
  // (a leaf trivial has zero children; a deep recipe has many). Cells
  // sharing depth pack into the same row. This makes the Level hierarchy
  // visible as horizontal bands.
  const byDepth = new Map<number, NodeID[]>();
  for (const node of cells) {
    const d = depthOf(k, node, 0, new Set());
    let bucket = byDepth.get(d);
    if (bucket === undefined) {
      bucket = [];
      byDepth.set(d, bucket);
    }
    bucket.push(node);
  }
  const depths = [...byDepth.keys()].sort((a, b) => a - b);
  let row = 0;
  for (const d of depths) {
    const bucket = byDepth.get(d)!;
    let col = 0;
    for (const node of bucket) {
      if (row >= rows) break;
      positions.push({ node, col, row });
      col++;
      if (col >= cols) {
        col = 0;
        row++;
      }
    }
    if (row >= rows) break;
    if (bucket.length > 0) row++; // depth separator
  }
  return positions;
}

function depthOf(
  k: Kernel,
  node: NodeID,
  acc: number,
  seen: Set<string>,
): number {
  if (node.level === Level.TRIVIAL) return acc;
  const key = nodeKey(node);
  if (seen.has(key)) return acc;
  seen.add(key);
  const kids = k.children(node);
  if (kids.length === 0) return acc;
  let max = acc;
  for (const c of kids) {
    const d = depthOf(k, c, acc + 1, seen);
    if (d > max) max = d;
  }
  return max;
}

// ---------------------------------------------------------------------------
// CPU renderer — reference path, no GPU required
// ---------------------------------------------------------------------------

export function renderToRGBA8(
  k: Kernel,
  config: VisualizerConfig = DEFAULT_CONFIG,
): Uint8Array {
  const cells = collectCells(k);
  const positions = mapCellsToGrid(
    k,
    cells,
    config.gridCols,
    config.gridRows,
    config.layout,
  );
  return rasterize(positions, config);
}

export function rasterize(
  positions: CellPositions,
  config: VisualizerConfig,
): Uint8Array {
  const { width, height, gridCols, gridRows, colorScheme, background } = config;
  const buf = new Uint8Array(width * height * 4);
  // Paint background.
  for (let i = 0; i < width * height; i++) {
    buf[i * 4] = background[0]!;
    buf[i * 4 + 1] = background[1]!;
    buf[i * 4 + 2] = background[2]!;
    buf[i * 4 + 3] = background[3]!;
  }
  const tileW = Math.max(1, (width / gridCols) | 0);
  const tileH = Math.max(1, (height / gridRows) | 0);
  for (const p of positions) {
    const [r, g, b, a] = nodeIDToColor(p.node, colorScheme);
    const px0 = p.col * tileW;
    const py0 = p.row * tileH;
    const px1 = Math.min(width, px0 + tileW);
    const py1 = Math.min(height, py0 + tileH);
    for (let y = py0; y < py1; y++) {
      for (let x = px0; x < px1; x++) {
        const off = (y * width + x) * 4;
        buf[off] = r;
        buf[off + 1] = g;
        buf[off + 2] = b;
        buf[off + 3] = a;
      }
    }
  }
  return buf;
}

// ---------------------------------------------------------------------------
// Form recipe-tree builder
// ---------------------------------------------------------------------------
//
// `renderSubstrate` emits a Form recipe representing the render pipeline.
// The tree composes from the substrate's own primitives — same body, same
// content-addressing. Visually, the recipe is a SEQUENCE block of per-cell
// LET bindings: each cell's color is a recipe whose value is the four-byte
// RGBA quartet, expressed as four trivial INT children inside a LIST.
//
// Why this shape? Three things:
//
//   • The LIST-of-four-INTs is the format-recipe shape that the future
//     `formats.ts` UINT8-quartet (RGBA8) will resolve to. When format-
//     recipes land, this builder swaps in `formatRecipes.rgba8.ctor(...)`
//     without changing call sites.
//
//   • The outer SEQUENCE block is the same shape the WGSL emitter expects:
//     one statement per cell, write to storage buffer at (col,row).
//
//   • The composition stays structurally addressable: identical render
//     pipelines for two snapshots of an identical substrate produce
//     identical Blueprint NodeIDs at every level. The visualizer itself
//     becomes a substrate-resident artifact.

export interface ShaderProgram {
  readonly recipe: NodeID; // Form recipe describing the render pipeline
  readonly positions: CellPositions; // resolved cell positions
  readonly config: VisualizerConfig;
}

export function renderSubstrate(
  k: Kernel,
  config: VisualizerConfig = DEFAULT_CONFIG,
): ShaderProgram {
  const cells = collectCells(k);
  const positions = mapCellsToGrid(
    k,
    cells,
    config.gridCols,
    config.gridRows,
    config.layout,
  );
  const recipe = buildRenderRecipe(k, positions, config);
  return { recipe, positions, config };
}

function buildRenderRecipe(
  k: Kernel,
  positions: CellPositions,
  config: VisualizerConfig,
): NodeID {
  // SEQUENCE block of LET bindings, one per cell:
  //   (let pixel_<col>_<row> (list r g b a))
  const blockCat = trivialOf(k, Level.BASIC, RBasic.BLOCK, RBlock.SEQUENCE);
  const letCat = trivialOf(k, Level.BASIC, RBasic.BLOCK, RBlock.LET);
  const listCat = trivialOf(k, Level.BASIC, RBasic.LIST, 0);
  const stmts: NodeID[] = [];
  for (const p of positions) {
    const [r, g, b, a] = nodeIDToColor(p.node, config.colorScheme);
    const rgbaList = k.intern(listCat, [
      k.internTrivialInt(r),
      k.internTrivialInt(g),
      k.internTrivialInt(b),
      k.internTrivialInt(a),
    ]);
    const nameSym = k.internString(`pixel_${p.col}_${p.row}`);
    stmts.push(k.intern(letCat, [nameSym, rgbaList]));
  }
  if (stmts.length === 0) {
    // Empty substrate — emit a no-op DO so the recipe still has a NodeID.
    const doCat = trivialOf(k, Level.BASIC, RBasic.BLOCK, RBlock.DO);
    return k.intern(doCat, []);
  }
  return k.intern(blockCat, stmts);
}

// Helper — build a (pkg=1, level, type, inst) NodeID for a basic category.
// The kernel's intern path uses the category's (level, type) to inherit
// into the composite's identity; for category nodes themselves we keep the
// pkg=1 convention shared with the kernel's intern.
function trivialOf(
  _k: Kernel,
  level: number,
  type: number,
  inst: number,
): NodeID {
  return { pkg: 1, level, type, inst };
}

// ---------------------------------------------------------------------------
// WGSL emission
// ---------------------------------------------------------------------------
//
// The visualizer ships a small, self-contained WGSL emitter for its own
// pipeline shape (SEQUENCE-of-LET-with-RGBA-LISTs). This is the load-bearing
// fact: even before the general-purpose WGSL backend lands (task #10), the
// visualizer can already produce browser-runnable shader source for the
// concrete shape it emits.
//
// When task #10's WgslBackend module is added at `src/backends/wgsl.ts`,
// the seam below switches: `compileToWGSL` checks for an injected
// `WgslEmitter` and delegates expression-level emission to it, while
// keeping the visualizer's @compute scaffold (workgroup_size, storage
// binding, dispatch) as the outer frame. The fallback path stays as the
// reference oracle for cross-backend conformance.

export interface WgslEmitter {
  emitExpression(k: Kernel, node: NodeID): string;
}

export interface CompileOptions {
  readonly workgroupSize?: number; // default 8
  readonly backend?: WgslEmitter; // optional injected #10 backend
}

export function compileToWGSL(
  k: Kernel,
  program: ShaderProgram,
  opts: CompileOptions = {},
): string {
  const workgroupSize = opts.workgroupSize ?? 8;
  const { positions, config } = program;
  const lines: string[] = [];
  lines.push("// form-kernel-ts visualizer — substrate framebuffer shader");
  lines.push(`// width=${config.width} height=${config.height}`);
  lines.push(
    `// grid=${config.gridCols}x${config.gridRows} scheme=${config.colorScheme}`,
  );
  lines.push("");
  lines.push("@group(0) @binding(0) var<storage, read_write> framebuffer: array<u32>;");
  lines.push("");
  lines.push("fn pack_rgba8(r: u32, g: u32, b: u32, a: u32) -> u32 {");
  lines.push("  return (a << 24u) | (b << 16u) | (g << 8u) | r;");
  lines.push("}");
  lines.push("");
  lines.push(
    `@compute @workgroup_size(${workgroupSize}, ${workgroupSize})`,
  );
  lines.push(
    "fn main(@builtin(global_invocation_id) gid: vec3<u32>) {",
  );
  lines.push(`  let width: u32 = ${config.width}u;`);
  lines.push(`  let height: u32 = ${config.height}u;`);
  lines.push("  if (gid.x >= width || gid.y >= height) { return; }");
  lines.push("  let idx: u32 = gid.y * width + gid.x;");
  lines.push("");
  lines.push("  // Background");
  lines.push(
    `  var color: u32 = pack_rgba8(${config.background[0]}u, ${config.background[1]}u, ${config.background[2]}u, ${config.background[3]}u);`,
  );
  lines.push("");
  // Per-cell tile writes. We emit a chained-if shape rather than a giant
  // switch so each branch is independently optimizable; for large grids
  // the future general WGSL backend will lift these to a uniform table.
  const tileW = Math.max(1, (config.width / config.gridCols) | 0);
  const tileH = Math.max(1, (config.height / config.gridRows) | 0);
  for (const p of positions) {
    const [r, g, b, a] = nodeIDToColor(p.node, config.colorScheme);
    const x0 = p.col * tileW;
    const y0 = p.row * tileH;
    const x1 = x0 + tileW;
    const y1 = y0 + tileH;
    // Optional: when a #10 backend is injected, ask it to render the
    // expression for the color. For now the result is identical because
    // colors are pure data.
    if (opts.backend !== undefined) {
      // Touch the backend so it participates in the type contract even
      // when its expression emit is unused. Future: delegate the per-
      // pixel color expression here once visualizer recipes carry
      // arithmetic in the color channel (e.g. coherence-modulated tint).
      void opts.backend.emitExpression;
    }
    lines.push(
      `  if (gid.x >= ${x0}u && gid.x < ${x1}u && gid.y >= ${y0}u && gid.y < ${y1}u) {`,
    );
    lines.push(
      `    color = pack_rgba8(${r}u, ${g}u, ${b}u, ${a}u); // node ${nodeKey(p.node)}`,
    );
    lines.push("  }");
  }
  lines.push("");
  lines.push("  framebuffer[idx] = color;");
  lines.push("}");
  lines.push("");
  return lines.join("\n");
}

// ---------------------------------------------------------------------------
// Convenience — single-call full pipeline (substrate → WGSL string)
// ---------------------------------------------------------------------------

export function visualizeToWGSL(
  k: Kernel,
  config: VisualizerConfig = DEFAULT_CONFIG,
  opts: CompileOptions = {},
): { program: ShaderProgram; wgsl: string; rgba8: Uint8Array } {
  const program = renderSubstrate(k, config);
  const wgsl = compileToWGSL(k, program, opts);
  const rgba8 = rasterize(program.positions, config);
  return { program, wgsl, rgba8 };
}

// ---------------------------------------------------------------------------
// Form notation references (for documentation / debugging)
// ---------------------------------------------------------------------------
//
// Once `formats.ts` lands, the per-cell pixel recipe becomes:
//
//   (rgba8 r g b a)            ; UINT8 quartet, format-resident
//
// and the dispatch uniform becomes:
//
//   (fp32 width height time)   ; FP32 triple
//
// Until then, the corresponding shapes are:
//
//   (list r g b a)             ; plain LIST-of-INT, same numeric content
//
// Both forms intern to a stable Blueprint NodeID — the seam is shape-level,
// not byte-level. The body is composed even before the format-recipe leaves
// arrive.

// Keep unused-import suppression at module scope for the constants the
// visualizer surfaces but doesn't reference in this slice. They are part
// of the public-API budget for callers building custom configs.
void Triv;
void RMath;
