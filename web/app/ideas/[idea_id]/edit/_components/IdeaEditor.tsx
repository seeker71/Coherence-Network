"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { IdeaWithScore } from "@/lib/types";

type EditableFields = {
  name: string;
  description: string;
  potential_value: number;
  estimated_cost: number;
  confidence: number;
};

export function IdeaEditor({ idea }: { idea: IdeaWithScore }) {
  const router = useRouter();
  const [fields, setFields] = useState<EditableFields>({
    name: idea.name,
    description: idea.description,
    potential_value: idea.potential_value,
    estimated_cost: idea.estimated_cost,
    confidence: idea.confidence,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const update = <K extends keyof EditableFields>(key: K, value: EditableFields[K]) => {
    setFields((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const patch: Partial<EditableFields> = {};
      if (fields.name !== idea.name) patch.name = fields.name;
      if (fields.description !== idea.description) patch.description = fields.description;
      if (fields.potential_value !== idea.potential_value) patch.potential_value = fields.potential_value;
      if (fields.estimated_cost !== idea.estimated_cost) patch.estimated_cost = fields.estimated_cost;
      if (fields.confidence !== idea.confidence) patch.confidence = fields.confidence;

      if (Object.keys(patch).length === 0) {
        setSaved(true);
        return;
      }

      const res = await fetch(`/api/ideas/${encodeURIComponent(idea.id)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Save failed (${res.status})`);
      }
      setSaved(true);
      setTimeout(() => router.push(`/ideas/${encodeURIComponent(idea.id)}`), 1200);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <label className="block space-y-2">
        <span className="text-sm text-stone-400">Name</span>
        <input
          type="text"
          value={fields.name}
          onChange={(e) => update("name", e.target.value)}
          className="w-full rounded-xl border border-stone-800/40 bg-stone-900/50 px-4 py-2.5 text-stone-200 focus:border-amber-500/30 focus:outline-none"
        />
      </label>

      <label className="block space-y-2">
        <span className="text-sm text-stone-400">Description</span>
        <textarea
          value={fields.description}
          onChange={(e) => update("description", e.target.value)}
          rows={8}
          className="w-full rounded-xl border border-stone-800/40 bg-stone-900/50 p-4 font-mono text-sm text-stone-300 leading-relaxed resize-y focus:border-amber-500/30 focus:outline-none"
        />
      </label>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <label className="block space-y-2">
          <span className="text-sm text-stone-400">Potential value (USD)</span>
          <input
            type="number"
            min={0}
            step={1000}
            value={fields.potential_value}
            onChange={(e) => update("potential_value", Number(e.target.value))}
            className="w-full rounded-xl border border-stone-800/40 bg-stone-900/50 px-4 py-2.5 font-mono text-stone-200 focus:border-amber-500/30 focus:outline-none"
          />
        </label>
        <label className="block space-y-2">
          <span className="text-sm text-stone-400">Estimated cost (USD)</span>
          <input
            type="number"
            min={0}
            step={1000}
            value={fields.estimated_cost}
            onChange={(e) => update("estimated_cost", Number(e.target.value))}
            className="w-full rounded-xl border border-stone-800/40 bg-stone-900/50 px-4 py-2.5 font-mono text-stone-200 focus:border-amber-500/30 focus:outline-none"
          />
        </label>
        <label className="block space-y-2">
          <span className="text-sm text-stone-400">Confidence (0–1)</span>
          <input
            type="number"
            min={0}
            max={1}
            step={0.05}
            value={fields.confidence}
            onChange={(e) => update("confidence", Number(e.target.value))}
            className="w-full rounded-xl border border-stone-800/40 bg-stone-900/50 px-4 py-2.5 font-mono text-stone-200 focus:border-amber-500/30 focus:outline-none"
          />
        </label>
      </div>

      {error && (
        <div className="rounded-xl border border-red-800/30 bg-red-900/10 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {saved && !error && (
        <div className="rounded-xl border border-emerald-800/30 bg-emerald-900/10 p-3 text-sm text-emerald-300">
          Saved. Returning to idea...
        </div>
      )}

      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="rounded-xl border border-amber-500/20 bg-amber-500/10 px-5 py-2.5 text-sm font-medium text-amber-300/90 transition-all hover:border-amber-500/30 hover:bg-amber-500/20 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {saving ? "Saving..." : "Save changes"}
        </button>
        <button
          onClick={() => router.push(`/ideas/${encodeURIComponent(idea.id)}`)}
          className="rounded-xl border border-stone-800/40 px-5 py-2.5 text-sm text-stone-500 transition-all hover:border-stone-700/40 hover:text-stone-300"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
