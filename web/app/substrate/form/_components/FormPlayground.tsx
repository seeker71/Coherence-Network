"use client";

import { useState } from "react";
import Link from "next/link";

type NodeIDOut = { package: number; level: number; type: number; instance: number };

type CellOut = {
  cell_id: number;
  name: string;
  domain: string;
  blueprint: NodeIDOut;
  base: NodeIDOut | null;
  access: NodeIDOut | null;
  ctor: NodeIDOut | null;
  source_path: string | null;
};

type CellViewOut = {
  cell: CellOut;
  view_blueprint: NodeIDOut;
  compatible: boolean;
  reason: string;
};

type FormResultOut = {
  kind: "node_id" | "recipe" | "cell" | "view" | "cells" | "views";
  node_id?: NodeIDOut | null;
  cell?: CellOut | null;
  view?: CellViewOut | null;
  cells?: CellOut[] | null;
  views?: CellViewOut[] | null;
};

const EXAMPLES: { label: string; expr: string }[] = [
  {
    label: "All memory cells",
    expr: '?cells where domain == "memory"',
  },
  {
    label: "All spec cells",
    expr: '?cells where domain == "spec"',
  },
  {
    label: "Resolve a NodeID literal",
    expr: "@1.5.4.1",
  },
  {
    label: "All concept cells",
    expr: '?cells where domain == "concept"',
  },
];

function formatNodeId(n: NodeIDOut): string {
  return `@${n.package}.${n.level}.${n.type}.${n.instance}`;
}

function CellCard({ cell }: { cell: CellOut }) {
  return (
    <div className="rounded border border-stone-800/40 bg-stone-900/30 p-3">
      <div className="flex items-baseline justify-between gap-3">
        <Link
          href={`/substrate/${cell.domain}/${encodeURIComponent(cell.name)}`}
          className="text-amber-300/90 hover:text-amber-200 transition-colors"
        >
          {cell.domain}:{cell.name}
        </Link>
        <span className="font-mono text-xs text-stone-500">
          {formatNodeId(cell.blueprint)}
        </span>
      </div>
      {cell.source_path && (
        <div className="mt-1 font-mono text-xs text-stone-600">{cell.source_path}</div>
      )}
    </div>
  );
}

function ResultPanel({ result }: { result: FormResultOut }) {
  if (result.kind === "node_id" || result.kind === "recipe") {
    return (
      <div className="rounded border border-stone-800/40 bg-stone-900/30 p-3">
        <div className="text-xs uppercase tracking-wide text-stone-500 mb-1">
          {result.kind === "node_id" ? "NodeID" : "Recipe NodeID"}
        </div>
        <div className="font-mono text-amber-300/90">
          {result.node_id ? formatNodeId(result.node_id) : "(undefined)"}
        </div>
      </div>
    );
  }

  if (result.kind === "cell" && result.cell) {
    return <CellCard cell={result.cell} />;
  }

  if (result.kind === "cells" && result.cells) {
    return (
      <div className="space-y-2">
        <div className="text-xs uppercase tracking-wide text-stone-500">
          {result.cells.length} cell{result.cells.length !== 1 ? "s" : ""}
        </div>
        {result.cells.map((c) => (
          <CellCard key={`${c.domain}:${c.name}`} cell={c} />
        ))}
      </div>
    );
  }

  if (result.kind === "view" && result.view) {
    return (
      <div className="space-y-2">
        <div className="rounded border border-stone-800/40 bg-stone-900/30 p-3">
          <div className="text-xs uppercase tracking-wide text-stone-500 mb-1">
            View through {formatNodeId(result.view.view_blueprint)}
          </div>
          <div className="text-sm text-stone-300">
            {result.view.compatible ? "compatible" : "incompatible"} — {result.view.reason}
          </div>
        </div>
        <CellCard cell={result.view.cell} />
      </div>
    );
  }

  if (result.kind === "views" && result.views) {
    return (
      <div className="space-y-2">
        <div className="text-xs uppercase tracking-wide text-stone-500">
          {result.views.length} view{result.views.length !== 1 ? "s" : ""}
        </div>
        {result.views.map((v, i) => (
          <div key={i} className="space-y-1">
            <div className="text-xs text-stone-500">
              {v.compatible ? "compatible" : "incompatible"} — {v.reason}
            </div>
            <CellCard cell={v.cell} />
          </div>
        ))}
      </div>
    );
  }

  return (
    <pre className="rounded border border-stone-800/40 bg-stone-900/30 p-3 text-xs text-stone-400 overflow-auto">
      {JSON.stringify(result, null, 2)}
    </pre>
  );
}

export function FormPlayground() {
  const [expression, setExpression] = useState(EXAMPLES[0].expr);
  const [evaluating, setEvaluating] = useState(false);
  const [result, setResult] = useState<FormResultOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  const evaluate = async () => {
    if (!expression.trim()) return;
    setEvaluating(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch("/api/substrate/form", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expression }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || `Evaluation failed (${res.status})`);
        return;
      }
      setResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Evaluation failed");
    } finally {
      setEvaluating(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {EXAMPLES.map((ex) => (
          <button
            key={ex.expr}
            onClick={() => setExpression(ex.expr)}
            className="rounded border border-stone-800/40 bg-stone-900/30 px-3 py-1 text-xs text-stone-400 hover:text-amber-300 hover:border-amber-500/30 transition-colors"
          >
            {ex.label}
          </button>
        ))}
      </div>

      <textarea
        value={expression}
        onChange={(e) => setExpression(e.target.value)}
        onKeyDown={(e) => {
          if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
            e.preventDefault();
            evaluate();
          }
        }}
        className="w-full h-32 p-3 bg-stone-900/50 border border-stone-800/40 rounded-xl text-stone-300 font-mono text-sm leading-relaxed resize-y focus:outline-none focus:border-amber-500/30 transition-colors"
        placeholder="@spec(agent-pipeline)"
        spellCheck={false}
      />

      <div className="flex items-center gap-3">
        <button
          onClick={evaluate}
          disabled={evaluating || !expression.trim()}
          className="px-5 py-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 hover:bg-amber-500/20 hover:border-amber-500/30 transition-all text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {evaluating ? "Evaluating..." : "Evaluate"}
        </button>
        <span className="text-xs text-stone-600">⌘↩ to evaluate</span>
      </div>

      {error && (
        <div className="rounded-xl border border-red-800/30 bg-red-900/10 p-3 text-sm text-red-300 whitespace-pre-wrap">
          {error}
        </div>
      )}

      {result && <ResultPanel result={result} />}
    </div>
  );
}
