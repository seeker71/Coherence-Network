"use client";

import { useEffect, useState } from "react";

export function ConfigEditor() {
  const [config, setConfig] = useState<Record<string, unknown> | null>(null);
  const [editText, setEditText] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/config")
      .then((r) => r.json())
      .then((data) => {
        setConfig(data);
        setEditText(JSON.stringify(data, null, 2));
        setLoading(false);
      })
      .catch(() => {
        setConfig({});
        setEditText("{}");
        setLoading(false);
      });
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const parsed = JSON.parse(editText);
      const res = await fetch("/api/config", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ updates: parsed }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Save failed (${res.status})`);
      }
      const updated = await res.json();
      setConfig(updated);
      setEditText(JSON.stringify(updated, null, 2));
      setSaved(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Invalid JSON or save failed");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="text-stone-500 text-sm">Loading config...</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-light text-stone-300">Editable Config</h2>
        <span className="text-xs text-stone-600 font-mono">~/.coherence-network/config.json</span>
      </div>

      <textarea
        value={editText}
        onChange={(e) => { setEditText(e.target.value); setSaved(false); }}
        className="w-full h-[50vh] p-4 bg-stone-900/50 border border-stone-800/40 rounded-xl text-stone-300 font-mono text-sm leading-relaxed resize-y focus:outline-none focus:border-amber-500/30 transition-colors"
        spellCheck={false}
      />

      <div className="rounded-xl border border-stone-800/30 bg-stone-900/20 p-4 text-xs text-stone-600 space-y-1">
        <p>Edit JSON directly. Sensitive keys (api_key, github_token, database_url) are filtered out.</p>
        <p>Common keys: <code className="text-amber-400/60">web.api_base_url</code>, <code className="text-amber-400/60">contributor_id</code>, <code className="text-amber-400/60">live_updates.poll_ms</code></p>
      </div>

      {error && (
        <div className="rounded-xl border border-red-800/30 bg-red-900/10 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {saved && (
        <div className="rounded-xl border border-emerald-800/30 bg-emerald-900/10 p-3 text-sm text-emerald-300">
          Config saved.
        </div>
      )}

      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-5 py-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 hover:bg-amber-500/20 hover:border-amber-500/30 transition-all text-sm font-medium disabled:opacity-40"
        >
          {saving ? "Saving..." : "Save config"}
        </button>
        <button
          onClick={() => {
            setEditText(JSON.stringify(config, null, 2));
            setSaved(false);
            setError(null);
          }}
          className="px-5 py-2.5 rounded-xl border border-stone-800/40 text-stone-500 hover:text-stone-300 transition-all text-sm"
        >
          Reset
        </button>
      </div>
    </div>
  );
}
