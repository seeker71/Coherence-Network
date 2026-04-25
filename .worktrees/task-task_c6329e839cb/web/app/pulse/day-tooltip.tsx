"use client";

import { useId, useState } from "react";
import type { DailyBar, Silence } from "./types";
import { STATUS_LABEL, formatDuration } from "./status-tokens";

/**
 * Rich hover/focus tooltip anchored to a single day bar.
 *
 * The bar is a real interactive element (button), so tooltips work on
 * mouse, touch (tap to toggle), and keyboard (focus to show, Escape to
 * hide). The tooltip content is composed from the day's bucket data plus
 * any silences whose window overlaps that day, so hovering a red bar
 * tells you exactly what the witness recorded.
 */
export function DayBar({
  day,
  silencesForDay,
  organLabel,
  barClass,
}: {
  day: DailyBar;
  silencesForDay: Silence[];
  organLabel: string;
  barClass: string;
}) {
  const [visible, setVisible] = useState(false);
  const tooltipId = useId();

  const title = `${organLabel} · ${day.date}`;
  const statusLabel = STATUS_LABEL[day.status];
  const noData = day.samples === 0;

  return (
    <div className="relative flex-1 min-w-[3px]">
      <button
        type="button"
        aria-describedby={visible ? tooltipId : undefined}
        aria-label={`${title} · ${statusLabel}${
          noData ? " · no samples" : ` · ${day.samples} samples, ${day.failures} failures`
        }`}
        onMouseEnter={() => setVisible(true)}
        onMouseLeave={() => setVisible(false)}
        onFocus={() => setVisible(true)}
        onBlur={() => setVisible(false)}
        onClick={() => setVisible((v) => !v)}
        onKeyDown={(e) => {
          if (e.key === "Escape") setVisible(false);
        }}
        className={`block w-full rounded-sm ${barClass} hover:opacity-100 opacity-90 focus:opacity-100 focus:outline-none focus:ring-1 focus:ring-emerald-400/60 transition-opacity`}
        style={{ height: noData ? "35%" : "100%", minHeight: "4px" }}
      />
      {visible && (
        <div
          id={tooltipId}
          role="tooltip"
          className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-20 w-64 rounded-xl border border-border/40 bg-popover/95 backdrop-blur-md shadow-xl p-3 text-left pointer-events-none"
        >
          <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
            {organLabel}
          </p>
          <p className="text-sm font-medium">{day.date}</p>
          <div className="mt-2 flex items-center justify-between">
            <span className="text-xs text-muted-foreground">state</span>
            <span className="text-xs font-medium">{statusLabel}</span>
          </div>
          {noData ? (
            <p className="mt-2 text-xs text-muted-foreground italic">
              no samples recorded — witness was quiet this day
            </p>
          ) : (
            <>
              <div className="mt-2 flex items-center justify-between">
                <span className="text-xs text-muted-foreground">samples</span>
                <span className="text-xs font-mono">{day.samples}</span>
              </div>
              {day.failures > 0 && (
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">failures</span>
                  <span className="text-xs font-mono text-rose-400">
                    {day.failures}
                  </span>
                </div>
              )}
              {day.latency_p50_ms !== null && (
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">p50</span>
                  <span className="text-xs font-mono">{day.latency_p50_ms} ms</span>
                </div>
              )}
              {day.latency_p95_ms !== null && (
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">p95</span>
                  <span className="text-xs font-mono">{day.latency_p95_ms} ms</span>
                </div>
              )}
            </>
          )}
          {silencesForDay.length > 0 && (
            <div className="mt-3 border-t border-border/30 pt-2 space-y-1">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
                silences on this day
              </p>
              {silencesForDay.map((s) => (
                <div key={s.id} className="text-xs">
                  <span
                    className={
                      s.severity === "silent" ? "text-rose-400" : "text-amber-400"
                    }
                  >
                    {s.severity}
                  </span>
                  <span className="text-muted-foreground">
                    {" · "}
                    {formatDuration(s.duration_seconds)}
                  </span>
                  {s.note && (
                    <p className="text-muted-foreground italic truncate">{s.note}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

