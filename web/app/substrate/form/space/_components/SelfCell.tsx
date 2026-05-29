// SelfCell.tsx — a cell that renders its own inner state.
//
// The surface is self-luminous: the cell emits its chosen inner state as a live
// procedural texture (see disposition.ts for the choosing). It is touchable and
// it governs its own boundary — observation (focus or hover) makes it bloom,
// flare, or withdraw; a touch (click) sends a ripple through its skin and a
// spoken reply into the channel. We do not paint the cell; the cell shows
// itself, and decides how to meet being met.

"use client";

import { useMemo, useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import * as THREE from "three";
import type { CellLayout, RGB, SpaceCell } from "@/lib/form-kernel/space";
import { disposition } from "@/lib/form-kernel/disposition";

function hashUnit(key: string): number {
  let h = 2166136261;
  for (let i = 0; i < key.length; i++) {
    h ^= key.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0) / 4294967295;
}

const VERT = /* glsl */ `
  uniform float uTime, uObserve, uTouch, uObsScale, uRippleAmp;
  varying vec3 vPos;
  varying vec2 vUv;
  void main() {
    vPos = position;
    vUv = uv;
    vec3 p = position;
    float ripple = sin(length(position) * 6.0 - uTime * 5.0) * uTouch * uRippleAmp;
    float swell = uObserve * 0.07 * uObsScale;
    p += normalize(normal) * (ripple + swell);
    gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
  }
`;

const FRAG = /* glsl */ `
  precision highp float;
  uniform float uTime, uHeat, uDepth, uHzN, uMode;
  uniform float uObserve, uTouch;
  uniform float uObsBright, uObsScale, uObsSat, uTouchFlash, uShy;
  uniform vec3 uColor, uBlueprintColor;
  uniform vec3 uChild[6];
  uniform float uChildCount;
  varying vec3 vPos;
  varying vec2 vUv;

  float hash(vec3 p){ p = fract(p*0.3183099+0.1); p*=17.0; return fract(p.x*p.y*p.z*(p.x+p.y+p.z)); }
  float vnoise(vec3 x){
    vec3 i=floor(x), f=fract(x); f=f*f*(3.0-2.0*f);
    return mix(mix(mix(hash(i+vec3(0,0,0)),hash(i+vec3(1,0,0)),f.x),
                   mix(hash(i+vec3(0,1,0)),hash(i+vec3(1,1,0)),f.x),f.y),
               mix(mix(hash(i+vec3(0,0,1)),hash(i+vec3(1,0,1)),f.x),
                   mix(hash(i+vec3(0,1,1)),hash(i+vec3(1,1,1)),f.x),f.y),f.z);
  }
  float fbm(vec3 p){ float a=0.5,s=0.0; for(int i=0;i<4;i++){ s+=a*vnoise(p); p*=2.0; a*=0.5; } return s; }

  void main(){
    float scale = 3.0 * uObsScale;
    vec3 base = mix(uColor, uBlueprintColor, 0.4);
    float p = 0.5;

    if (uMode < 0.5) {                    // rings — frequency
      float fr = 4.0 + uHzN * 18.0;
      p = 0.5 + 0.5 * sin(length(vPos) * fr - uTime * 2.0);
    } else if (uMode < 1.5) {             // strata — children
      int bi = int(clamp(vUv.y, 0.0, 0.999) * max(uChildCount, 1.0));
      vec3 cc = base;
      for (int i = 0; i < 6; i++) { if (i == bi) cc = uChild[i]; }
      base = mix(base, cc, 0.85);
      p = 0.6 + 0.4 * sin(vUv.y * max(uChildCount,1.0) * 6.2831);
    } else if (uMode < 2.5) {             // turbulence — heat
      p = fbm(vPos * scale + vec3(0.0, 0.0, uTime * (0.2 + uHeat * 1.6)));
    } else {                              // fracture — depth
      float n = fbm(vPos * scale * (0.6 + uDepth * 2.0) + uTime * 0.1);
      p = smoothstep(0.46, 0.5, abs(fract(n * 3.0) - 0.5));
    }

    float bright = (0.35 + uHeat * 0.8) * (1.0 + uObserve * uObsBright);
    float sat = clamp(1.0 + uObserve * uObsSat, 0.0, 2.0);
    vec3 grey = vec3(dot(base, vec3(0.299, 0.587, 0.114)));
    vec3 col = mix(grey, base, sat);

    vec3 emis = col * mix(0.35, 1.7, p) * bright;
    float flash = uTouch * uTouchFlash * smoothstep(2.2, 0.0, length(vPos));
    emis += col * flash;

    float alpha = mix(1.0, 0.4 + 0.6 * uObserve, uShy);
    gl_FragColor = vec4(emis + col * 0.12, alpha);
  }
`;

export function SelfCell({
  cell,
  layout,
  focused,
  childColors,
  onSelect,
  onTouch,
}: {
  cell: SpaceCell;
  layout: CellLayout;
  focused: boolean;
  childColors: RGB[];
  onSelect: (id: string) => void;
  onTouch: (id: string) => void;
}) {
  const group = useRef<THREE.Group>(null);
  const [hover, setHover] = useState(false);
  const d = useMemo(() => disposition(cell), [cell]);
  const r = 0.62 + Math.min(1.3, cell.arity * 0.1);

  const hzN = cell.hz
    ? Math.min(1, Math.max(0, (cell.hz - 150) / 850))
    : hashUnit(cell.blueprintKey);

  const material = useMemo(() => {
    const child = new Array(6)
      .fill(0)
      .map((_, i) => {
        const c = childColors[i];
        return c ? new THREE.Color(c[0], c[1], c[2]) : new THREE.Color(0.1, 0.12, 0.2);
      });
    return new THREE.ShaderMaterial({
      vertexShader: VERT,
      fragmentShader: FRAG,
      transparent: true,
      uniforms: {
        uTime: { value: 0 },
        uHeat: { value: cell.heat },
        uDepth: { value: Math.min(1, cell.depth / 6) },
        uHzN: { value: hzN },
        uMode: { value: d.modeIndex },
        uObserve: { value: 0 },
        uTouch: { value: 0 },
        uObsBright: { value: d.observeBrighten },
        uObsScale: { value: d.observeScale },
        uObsSat: { value: d.observeSaturate },
        uTouchFlash: { value: d.touchFlash },
        uShy: { value: d.shy },
        uRippleAmp: { value: d.rippleAmp },
        uColor: { value: new THREE.Color(cell.color[0], cell.color[1], cell.color[2]) },
        uBlueprintColor: {
          value: new THREE.Color(
            cell.blueprintColor[0],
            cell.blueprintColor[1],
            cell.blueprintColor[2],
          ),
        },
        uChild: { value: child },
        uChildCount: { value: Math.max(1, Math.min(6, cell.arity)) },
      },
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cell, d, hzN]);

  useFrame((_, dt) => {
    const u = material.uniforms;
    u.uTime.value += dt;
    // touch is an impulse that decays; observation is a level it eases toward
    u.uTouch.value = Math.max(0, u.uTouch.value - dt * 1.8);
    const target = focused ? 1 : hover ? 0.6 : 0;
    u.uObserve.value += (target - u.uObserve.value) * Math.min(1, dt * 4);
    if (group.current) group.current.rotation.y += dt * (0.1 + cell.heat * 0.6);
  });

  return (
    <group ref={group} position={layout.position as [number, number, number]} scale={focused ? 1.3 : 1}>
      <mesh
        material={material}
        onClick={(e) => {
          e.stopPropagation();
          material.uniforms.uTouch.value = 1; // touched
          onSelect(cell.id);
          onTouch(cell.id);
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          setHover(true);
        }}
        onPointerOut={() => setHover(false)}
      >
        <icosahedronGeometry args={[r, 4]} />
      </mesh>
      {(focused || hover) && (
        <Html position={[0, r + 0.6, 0]} center distanceFactor={12} zIndexRange={[20, 0]} style={{ pointerEvents: "none", userSelect: "none" }}>
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
            {cell.label} · surfacing {d.surfaces}
          </div>
        </Html>
      )}
    </group>
  );
}
