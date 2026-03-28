"use client";

/**
 * BeliefRadarChart — SVG hexagonal radar chart for 6 worldview axes.
 * No external dependencies (recharts not installed); uses pure SVG.
 * spec-169 (belief-system-interface)
 */

import React from "react";

export type WorldviewAxes = {
  scientific?: number;
  spiritual?: number;
  pragmatic?: number;
  holistic?: number;
  relational?: number;
  systemic?: number;
  [key: string]: number | undefined;
};

const AXES = [
  "scientific",
  "pragmatic",
  "relational",
  "systemic",
  "holistic",
  "spiritual",
] as const;

const AXIS_LABELS: Record<string, string> = {
  scientific: "Scientific",
  pragmatic: "Pragmatic",
  relational: "Relational",
  systemic: "Systemic",
  holistic: "Holistic",
  spiritual: "Spiritual",
};

const SIZE = 240;
const CENTER = SIZE / 2;
const RADIUS = 90;
const LEVELS = 4;

function polarToCartesian(angleDeg: number, r: number): [number, number] {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return [CENTER + r * Math.cos(rad), CENTER + r * Math.sin(rad)];
}

function buildPolygonPoints(values: number[]): string {
  return values
    .map((v, i) => {
      const angle = (360 / AXES.length) * i;
      const [x, y] = polarToCartesian(angle, v * RADIUS);
      return `${x},${y}`;
    })
    .join(" ");
}

interface Props {
  axes: WorldviewAxes;
  className?: string;
}

export function BeliefRadarChart({ axes, className }: Props) {
  const values = AXES.map((a) => Math.max(0, Math.min(1, axes[a] ?? 0)));

  return (
    <svg
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      width={SIZE}
      height={SIZE}
      className={className}
      aria-label="Worldview axes radar chart"
    >
      {/* Grid levels */}
      {Array.from({ length: LEVELS }, (_, i) => {
        const r = (RADIUS * (i + 1)) / LEVELS;
        const pts = AXES.map((_, j) => {
          const angle = (360 / AXES.length) * j;
          const [x, y] = polarToCartesian(angle, r);
          return `${x},${y}`;
        }).join(" ");
        return (
          <polygon
            key={i}
            points={pts}
            fill="none"
            stroke="currentColor"
            strokeOpacity={0.15}
            strokeWidth={1}
          />
        );
      })}

      {/* Axis lines */}
      {AXES.map((_, i) => {
        const angle = (360 / AXES.length) * i;
        const [x, y] = polarToCartesian(angle, RADIUS);
        return (
          <line
            key={i}
            x1={CENTER}
            y1={CENTER}
            x2={x}
            y2={y}
            stroke="currentColor"
            strokeOpacity={0.2}
            strokeWidth={1}
          />
        );
      })}

      {/* Data polygon */}
      <polygon
        points={buildPolygonPoints(values)}
        fill="rgba(99,102,241,0.25)"
        stroke="rgb(99,102,241)"
        strokeWidth={2}
      />

      {/* Axis labels */}
      {AXES.map((axis, i) => {
        const angle = (360 / AXES.length) * i;
        const [x, y] = polarToCartesian(angle, RADIUS + 18);
        const anchor =
          Math.abs(x - CENTER) < 5 ? "middle" : x < CENTER ? "end" : "start";
        return (
          <text
            key={axis}
            x={x}
            y={y}
            textAnchor={anchor}
            dominantBaseline="middle"
            fontSize={10}
            fill="currentColor"
            fillOpacity={0.75}
          >
            {AXIS_LABELS[axis]}
          </text>
        );
      })}

      {/* Value dots */}
      {values.map((v, i) => {
        const angle = (360 / AXES.length) * i;
        const [x, y] = polarToCartesian(angle, v * RADIUS);
        return (
          <circle key={i} cx={x} cy={y} r={3} fill="rgb(99,102,241)" />
        );
      })}
    </svg>
  );
}
