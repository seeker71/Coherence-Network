import type { DailyBar } from "./types";

/**
 * Small inline SVG sparkline of daily p50 latency across the window.
 *
 * Days with no successful samples are skipped (no point plotted there) so
 * gaps appear as breaks in the line rather than phantom zeros. A faint
 * reference band shows p50..p95 where both exist.
 */
export function LatencySparkline({
  daily,
  width = 240,
  height = 24,
}: {
  daily: DailyBar[];
  width?: number;
  height?: number;
}) {
  const points = daily
    .map((d, i) => ({
      i,
      p50: d.latency_p50_ms,
      p95: d.latency_p95_ms,
    }))
    .filter((p) => p.p50 !== null);

  if (points.length === 0) {
    return (
      <div
        className="text-[10px] text-muted-foreground/60 italic"
        style={{ width, height }}
      >
        no latency data yet
      </div>
    );
  }

  const xs = points.map((p) => p.i);
  const values = points.flatMap((p) => [p.p50 as number, p.p95 ?? (p.p50 as number)]);
  const minY = Math.min(...values);
  const maxY = Math.max(...values);
  const yRange = Math.max(1, maxY - minY);
  const xRange = Math.max(1, daily.length - 1);

  const toX = (i: number) => (i / xRange) * (width - 4) + 2;
  const toY = (v: number) =>
    height - 2 - ((v - minY) / yRange) * (height - 4);

  // Band polygon: p95 top to p50 bottom (reversed) — creates a filled area.
  const bandTop = points.map((p) => `${toX(p.i)},${toY(p.p95 ?? (p.p50 as number))}`);
  const bandBottom = [...points]
    .reverse()
    .map((p) => `${toX(p.i)},${toY(p.p50 as number)}`);
  const bandPoly = [...bandTop, ...bandBottom].join(" ");

  const p50Path = points
    .map((p, idx) => {
      const cmd = idx === 0 ? "M" : "L";
      return `${cmd}${toX(p.i).toFixed(1)},${toY(p.p50 as number).toFixed(1)}`;
    })
    .join(" ");

  const latest = points[points.length - 1];
  const latestLabel =
    latest.p50 !== null ? `${latest.p50} ms` : "—";

  return (
    <div className="flex items-center gap-2">
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className="flex-shrink-0"
        aria-label={`latency p50 sparkline, latest ${latestLabel}`}
      >
        <polygon points={bandPoly} fill="currentColor" opacity={0.15} />
        <path
          d={p50Path}
          fill="none"
          stroke="currentColor"
          strokeWidth={1.2}
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity={0.9}
        />
      </svg>
      <span className="text-[10px] font-mono text-muted-foreground whitespace-nowrap">
        {latestLabel}
      </span>
    </div>
  );
}
