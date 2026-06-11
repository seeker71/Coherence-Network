// membrane.ts — graphic kernels for the cell membrane, generated from inner state.
//
// The boundary axiom made visible: every recipe cell wears a membrane whose
// texture IS its inner state, projected from both sides. One generic GPU
// kernel (a single GLSL program, compiled once) renders every membrane;
// per-cell variation arrives purely as DATA — the matvec-emitter pattern
// carried to graphics:
//
//   blueprint hash        → seeds the skin's domain-warped pattern, so two
//                           structurally-equivalent cells wear the SAME skin
//                           anywhere in the space (ice, worn on the body).
//   subtree category mix  → a histogram over Form categories blends eight
//                           procedural texture fields (interference for MATH,
//                           spirals for FNCALL, bifurcating veins for COND,
//                           iris rings for WITNESS, …). The cell's inner
//                           composition literally textures its surface.
//   children              → pores. Each child claims a deterministic site on
//                           the membrane (golden-spiral, seeded); its door
//                           beam attaches THERE, glows its color, and ripples
//                           at its runtime heat. Offers cross the boundary at
//                           named pores.
//   gl_FrontFacing        → the inner projection. From inside, the membrane
//                           is a planetarium: pores become windows, the
//                           category nebula intensifies, and the substrate
//                           lattice framebuffer belts the equator — the
//                           body's memory projected on the boundary's skin.
//
// The fragment kernel is GENERATED: each category field is a row in
// FIELD_LIBRARY (data, not code paths); buildMembraneShaders() assembles the
// GLSL from the table. Adding a texture vocabulary = adding a row.

import * as THREE from "three";
import { RBasic } from "./vendor/kernel.ts";
import type { KernelSpace, SpaceCell } from "./space.ts";

export const MAX_PORES = 32;
export const FIELD_COUNT = 8;

// --- deterministic seeds ------------------------------------------------------

// FNV-1a over a string → [0,1). Stable per key; shared by encoder and tests.
export function hash01(key: string): number {
  let h = 2166136261;
  for (let i = 0; i < key.length; i++) {
    h ^= key.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0) / 4294967295;
}

// --- pores: deterministic sites on the unit sphere ----------------------------
//
// Golden-spiral distribution, rotated by the cell's seed so each cell wears
// its doors in its own arrangement — but the SAME arrangement every build.
// Exported so the JS beam layer attaches doors exactly where the GPU draws
// the pore: one geometry of the boundary, two carriers.

export function porePosition(
  index: number,
  count: number,
  seed: number,
): readonly [number, number, number] {
  const n = Math.max(1, count);
  const golden = Math.PI * (3 - Math.sqrt(5));
  // tilt band: keep pores off the exact poles so doors read sideways
  const y = 1 - ((index + 0.5) / n) * 2;
  const yl = y * 0.82;
  const r = Math.sqrt(Math.max(0, 1 - yl * yl));
  const theta = golden * index + seed * Math.PI * 2;
  return [Math.cos(theta) * r, yl, Math.sin(theta) * r] as const;
}

// membrane radius — grows gently with arity so busy cells read bigger
export function membraneRadius(arity: number): number {
  return 2.55 + Math.min(1.3, arity * 0.09);
}

// --- category bins ------------------------------------------------------------
//
// RBasic category → texture-field bin. A DATA table: the shader carries eight
// generic fields; Form categories drop in here, never as parallel shaders.

export const CATEGORY_BIN: Record<number, number> = {
  [RBasic.MATH]: 0,
  [RBasic.COMPARE]: 0,
  [RBasic.LIST]: 1,
  [RBasic.ACCESS]: 1,
  [RBasic.VECTOR]: 1,
  [RBasic.FNCALL]: 2,
  [RBasic.FNDEF]: 2,
  [RBasic.CALL]: 2,
  [RBasic.METHOD]: 2,
  [RBasic.COND]: 3,
  [RBasic.CHOICE]: 3,
  [RBasic.LOGIC]: 3,
  [RBasic.WITNESS]: 4,
  [RBasic.OBSERVER]: 4,
  [RBasic.PROOF]: 4,
  [RBasic.INFERENCE]: 4,
  [RBasic.IDENT]: 5,
  [RBasic.ALIAS]: 5,
  [RBasic.BLOCK]: 6,
};
const DEFAULT_BIN = 7;

export const FIELD_NAMES = [
  "interference", // 0 MATH/COMPARE — standing waves meeting
  "strata", // 1 LIST/ACCESS — ordered banding, shelves of elements
  "spiral", // 2 FNCALL/CALL — recursion winding inward
  "veins", // 3 COND/CHOICE/LOGIC — bifurcating decision paths
  "iris", // 4 WITNESS/OBSERVER — concentric attention rings
  "filament", // 5 IDENT — name-threads, script-like strands
  "sediment", // 6 BLOCK — layered statement strata, coarse
  "cellular", // 7 everything else — voronoi tissue
] as const;

// subtree category histogram, normalized — what mixture of Form-shapes lives
// inside this boundary. Leaf-only subtrees weight the cellular field.
export function subtreeCategoryWeights(
  space: Pick<KernelSpace, "cells">,
  rootId: string,
): Float32Array {
  const w = new Float32Array(FIELD_COUNT);
  const seen = new Set<string>([rootId]);
  const queue = [rootId];
  let total = 0;
  while (queue.length > 0) {
    const cell = space.cells[queue.shift()!];
    if (!cell) continue;
    if (cell.kind === "recipe") {
      w[CATEGORY_BIN[cell.node.type] ?? DEFAULT_BIN]! += 1;
      total++;
    }
    for (const c of cell.childIds) {
      if (!seen.has(c)) {
        seen.add(c);
        queue.push(c);
      }
    }
  }
  if (total === 0) {
    w[DEFAULT_BIN] = 1;
    return w;
  }
  for (let i = 0; i < FIELD_COUNT; i++) w[i]! /= total;
  return w;
}

// --- inner-state encoding -----------------------------------------------------
//
// The membrane's data feed: one tiny float texture per cell.
//   row 0, texel i — pore direction.xyz, child heat
//   row 1, texel i — child color.rgb, child kind (1 recipe / 0 leaf)

export interface MembraneState {
  poreCount: number;
  poreTexture: THREE.DataTexture;
  catWeights: Float32Array;
  seed: number; // blueprint identity — the skin pattern
  instSeed: number; // instance identity — pore arrangement
  data: Float32Array; // raw texel payload (exported for tests)
}

export function encodeMembraneState(
  space: Pick<KernelSpace, "cells">,
  cell: SpaceCell,
): MembraneState {
  const children = cell.childIds
    .map((id) => space.cells[id])
    .filter((c): c is SpaceCell => Boolean(c));
  const n = Math.min(MAX_PORES, children.length);
  const instSeed = hash01(cell.id);
  const data = new Float32Array(MAX_PORES * 2 * 4);
  for (let i = 0; i < n; i++) {
    const child = children[i]!;
    const dir = porePosition(i, children.length, instSeed);
    const o = i * 4;
    data[o] = dir[0];
    data[o + 1] = dir[1];
    data[o + 2] = dir[2];
    data[o + 3] = child.heat;
    const p = (MAX_PORES + i) * 4;
    data[p] = child.color[0];
    data[p + 1] = child.color[1];
    data[p + 2] = child.color[2];
    data[p + 3] = child.kind === "recipe" ? 1 : 0;
  }
  const poreTexture = new THREE.DataTexture(
    data,
    MAX_PORES,
    2,
    THREE.RGBAFormat,
    THREE.FloatType,
  );
  poreTexture.magFilter = THREE.NearestFilter;
  poreTexture.minFilter = THREE.NearestFilter;
  poreTexture.needsUpdate = true;
  return {
    poreCount: n,
    poreTexture,
    catWeights: subtreeCategoryWeights(space, cell.id),
    seed: hash01(cell.blueprintKey),
    instSeed,
    data,
  };
}

// --- the field library — GLSL texture vocabularies, as data --------------------
//
// Each row is `float fieldN(vec3 p, float s, float t)` returning [0,1].
// p = unit-sphere position, s = blueprint seed, t = time. The generator
// assembles these into one kernel; the histogram mixes them at runtime.

const FIELD_LIBRARY: readonly string[] = [
  // 0 interference — standing waves from three seeded directions meeting
  `float a1 = sin(dot(p, dirOf(s)) * 9.0 + t * 0.9);
   float a2 = sin(dot(p, dirOf(s + 0.37)) * 11.0 - t * 0.7);
   float a3 = sin(dot(p, dirOf(s + 0.71)) * 7.0 + t * 0.5);
   return 0.5 + 0.5 * (a1 * a2 * 0.6 + a3 * 0.4);`,
  // 1 strata — ordered latitude banding, elements shelved in sequence
  `float band = sin((p.y * 0.5 + 0.5) * 28.0 + s * 31.0 + sin(atan(p.z, p.x) * 2.0 + t * 0.3) * 0.8);
   return smoothstep(-0.45, 0.45, band);`,
  // 2 spiral — recursion winding into the poles
  `float ang = atan(p.z, p.x);
   float lat = acos(clamp(p.y, -1.0, 1.0));
   float arm = sin(ang * 3.0 + lat * 9.0 - t * 1.1 + s * 17.0);
   return 0.5 + 0.5 * arm * sin(lat * 5.0 + t * 0.4);`,
  // 3 veins — bifurcating decision paths, domain-warped ridges
  `vec3 q = p * 3.0 + vec3(s * 19.0);
   float v = fbm(q + fbm(q + t * 0.12) * 1.6);
   return 1.0 - abs(2.0 * v - 1.0);`,
  // 4 iris — concentric attention rings around a seeded gaze axis
  `float d = acos(clamp(dot(p, dirOf(s + 0.13)), -1.0, 1.0));
   float ring = sin(d * 22.0 - t * 1.3) * 0.5 + 0.5;
   return ring * smoothstep(2.6, 0.6, d);`,
  // 5 filament — name-threads streaming along seeded flow
  `vec3 q = p * 4.0;
   float f = fbm(vec3(q.x + t * 0.25, q.y * 3.2, q.z) + s * 23.0);
   return smoothstep(0.32, 0.68, f);`,
  // 6 sediment — coarse statement layers, slow drift
  `float layer = floor((p.y * 0.5 + 0.5) * 9.0 + fbm(p * 2.0 + s * 11.0) * 2.0);
   return fract(layer * 0.618 + s + t * 0.015);`,
  // 7 cellular — voronoi tissue, the generic living ground
  `return voronoi(p * 3.4 + vec3(s * 29.0), t);`,
];

// shared GLSL helpers — hash noise, fbm, voronoi, seeded directions
const GLSL_COMMON = /* glsl */ `
  float hash13(vec3 p3) {
    p3 = fract(p3 * 0.1031);
    p3 += dot(p3, p3.zyx + 31.32);
    return fract((p3.x + p3.y) * p3.z);
  }
  float vnoise(vec3 p) {
    vec3 i = floor(p), f = fract(p);
    vec3 u = f * f * (3.0 - 2.0 * f);
    return mix(
      mix(mix(hash13(i), hash13(i + vec3(1,0,0)), u.x),
          mix(hash13(i + vec3(0,1,0)), hash13(i + vec3(1,1,0)), u.x), u.y),
      mix(mix(hash13(i + vec3(0,0,1)), hash13(i + vec3(1,0,1)), u.x),
          mix(hash13(i + vec3(0,1,1)), hash13(i + vec3(1,1,1)), u.x), u.y),
      u.z);
  }
  float fbm(vec3 p) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 4; i++) { v += a * vnoise(p); p = p * 2.03 + 11.7; a *= 0.5; }
    return v;
  }
  float voronoi(vec3 p, float t) {
    vec3 i = floor(p), f = fract(p);
    float md = 8.0;
    for (int z = -1; z <= 1; z++)
    for (int y = -1; y <= 1; y++)
    for (int x = -1; x <= 1; x++) {
      vec3 g = vec3(float(x), float(y), float(z));
      vec3 o = vec3(hash13(i + g), hash13(i + g + 7.7), hash13(i + g + 17.3));
      o = 0.5 + 0.42 * sin(t * 0.6 + 6.2831 * o);
      float d = length(g + o - f);
      md = min(md, d);
    }
    return 1.0 - md;
  }
  vec3 dirOf(float s) {
    float a = s * 39.4784, b = s * 17.2;
    return normalize(vec3(cos(a) * cos(b), sin(b), sin(a) * cos(b)));
  }
  vec3 iri(float t) {
    return 0.55 + 0.45 * cos(6.28318 * (t + vec3(0.0, 0.33, 0.67)));
  }
`;

export interface MembraneShaders {
  vertex: string;
  fragment: string;
}

// Assemble the membrane kernel from the field table. Pure string → testable;
// the result compiles once per page (three.js caches programs by source).
export function buildMembraneShaders(): MembraneShaders {
  const fieldFns = FIELD_LIBRARY.map(
    (body, i) =>
      `float field${i}(vec3 p, float s, float t) {\n${body}\n}`,
  ).join("\n");
  const fieldMix = FIELD_LIBRARY.map(
    (_, i) => `acc += uCatWeights[${i}] * field${i}(p, uSeed, uTime);`,
  ).join("\n    ");

  const vertex = /* glsl */ `
  uniform float uTime;
  uniform float uSeed;
  uniform float uHeat;
  uniform float uPoreCount;
  uniform sampler2D uPoreTex;
  varying vec3 vPos;
  varying vec3 vNormal;
  varying vec3 vView;
  ${GLSL_COMMON}
  void main() {
    vec3 p = normalize(position);
    // breath — the whole membrane swells with runtime heat
    float breath = 1.0 + (0.025 + uHeat * 0.05) * sin(uTime * (1.1 + uHeat * 1.6) + uSeed * 20.0);
    // organic relief — blueprint-seeded, so twins undulate alike
    float relief = (fbm(p * 2.4 + uSeed * 13.0 + uTime * 0.08) - 0.5) * 0.22;
    // pores pucker — the surface reaches toward each door
    float pucker = 0.0;
    for (int i = 0; i < ${MAX_PORES}; i++) {
      if (i >= int(uPoreCount)) break;
      vec4 pore = texture2D(uPoreTex, vec2((float(i) + 0.5) / ${MAX_PORES}.0, 0.25));
      float d = acos(clamp(dot(p, pore.xyz), -1.0, 1.0));
      pucker += smoothstep(0.5, 0.0, d) * (0.10 + pore.w * 0.22);
    }
    vec3 displaced = position * breath + normal * (relief + pucker);
    vec4 mv = modelViewMatrix * vec4(displaced, 1.0);
    vPos = p;
    vNormal = normalize(normalMatrix * normal);
    vView = normalize(-mv.xyz);
    gl_Position = projectionMatrix * mv;
  }
  `;

  const fragment = /* glsl */ `
  uniform float uTime;
  uniform float uSeed;
  uniform float uHeat;
  uniform float uFocus;
  uniform float uTouchT;
  uniform float uPoreCount;
  uniform sampler2D uPoreTex;
  uniform sampler2D uLattice;
  uniform vec3 uColor;
  uniform vec3 uBlueprintColor;
  uniform float uCatWeights[${FIELD_COUNT}];
  varying vec3 vPos;
  varying vec3 vNormal;
  varying vec3 vView;
  ${GLSL_COMMON}
  ${fieldFns}
  float innerMix(vec3 p) {
    float acc = 0.0;
    ${fieldMix}
    return acc;
  }
  void main() {
    vec3 p = normalize(vPos);
    bool inside = !gl_FrontFacing;

    // the skin: blueprint-seeded warp carrying the category mixture
    float tex = innerMix(p);
    float warp = fbm(p * 2.0 + uSeed * 7.0 + tex * 0.9);
    vec3 skin = mix(uColor * 0.35, uBlueprintColor, clamp(tex * 0.85 + warp * 0.3, 0.0, 1.0));

    // pores — doors glowing their child's color, rippling at child heat
    vec3 poreGlow = vec3(0.0);
    float poreMask = 0.0;
    for (int i = 0; i < ${MAX_PORES}; i++) {
      if (i >= int(uPoreCount)) break;
      vec4 pore = texture2D(uPoreTex, vec2((float(i) + 0.5) / ${MAX_PORES}.0, 0.25));
      vec4 meta = texture2D(uPoreTex, vec2((float(i) + 0.5) / ${MAX_PORES}.0, 0.75));
      float d = acos(clamp(dot(p, pore.xyz), -1.0, 1.0));
      float core = smoothstep(0.16, 0.02, d);
      float halo = smoothstep(0.5, 0.1, d) * 0.5;
      float ripple = sin(d * 26.0 - uTime * (1.6 + pore.w * 5.0)) * 0.5 + 0.5;
      ripple *= smoothstep(0.85, 0.15, d) * (0.25 + pore.w);
      float win = core * (meta.a > 0.5 ? 1.0 : 0.65 + 0.35 * sin(uTime * 3.0 + float(i)));
      poreGlow += meta.rgb * (win + halo * 0.6 + ripple * 0.35);
      poreMask = max(poreMask, core);
    }

    // touch ripple — focus lands and a ring expands across the whole skin
    float since = max(uTime - uTouchT, 0.0);
    float ringR = since * 2.2;
    float dTop = acos(clamp(p.y, -1.0, 1.0));
    float touch = smoothstep(0.25, 0.0, abs(dTop - ringR)) * smoothstep(2.2, 0.0, since);

    // fresnel — the living edge; iridescent by blueprint
    float fres = pow(1.0 - max(dot(normalize(vNormal), normalize(vView)), 0.0), 2.6);
    vec3 rim = iri(uSeed + fres * 0.6 + uTime * 0.05) * fres;

    vec3 col = skin * (0.55 + uHeat * 0.9 + uFocus * 0.5);
    col += poreGlow;
    col += rim * (inside ? 0.6 : 1.4);
    col += uBlueprintColor * touch * 1.6;

    float alpha = 0.16 + fres * 0.30 + poreMask * 0.55 + tex * 0.10 + uFocus * 0.12;

    if (inside) {
      // planetarium: the inner projection. Category nebula brightens,
      // pores become windows, and the lattice framebuffer belts the equator.
      float lon = atan(p.z, p.x) / 6.28318 + 0.5;
      float lat = p.y * 0.5 + 0.5;
      vec3 mem = texture2D(uLattice, vec2(lon, lat)).rgb;
      float belt = smoothstep(0.42, 0.5, lat) * smoothstep(0.58, 0.5, lat);
      col += mem * belt * 1.3;
      col += skin * tex * 0.8 + poreGlow * 0.9;
      alpha = min(0.92, alpha + 0.22 + belt * 0.3);
    }

    gl_FragColor = vec4(col, clamp(alpha, 0.0, 0.95));
  }
  `;

  return { vertex, fragment };
}

// --- the living lattice — framebuffer floor kernel -----------------------------
//
// The substrate lattice arrives as a data texture; this kernel makes it a
// surface that breathes: per-tile phase pulse, a scan sweep (the framebuffer
// remembering it is a framebuffer), grid glow, and a soft height ripple.

export function buildLatticeShaders(): MembraneShaders {
  const vertex = /* glsl */ `
  uniform float uTime;
  uniform sampler2D uMap;
  varying vec2 vUv;
  void main() {
    vUv = uv;
    vec3 texel = texture2D(uMap, uv).rgb;
    float lum = dot(texel, vec3(0.299, 0.587, 0.114));
    vec3 displaced = position;
    displaced.z += lum * (0.6 + 0.4 * sin(uTime * 0.8 + uv.x * 9.0 + uv.y * 7.0));
    gl_Position = projectionMatrix * modelViewMatrix * vec4(displaced, 1.0);
  }
  `;
  const fragment = /* glsl */ `
  uniform float uTime;
  uniform float uHeat;
  uniform float uCells;
  uniform sampler2D uMap;
  varying vec2 vUv;
  float hash21(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
  }
  void main() {
    float n = max(uCells, 1.0);
    vec2 tile = floor(vUv * n);
    vec2 tuv = fract(vUv * n);
    vec3 texel = texture2D(uMap, vUv).rgb;
    // each occupied tile pulses on its own phase, tempo set by runtime heat
    float phase = hash21(tile) * 6.2831;
    float occupied = step(0.09, dot(texel, vec3(1.0)));
    float pulse = 0.75 + 0.45 * sin(uTime * (1.2 + uHeat * 2.4) + phase) * occupied;
    // grid glow — the lattice admits its cells
    vec2 g = abs(tuv - 0.5);
    float edge = smoothstep(0.5, 0.46, max(g.x, g.y));
    float grid = 1.0 - edge;
    // scan sweep — the framebuffer remembering it is a framebuffer
    float sweep = smoothstep(0.06, 0.0, abs(fract(vUv.y + uTime * 0.05) - 0.5) - 0.44);
    vec3 col = texel * pulse * edge;
    col += vec3(0.16, 0.22, 0.45) * grid * 0.55;
    col += texel * sweep * 0.8;
    float vign = smoothstep(1.25, 0.35, length(vUv - 0.5) * 2.0);
    gl_FragColor = vec4(col * vign, (0.6 + 0.4 * occupied) * vign);
  }
  `;
  return { vertex, fragment };
}
