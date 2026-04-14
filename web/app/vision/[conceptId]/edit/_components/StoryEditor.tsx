"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

type FormatWarning = { line: number; issue: string; message: string };

/** Client-side format validation — mirrors the server-side checks. */
function validateStoryFormat(text: string): FormatWarning[] {
  const warnings: FormatWarning[] = [];
  const lines = text.split("\n");

  for (let i = 0; i < lines.length; i++) {
    const stripped = lines[i].trim();
    const lineNum = i + 1;

    // ASCII arrow instead of Unicode →
    if (stripped.startsWith("-> ")) {
      warnings.push({ line: lineNum, issue: "ascii_arrow", message: "Use \u2192 (Unicode arrow) instead of ->" });
    }

    // Cross-ref with markdown link [Name](file.md)
    if (stripped.startsWith("\u2192 ") && /\[.*\]\(.*\.md\)/.test(stripped)) {
      warnings.push({ line: lineNum, issue: "annotated_crossref", message: "Cross-refs should be plain IDs: \u2192 lc-xxx, lc-yyy (no markdown links)" });
    }

    // Cross-ref with description after em-dash
    if (stripped.startsWith("\u2192 ") && stripped.includes(" \u2014 ")) {
      warnings.push({ line: lineNum, issue: "crossref_description", message: "Cross-refs should not have descriptions \u2014 remove text after \u2014" });
    }

    // Inline visual not isolated by blank line
    if (/^!\[.*\]\(visuals:/.test(stripped)) {
      if (i > 0 && lines[i - 1].trim() !== "" && !lines[i - 1].trim().startsWith("#")) {
        warnings.push({ line: lineNum, issue: "visual_not_isolated", message: "Add a blank line before inline visuals" });
      }
    }
  }

  return warnings;
}

export function StoryEditor({
  conceptId,
  conceptName,
  initialContent,
}: {
  conceptId: string;
  conceptName: string;
  initialContent: string;
}) {
  const [content, setContent] = useState(initialContent);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [serverWarnings, setServerWarnings] = useState<FormatWarning[]>([]);
  const [regenerating, setRegenerating] = useState(false);
  const [regenResult, setRegenResult] = useState<string | null>(null);
  const router = useRouter();

  // Live client-side validation
  const clientWarnings = useMemo(() => validateStoryFormat(content), [content]);
  const allWarnings = serverWarnings.length > 0 ? serverWarnings : clientWarnings;

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSaved(false);
    setServerWarnings([]);
    try {
      const res = await fetch(`/api/concepts/${conceptId}/story`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ story_content: content }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Save failed (${res.status})`);
      }
      const data = await res.json();
      if (data.warnings?.length > 0) {
        setServerWarnings(data.warnings);
      }
      setSaved(true);
      if (!data.warnings?.length) {
        setTimeout(() => router.push(`/vision/${conceptId}`), 1200);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const visualCount = (content.match(/!\[.*?\]\(visuals:/g) || []).length;
  const wordCount = content.split(/\s+/).filter(Boolean).length;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-light text-stone-300">Edit Living Story</h2>
        <div className="flex items-center gap-4 text-xs text-stone-600">
          <span>{wordCount} words</span>
          <span>{visualCount} visual{visualCount !== 1 ? "s" : ""}</span>
          {clientWarnings.length > 0 && (
            <span className="text-amber-400/70">{clientWarnings.length} warning{clientWarnings.length !== 1 ? "s" : ""}</span>
          )}
        </div>
      </div>

      <textarea
        value={content}
        onChange={(e) => { setContent(e.target.value); setSaved(false); setServerWarnings([]); }}
        className="w-full h-[60vh] p-4 bg-stone-900/50 border border-stone-800/40 rounded-xl text-stone-300 font-mono text-sm leading-relaxed resize-y focus:outline-none focus:border-amber-500/30 transition-colors"
        placeholder={`## The Feeling\n\nWrite the living story of ${conceptName}...\n\n![A visual description](visuals:photorealistic prompt for image generation)`}
        spellCheck={false}
      />

      {/* Live format warnings */}
      {allWarnings.length > 0 && (
        <div className="rounded-xl border border-amber-800/20 bg-amber-900/5 p-4 space-y-2">
          <p className="text-xs text-amber-400/70 font-medium">Format warnings:</p>
          <div className="space-y-1">
            {allWarnings.map((w, i) => (
              <div key={i} className="text-xs text-stone-400 flex gap-2">
                <span className="text-stone-600 font-mono shrink-0">L{w.line}</span>
                <span>{w.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="rounded-xl border border-stone-800/30 bg-stone-900/20 p-4 text-xs text-stone-600 space-y-2">
        <p className="text-stone-500 font-medium">Story format guide:</p>
        <div className="grid grid-cols-2 gap-2">
          <span><code className="text-amber-400/60">## Heading</code> — section</span>
          <span><code className="text-amber-400/60">&gt; quote</code> — blockquote</span>
          <span><code className="text-amber-400/60">**bold**</code> — emphasis</span>
          <span><code className="text-amber-400/60">*italic*</code> — gentle emphasis</span>
          <span><code className="text-amber-400/60">- item</code> — list</span>
          <span><code className="text-amber-400/60">{"\u2192"} lc-xxx, lc-yyy</code> — cross-references</span>
          <span className="col-span-2"><code className="text-amber-400/60">![caption](visuals:prompt)</code> — inline image (blank lines before and after)</span>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-red-800/30 bg-red-900/10 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {saved && !serverWarnings.length && (
        <div className="rounded-xl border border-emerald-800/30 bg-emerald-900/10 p-3 text-sm text-emerald-300">
          Story saved. Redirecting...
        </div>
      )}

      {saved && serverWarnings.length > 0 && (
        <div className="rounded-xl border border-amber-800/30 bg-amber-900/10 p-3 text-sm text-amber-300">
          Story saved with {serverWarnings.length} format warning{serverWarnings.length !== 1 ? "s" : ""}. Fix them and save again, or{" "}
          <button onClick={() => router.push(`/vision/${conceptId}`)} className="underline hover:text-amber-200">
            view the page
          </button>.
        </div>
      )}

      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={saving || !content.trim()}
          className="px-5 py-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 hover:bg-amber-500/20 hover:border-amber-500/30 transition-all text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {saving ? "Saving..." : "Save story"}
        </button>
        <button
          onClick={async () => {
            setRegenerating(true);
            setRegenResult(null);
            try {
              const res = await fetch(`/api/concepts/${conceptId}/visuals/regenerate?force=true`, { method: "POST" });
              const data = await res.json();
              setRegenResult(`${data.downloaded || 0} downloaded, ${data.existing || 0} existing, ${data.failed || 0} failed`);
            } catch {
              setRegenResult("Failed to regenerate");
            } finally {
              setRegenerating(false);
            }
          }}
          disabled={regenerating}
          className="px-5 py-2.5 rounded-xl border border-teal-800/30 text-teal-400/70 hover:text-teal-300 hover:border-teal-700/40 transition-all text-sm disabled:opacity-40"
        >
          {regenerating ? "Generating..." : "Regenerate images"}
        </button>
        <button
          onClick={() => router.push(`/vision/${conceptId}`)}
          className="px-5 py-2.5 rounded-xl border border-stone-800/40 text-stone-500 hover:text-stone-300 hover:border-stone-700/40 transition-all text-sm"
        >
          Cancel
        </button>
      </div>

      {regenResult && (
        <div className="rounded-xl border border-teal-800/30 bg-teal-900/10 p-3 text-sm text-teal-300">
          Images: {regenResult}
        </div>
      )}
    </div>
  );
}
