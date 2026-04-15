"use client";

import { Suspense, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, useGLTF, Environment, ContactShadows } from "@react-three/drei";

function NestModel({ url }: { url: string }) {
  const { scene } = useGLTF(url);
  const ref = useRef<any>(null);

  // Gentle rotation
  useFrame((_, delta) => {
    if (ref.current) {
      ref.current.rotation.y += delta * 0.15;
    }
  });

  return (
    <primitive ref={ref} object={scene} scale={0.4} position={[0, -0.5, 0]} />
  );
}

export function GLTFRenderer({
  modelUrl,
  caption,
  onLoad,
}: {
  modelUrl: string;
  caption?: string;
  onLoad?: () => void;
}) {
  return (
    <div className="space-y-3">
      <div className="relative aspect-[16/10] rounded-xl overflow-hidden bg-stone-900/50 border border-stone-800/30">
        <Canvas
          camera={{ position: [4, 3, 4], fov: 45 }}
          onCreated={() => onLoad?.()}
          gl={{ antialias: true }}
        >
          <ambientLight intensity={0.4} />
          <directionalLight position={[5, 8, 5]} intensity={0.8} castShadow />
          <directionalLight position={[-3, 4, -2]} intensity={0.3} color="#ffd4a0" />

          <Suspense fallback={null}>
            <NestModel url={modelUrl} />
            <ContactShadows position={[0, -1.5, 0]} opacity={0.3} scale={10} blur={2} />
            <Environment preset="sunset" />
          </Suspense>

          <OrbitControls
            enableZoom={true}
            enablePan={false}
            minDistance={2}
            maxDistance={10}
            autoRotate={false}
          />
        </Canvas>

        {/* Overlay controls hint */}
        <div className="absolute bottom-2 right-2 text-xs text-stone-600 bg-stone-950/80 px-2 py-1 rounded-lg">
          drag to rotate • scroll to zoom
        </div>
      </div>

      {caption && (
        <p className="text-xs text-stone-500 italic">{caption}</p>
      )}
    </div>
  );
}
