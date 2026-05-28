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
// Room — one recipe (or leaf). The core mesh is the cell; the box frame is
// its boundary. When focused, the core wears the lattice framebuffer skin.
// ---------------------------------------------------------------------------

function Room({
  cell,
  layout,
  focused,
  fbTexture,
  onSelect,
}: {
  cell: SpaceCell;
  layout: CellLayout;
  focused: boolean;
  fbTexture: THREE.Texture;
  onSelect: (id: string) => void;
}) {
  const core = useRef<THREE.Mesh>(null);
  const [hover, setHover] = useState(false);
  const color = rgb(cell.color);
  const isLeaf = cell.kind === "leaf";
  const emissive = 0.25 + cell.heat * 2.0;

  useFrame((_, dt) => {
    if (core.current) core.current.rotation.y += dt * (0.2 + cell.heat * 1.5);
  });

  return (
    <group position={layout.position as [number, number, number]}>
      {/* boundary box — the Markov blanket of the cell */}
      {!isLeaf && (
        <mesh>
          <boxGeometry args={[5, 5, 5]} />
          <meshBasicMaterial visible={false} />
          <Edges
            color={focused ? "#ffffff" : color}
            scale={1}
            threshold={15}
          />
        </mesh>
      )}

      {/* core mesh — the cell itself; focused rooms wear the memory skin */}
      <mesh
        ref={core}
        onClick={(e) => {
          e.stopPropagation();
          onSelect(cell.id);
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          setHover(true);
        }}
        onPointerOut={() => setHover(false)}
        scale={hover ? 1.12 : 1}
      >
        {isLeaf ? (
          <boxGeometry args={[1.1, 1.1, 1.1]} />
        ) : (
          <icosahedronGeometry args={[1.2, 1]} />
        )}
        {focused && !isLeaf ? (
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
  focusId,
  setFocusId,
  mode,
}: {
  space: KernelSpaceData;
  layout: Record<string, CellLayout>;
  focusId: string | null;
  setFocusId: (id: string) => void;
  mode: "orbit" | "walk";
}) {
  const fbTexture = useFramebufferTexture(space.framebuffer);
  const controls = useRef<{ target: THREE.Vector3; update: () => void } | null>(
    null,
  );
  const focusPos = focusId ? layout[focusId]?.position ?? null : null;
  const midZ = useMemo(() => {
    const zs = Object.values(layout).map((l) => l.position[2]);
    return zs.length ? (Math.min(...zs) + Math.max(...zs)) / 2 : 0;
  }, [layout]);

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
        const to = layout[childId]?.position;
        const child = space.cells[childId];
        if (!to || !child) continue;
        out.push({
          key: `${cell.id}->${childId}`,
          from,
          to,
          color: rgb(child.color),
          heat: child.heat,
        });
      }
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

      {beams.map((b) => (
        <Beam key={b.key} from={b.from} to={b.to} color={b.color} heat={b.heat} />
      ))}

      {Object.values(space.cells).map((cell) =>
        layout[cell.id] ? (
          <Room
            key={cell.id}
            cell={cell}
            layout={layout[cell.id]!}
            focused={cell.id === focusId}
            fbTexture={fbTexture}
            onSelect={setFocusId}
          />
        ) : null,
      )}

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

  const space = useMemo(() => {
    try {
      return buildKernelSpace(running);
    } catch (err) {
      return {
        root: "",
        cells: {},
        order: [],
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
  }, [running]);

  const layout = useMemo(() => layoutSpace(space), [space]);

  useEffect(() => {
    if (space.root) setFocusId(space.root);
  }, [space.root]);

  // step focus through discovery order with arrow keys (orbit mode)
  useEffect(() => {
    if (mode !== "orbit") return;
    const onKey = (e: KeyboardEvent) => {
      if (e.code !== "Tab" && e.code !== "ArrowRight" && e.code !== "ArrowLeft")
        return;
      if (space.order.length === 0) return;
      e.preventDefault();
      const i = focusId ? space.order.indexOf(focusId) : -1;
      const dir = e.code === "ArrowLeft" ? -1 : 1;
      const next = (i + dir + space.order.length) % space.order.length;
      setFocusId(space.order[next]!);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mode, focusId, space.order]);

  const focusCell = focusId ? space.cells[focusId] : undefined;
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
            onClick={() => setRunning(source)}
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
          </div>
        )}

        <p className="mt-auto text-[10px] text-white/35">
          {mode === "orbit"
            ? "Orbit: drag to look · scroll to zoom · click a room to fly in · ←/→ to step cells."
            : "Walk: click canvas to capture mouse · WASD move · Q/E down/up · Esc to release."}
        </p>
      </div>

      {/* right: the space */}
      <div className="relative min-h-[50vh] flex-1">
        <Canvas camera={{ position: [12, 8, 22], fov: 60 }} dpr={[1, 2]}>
          <Scene
            space={space}
            layout={layout}
            focusId={focusId}
            setFocusId={setFocusId}
            mode={mode}
          />
        </Canvas>
        <div className="pointer-events-none absolute left-3 top-3 rounded bg-black/40 px-2 py-1 text-[10px] text-white/50">
          🜂 water = rooms + flowing doors · 🜁 ice = blueprint crystals · 🜄 gas
          = name haze
        </div>
      </div>
    </div>
  );
}
