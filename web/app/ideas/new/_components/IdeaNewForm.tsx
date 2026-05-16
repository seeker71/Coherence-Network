"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export function IdeaNewForm() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [potentialValue, setPotentialValue] = useState(100000);
  const [estimatedCost, setEstimatedCost] = useState(10000);
  const [confidence, setConfidence] = useState(0.5);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = name.trim().length > 0 && description.trim().length > 0 && !saving;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setSaving(true);
    setError(null);
    try {
      const res = await fetch("/api/ideas", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim(),
          potential_value: potentialValue,
          estimated_cost: estimatedCost,
          confidence,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail?.message || data.detail || `Create failed (${res.status})`);
      }
      const created = await res.json();
      router.push(`/ideas/${encodeURIComponent(created.id)}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Create failed");
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <label className="block space-y-2">
        <span className="text-sm text-stone-400">Name</span>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          placeholder="A short, clear name for the idea"
          className="w-full rounded-xl border border-stone-800/40 bg-stone-900/50 px-4 py-2.5 text-stone-200 focus:border-amber-500/30 focus:outline-none"
        />
      </label>

      <label className="block space-y-2">
        <span className="text-sm text-stone-400">Description</span>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          required
          rows={8}
          placeholder="What's the problem? What does the answer look like? Who benefits?"
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
            value={potentialValue}
            onChange={(e) => setPotentialValue(Number(e.target.value))}
            className="w-full rounded-xl border border-stone-800/40 bg-stone-900/50 px-4 py-2.5 font-mono text-stone-200 focus:border-amber-500/30 focus:outline-none"
          />
        </label>
        <label className="block space-y-2">
          <span className="text-sm text-stone-400">Estimated cost (USD)</span>
          <input
            type="number"
            min={0}
            step={1000}
            value={estimatedCost}
            onChange={(e) => setEstimatedCost(Number(e.target.value))}
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
            value={confidence}
            onChange={(e) => setConfidence(Number(e.target.value))}
            className="w-full rounded-xl border border-stone-800/40 bg-stone-900/50 px-4 py-2.5 font-mono text-stone-200 focus:border-amber-500/30 focus:outline-none"
          />
        </label>
      </div>

      {error && (
        <div className="rounded-xl border border-red-800/30 bg-red-900/10 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={!canSubmit}
          className="rounded-xl border border-amber-500/20 bg-amber-500/10 px-5 py-2.5 text-sm font-medium text-amber-300/90 transition-all hover:border-amber-500/30 hover:bg-amber-500/20 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {saving ? "Creating..." : "Create idea"}
        </button>
        <button
          type="button"
          onClick={() => router.push("/ideas")}
          className="rounded-xl border border-stone-800/40 px-5 py-2.5 text-sm text-stone-500 transition-all hover:border-stone-700/40 hover:text-stone-300"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
