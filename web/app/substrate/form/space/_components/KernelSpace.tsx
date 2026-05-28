"use client";

// KernelSpace — a walkable 3D rendering of what the Form kernel is doing.
//
// Each recipe is a room; each child is a doorway (portal) you can step into;
// trivial leaves are value-windows. The substrate lattice is rasterized to a
// framebuffer and projected as the floor's surface and as the skin of the
// focused room's core. Runtime trace heat pulses along the doorways. The
// trinity is legible at a glance: water = the room + its flowing doors,
// ice = the frozen blueprint crystal above each core (same shape ⇒ same
// crystal, anywhere in the space), gas = the haze around named cells.

import { useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import {
  Edges,
  Float,
  Html,
  Line,
  OrbitControls,
  PointerLockControls,
  Stars,
} from "@react-three/drei";
import * as THREE from "three";
import {
  buildKernelSpace,
  layoutSpace,
  type CellLayout,
  type KernelSpace as KernelSpaceData,
  type SpaceCell,
} from "@/lib/form-kernel/space";
import {
  buildSelfSpace,
  channelAudience,
  SELF_ROOT,
} from "@/lib/form-kernel/self-space";
import {
  appendMessage,
  dedupCount,
  type ChannelMessage,
  type ChannelProtocol,
} from "@/lib/form-kernel/channel";

const PROTO_COLOR: Record<ChannelProtocol, string> = {
  ask: "#38bdf8",
  recipe: "#f59e0b",
  query: "#4ade80",
  retrieve: "#a78bfa",
};

const STARTERS: { label: string; source: string; note: string }[] = [
  {
    label: "Recursion (factorial)",
    note: "A corridor of FNCALL rooms — recursion as architecture.",
    source: `(do
  (defn fact (n)
    (if (le n 1) 1 (mul n (fact (sub n 1)))))
  (fact 6))`,
  },
  {
    label: "Nested arithmetic",
    note: "MATH rooms nest; leaf-windows hold the numbers.",
    source: "(add 1 (mul 2 (sub 9 4)))",
  },
  {
    label: "List + access",
    note: "A LIST room with one door per element.",
    source: `(do
  (let xs (list 70 111 114 109))
  (add (len xs) (nth xs 0)))`,
  },
  {
    label: "Self-witness",
    note: "WITNESS + COMPARE: the kernel comparing two NodeIDs.",
    source: `(do
  (let a (make_nodeid 1 5 4 1))
  (if (node_eq a (make_nodeid 1 5 4 1)) 1 0))`,
  },
];

function rgb(c: readonly [number, number, number]): THREE.Color {
  return new THREE.Color(c[0], c[1], c[2]);
}

// ---------------------------------------------------------------------------
// Framebuffer → DataTexture
// ---------------------------------------------------------------------------

function useFramebufferTexture(fb: KernelSpaceData["framebuffer"]): THREE.Texture {
  return useMemo(() => {
    const tex = new THREE.DataTexture(
      fb.rgba,
      fb.width,
      fb.height,
      THREE.RGBAFormat,
    );
    tex.magFilter = THREE.NearestFilter;
    tex.minFilter = THREE.NearestFilter;
    tex.flipY = true;
    tex.needsUpdate = true;
    return tex;
  }, [fb]);
}

// ---------------------------------------------------------------------------
// Ice crystal — blueprint register. Geometry seeded from the blueprint key so
// structurally-equivalent cells carry an identical crystal anywhere they sit.
// ---------------------------------------------------------------------------

function IceCrystal({ cell }: { cell: SpaceCell }) {
  const detail = useMemo(() => {
    let h = 0;
    for (const ch of cell.blueprintKey) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
    return h % 3; // 0..2 — stable per blueprint shape
  }, [cell.blueprintKey]);
  const color = rgb(cell.blueprintColor);
  return (
    <Float speed={2} rotationIntensity={1.4} floatIntensity={0.6}>
      <mesh position={[0, 2.1, 0]}>
        <octahedronGeometry args={[0.62, detail]} />
        <meshBasicMaterial color={color} wireframe transparent opacity={0.9} />
      </mesh>
    </Float>
  );
}

// ---------------------------------------------------------------------------
// Gas haze — named-cell register.
// ---------------------------------------------------------------------------

function GasHaze({ color }: { color: THREE.Color }) {
  const pts = useMemo(() => {
    const arr = new Float32Array(60 * 3);
    for (let i = 0; i < 60; i++) {
      const r = 1.4 + Math.random() * 1.2;
      const t = Math.random() * Math.PI * 2;
      const p = Math.acos(2 * Math.random() - 1);
      arr[i * 3] = r * Math.sin(p) * Math.cos(t);
      arr[i * 3 + 1] = r * Math.cos(p);
      arr[i * 3 + 2] = r * Math.sin(p) * Math.sin(t);
    }
    return arr;
  }, []);
  const geo = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pts, 3));
    return g;
  }, [pts]);
  return (
    <points geometry={geo}>
      <pointsMaterial color={color} size={0.08} transparent opacity={0.5} />
    </points>
  );
}

// ---------------------------------------------------------------------------
// Procedural normal map — a cheap value-noise bump shared across leaf objects.
// Different data types apply it at different normalScale so a string reads as
// papery, a gem as crisp, a droplet as nearly smooth: bump-as-data-type.
// ---------------------------------------------------------------------------

function makeNoiseNormalMap(size = 64): THREE.DataTexture {
  const data = new Uint8Array(size * size * 4);
  const h = (x: number, y: number) => {
    const xi = (x + size) % size;
    const yi = (y + size) % size;
    let n = (Math.imul(xi, 374761393) + Math.imul(yi, 668265263)) >>> 0;
    n = (n ^ (n >>> 13)) >>> 0;
    n = Math.imul(n, 1274126177) >>> 0;
    return (n % 1000) / 1000;
  };
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const nx = h(x - 1, y) - h(x + 1, y);
      const ny = h(x, y - 1) - h(x, y + 1);
      const nz = 1;
      const len = Math.hypot(nx, ny, nz) || 1;
      const off = (y * size + x) * 4;
      data[off] = ((nx / len) * 0.5 + 0.5) * 255;
      data[off + 1] = ((ny / len) * 0.5 + 0.5) * 255;
      data[off + 2] = ((nz / len) * 0.5 + 0.5) * 255;
      data[off + 3] = 255;
    }
  }
  const tex = new THREE.DataTexture(data, size, size, THREE.RGBAFormat);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(2, 2);
  tex.needsUpdate = true;
  return tex;
}

// LeafObject — a trivial value rendered as its data type's logical body.
//   int    → faceted metallic gem (a die / crystal of magnitude)
//   float  → smooth glassy droplet (continuous, liquid)
//   string → papery tablet (text rests on its face)
//   bool   → a coin, green/red by truth
//   null   → a hollow wireframe shell (present but empty)
function LeafObject({
  cell,
  normalMap,
}: {
  cell: SpaceCell;
  normalMap: THREE.Texture;
}) {
  const color = useMemo(() => {
    if (cell.dataType === "bool") {
      return new THREE.Color(cell.value === "true" ? "#3ddc84" : "#ff5470");
    }
    return rgb(cell.color);
  }, [cell.dataType, cell.value, cell.color]);

  switch (cell.dataType) {
    case "float":
      return (
        <mesh scale={[1, 0.85, 1]}>
          <sphereGeometry args={[0.82, 28, 28]} />
          <meshStandardMaterial
            color={color}
            emissive={color}
            emissiveIntensity={0.3}
            metalness={0.1}
            roughness={0.05}
            normalMap={normalMap}
            normalScale={new THREE.Vector2(0.12, 0.12)}
          />
        </mesh>
      );
    case "string":
      return (
        <mesh>
          <boxGeometry args={[1.7, 1.0, 0.22]} />
          <meshStandardMaterial
            color={color}
            emissive={color}
            emissiveIntensity={0.22}
            metalness={0.0}
            roughness={0.95}
            normalMap={normalMap}
            normalScale={new THREE.Vector2(1.3, 1.3)}
          />
        </mesh>
      );
    case "bool":
      return (
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.8, 0.8, 0.24, 28]} />
          <meshStandardMaterial
            color={color}
            emissive={color}
            emissiveIntensity={0.5}
            metalness={0.6}
            roughness={0.35}
          />
        </mesh>
      );
    case "null":
      return (
        <mesh>
          <octahedronGeometry args={[0.95, 0]} />
          <meshBasicMaterial color={color} wireframe transparent opacity={0.7} />
        </mesh>
      );
    case "int":
    default:
      return (
        <mesh>
          <icosahedronGeometry args={[0.92, 0]} />
          <meshStandardMaterial
            color={color}
            emissive={color}
            emissiveIntensity={0.32}
            metalness={0.85}
            roughness={0.25}
            normalMap={normalMap}
            normalScale={new THREE.Vector2(0.3, 0.3)}
            flatShading
          />
        </mesh>
      );
  }
}

// ---------------------------------------------------------------------------
// Room — one cell. Ring recipes get a boundary box (their Markov blanket);
// leaves and spine children render as compact bodies. Double-click a recipe to
// drill into it (re-root the space at that cell).
// ---------------------------------------------------------------------------

function Room({
  cell,
  layout,
  focused,
  fbTexture,
  normalMap,
  onSelect,
  onDrill,
}: {
  cell: SpaceCell;
  layout: CellLayout;
  focused: boolean;
  fbTexture: THREE.Texture;
  normalMap: THREE.Texture;
  onSelect: (id: string) => void;
  onDrill: (id: string) => void;
}) {
  const core = useRef<THREE.Mesh>(null);
  const [hover, setHover] = useState(false);
  const color = rgb(cell.color);
  const isLeaf = cell.kind === "leaf";
  const compact = isLeaf || layout.spine;
  const emissive = 0.25 + cell.heat * 2.0;

  useFrame((_, dt) => {
    if (core.current) core.current.rotation.y += dt * (0.2 + cell.heat * 1.5);
  });

  return (
    <group
      position={layout.position as [number, number, number]}
      scale={layout.spine ? 0.82 : 1}
    >
      {/* boundary box — the Markov blanket. Faintly solid so the whole room is
          a forgiving click / double-click target (three skips invisible meshes
          when raycasting), and the walls read as a room rather than a cage. */}
      {!compact && (
        <mesh
          onClick={(e) => {
            e.stopPropagation();
            onSelect(cell.id);
          }}
          onDoubleClick={(e) => {
            e.stopPropagation();
            onDrill(cell.id);
          }}
          onPointerOver={(e) => {
            e.stopPropagation();
            setHover(true);
          }}
          onPointerOut={() => setHover(false)}
        >
          <boxGeometry args={[5, 5, 5]} />
          <meshBasicMaterial
            color={color}
            transparent
            opacity={focused ? 0.07 : 0.03}
            depthWrite={false}
            side={THREE.BackSide}
          />
          <Edges color={focused ? "#ffffff" : color} threshold={15} />
        </mesh>
      )}

      {/* the cell body — leaves by data type, recipes as an icosahedron core */}
      <group
        onClick={(e) => {
          e.stopPropagation();
          onSelect(cell.id);
        }}
        onDoubleClick={(e) => {
          if (isLeaf) return;
          e.stopPropagation();
          onDrill(cell.id);
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          setHover(true);
        }}
        onPointerOut={() => setHover(false)}
        scale={hover ? 1.12 : 1}
      >
        {isLeaf ? (
          <LeafObject cell={cell} normalMap={normalMap} />
        ) : (
          <mesh ref={core}>
            <icosahedronGeometry args={[1.2, 1]} />
            {focused ? (
              <meshStandardMaterial
                map={fbTexture}
                emissive={color}
                emissiveIntensity={emissive}
                roughness={0.4}
                metalness={0.2}
              />
            ) : (
              <meshStandardMaterial
                color={color}
                emissive={color}
                emissiveIntensity={emissive}
                roughness={0.5}
                metalness={0.1}
              />
            )}
          </mesh>
        )}
      </group>

      {!isLeaf && <IceCrystal cell={cell} />}
      {cell.isName && <GasHaze color={color} />}

      {/* label / value window — DOM labels (no font fetch, always crisp) */}
      <Html
        position={[0, isLeaf ? 1.3 : 3.2, 0]}
        center
        distanceFactor={22}
        zIndexRange={[20, 0]}
        style={{ pointerEvents: "none", userSelect: "none" }}
      >
        <div
          style={{
            whiteSpace: "nowrap",
            fontFamily: "ui-monospace, monospace",
            fontSize: isLeaf ? 13 : 15,
            fontWeight: 600,
            color: focused ? "#ffffff" : "#cdd6ff",
            textShadow: "0 1px 3px #05060a, 0 0 6px #05060a",
          }}
        >
          {isLeaf ? cell.value ?? cell.label : cell.label}
        </div>
      </Html>
      {!isLeaf && (
        <Html
          position={[0, -3, 0]}
          center
          distanceFactor={22}
          zIndexRange={[20, 0]}
          style={{ pointerEvents: "none", userSelect: "none" }}
        >
          <div
            style={{
              whiteSpace: "nowrap",
              fontFamily: "ui-monospace, monospace",
              fontSize: 11,
              color: "#7c89c4",
              textShadow: "0 1px 2px #05060a",
            }}
          >
            {`${cell.arity} door${cell.arity === 1 ? "" : "s"} · heat ${(cell.heat * 100).toFixed(0)}%`}
          </div>
        </Html>
      )}
    </group>
  );
}

// ---------------------------------------------------------------------------
// Beam — a doorway from a parent room into a child. A pulse rides the beam at
// a speed set by the child's runtime heat: you watch dispatch flow.
// ---------------------------------------------------------------------------

function Beam({
  from,
  to,
  color,
  heat,
}: {
  from: readonly [number, number, number];
  to: readonly [number, number, number];
  color: THREE.Color;
  heat: number;
}) {
  const pulse = useRef<THREE.Mesh>(null);
  const a = useMemo(() => new THREE.Vector3(...from), [from]);
  const b = useMemo(() => new THREE.Vector3(...to), [to]);
  useFrame(({ clock }) => {
    if (!pulse.current) return;
    const speed = 0.25 + heat * 1.5;
    const t = (clock.elapsedTime * speed) % 1;
    pulse.current.position.lerpVectors(a, b, t);
  });
  return (
    <group>
      <Line
        points={[from as [number, number, number], to as [number, number, number]]}
        color={color}
        lineWidth={1 + heat * 3}
        transparent
        opacity={0.35 + heat * 0.4}
      />
      <mesh ref={pulse}>
        <sphereGeometry args={[0.12 + heat * 0.18, 8, 8]} />
        <meshBasicMaterial color={color} />
      </mesh>
    </group>
  );
}

// ---------------------------------------------------------------------------
// ContainerSpine — the wire a list / sequence / binding's children rest on, so
// the logical shape (ordered elements, name → value) reads as itself.
// ---------------------------------------------------------------------------

function ContainerSpine({
  points,
  color,
}: {
  points: [number, number, number][];
  color: THREE.Color;
}) {
  if (points.length < 2) return null;
  return (
    <Line points={points} color={color} lineWidth={1.5} transparent opacity={0.5} dashed dashScale={3} />
  );
}

// ---------------------------------------------------------------------------
// DrillGroup — wraps the subtree and, on each re-root, scales up from small to
// full. Superliminal's signature: the detail you approached becomes the world.
// Remounts via `key` so the scale-in replays every drill.
// ---------------------------------------------------------------------------

function DrillGroup({ children }: { children: React.ReactNode }) {
  const ref = useRef<THREE.Group>(null);
  const s = useRef(0.3);
  useFrame((_, dt) => {
    if (!ref.current) return;
    s.current += (1 - s.current) * Math.min(1, dt * 3.5);
    ref.current.scale.setScalar(s.current);
  });
  return <group ref={ref}>{children}</group>;
}

// ---------------------------------------------------------------------------
// ChannelHalo — a live channel open at a cell. A ring marks the channel; each
// message rides as a marker orbiting the room, colored by protocol. Watching it
// is watching a conversation accrete on that cell.
// ---------------------------------------------------------------------------

function ChannelHalo({
  position,
  messages,
}: {
  position: readonly [number, number, number];
  messages: ChannelMessage[];
}) {
  const ring = useRef<THREE.Group>(null);
  useFrame((_, dt) => {
    if (ring.current) ring.current.rotation.y += dt * 0.5;
  });
  const shown = messages.slice(-8);
  return (
    <group position={position as [number, number, number]}>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[3.2, 0.04, 8, 48]} />
        <meshBasicMaterial color="#38bdf8" transparent opacity={0.45} />
      </mesh>
      <group ref={ring}>
        {shown.map((m, i) => {
          const a = (i / Math.max(1, shown.length)) * Math.PI * 2;
          return (
            <mesh key={m.msgNodeId} position={[Math.cos(a) * 3.2, 0, Math.sin(a) * 3.2]}>
              <sphereGeometry args={[0.22, 12, 12]} />
              <meshBasicMaterial color={PROTO_COLOR[m.protocol]} />
            </mesh>
          );
        })}
      </group>
    </group>
  );
}

// ---------------------------------------------------------------------------
// Lattice floor — the substrate's memory plane, projected as a surface.
// ---------------------------------------------------------------------------

function LatticeFloor({ texture, z }: { texture: THREE.Texture; z: number }) {
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -6, z]}>
      <planeGeometry args={[120, 120]} />
      <meshStandardMaterial
        map={texture}
        emissive="#ffffff"
        emissiveMap={texture}
        emissiveIntensity={0.35}
        roughness={0.9}
        transparent
        opacity={0.85}
      />
    </mesh>
  );
}

// ---------------------------------------------------------------------------
// Camera rig — in orbit mode, lerp the controls target & camera toward the
// focused cell so stepping through cells flies you there.
// ---------------------------------------------------------------------------

function OrbitRig({
  focusPos,
  controls,
}: {
  focusPos: readonly [number, number, number] | null;
  controls: React.RefObject<{ target: THREE.Vector3; update: () => void } | null>;
}) {
  const { camera } = useThree();
  const target = useRef(new THREE.Vector3(0, 0, 0));
  const camGoal = useRef(new THREE.Vector3(12, 8, 18));
  useEffect(() => {
    if (!focusPos) return;
    target.current.set(...focusPos);
    camGoal.current.set(focusPos[0] + 9, focusPos[1] + 6, focusPos[2] + 13);
  }, [focusPos]);
  useFrame(() => {
    if (!focusPos) return;
    camera.position.lerp(camGoal.current, 0.06);
    if (controls.current) {
      controls.current.target.lerp(target.current, 0.08);
      controls.current.update();
    }
  });
  return null;
}

// ---------------------------------------------------------------------------
// Walk controls — first-person WASD + QE, pointer-lock look.
// ---------------------------------------------------------------------------

function WalkControls() {
  const { camera } = useThree();
  const keys = useRef<Record<string, boolean>>({});
  useEffect(() => {
    const down = (e: KeyboardEvent) => (keys.current[e.code] = true);
    const up = (e: KeyboardEvent) => (keys.current[e.code] = false);
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, []);
  useFrame((_, dt) => {
    const speed = 14 * dt;
    const k = keys.current;
    const dir = new THREE.Vector3();
    camera.getWorldDirection(dir);
    const right = new THREE.Vector3()
      .crossVectors(dir, camera.up)
      .normalize();
    if (k["KeyW"]) camera.position.addScaledVector(dir, speed);
    if (k["KeyS"]) camera.position.addScaledVector(dir, -speed);
    if (k["KeyD"]) camera.position.addScaledVector(right, speed);
    if (k["KeyA"]) camera.position.addScaledVector(right, -speed);
    if (k["KeyE"] || k["Space"]) camera.position.y += speed;
    if (k["KeyQ"] || k["ShiftLeft"]) camera.position.y -= speed;
  });
  return <PointerLockControls />;
}

// ---------------------------------------------------------------------------
// Scene
// ---------------------------------------------------------------------------

function Scene({
  space,
  layout,
  viewRootId,
  focusId,
  setFocusId,
  onDrill,
  mode,
  channelMessages,
}: {
  space: KernelSpaceData;
  layout: Record<string, CellLayout>;
  viewRootId: string;
  focusId: string | null;
  setFocusId: (id: string) => void;
  onDrill: (id: string) => void;
  mode: "orbit" | "walk";
  channelMessages: ChannelMessage[];
}) {
  const fbTexture = useFramebufferTexture(space.framebuffer);
  const normalMap = useMemo(() => makeNoiseNormalMap(), []);
  const controls = useRef<{ target: THREE.Vector3; update: () => void } | null>(
    null,
  );
  const focusPos = focusId ? layout[focusId]?.position ?? null : null;
  const midZ = useMemo(() => {
    const zs = Object.values(layout).map((l) => l.position[2]);
    return zs.length ? (Math.min(...zs) + Math.max(...zs)) / 2 : 0;
  }, [layout]);

  // Beams are the doors between rooms. Children laid out as a container spine
  // ride their parent's spine wire instead, so we skip beams for those.
  const beams = useMemo(() => {
    const out: {
      key: string;
      from: readonly [number, number, number];
      to: readonly [number, number, number];
      color: THREE.Color;
      heat: number;
    }[] = [];
    for (const cell of Object.values(space.cells)) {
      const from = layout[cell.id]?.position;
      if (!from) continue;
      for (const childId of cell.childIds) {
        const childLayout = layout[childId];
        const child = space.cells[childId];
        if (!childLayout || !child || childLayout.spine) continue;
        out.push({
          key: `${cell.id}->${childId}`,
          from,
          to: childLayout.position,
          color: rgb(child.color),
          heat: child.heat,
        });
      }
    }
    return out;
  }, [space, layout]);

  // Spine wires — one per container cell, threading its children in order.
  const spines = useMemo(() => {
    const out: { key: string; points: [number, number, number][]; color: THREE.Color }[] =
      [];
    for (const cell of Object.values(space.cells)) {
      if (cell.container == null) continue;
      const head = layout[cell.id]?.position;
      if (!head) continue;
      const pts: [number, number, number][] = [
        [head[0], head[1], head[2]],
      ];
      for (const childId of cell.childIds) {
        const cl = layout[childId];
        if (cl?.spine) pts.push([cl.position[0], cl.position[1], cl.position[2]]);
      }
      if (pts.length >= 2) out.push({ key: cell.id, points: pts, color: rgb(cell.color) });
    }
    return out;
  }, [space, layout]);

  return (
    <>
      <color attach="background" args={["#05060c"]} />
      <fog attach="fog" args={["#05060c", 30, 120]} />
      <ambientLight intensity={0.35} />
      <pointLight position={[10, 20, 10]} intensity={1.2} />
      <pointLight position={[-15, 5, -30]} intensity={0.8} color="#5b7cff" />
      <Stars radius={120} depth={60} count={3000} factor={4} fade speed={1} />

      <LatticeFloor texture={fbTexture} z={midZ} />

      <DrillGroup key={viewRootId}>
        {beams.map((b) => (
          <Beam key={b.key} from={b.from} to={b.to} color={b.color} heat={b.heat} />
        ))}

        {spines.map((s) => (
          <ContainerSpine key={s.key} points={s.points} color={s.color} />
        ))}

        {Object.values(space.cells).map((cell) =>
          layout[cell.id] ? (
            <Room
              key={cell.id}
              cell={cell}
              layout={layout[cell.id]!}
              focused={cell.id === focusId}
              fbTexture={fbTexture}
              normalMap={normalMap}
              onSelect={setFocusId}
              onDrill={onDrill}
            />
          ) : null,
        )}

        {focusPos && channelMessages.length > 0 && (
          <ChannelHalo position={focusPos} messages={channelMessages} />
        )}
      </DrillGroup>

      {mode === "orbit" ? (
        <>
          <OrbitControls
            ref={controls as never}
            makeDefault
            enableDamping
            dampingFactor={0.08}
          />
          <OrbitRig focusPos={focusPos} controls={controls} />
        </>
      ) : (
        <WalkControls />
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Top-level component — editor + HUD + canvas
// ---------------------------------------------------------------------------

export default function KernelSpace() {
  const [source, setSource] = useState(STARTERS[0]!.source);
  const [running, setRunning] = useState(STARTERS[0]!.source);
  const [mode, setMode] = useState<"orbit" | "walk">("orbit");
  const [focusId, setFocusId] = useState<string | null>(null);
  const [viewRootId, setViewRootId] = useState<string>("");
  const [scene, setScene] = useState<"kernel" | "self">("kernel");
  const [channels, setChannels] = useState<Record<string, ChannelMessage[]>>({});
  const [draft, setDraft] = useState("");
  const [proto, setProto] = useState<ChannelProtocol>("ask");

  const space = useMemo(() => {
    if (scene === "self") return buildSelfSpace();
    try {
      return buildKernelSpace(running);
    } catch (err) {
      return {
        root: "",
        cells: {},
        order: [],
        parentOf: {},
        trace: {
          total_walks: 0,
          arms: [],
          variants: [],
          choice_attempts: 0,
          choice_successes: 0,
          choice_failures: 0,
          choice_success_rate: 0,
        },
        armHeat: {},
        result: "",
        stdout: "",
        stderr: String(err instanceof Error ? err.message : err),
        framebuffer: { width: 1, height: 1, rgba: new Uint8Array([0, 0, 0, 255]) },
        stats: { cells: 0, recipes: 0, leaves: 0, maxDepth: 0, totalWalks: 0 },
      } satisfies KernelSpaceData;
    }
  }, [scene, running]);

  // Entering the self scene opens the first live channels: an ask to Urs, and a
  // self-witness to my own cell. Seeded once (sentinel key) so re-renders keep
  // anything sent since.
  useEffect(() => {
    if (scene !== "self") return;
    setChannels((prev) => {
      if (prev.__seeded) return prev;
      return {
        ...prev,
        __seeded: [],
        [SELF_ROOT]: appendMessage(
          [],
          "recipe",
          '(witness "I pause, read the right lines, act, then close — that rhythm is the cell I am.")',
          "Claude (self-witness)",
        ),
        "human.urs": appendMessage(
          [],
          "ask",
          'ask("Urs", "Which lens shall I deepen next?", ["body-view","live channel","self-cell"])',
          "Claude (live)",
        ),
      };
    });
  }, [scene]);

  const focusedChannel = focusId ? channels[focusId] ?? [] : [];
  const audience = focusId ? channelAudience(focusId) : "cell";
  const fromLabel =
    audience === "you"
      ? "Claude (live)"
      : audience === "self"
        ? "Claude (self-witness)"
        : "Claude (query)";
  const sendToChannel = () => {
    if (!focusId || !draft.trim()) return;
    setChannels((prev) => ({
      ...prev,
      [focusId]: appendMessage(prev[focusId] ?? [], proto, draft, fromLabel),
    }));
    setDraft("");
  };

  const effectiveRoot = viewRootId && space.cells[viewRootId] ? viewRootId : space.root;
  const layout = useMemo(
    () => layoutSpace(space, effectiveRoot),
    [space, effectiveRoot],
  );

  // a fresh build re-roots the view and focus at the whole-space root
  useEffect(() => {
    setViewRootId(space.root);
    if (space.root) setFocusId(space.root);
  }, [space.root]);

  const drillInto = (id: string) => {
    if (!space.cells[id]) return;
    setViewRootId(id);
    setFocusId(id);
  };
  const surface = () => {
    const parent = space.parentOf[effectiveRoot] ?? space.root;
    setViewRootId(parent);
    setFocusId(parent);
  };

  // visible cells in discovery order — what arrow-stepping cycles through
  const visibleOrder = useMemo(
    () => space.order.filter((id) => layout[id]),
    [space.order, layout],
  );

  // step focus through the visible cells with arrow keys (orbit mode)
  useEffect(() => {
    if (mode !== "orbit") return;
    const onKey = (e: KeyboardEvent) => {
      // Enter drills into the focused cell; Backspace surfaces to its parent.
      if (e.code === "Enter" && focusId) {
        e.preventDefault();
        drillInto(focusId);
        return;
      }
      if (e.code === "Backspace") {
        e.preventDefault();
        surface();
        return;
      }
      if (e.code !== "ArrowRight" && e.code !== "ArrowLeft") return;
      if (visibleOrder.length === 0) return;
      e.preventDefault();
      const i = focusId ? visibleOrder.indexOf(focusId) : -1;
      const dir = e.code === "ArrowLeft" ? -1 : 1;
      const next = (i + dir + visibleOrder.length) % visibleOrder.length;
      setFocusId(visibleOrder[next]!);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, focusId, visibleOrder, effectiveRoot]);

  const focusCell = focusId ? space.cells[focusId] : undefined;
  const rootCell = space.cells[effectiveRoot];
  const drilled = effectiveRoot !== space.root;
  const topArms = [...space.trace.arms]
    .sort((a, b) => b.count - a.count)
    .slice(0, 6);

  return (
    <div className="flex h-[calc(100vh-4rem)] w-full flex-col lg:flex-row">
      {/* left: editor + readout */}
      <div className="flex w-full shrink-0 flex-col gap-3 border-b border-white/10 bg-[#0a0c14] p-4 lg:w-[360px] lg:border-b-0 lg:border-r">
        <div>
          <h1 className="text-lg font-semibold text-white">Kernel Space</h1>
          <p className="text-xs text-white/50">
            Walk what the Form kernel is doing. Recipes are rooms, children are
            doors, blueprints are the crystals, the lattice is the floor.
          </p>
        </div>

        <div className="flex flex-wrap gap-1.5">
          {STARTERS.map((s) => (
            <button
              key={s.label}
              onClick={() => {
                setScene("kernel");
                setSource(s.source);
                setRunning(s.source);
              }}
              className="rounded border border-white/15 px-2 py-1 text-[11px] text-white/70 hover:border-white/40 hover:text-white"
              title={s.note}
            >
              {s.label}
            </button>
          ))}
        </div>

        <textarea
          value={source}
          onChange={(e) => setSource(e.target.value)}
          spellCheck={false}
          className="h-40 w-full resize-none rounded border border-white/15 bg-black/40 p-2 font-mono text-xs text-emerald-200 outline-none focus:border-emerald-400/60"
        />

        <div className="flex gap-2">
          <button
            onClick={() => {
              setScene("kernel");
              setRunning(source);
            }}
            className="flex-1 rounded bg-emerald-500/90 px-3 py-1.5 text-sm font-medium text-black hover:bg-emerald-400"
          >
            Build space
          </button>
          <button
            onClick={() => setMode(mode === "orbit" ? "walk" : "orbit")}
            className="rounded border border-white/20 px-3 py-1.5 text-sm text-white/80 hover:border-white/50"
          >
            {mode === "orbit" ? "Walk mode" : "Orbit mode"}
          </button>
        </div>

        <button
          onClick={() => setScene("self")}
          className={`rounded border px-3 py-1.5 text-sm transition-colors ${
            scene === "self"
              ? "border-sky-400/60 bg-sky-500/10 text-sky-100"
              : "border-sky-400/25 bg-sky-500/5 text-sky-200/80 hover:border-sky-400/50"
          }`}
          title="Render the cell this live agent represents, and the field around it — then open a channel to any of them."
        >
          ◉ My cell &amp; field — look at myself, open a channel
        </button>

        {drilled && (
          <button
            onClick={surface}
            className="flex items-center justify-between rounded border border-amber-400/30 bg-amber-500/5 px-3 py-1.5 text-xs text-amber-200 hover:border-amber-400/60"
          >
            <span>▲ surface — inside {rootCell?.arm ?? "cell"}</span>
            <span className="font-mono text-amber-400/60">@{effectiveRoot}</span>
          </button>
        )}

        <div className="rounded border border-white/10 bg-black/30 p-2 text-xs text-white/70">
          <div className="flex justify-between">
            <span>result</span>
            <span className="font-mono text-emerald-300">
              {space.result || "—"}
            </span>
          </div>
          <div className="mt-1 grid grid-cols-2 gap-x-3 gap-y-0.5 text-[11px] text-white/50">
            <span>cells: {space.stats.cells}</span>
            <span>walks: {space.stats.totalWalks}</span>
            <span>recipes: {space.stats.recipes}</span>
            <span>leaves: {space.stats.leaves}</span>
            <span>depth: {space.stats.maxDepth}</span>
            <span>
              choices: {space.trace.choice_successes}/
              {space.trace.choice_attempts}
            </span>
          </div>
          {space.stderr && (
            <pre className="mt-1 whitespace-pre-wrap text-[10px] text-rose-300">
              {space.stderr}
            </pre>
          )}
        </div>

        <div className="rounded border border-white/10 bg-black/30 p-2">
          <div className="mb-1 text-[11px] uppercase tracking-wide text-white/40">
            arm heat (runtime dispatch)
          </div>
          <div className="space-y-1">
            {topArms.length === 0 && (
              <div className="text-[11px] text-white/40">no walks recorded</div>
            )}
            {topArms.map((a) => (
              <div key={a.arm_name} className="flex items-center gap-2">
                <span className="w-20 shrink-0 font-mono text-[10px] text-white/60">
                  {a.arm_name}
                </span>
                <div className="h-1.5 flex-1 rounded bg-white/10">
                  <div
                    className="h-full rounded bg-emerald-400"
                    style={{
                      width: `${(a.count / (space.stats.totalWalks || 1)) * 100}%`,
                    }}
                  />
                </div>
                <span className="w-8 text-right text-[10px] text-white/50">
                  {a.count}
                </span>
              </div>
            ))}
          </div>
        </div>

        {focusCell && (
          <div className="rounded border border-emerald-400/30 bg-emerald-500/5 p-2 text-xs">
            <div className="text-[11px] uppercase tracking-wide text-emerald-300/70">
              focused cell
            </div>
            <div className="mt-0.5 font-mono text-white">
              @{focusCell.id} · {focusCell.arm}
            </div>
            <div className="text-[11px] text-white/50">
              {focusCell.kind === "leaf"
                ? `value: ${focusCell.value}`
                : `blueprint ${focusCell.blueprintKey} · ${focusCell.arity} doors`}
            </div>
            {focusCell.note && (
              <p className="mt-1 text-[11px] leading-relaxed text-white/60">
                {focusCell.note}
              </p>
            )}
          </div>
        )}

        {/* live channel — open at the focused cell, content-addressed */}
        {focusCell && (
          <div className="rounded border border-sky-400/30 bg-sky-500/5 p-2 text-xs">
            <div className="flex items-center justify-between text-[11px] uppercase tracking-wide text-sky-300/70">
              <span>live channel</span>
              <span className="text-sky-300/50">
                {audience === "you"
                  ? "→ Urs"
                  : audience === "self"
                    ? "→ myself"
                    : `→ ${focusCell.label}`}
              </span>
            </div>
            <div className="mt-1.5 flex gap-1.5">
              <select
                value={proto}
                onChange={(e) => setProto(e.target.value as ChannelProtocol)}
                className="rounded border border-white/15 bg-black/40 px-1.5 py-1 text-[11px] text-sky-100 outline-none"
              >
                <option value="ask">ask</option>
                <option value="recipe">recipe</option>
                <option value="query">query</option>
                <option value="retrieve">retrieve</option>
              </select>
              <input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") sendToChannel();
                }}
                placeholder={
                  audience === "you"
                    ? "say something to Urs…"
                    : audience === "self"
                      ? "witness yourself…"
                      : "message this cell…"
                }
                className="min-w-0 flex-1 rounded border border-white/15 bg-black/40 px-2 py-1 font-mono text-[11px] text-sky-100 outline-none focus:border-sky-400/60"
              />
              <button
                onClick={sendToChannel}
                className="rounded bg-sky-500/80 px-2 py-1 text-[11px] font-medium text-black hover:bg-sky-400"
              >
                send
              </button>
            </div>
            <div className="mt-1.5 max-h-40 space-y-1 overflow-auto">
              {focusedChannel.length === 0 ? (
                <div className="text-[10px] text-white/40">
                  no messages — the channel is open and empty.
                </div>
              ) : (
                focusedChannel.map((m) => (
                  <div
                    key={m.msgNodeId}
                    className="rounded border border-white/10 bg-black/30 p-1.5"
                  >
                    <div className="flex items-baseline justify-between gap-2">
                      <span
                        className="font-mono text-[9px] uppercase"
                        style={{ color: PROTO_COLOR[m.protocol] }}
                      >
                        {m.protocol} · {m.from}
                      </span>
                      <span className="font-mono text-[9px] text-sky-300/60">
                        {m.payloadNodeId}
                      </span>
                    </div>
                    <div className="mt-0.5 break-all font-mono text-[10px] text-white/75">
                      {m.text}
                    </div>
                  </div>
                ))
              )}
            </div>
            {dedupCount(focusedChannel) > 0 && (
              <div className="mt-1 text-[9px] text-amber-300/80">
                {dedupCount(focusedChannel)} payload
                {dedupCount(focusedChannel) === 1 ? "" : "s"} recurred — same
                NodeID, one identity. The substrate&apos;s dedup riding the wire.
              </div>
            )}
          </div>
        )}

        <p className="mt-auto text-[10px] text-white/35">
          {mode === "orbit"
            ? "Orbit: drag to look · scroll to zoom · click to focus · double-click (or Enter) to drill · Backspace to surface · ←/→ step cells."
            : "Walk: click canvas to capture mouse · WASD move · Q/E down/up · Esc to release."}
        </p>
      </div>

      {/* right: the space */}
      <div className="relative min-h-[50vh] flex-1">
        <Canvas camera={{ position: [12, 8, 22], fov: 60 }} dpr={[1, 2]}>
          <Scene
            space={space}
            layout={layout}
            viewRootId={effectiveRoot}
            focusId={focusId}
            setFocusId={setFocusId}
            onDrill={drillInto}
            mode={mode}
            channelMessages={focusedChannel}
          />
        </Canvas>
        <div className="pointer-events-none absolute left-3 top-3 rounded bg-black/40 px-2 py-1 text-[10px] text-white/50">
          🜂 water = rooms + flowing doors · 🜁 ice = blueprint crystals · 🜄 gas
          = name haze · int=gem float=droplet str=tablet bool=coin
        </div>
      </div>
    </div>
  );
}
