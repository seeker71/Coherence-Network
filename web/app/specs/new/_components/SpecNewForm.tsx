"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export function SpecNewForm() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [ideaId, setIdeaId] = useState("");
  const [processSummary, setProcessSummary] = useState("");
  const [potentialValue, setPotentialValue] = useState(50000);
  const [estimatedCost, setEstimatedCost] = useState(5000);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = title.trim().length > 0 && summary.trim().length > 0 && !saving;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setSaving(true);
    setError(null);
    try {
      const res = await fetch("/api/spec-registry", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: title.trim(),
          summary: summary.trim(),
          idea_id: ideaId.trim() || null,
          process_summary: processSummary.trim() || null,
          potential_value: potentialValue,
          estimated_cost: estimatedCost,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail?.message || data.detail || `Create failed (${res.status})`);
      }
      const created = await res.json();
      router.push(`/specs/${encodeURIComponent(created.spec_id)}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Create failed");
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <label className="block space-y-2">
        <span className="text-sm text-stone-400">Title</span>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
          placeholder="A short title naming what this spec realizes"
          className="w-full rounded-xl border border-stone-800/40 bg-stone-900/50 px-4 py-2.5 text-stone-200 focus:border-amber-500/30 focus:outline-none"
        />
      </label>

      <label className="block space-y-2">
        <span className="text-sm text-stone-400">Summary</span>
        <textarea
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
          required
          rows={6}
          placeholder="What does this spec realize? What's the shape of the answer?"
          className="w-full rounded-xl border border-stone-800/40 bg-stone-900/50 p-4 font-mono text-sm text-stone-300 leading-relaxed resize-y focus:border-amber-500/30 focus:outline-none"
        />
      </label>

      <label className="block space-y-2">
        <span className="text-sm text-stone-400">Parent idea (slug, optional)</span>
        <input
          type="text"
          value={ideaId}
          onChange={(e) => setIdeaId(e.target.value)}
          placeholder="e.g. agent-pipeline"
          className="w-full rounded-xl border border-stone-800/40 bg-stone-900/50 px-4 py-2.5 text-stone-200 focus:border-amber-500/30 focus:outline-none"
        />
      </label>

      <label className="block space-y-2">
        <span className="text-sm text-stone-400">Process summary (optional)</span>
        <textarea
          value={processSummary}
          onChange={(e) => setProcessSummary(e.target.value)}
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
          {saving ? "Creating..." : "Create spec"}
        </button>
        <button
          type="button"
          onClick={() => router.push("/specs")}
          className="rounded-xl border border-stone-800/40 px-5 py-2.5 text-sm text-stone-500 transition-all hover:border-stone-700/40 hover:text-stone-300"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
