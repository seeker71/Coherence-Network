"use client";

import { useState } from "react";

export type WorldviewAxes = {
  scientific: number;
  spiritual: number;
  pragmatic: number;
  holistic: number;
  relational: number;
  systemic: number;
};

const AXIS_DESCRIPTIONS: Record<keyof WorldviewAxes, string> = {
  scientific: "Evidence-based, empirical, quantitative reasoning",
  spiritual: "Meaning-driven, transcendent, inner-knowing",
  pragmatic: "Outcome-focused, practical, action-oriented",
  holistic: "Whole-systems, integrative, context-aware",
  relational: "Connection-centric, empathic, community-driven",
  systemic: "Structural, emergent, feedback-loop thinking",
};

interface Props {
  axes: WorldviewAxes;
  onSave: (updated: WorldviewAxes) => Promise<void>;
  readOnly?: boolean;
}

export function WorldviewSelector({ axes, onSave, readOnly = false }: Props) {
  const [local, setLocal] = useState<WorldviewAxes>({ ...axes });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const handleChange = (axis: keyof WorldviewAxes, value: number) => {
    setLocal((prev) => ({ ...prev, [axis]: value }));
    setSaved(false);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave(local);
      setSaved(true);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
        Worldview Axes
      </h3>
      <div className="grid gap-4 sm:grid-cols-2">
        {(Object.keys(local) as Array<keyof WorldviewAxes>).map((axis) => (
          <div key={axis} className="rounded-lg border p-4 space-y-2">
            <div className="flex justify-between items-center">
              <span className="font-medium capitalize">{axis}</span>
              <span className="text-sm text-muted-foreground tabular-nums">
                {(local[axis] * 100).toFixed(0)}%
              </span>
            </div>
            <p className="text-xs text-muted-foreground">{AXIS_DESCRIPTIONS[axis]}</p>
            <input
              type="range"
              min={0}
              max={100}
              step={1}
              value={Math.round(local[axis] * 100)}
              disabled={readOnly}
              onChange={(e) =>
                handleChange(axis, parseInt(e.target.value, 10) / 100)
              }
              className="w-full accent-primary disabled:opacity-50"
              aria-label={`${axis} axis weight`}
            />
          </div>
        ))}
      </div>
      {!readOnly && (
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50 hover:opacity-90 transition-opacity"
        >
          {saving ? "Saving…" : saved ? "Saved ✓" : "Save Worldview"}
        </button>
      )}
    </div>
  );
}
