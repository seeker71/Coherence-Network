// lenses.tsx — manifestation lenses for the Form recipe tree.
//
// A recipe is invariant structure (ice). Its *manifestation* is a choice of
// lens: the same tree can become a crystal lattice, a circuit board, living
// tissue, a library, a frequency terrain. Swapping the lens changes nothing
// about the recipe — only how reality renders it. That is the teaching the
// playground is reaching for: structure is one, manifestation is many.
//
// The blueprint-keyed shader is the spine of it. Every cell's surface is
// displaced by a procedural field seeded from its `blueprintKey` — so two
// cells with the *same blueprint* (structurally identical, by the substrate's
// content-addressing) get the *same* surface in every lens. Structural
// equivalence becomes something the eye can see: twins shimmer alike.

"use client";

import { useMemo, useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import { Html, Line } from "@react-three/drei";
import * as THREE from "three";
import type { CellLayout, RGB, SpaceCell } from "@/lib/form-kernel/space";

export type LensId =
  | "rooms"
  | "crystal"
  | "circuit"
  | "organism"
  | "library"
  | "terrain";

export interface Lens {
  id: LensId;
  name: string;
  glyph: string;
  blurb: string;
  bg: string;
  cellShape: "room" | "crystal" | "chip" | "membrane" | "cabinet";
  edge: "beam" | "wire" | "vessel" | "road" | "none";
  displace: number; // blueprint-shader surface displacement amount
  translucent: boolean;
  metalness: number;
  roughness: number;
  emissive: number;
  breathe: number; // displacement breathing speed
  ground: boolean; // render a terrain heightfield
}

export const LENSES: Lens[] = [
  {
    id: "rooms",
    name: "Architecture",
    glyph: "▦",
    blurb: "Recipes are buildings, children are rooms, leaves are objects inside.",
    bg: "#05060a",
    cellShape: "room",
    edge: "beam",
    displace: 0,
    translucent: false,
    metalness: 0.1,
    roughness: 0.6,
    emissive: 0.3,
    breathe: 0,
    ground: false,
  },
  {
    id: "crystal",
    name: "Crystal lattice",
    glyph: "◈",
    blurb: "Every cell a faceted crystal grown from its blueprint — identical blueprints grow identical crystals.",
    bg: "#070612",
    cellShape: "crystal",
    edge: "beam",
    displace: 0.5,
    translucent: false,
    metalness: 0.35,
    roughness: 0.2,
    emissive: 0.55,
    breathe: 0.3,
    ground: false,
  },
  {
    id: "circuit",
    name: "Circuit board",
    glyph: "⊞",
    blurb: "Cells are chips, edges are traces carrying current — watch the recipe compute.",
    bg: "#02100c",
    cellShape: "chip",
    edge: "wire",
    displace: 0.12,
    translucent: false,
    metalness: 0.6,
    roughness: 0.35,
    emissive: 1.1,
    breathe: 0,
    ground: false,
  },
  {
    id: "organism",
    name: "Living tissue",
    glyph: "❍",
    blurb: "Cells are translucent membranes with nuclei, edges are vessels — the recipe breathes.",
    bg: "#0a0410",
    cellShape: "membrane",
    edge: "vessel",
    displace: 0.34,
    translucent: true,
    metalness: 0.05,
    roughness: 0.5,
    emissive: 0.4,
    breathe: 1.0,
    ground: false,
  },
  {
    id: "library",
    name: "Library",
    glyph: "▤",
    blurb: "Maps are cabinets of labeled drawers, lists are shelves, leaves are books.",
    bg: "#0b0805",
    cellShape: "cabinet",
    edge: "none",
    displace: 0.05,
    translucent: false,
    metalness: 0.1,
    roughness: 0.8,
    emissive: 0.25,
    breathe: 0,
    ground: false,
  },
  {
    id: "terrain",
    name: "Frequency terrain",
    glyph: "⏚",
    blurb: "The recipe becomes a landscape — each cell raises a hill by its heat, blueprint sets the texture.",
    bg: "#030712",
    cellShape: "crystal",
    edge: "road",
    displace: 0.3,
    translucent: false,
    metalness: 0.2,
    roughness: 0.7,
    emissive: 0.5,
    breathe: 0.4,
    ground: true,
  },
];

export function lensById(id: LensId): Lens {
  return LENSES.find((l) => l.id === id) ?? LENSES[0]!;
}

function toColor(c: RGB): THREE.Color {
  return new THREE.Color(c[0], c[1], c[2]);
}

// blueprintKey → stable seed in [0, 2π). Identical blueprint ⇒ identical seed.
function seedOf(key: string): number {
  let h = 2166136261;
  for (let i = 0; i < key.length; i++) {
    h ^= key.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return ((h >>> 0) / 4294967295) * Math.PI * 2;
}

// A MeshStandardMaterial whose surface is displaced by a procedural field
// seeded from the cell's blueprint. This is the "shader per blueprint" — the
// primitive's surface is transformed into a bump unique to its structure, and
// shared across all structurally-equivalent cells.
function useBlueprintMaterial(cell: SpaceCell, lens: Lens): THREE.MeshStandardMaterial {
  const uniforms = useRef({
    uTime: { value: 0 },
    uSeed: { value: seedOf(cell.blueprintKey) },
    uDisplace: { value: lens.displace * (0.55 + cell.heat) },
    uBreathe: { value: lens.breathe },
  });
  uniforms.current.uSeed.value = seedOf(cell.blueprintKey);
  uniforms.current.uDisplace.value = lens.displace * (0.55 + cell.heat);
  uniforms.current.uBreathe.value = lens.breathe;

  const mat = useMemo(() => {
    const m = new THREE.MeshStandardMaterial({
      color: toColor(cell.color),
      emissive: toColor(lens.cellShape === "chip" ? cell.color : cell.blueprintColor),
      emissiveIntensity: lens.emissive,
      transparent: lens.translucent,
      opacity: lens.translucent ? 0.5 : 1,
      metalness: lens.metalness,
      roughness: lens.roughness,
      flatShading: lens.cellShape === "crystal",
    });
    m.onBeforeCompile = (shader) => {
      shader.uniforms.uTime = uniforms.current.uTime;
      shader.uniforms.uSeed = uniforms.current.uSeed;
      shader.uniforms.uDisplace = uniforms.current.uDisplace;
      shader.uniforms.uBreathe = uniforms.current.uBreathe;
      shader.vertexShader = shader.vertexShader
        .replace(
          "#include <common>",
          `#include <common>
           uniform float uTime; uniform float uSeed;
           uniform float uDisplace; uniform float uBreathe;`,
        )
        .replace(
          "#include <begin_vertex>",
          `#include <begin_vertex>
           float br = 1.0 + uBreathe * 0.18 * sin(uTime * 1.4 + uSeed);
           float d = sin(position.x * 3.1 + uSeed)
                   * sin(position.y * 2.7 + uSeed * 1.7)
                   * sin(position.z * 3.4 + uSeed * 2.3);
           transformed += normalize(normal) * (d * uDisplace * br);`,
        );
    };
    return m;
  }, [cell.blueprintKey, cell.color, cell.blueprintColor, lens]);

  useFrame(({ clock }) => {
    uniforms.current.uTime.value = clock.elapsedTime;
  });

  return mat;
}

function cellGeometry(cell: SpaceCell, lens: Lens): THREE.BufferGeometry {
  const r = 0.55 + Math.min(1.4, cell.arity * 0.1);
  switch (lens.cellShape) {
    case "crystal":
      return cell.kind === "leaf"
        ? new THREE.TetrahedronGeometry(r * 0.8, 0)
        : new THREE.OctahedronGeometry(r, 0);
    case "chip":
      return cell.kind === "leaf"
        ? new THREE.BoxGeometry(r, 0.3, r)
        : new THREE.CylinderGeometry(r, r, 0.35, 6);
    case "membrane":
      return new THREE.IcosahedronGeometry(r, 3);
    case "cabinet":
      // maps → tall cabinets, lists → wide shelves, leaves → books
      if (cell.kind === "leaf") return new THREE.BoxGeometry(0.3, r * 1.3, r);
      return cell.container === "list" || cell.container === "sequence"
        ? new THREE.BoxGeometry(r * 2.2, 0.6, r)
        : new THREE.BoxGeometry(r * 1.3, r * 1.8, r * 0.9);
    default:
      return new THREE.OctahedronGeometry(r, 1);
  }
}

export function LensCell({
  cell,
  layout,
  lens,
  focused,
  onSelect,
}: {
  cell: SpaceCell;
  layout: CellLayout;
  lens: Lens;
  focused: boolean;
  onSelect: (id: string) => void;
}) {
  const group = useRef<THREE.Group>(null);
  const [hover, setHover] = useState(false);
  const material = useBlueprintMaterial(cell, lens);
  const geometry = useMemo(() => cellGeometry(cell, lens), [cell, lens]);

  useFrame((_, dt) => {
    if (!group.current) return;
    if (lens.cellShape === "crystal" || lens.cellShape === "membrane") {
      group.current.rotation.y += dt * (0.15 + cell.heat);
    }
  });

  const labelY = lens.cellShape === "cabinet" ? 1.6 : 1.2;
  const showLabel = focused || hover;

  return (
    <group
      ref={group}
      position={layout.position as [number, number, number]}
      scale={focused ? 1.35 : 1}
    >
      <mesh
        geometry={geometry}
        material={material}
        onClick={(e) => {
          e.stopPropagation();
          onSelect(cell.id);
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          setHover(true);
        }}
        onPointerOut={() => setHover(false)}
      />
      {/* nucleus for living tissue — the instance heart inside the membrane */}
      {lens.cellShape === "membrane" && (
        <mesh>
          <icosahedronGeometry args={[0.28 + cell.heat * 0.3, 1]} />
          <meshStandardMaterial
            color={toColor(cell.color)}
            emissive={toColor(cell.color)}
            emissiveIntensity={1.4}
          />
        </mesh>
      )}
      {/* drawer / shelf seams for the library cabinets */}
      {lens.cellShape === "cabinet" && cell.kind === "recipe" && (
        <lineSegments>
          <edgesGeometry args={[geometry]} />
          <lineBasicMaterial color="#d9b38c" transparent opacity={0.5} />
        </lineSegments>
      )}
      {showLabel && (
        <Html
          position={[0, labelY, 0]}
          center
          distanceFactor={12}
          zIndexRange={[20, 0]}
          style={{ pointerEvents: "none", userSelect: "none" }}
        >
          <div
            style={{
              whiteSpace: "nowrap",
              fontFamily: "ui-monospace, monospace",
              fontSize: 12,
              fontWeight: 600,
              color: focused ? "#fff" : "#dbe3ff",
              textShadow: "0 1px 4px #000, 0 0 8px #000",
            }}
          >
            {cell.label}
          </div>
        </Html>
      )}
    </group>
  );
}

export function LensEdge({
  from,
  to,
  color,
  heat,
  lens,
}: {
  from: readonly [number, number, number];
  to: readonly [number, number, number];
  color: RGB;
  heat: number;
  lens: Lens;
}) {
  const dot = useRef<THREE.Mesh>(null);
  const c = useMemo(() => toColor(color), [color]);

  // routing: circuit traces bend at right angles; vessels bow outward; roads
  // drop to the ground plane; beams go straight.
  const points = useMemo(() => {
    const a = new THREE.Vector3(...from);
    const b = new THREE.Vector3(...to);
    if (lens.edge === "wire") {
      const elbow = new THREE.Vector3(b.x, (a.y + b.y) / 2, a.z);
      return [a, elbow, b];
    }
    if (lens.edge === "vessel") {
      const mid = a.clone().lerp(b, 0.5);
      mid.y += a.distanceTo(b) * 0.18;
      const curve = new THREE.QuadraticBezierCurve3(a, mid, b);
      return curve.getPoints(16);
    }
    if (lens.edge === "road") {
      return [new THREE.Vector3(a.x, 0.02, a.z), new THREE.Vector3(b.x, 0.02, b.z)];
    }
    return [a, b];
  }, [from, to, lens.edge]);

  useFrame(({ clock }) => {
    if (!dot.current) return;
    const t = (clock.elapsedTime * 0.35 + heat) % 1;
    const seg = t * (points.length - 1);
    const i = Math.min(points.length - 2, Math.floor(seg));
    const p = points[i]!.clone().lerp(points[i + 1]!, seg - i);
    dot.current.position.copy(p);
  });

  const flowing = lens.edge === "wire" || lens.edge === "vessel";

  return (
    <group>
      <Line
        points={points.map((p) => [p.x, p.y, p.z]) as [number, number, number][]}
        color={c}
        transparent
        opacity={lens.edge === "road" ? 0.4 : lens.edge === "vessel" ? 0.45 : 0.7}
        lineWidth={lens.edge === "vessel" ? 3 : lens.edge === "wire" ? 2 : 1.5}
      />
      {flowing && (
        <mesh ref={dot}>
          <sphereGeometry args={[0.12, 8, 8]} />
          <meshBasicMaterial color={c} />
        </mesh>
      )}
    </group>
  );
}

// A heightfield manifestation: the recipe's cells raise hills in a ground
// plane (height ∝ heat + connectivity), tinted by the nearest cell's blueprint.
// Walking the terrain is walking the recipe's energy landscape.
export function TerrainField({
  cells,
  layout,
}: {
  cells: SpaceCell[];
  layout: Record<string, CellLayout>;
}) {
  const geometry = useMemo(() => {
    const size = 60;
    const seg = 90;
    const geo = new THREE.PlaneGeometry(size, size, seg, seg);
    geo.rotateX(-Math.PI / 2);
    const pos = geo.attributes.position;
    const colors = new Float32Array(pos.count * 3);
    const placed = cells
      .map((c) => ({ c, l: layout[c.id] }))
      .filter((x) => x.l) as { c: SpaceCell; l: CellLayout }[];
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i);
      const z = pos.getZ(i);
      let h = 0;
      let r = 0.05;
      let g = 0.07;
      let b = 0.13;
      let wSum = 0.0001;
      for (const { c, l } of placed) {
        const dx = x - l.position[0];
        const dz = z - l.position[2];
        const d2 = dx * dx + dz * dz;
        const amp = 2.2 + c.heat * 7 + c.arity * 0.4;
        const w = Math.exp(-d2 / 18);
        h += amp * w;
        r += c.blueprintColor[0] * w;
        g += c.blueprintColor[1] * w;
        b += c.blueprintColor[2] * w;
        wSum += w;
      }
      pos.setY(i, h);
      colors[i * 3] = Math.min(1, r / wSum);
      colors[i * 3 + 1] = Math.min(1, g / wSum);
      colors[i * 3 + 2] = Math.min(1, b / wSum);
    }
    geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    geo.computeVertexNormals();
    return geo;
  }, [cells, layout]);

  return (
    <mesh geometry={geometry} position={[0, -2, 0]}>
      <meshStandardMaterial vertexColors metalness={0.1} roughness={0.85} flatShading />
    </mesh>
  );
}
