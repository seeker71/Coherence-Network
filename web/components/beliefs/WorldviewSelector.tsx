"use client";

/**
 * WorldviewSelector — axis sliders (0–100) for all 6 worldview axes.
 * PATCH with 500ms debounce; optimistic update with rollback on error.
 * spec-169 (belief-system-interface)
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import { getApiBase } from "@/lib/api";

const AXES = [
  { key: "scientific", label: "Scientific", desc: "Evidence-based, empirical reasoning" },
  { key: "pragmatic", label: "Pragmatic", desc: "Practical outcomes and utility" },
  { key: "relational", label: "Relational", desc: "Connection, context, and relationships" },
  { key: "systemic", label: "Systemic", desc: "Patterns, emergence, and systems thinking" },
  { key: "holistic", label: "Holistic", desc: "Whole-system integration, mind-body" },
  { key: "spiritual", label: "Spiritual", desc: "Meaning, transcendence, inner experience" },
] as const;

type AxisKey = (typeof AXES)[number]["key"];
type AxesState = Record<AxisKey, number>;

interface Props {
  contributorId: string;
  initialAxes: Record<string, number>;
  onSaved?: (axes: AxesState) => void;
}

const API_BASE = getApiBase();

function useDebounce<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(t);
  }, [value, delayMs]);
  return debounced;
}

export function WorldviewSelector({ contributorId, initialAxes, onSaved }: Props) {
  const [axes, setAxes] = useState<AxesState>(() => {
    const base: AxesState = {
      scientific: 0, pragmatic: 0, relational: 0,
      systemic: 0, holistic: 0, spiritual: 0,
    };
    for (const { key } of AXES) {
      base[key] = Math.round((initialAxes[key] ?? 0) * 100);
    }
    return base;
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const prevAxesRef = useRef<AxesState>(axes);
  const debouncedAxes = useDebounce(axes, 500);
  const hasChangedRef = useRef(false);

  const save = useCallback(async (toSave: AxesState) => {
    setSaving(true);
    setError(null);
    const prev = prevAxesRef.current;
    const payload: Record<string, number> = {};
    for (const { key } of AXES) {
      payload[key] = toSave[key] / 100;
    }
    try {
      const res = await fetch(`${API_BASE}/api/contributors/${encodeURIComponent(contributorId)}/beliefs`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ worldview_axes: payload }),
      });
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg);
      }
      prevAxesRef.current = toSave;
      onSaved?.(toSave);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
      // Optimistic rollback
      setAxes(prev);
    } finally {
      setSaving(false);
    }
  }, [contributorId, onSaved]);

  useEffect(() => {
    if (!hasChangedRef.current) {
      hasChangedRef.current = true;
      return;
    }
    save(debouncedAxes);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedAxes]);

  function handleChange(key: AxisKey, rawValue: string) {
    hasChangedRef.current = true;
    const v = Math.max(0, Math.min(100, Number(rawValue)));
    setAxes((prev) => ({ ...prev, [key]: v }));
  }

  function barWidth(value: number): string {
    return `${value}%`;
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        {AXES.map(({ key, label, desc }) => (
          <div key={key} className="space-y-1">
            <div className="flex items-center justify-between">
              <label htmlFor={`axis-${key}`} className="text-sm font-medium">
                {label}
              </label>
              <span className="text-xs text-muted-foreground tabular-nums w-8 text-right">
                {axes[key]}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">{desc}</p>
            <div className="relative h-2 rounded-full bg-secondary overflow-hidden">
              <div
                className="absolute inset-y-0 left-0 bg-indigo-500 rounded-full transition-all"
                style={{ width: barWidth(axes[key]) }}
              />
            </div>
            <input
              id={`axis-${key}`}
              type="range"
              min={0}
              max={100}
              value={axes[key]}
              onChange={(e) => handleChange(key, e.target.value)}
              className="w-full h-2 opacity-0 absolute cursor-pointer"
              aria-label={`${label} worldview axis`}
            />
          </div>
        ))}
      </div>

      {saving && (
        <p className="text-xs text-muted-foreground">Saving…</p>
      )}
      {error && (
        <p className="text-xs text-destructive">{error}</p>
      )}
    </div>
  );
}
