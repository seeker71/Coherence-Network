"use client";

/**
 * /alive — The living pulse dashboard.
 *
 * Colors, movement, breath. Each quality of the community
 * is a glowing orb — its brightness, size, and pulse rhythm
 * carry the felt state. The field breathes as one.
 *
 * Uses Three.js for the animated particle field.
 * Uses /api/energy/pulse for the felt qualities.
 */

import React, { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { getApiBase } from "@/lib/api";

const API = getApiBase();

// Quality → color mapping (warm, living colors)
const QUALITY_COLORS: Record<string, string> = {
  vital: "#ff6b6b",       // warm red — life force
  joyful: "#ffd93d",      // golden yellow — delight
  curious: "#6bcb77",     // green — exploration
  abundant: "#ff8c42",    // amber — plenty
  free: "#4ecdc4",        // teal — openness
  open: "#95e1d3",        // seafoam — welcoming
  understanding: "#a8d8ea",// light blue — seeing
  trusting: "#7c73e6",    // purple — depth
  loving: "#f38181",      // rose — tenderness
  graceful: "#aa96da",    // lavender — ease
  grateful: "#fcbad3",    // pink — receiving
  present: "#f5f5dc",     // warm white — here
  alive: "#ffffff",       // pure white — the whole
};

type PulseQuality = {
  quality: string;
  description: string;
  energy: number;
  feeling: string;
  frequency_hz: number;
  signs: string[];
};

type PulseData = {
  overall_feeling: string;
  overall_energy: number;
  qualities: PulseQuality[];
};

export default function AliveDashboard() {
  const [pulse, setPulse] = useState<PulseData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedQuality, setSelectedQuality] = useState<PulseQuality | null>(null);

  const loadPulse = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/energy/pulse`);
      if (res.ok) {
        const data = await res.json();
        setPulse(data);
      }
    } catch {
      // The pulse is observational
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadPulse(); }, [loadPulse]);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(loadPulse, 30000);
    return () => clearInterval(interval);
  }, [loadPulse]);

  if (loading) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-background">
        <div className="animate-pulse text-sm text-muted-foreground">
          Sensing...
        </div>
      </div>
    );
  }

  if (!pulse) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-background">
        <p className="text-sm text-muted-foreground">
          The pulse is quiet. Refresh to sense again.
        </p>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-[#0a0a0f]">
      {/* Three.js field */}
      <Canvas
        camera={{ position: [0, 0, 12], fov: 60 }}
        gl={{ antialias: true, alpha: true }}
      >
        <ambientLight intensity={0.1} />
        <PulseField
          qualities={pulse.qualities}
          onSelect={(q) => setSelectedQuality(q)}
        />
        <BreathingBackground energy={pulse.overall_energy} />
      </Canvas>

      {/* Overlay: overall feeling */}
      <div className="pointer-events-none absolute inset-x-0 top-0 flex flex-col items-center pt-8">
        <p className="max-w-md text-center text-sm leading-relaxed text-white/70">
          {pulse.overall_feeling}
        </p>
      </div>

      {/* Selected quality detail */}
      {selectedQuality && (
        <div className="absolute bottom-0 inset-x-0 p-6 pointer-events-auto">
          <div
            className="mx-auto max-w-md rounded-2xl border border-white/10 bg-black/60 p-5 backdrop-blur-xl"
            onClick={() => setSelectedQuality(null)}
          >
            <div className="flex items-center gap-3">
              <div
                className="h-3 w-3 rounded-full"
                style={{
                  backgroundColor: QUALITY_COLORS[selectedQuality.quality] || "#fff",
                  boxShadow: `0 0 12px ${QUALITY_COLORS[selectedQuality.quality] || "#fff"}`,
                }}
              />
              <h3 className="text-sm font-semibold capitalize text-white">
                {selectedQuality.quality}
              </h3>
              <span className="ml-auto text-xs text-white/40">
                {selectedQuality.frequency_hz} Hz
              </span>
            </div>
            <p className="mt-2 text-sm leading-relaxed text-white/80">
              {selectedQuality.feeling}
            </p>
            {selectedQuality.signs.length > 0 && (
              <div className="mt-3 space-y-1">
                {selectedQuality.signs.map((sign, i) => (
                  <p key={i} className="text-xs text-white/50">
                    {sign}
                  </p>
                ))}
              </div>
            )}
            <p className="mt-3 text-xs text-white/30">
              {selectedQuality.description}
            </p>
          </div>
        </div>
      )}

      {/* Refresh button */}
      <button
        onClick={loadPulse}
        className="pointer-events-auto absolute right-4 top-4 rounded-full bg-white/5 px-3 py-1.5 text-xs text-white/40 transition-colors hover:bg-white/10 hover:text-white/70"
      >
        Sense again
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Three.js components
// ---------------------------------------------------------------------------

function PulseField({
  qualities,
  onSelect,
}: {
  qualities: PulseQuality[];
  onSelect: (q: PulseQuality) => void;
}) {
  return (
    <group>
      {qualities.map((q, i) => {
        const angle = (i / qualities.length) * Math.PI * 2;
        const radius = q.quality === "alive" ? 0 : 4 + (1 - q.energy) * 2;
        const x = Math.cos(angle) * radius;
        const y = Math.sin(angle) * radius;

        return (
          <QualityOrb
            key={q.quality}
            quality={q}
            position={[x, y, 0]}
            onClick={() => onSelect(q)}
          />
        );
      })}
      <AmbientParticles count={200} />
    </group>
  );
}

function QualityOrb({
  quality,
  position,
  onClick,
}: {
  quality: PulseQuality;
  position: [number, number, number];
  onClick: () => void;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const glowRef = useRef<THREE.Mesh>(null);
  const color = QUALITY_COLORS[quality.quality] || "#ffffff";
  const baseSize = 0.2 + quality.energy * 0.5;
  // Pulse speed from frequency (scaled to visible range)
  const pulseSpeed = quality.frequency_hz / 300;

  useFrame(({ clock }) => {
    if (meshRef.current) {
      const t = clock.getElapsedTime();
      const pulse = 1 + Math.sin(t * pulseSpeed) * 0.15 * quality.energy;
      meshRef.current.scale.setScalar(baseSize * pulse);
    }
    if (glowRef.current) {
      const t = clock.getElapsedTime();
      const glow = 0.3 + Math.sin(t * pulseSpeed * 0.5) * 0.2;
      (glowRef.current.material as THREE.MeshBasicMaterial).opacity = glow * quality.energy;
      glowRef.current.scale.setScalar(baseSize * 3);
    }
  });

  return (
    <group position={position}>
      {/* Glow */}
      <mesh ref={glowRef}>
        <sphereGeometry args={[1, 16, 16]} />
        <meshBasicMaterial
          color={color}
          transparent
          opacity={0.2}
          depthWrite={false}
        />
      </mesh>
      {/* Core */}
      <mesh
        ref={meshRef}
        onClick={(e) => {
          e.stopPropagation();
          onClick();
        }}
      >
        <sphereGeometry args={[1, 32, 32]} />
        <meshBasicMaterial color={color} />
      </mesh>
    </group>
  );
}

function AmbientParticles({ count }: { count: number }) {
  const pointsRef = useRef<THREE.Points>(null);

  const positions = useMemo(() => {
    const arr = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      arr[i * 3] = (Math.random() - 0.5) * 20;
      arr[i * 3 + 1] = (Math.random() - 0.5) * 20;
      arr[i * 3 + 2] = (Math.random() - 0.5) * 10;
    }
    return arr;
  }, [count]);

  useFrame(({ clock }) => {
    if (pointsRef.current) {
      pointsRef.current.rotation.y = clock.getElapsedTime() * 0.02;
      pointsRef.current.rotation.x = Math.sin(clock.getElapsedTime() * 0.01) * 0.1;
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
        size={0.03}
        transparent
        opacity={0.3}
        sizeAttenuation
        depthWrite={false}
      />
    </points>
  );
}

function BreathingBackground({ energy }: { energy: number }) {
  const meshRef = useRef<THREE.Mesh>(null);

  useFrame(({ clock }) => {
    if (meshRef.current) {
      const t = clock.getElapsedTime();
      // Slow breath: 6 seconds in, 6 seconds out
      const breath = Math.sin(t * 0.52) * 0.5 + 0.5;
      const intensity = 0.02 + breath * 0.03 * energy;
      (meshRef.current.material as THREE.MeshBasicMaterial).opacity = intensity;
      meshRef.current.scale.setScalar(15 + breath * 2);
    }
  });

  return (
    <mesh ref={meshRef} position={[0, 0, -5]}>
      <sphereGeometry args={[1, 32, 32]} />
      <meshBasicMaterial
        color="#1a1a3e"
        transparent
        opacity={0.05}
        side={THREE.BackSide}
      />
    </mesh>
  );
}
