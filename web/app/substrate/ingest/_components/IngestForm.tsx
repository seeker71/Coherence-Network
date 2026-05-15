"use client";

import { useState } from "react";
import Link from "next/link";

type NodeIDOut = { package: number; level: number; type: number; instance: number };

type IngestResponse = {
  cell: {
    cell_id: number;
    name: string;
    domain: string;
    blueprint: NodeIDOut;
    source_path: string | null;
  };
  blueprint: NodeIDOut;
  ctor: NodeIDOut | null;
};

const DOMAINS = ["memory", "spec", "idea", "concept", "presence"] as const;

const DOMAIN_HINTS: Record<(typeof DOMAINS)[number], string> = {
  memory: "Tender notes carrying context across sessions. Frontmatter: name, description, type.",
  spec: "Executable form of an idea. Frontmatter: title, source, requirements, done_when, test.",
  idea: "Problem-shape with capabilities and absorbed ideas. Frontmatter: idea_id, title, stage.",
  concept: "Vision-kb story. Frontmatter: id (lc-*), name, parent, cross_refs.",
  presence: "Contributor cell. Frontmatter: name, role, lineage.",
};

const EXAMPLE_TEMPLATE = `---
name: my-first-memory
description: arriving into the substrate from the web
type: user
---

## What this is

Replace this body with your content. The frontmatter above carries the
structural identity — two memories with the same frontmatter keys and
types share the same Blueprint in the lattice.
`;

function formatNodeId(n: NodeIDOut): string {
  return `@${n.package}.${n.level}.${n.type}.${n.instance}`;
}

export function IngestForm() {
  const [domain, setDomain] = useState<(typeof DOMAINS)[number]>("memory");
  const [content, setContent] = useState(EXAMPLE_TEMPLATE);
  const [sourceLabel, setSourceLabel] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<IngestResponse | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch("/api/substrate/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          domain,
          content,
          source_label: sourceLabel.trim() || `web:visitor`,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || `Ingest failed (${res.status})`);
        return;
      }
      setResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ingest failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div>
        <span className="mb-2 block text-sm text-stone-400">Domain</span>
        <div className="flex flex-wrap gap-2">
          {DOMAINS.map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => setDomain(d)}
              className={`rounded border px-3 py-1 text-xs transition-colors ${
                d === domain
                  ? "border-amber-500/30 bg-amber-500/10 text-amber-300"
                  : "border-stone-800/40 bg-stone-900/30 text-stone-400 hover:text-amber-300/80 hover:border-amber-500/20"
              }`}
            >
              {d}
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-stone-500">{DOMAIN_HINTS[domain]}</p>
      </div>

      <label className="block space-y-2">
        <span className="text-sm text-stone-400">Content (markdown with frontmatter)</span>
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          required
          rows={18}
          className="w-full rounded-xl border border-stone-800/40 bg-stone-900/50 p-4 font-mono text-sm text-stone-300 leading-relaxed resize-y focus:border-amber-500/30 focus:outline-none"
          spellCheck={false}
        />
      </label>

      <label className="block space-y-2">
        <span className="text-sm text-stone-400">Source label (optional)</span>
        <input
          type="text"
          value={sourceLabel}
          onChange={(e) => setSourceLabel(e.target.value)}
          placeholder="web:visitor (default) — honest provenance hint"
          className="w-full rounded-xl border border-stone-800/40 bg-stone-900/50 px-4 py-2.5 text-stone-200 focus:border-amber-500/30 focus:outline-none"
        />
      </label>

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={submitting || !content.trim()}
          className="rounded-xl border border-amber-500/20 bg-amber-500/10 px-5 py-2.5 text-sm font-medium text-amber-300/90 transition-all hover:border-amber-500/30 hover:bg-amber-500/20 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {submitting ? "Ingesting..." : "Ingest"}
        </button>
        <button
          type="button"
          onClick={() => setContent(EXAMPLE_TEMPLATE)}
          className="rounded-xl border border-stone-800/40 px-5 py-2.5 text-sm text-stone-500 transition-all hover:border-stone-700/40 hover:text-stone-300"
        >
          Reset to template
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-red-800/30 bg-red-900/10 p-3 text-sm text-red-300 whitespace-pre-wrap">
          {error}
        </div>
      )}

      {result && (
        <div className="rounded-xl border border-emerald-800/30 bg-emerald-900/10 p-4 space-y-2 text-sm">
          <p className="font-medium text-emerald-300">Placed in the lattice.</p>
          <p className="text-stone-300">
            <Link
              href={`/substrate/${result.cell.domain}/${encodeURIComponent(result.cell.name)}`}
              className="text-amber-300/90 hover:text-amber-200"
            >
              {result.cell.domain}:{result.cell.name}
            </Link>{" "}
            <span className="font-mono text-xs text-stone-500">
              {formatNodeId(result.cell.blueprint)}
            </span>
          </p>
          {result.cell.source_path && (
            <p className="font-mono text-xs text-stone-500">
              source: {result.cell.source_path}
            </p>
          )}
        </div>
      )}
    </form>
  );
}
