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
import { Billboard, Html } from "@react-three/drei";
import * as THREE from "three";
import type { CellLayout, RGB, SpaceCell } from "@/lib/form-kernel/space";
import { disposition } from "@/lib/form-kernel/disposition";
import { glowTexture } from "./lenses";

function hashUnit(key: string): number {
  let h = 2166136261;
  for (let i = 0; i < key.length; i++) {
    h ^= key.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0) / 4294967295;
}

const NOISE = /* glsl */ `
  float hash(vec3 p){ p = fract(p*0.3183099+0.1); p*=17.0; return fract(p.x*p.y*p.z*(p.x+p.y+p.z)); }
  float vnoise(vec3 x){
    vec3 i=floor(x), f=fract(x); f=f*f*(3.0-2.0*f);
    return mix(mix(mix(hash(i+vec3(0,0,0)),hash(i+vec3(1,0,0)),f.x),
                   mix(hash(i+vec3(0,1,0)),hash(i+vec3(1,1,0)),f.x),f.y),
               mix(mix(hash(i+vec3(0,0,1)),hash(i+vec3(1,0,1)),f.x),
                   mix(hash(i+vec3(0,1,1)),hash(i+vec3(1,1,1)),f.x),f.y),f.z);
  }
  float fbm(vec3 p){ float a=0.5,s=0.0; for(int i=0;i<5;i++){ s+=a*vnoise(p); p*=2.0; a*=0.5; } return s; }
`;

const VERT = /* glsl */ `
  uniform float uTime, uObserve, uTouch, uObsScale, uRippleAmp, uHeat;
  varying vec3 vPos;
  varying vec2 vUv;
  varying vec3 vN;
  varying vec3 vV;
  ${NOISE}
  void main() {
    vPos = position;
    vUv = uv;
    vec3 p = position;
    // living relief — the surface is lumpy with its own activity
    float relief = fbm(position * 3.0 + uTime * 0.15 * (0.3 + uHeat)) - 0.5;
    float amp = 0.05 + uHeat * 0.18 + uObserve * 0.05 * uObsScale;
    float ripple = sin(length(position) * 7.0 - uTime * 5.0) * uTouch * uRippleAmp;
    p += normalize(normal) * (relief * amp + ripple);
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    vN = normalize(normalMatrix * normal);
    vV = normalize(-mv.xyz);
    gl_Position = projectionMatrix * mv;
  }
`;

const FRAG = /* glsl */ `
  precision highp float;
  uniform float uTime, uHeat, uDepth, uHzN, uArityN, uMode;
  uniform float uObserve, uTouch;
  uniform float uObsBright, uObsScale, uObsSat, uTouchFlash, uShy;
  uniform vec3 uColor, uBlueprintColor;
  uniform vec3 uChild[6];
  uniform float uChildCount;
  varying vec3 vPos;
  varying vec2 vUv;
  varying vec3 vN;
  varying vec3 vV;
  ${NOISE}
  // cosine palette — vivid, harmonious iridescence (Inigo Quilez)
  vec3 pal(float t){ return 0.55 + 0.45 * cos(6.28318 * (vec3(1.0) * t + vec3(0.0, 0.33, 0.67))); }

  void main(){
    float scale = 3.0 * uObsScale;
    vec3 ident = mix(uColor, uBlueprintColor, 0.4);
    float p = 0.5;
    vec3 strataCol = ident;

    if (uMode < 0.5) {                    // rings — frequency
      float fr = 4.0 + uHzN * 20.0 + uArityN * 6.0;
      p = 0.5 + 0.5 * sin(length(vPos) * fr - uTime * 2.0);
    } else if (uMode < 1.5) {             // strata — children
      int bi = int(clamp(vUv.y, 0.0, 0.999) * max(uChildCount, 1.0));
      for (int i = 0; i < 6; i++) { if (i == bi) strataCol = uChild[i]; }
      p = 0.6 + 0.4 * sin(vUv.y * max(uChildCount, 1.0) * 6.2831);
    } else if (uMode < 2.5) {             // turbulence — heat (domain-warped)
      vec3 q = vPos * scale;
      vec3 warp = vec3(fbm(q + uTime * 0.1), fbm(q + 5.2), fbm(q + 9.1));
      p = fbm(q + warp * 1.7 + vec3(0.0, 0.0, uTime * (0.2 + uHeat * 1.6)));
    } else {                              // fracture — depth (cellular cracks)
      vec3 q = vPos * scale * (0.6 + uDepth * 2.0);
      float n = fbm(q + uTime * 0.1);
      p = smoothstep(0.44, 0.5, abs(fract(n * 3.0) - 0.5));
    }

    float fres = pow(1.0 - max(dot(normalize(vN), normalize(vV)), 0.0), 3.0);
    // identity colour kept, iridescent shimmer layered over it
    float t = uHzN + p * 0.35 + fres * 0.4 + uTime * 0.03 + uDepth * 0.12;
    vec3 baseCol = (uMode > 0.5 && uMode < 1.5) ? mix(ident, strataCol, 0.85) : ident;
    vec3 col = mix(baseCol, pal(t), 0.45);

    float sat = clamp(1.0 + uObserve * uObsSat, 0.0, 2.0);
    vec3 grey = vec3(dot(col, vec3(0.299, 0.587, 0.114)));
    col = mix(grey, col, sat);

    float bright = (0.4 + uHeat * 0.9) * (1.0 + uObserve * uObsBright);
    vec3 emis = col * mix(0.3, 1.95, p) * bright;
    // iridescent fresnel rim — the living edge
    emis += pal(t + 0.3) * fres * (1.2 + uObserve * 0.9);
    // touch — an expanding bright ring sweeps the surface
    float ring = smoothstep(0.08, 0.0, abs(length(vPos) - uTouch * 2.4)) * uTouch;
    emis += pal(t + 0.5) * ring * uTouchFlash * 1.5;
    emis += col * uTouch * uTouchFlash * 0.35;

    float alpha = mix(1.0, 0.45 + 0.55 * uObserve, uShy);
    gl_FragColor = vec4(emis, alpha);
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
        uArityN: { value: Math.min(1, cell.arity / 8) },
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

  const glowRef = useRef<THREE.MeshBasicMaterial>(null);
  const tex = useMemo(() => glowTexture(), []);

  useFrame((_, dt) => {
    const u = material.uniforms;
    u.uTime.value += dt;
    // touch is an impulse that decays; observation is a level it eases toward
    u.uTouch.value = Math.max(0, u.uTouch.value - dt * 1.8);
    const target = focused ? 1 : hover ? 0.6 : 0;
    u.uObserve.value += (target - u.uObserve.value) * Math.min(1, dt * 4);
    if (group.current) group.current.rotation.y += dt * (0.1 + cell.heat * 0.6);
    // the glow halo breathes with attention and flares on touch
    if (glowRef.current) {
      glowRef.current.opacity =
        0.3 + cell.heat * 0.5 + u.uObserve.value * 0.7 + u.uTouch.value * 1.4;
    }
  });

  return (
    <group ref={group} position={layout.position as [number, number, number]} scale={focused ? 1.3 : 1}>
      {tex && (
        <Billboard>
          <mesh>
            <planeGeometry args={[r * 5, r * 5]} />
            <meshBasicMaterial
              ref={glowRef}
              map={tex}
              color={new THREE.Color(cell.color[0], cell.color[1], cell.color[2])}
              transparent
              opacity={0.4}
              blending={THREE.AdditiveBlending}
              depthWrite={false}
            />
          </mesh>
        </Billboard>
      )}
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
        <icosahedronGeometry args={[r, 5]} />
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
