"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export type SpecRegistryEntry = {
  spec_id: string;
  title: string;
  summary: string;
  potential_value: number;
  estimated_cost: number;
  idea_id?: string | null;
  process_summary?: string | null;
  pseudocode_summary?: string | null;
  implementation_summary?: string | null;
};

type EditableFields = {
  title: string;
  summary: string;
  potential_value: number;
  estimated_cost: number;
  idea_id: string;
  process_summary: string;
};

export function SpecEditor({ spec }: { spec: SpecRegistryEntry }) {
  const router = useRouter();
  const [fields, setFields] = useState<EditableFields>({
    title: spec.title,
    summary: spec.summary,
    potential_value: spec.potential_value,
    estimated_cost: spec.estimated_cost,
    idea_id: spec.idea_id || "",
    process_summary: spec.process_summary || "",
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
      const patch: Record<string, unknown> = {};
      if (fields.title !== spec.title) patch.title = fields.title;
      if (fields.summary !== spec.summary) patch.summary = fields.summary;
      if (fields.potential_value !== spec.potential_value) patch.potential_value = fields.potential_value;
      if (fields.estimated_cost !== spec.estimated_cost) patch.estimated_cost = fields.estimated_cost;
      if (fields.idea_id !== (spec.idea_id || "")) patch.idea_id = fields.idea_id || null;
      if (fields.process_summary !== (spec.process_summary || "")) {
        patch.process_summary = fields.process_summary || null;
      }

      if (Object.keys(patch).length === 0) {
        setSaved(true);
        return;
      }

      const res = await fetch(`/api/spec-registry/${encodeURIComponent(spec.spec_id)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Save failed (${res.status})`);
      }
      setSaved(true);
      setTimeout(() => router.push(`/specs/${encodeURIComponent(spec.spec_id)}`), 1200);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <label className="block space-y-2">
        <span className="text-sm text-stone-400">Title</span>
        <input
          type="text"
          value={fields.title}
          onChange={(e) => update("title", e.target.value)}
          className="w-full rounded-xl border border-stone-800/40 bg-stone-900/50 px-4 py-2.5 text-stone-200 focus:border-amber-500/30 focus:outline-none"
        />
      </label>

      <label className="block space-y-2">
        <span className="text-sm text-stone-400">Summary</span>
        <textarea
          value={fields.summary}
          onChange={(e) => update("summary", e.target.value)}
          rows={6}
          className="w-full rounded-xl border border-stone-800/40 bg-stone-900/50 p-4 font-mono text-sm text-stone-300 leading-relaxed resize-y focus:border-amber-500/30 focus:outline-none"
        />
      </label>

      <label className="block space-y-2">
        <span className="text-sm text-stone-400">Idea (slug)</span>
        <input
          type="text"
          value={fields.idea_id}
          onChange={(e) => update("idea_id", e.target.value)}
          placeholder="parent idea this spec realizes"
          className="w-full rounded-xl border border-stone-800/40 bg-stone-900/50 px-4 py-2.5 text-stone-200 focus:border-amber-500/30 focus:outline-none"
        />
      </label>

      <label className="block space-y-2">
        <span className="text-sm text-stone-400">Process summary</span>
        <textarea
          value={fields.process_summary}
          onChange={(e) => update("process_summary", e.target.value)}
          rows={4}
          placeholder="How the work flows: source maps, tests, done_when"
          className="w-full rounded-xl border border-stone-800/40 bg-stone-900/50 p-4 font-mono text-sm text-stone-300 leading-relaxed resize-y focus:border-amber-500/30 focus:outline-none"
        />
      </label>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
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
      </div>

      {error && (
        <div className="rounded-xl border border-red-800/30 bg-red-900/10 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {saved && !error && (
        <div className="rounded-xl border border-emerald-800/30 bg-emerald-900/10 p-3 text-sm text-emerald-300">
          Saved. Returning to spec...
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
          onClick={() => router.push(`/specs/${encodeURIComponent(spec.spec_id)}`)}
          className="rounded-xl border border-stone-800/40 px-5 py-2.5 text-sm text-stone-500 transition-all hover:border-stone-700/40 hover:text-stone-300"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
