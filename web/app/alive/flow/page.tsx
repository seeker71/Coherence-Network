"use client";

/**
 * /alive/flow — Energy flow renderer.
 *
 * Experimental. Particles flowing along paths between nodes.
 * Each flow type is a different color stream. Intensity = particle
 * density. Speed = how fast particles travel. Multiple streams
 * overlap and weave.
 *
 * This is research — the right multi-dimensional frequency renderer
 * hasn't been invented yet. This is a first attempt at making
 * energy movement visible.
 */

import React, { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { getApiBase } from "@/lib/api";

const API = getApiBase();

type FlowNode = {
  id: string;
  label: string;
  type: string;
  size: number;
  color: string;
  x: number;
  y: number;
};

type FlowStream = {
  from: string;
  to: string;
  type: string;
  color: string;
  intensity: number;
  speed: number;
  label: string;
  particles: number;
};

type FlowData = {
  nodes: FlowNode[];
  flows: FlowStream[];
  flow_styles: Record<string, { color: string; label: string; speed: number }>;
  stats: { node_count: number; flow_count: number; flow_types: string[] };
};

export default function FlowRenderer() {
  const [data, setData] = useState<FlowData | null>(null);
  const [loading, setLoading] = useState(true);
  const [hoveredFlow, setHoveredFlow] = useState<string | null>(null);
  const [activeTypes, setActiveTypes] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/flow/render?days=30&max_nodes=60`);
      if (res.ok) {
        const d: FlowData = await res.json();
        setData(d);
        setActiveTypes(new Set(d.stats.flow_types));
      }
    } catch {
      // Flow data is exploratory
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  function toggleType(type: string) {
    setActiveTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  }

  if (loading) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-[#060610]">
        <p className="animate-pulse text-sm text-white/40">Loading flow topology...</p>
      </div>
    );
  }

  if (!data || data.nodes.length === 0) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-[#060610]">
        <p className="text-sm text-white/40">The flow is quiet. Energy will appear as the community moves.</p>
      </div>
    );
  }

  const visibleFlows = data.flows.filter((f) => activeTypes.has(f.type));

  return (
    <div className="fixed inset-0 bg-[#060610]">
      <Canvas
        camera={{ position: [0, 0, 18], fov: 50 }}
        gl={{ antialias: true, alpha: true }}
      >
        <OrbitControls
          enablePan
          enableZoom
          enableRotate
          minDistance={5}
          maxDistance={40}
          autoRotate
          autoRotateSpeed={0.3}
        />
        <ambientLight intensity={0.05} />

        {/* Nodes */}
        {data.nodes.map((node) => (
          <NodeSphere key={node.id} node={node} />
        ))}

        {/* Flow streams */}
        {visibleFlows.map((flow, i) => {
          const fromNode = data.nodes.find((n) => n.id === flow.from);
          const toNode = data.nodes.find((n) => n.id === flow.to);
          if (!fromNode || !toNode) return null;
          return (
            <FlowParticles
              key={`${flow.from}-${flow.to}-${flow.type}-${i}`}
              from={[fromNode.x, fromNode.y, 0]}
              to={[toNode.x, toNode.y, 0]}
              color={flow.color}
              intensity={flow.intensity}
              speed={flow.speed}
              particleCount={flow.particles}
            />
          );
        })}

        {/* Ambient dust */}
        <CosmicDust />
      </Canvas>

      {/* Flow type legend / toggles */}
      <div className="absolute left-4 top-4 space-y-1">
        <p className="mb-2 text-xs font-medium text-white/30 uppercase tracking-wider">
          Energy Flows
        </p>
        {Object.entries(data.flow_styles).map(([type, style]) => {
          const count = data.flows.filter((f) => f.type === type).length;
          if (count === 0) return null;
          const active = activeTypes.has(type);
          return (
            <button
              key={type}
              onClick={() => toggleType(type)}
              className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs transition-all ${
                active
                  ? "bg-white/10 text-white/80"
                  : "bg-white/5 text-white/30"
              }`}
            >
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{
                  backgroundColor: active ? style.color : "#444",
                  boxShadow: active ? `0 0 6px ${style.color}` : "none",
                }}
              />
              <span>{style.label}</span>
              <span className="ml-1 text-white/20">{count}</span>
            </button>
          );
        })}
      </div>

      {/* Stats */}
      <div className="absolute right-4 top-4 text-right">
        <p className="text-xs text-white/20">
          {data.stats.node_count} entities · {visibleFlows.length} flows
        </p>
      </div>

      {/* Hover info */}
      {hoveredFlow && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 rounded-xl bg-black/60 px-4 py-2 text-xs text-white/70 backdrop-blur">
          {hoveredFlow}
        </div>
      )}

      {/* Refresh */}
      <button
        onClick={load}
        className="absolute bottom-4 right-4 rounded-full bg-white/5 px-3 py-1.5 text-xs text-white/30 transition-colors hover:bg-white/10 hover:text-white/60"
      >
        Refresh
      </button>

      {/* Back */}
      <a
        href="/alive"
        className="absolute bottom-4 left-4 text-xs text-white/20 transition-colors hover:text-white/50"
      >
        ← Pulse
      </a>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Three.js components
// ---------------------------------------------------------------------------

function NodeSphere({ node }: { node: FlowNode }) {
  const meshRef = useRef<THREE.Mesh>(null);
  const glowRef = useRef<THREE.Mesh>(null);

  useFrame(({ clock }) => {
    if (meshRef.current) {
      const t = clock.getElapsedTime();
      const pulse = 1 + Math.sin(t * 1.5 + node.x) * 0.08;
      meshRef.current.scale.setScalar(node.size * pulse);
    }
    if (glowRef.current) {
      const t = clock.getElapsedTime();
      (glowRef.current.material as THREE.MeshBasicMaterial).opacity =
        0.08 + Math.sin(t * 0.8 + node.y) * 0.04;
      glowRef.current.scale.setScalar(node.size * 3);
    }
  });

  return (
    <group position={[node.x, node.y, 0]}>
      <mesh ref={glowRef}>
        <sphereGeometry args={[1, 12, 12]} />
        <meshBasicMaterial
          color={node.color}
          transparent
          opacity={0.1}
          depthWrite={false}
        />
      </mesh>
      <mesh ref={meshRef}>
        <sphereGeometry args={[1, 24, 24]} />
        <meshBasicMaterial color={node.color} />
      </mesh>
    </group>
  );
}

function FlowParticles({
  from,
  to,
  color,
  intensity,
  speed,
  particleCount,
}: {
  from: [number, number, number];
  to: [number, number, number];
  color: string;
  intensity: number;
  speed: number;
  particleCount: number;
}) {
  const pointsRef = useRef<THREE.Points>(null);
  const count = Math.max(3, particleCount);

  // Curved path between from and to
  const curve = useMemo(() => {
    const mid: [number, number, number] = [
      (from[0] + to[0]) / 2,
      (from[1] + to[1]) / 2,
      // Curve lifts perpendicular to the line
      1.5 + Math.random() * 1.5,
    ];
    return new THREE.QuadraticBezierCurve3(
      new THREE.Vector3(...from),
      new THREE.Vector3(...mid),
      new THREE.Vector3(...to),
    );
  }, [from, to]);

  // Initial positions distributed along curve
  const { positions, offsets } = useMemo(() => {
    const pos = new Float32Array(count * 3);
    const off = new Float32Array(count); // phase offset per particle
    for (let i = 0; i < count; i++) {
      off[i] = i / count;
      const p = curve.getPoint(off[i]);
      pos[i * 3] = p.x;
      pos[i * 3 + 1] = p.y;
      pos[i * 3 + 2] = p.z;
    }
    return { positions: pos, offsets: off };
  }, [curve, count]);

  useFrame(({ clock }) => {
    if (!pointsRef.current) return;
    const geo = pointsRef.current.geometry;
    const posAttr = geo.attributes.position;
    if (!posAttr) return;

    const t = clock.getElapsedTime();
    for (let i = 0; i < count; i++) {
      // Each particle travels along the curve at its own phase
      const phase = (offsets[i] + t * speed * 0.3) % 1.0;
      const p = curve.getPoint(phase);
      (posAttr as THREE.BufferAttribute).setXYZ(i, p.x, p.y, p.z);
    }
    posAttr.needsUpdate = true;
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
        />
      </bufferGeometry>
      <pointsMaterial
        color={color}
        size={0.08 + intensity * 0.12}
        transparent
        opacity={0.3 + intensity * 0.5}
        sizeAttenuation
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}

function CosmicDust() {
  const pointsRef = useRef<THREE.Points>(null);
  const count = 300;

  const positions = useMemo(() => {
    const arr = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      arr[i * 3] = (Math.random() - 0.5) * 30;
      arr[i * 3 + 1] = (Math.random() - 0.5) * 30;
      arr[i * 3 + 2] = (Math.random() - 0.5) * 15;
    }
    return arr;
  }, []);

  useFrame(({ clock }) => {
    if (pointsRef.current) {
      pointsRef.current.rotation.y = clock.getElapsedTime() * 0.01;
    }
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
        />
      </bufferGeometry>
      <pointsMaterial
        color="#ffffff"
        size={0.02}
        transparent
        opacity={0.15}
        sizeAttenuation
        depthWrite={false}
      />
    </points>
  );
}
