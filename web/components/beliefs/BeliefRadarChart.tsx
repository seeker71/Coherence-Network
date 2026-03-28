"use client";

import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

type WorldviewAxes = {
  scientific: number;
  spiritual: number;
  pragmatic: number;
  holistic: number;
  relational: number;
  systemic: number;
};

interface Props {
  axes: WorldviewAxes;
}

const AXIS_LABELS: Record<string, string> = {
  scientific: "Scientific",
  spiritual: "Spiritual",
  pragmatic: "Pragmatic",
  holistic: "Holistic",
  relational: "Relational",
  systemic: "Systemic",
};

export function BeliefRadarChart({ axes }: Props) {
  const data = Object.entries(axes).map(([key, value]) => ({
    subject: AXIS_LABELS[key] ?? key,
    value: Math.round(value * 100),
    fullMark: 100,
  }));

  const hasData = data.some((d) => d.value > 0);

  return (
    <div style={{ minHeight: 280 }}>
      {!hasData && (
        <p className="text-sm text-muted-foreground text-center pt-10 italic">
          No worldview data yet — set your axes below to see your belief radar.
        </p>
      )}
      <ResponsiveContainer width="100%" height={280}>
        <RadarChart cx="50%" cy="50%" outerRadius="70%" data={data}>
          <PolarGrid />
          <PolarAngleAxis dataKey="subject" tick={{ fontSize: 12 }} />
          <PolarRadiusAxis angle={90} domain={[0, 100]} tick={false} axisLine={false} />
          <Radar
            name="Beliefs"
            dataKey="value"
            stroke="hsl(var(--primary))"
            fill="hsl(var(--primary))"
            fillOpacity={0.3}
          />
          <Tooltip formatter={(v: number) => [`${v}%`, "Weight"]} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
