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
  kind:
    | "node_id"
    | "recipe"
    | "cell"
    | "view"
    | "cells"
    | "views"
    | "lattice"
    | "keywords"
    | "vocabulary";
  node_id?: NodeIDOut | null;
  cell?: CellOut | null;
  view?: CellViewOut | null;
  cells?: CellOut[] | null;
  views?: CellViewOut[] | null;
  lattice?: Record<string, number> | null;
  keywords?: string[] | null;
  vocabulary?: { recipes: Record<string, number>; blueprints: Record<string, number> } | null;
};

type Example = {
  label: string;
  expr: string;
  // Names the unique Form feature this example exercises.
  showcases: string;
};

type ExampleGroup = {
  heading: string;
  blurb: string;
  examples: Example[];
};

// Curated tour of every unique Form construct. Each example is runnable
// against the live substrate. Grouped so the reader can sense the
// language's surface area at a glance.
const GROUPS: ExampleGroup[] = [
  {
    heading: "Lattice references",
    blurb:
      "NodeIDs are first-class. Names are query keys, not identities. Three ways to point at the lattice.",
    examples: [
      {
        label: "NodeID literal",
        expr: "@1.5.4.1",
        showcases:
          "Bare 4-tuple — package.level.type.instance — resolves to the canonical NodeID.",
      },
      {
        label: "Trivial blueprint by name",
        expr: "~Memory",
        showcases:
          "Trivial constructor — gives names to well-known leaf NodeIDs (~Integer, ~String, ~Slug, ~Object).",
      },
      {
        label: "Cell lookup by (domain, name)",
        expr: "@memory(presences_of_the_field)",
        showcases:
          "Cell reference. Name is a query key; the substrate resolves it to a content-addressed NodeID.",
      },
      {
        label: "Bare domain",
        expr: "@memory",
        showcases: "Bare @<domain> returns the canonical domain blueprint NodeID.",
      },
    ],
  },
  {
    heading: "Tree navigation — the fractal seam",
    blurb:
      "The dot is the seam between holographic levels. Every cell is a tree of categories composing children composing categories, down to numeric trivials.",
    examples: [
      {
        label: ".blueprint — the shape (ice)",
        expr: "@memory(presences_of_the_field).blueprint",
        showcases: "Walk to the Blueprint NodeID — the structural identity of the cell.",
      },
      {
        label: ".blueprint.category",
        expr: "@memory(presences_of_the_field).blueprint.category",
        showcases: "The type-of-the-type — B_Domain.MEMORY here.",
      },
      {
        label: ".blueprint.nchildren",
        expr: "@memory(presences_of_the_field).blueprint.nchildren",
        showcases: "Arity of the composition — how many children the shape carries.",
      },
      {
        label: ".blueprint.child(0)",
        expr: "@memory(presences_of_the_field).blueprint.child(0)",
        showcases: "Indexed child — descend one level of the holographic tree.",
      },
      {
        label: ".ctor — composed values (water)",
        expr: "@memory(presences_of_the_field).ctor",
        showcases:
          "The CTOR recipe — how the cell's frontmatter values compose under R_Block.DO.",
      },
    ],
  },
  {
    heading: "Queries — set-valued lookups",
    blurb:
      "Queries return NodeID sets, not strings. The substrate is the answer; Form is just the surface.",
    examples: [
      {
        label: "All memory cells",
        expr: '?cells where domain == "memory"',
        showcases: "Predicate query — every cell whose domain matches.",
      },
      {
        label: "All spec cells",
        expr: '?cells where domain == "spec"',
        showcases: "Same shape, different domain — uniform query interface.",
      },
      {
        label: "Equivalent by structure",
        expr: "?equivalent @memory(presences_of_the_field)",
        showcases:
          "Structural equivalents — cells sharing the same Blueprint NodeID regardless of name.",
      },
      {
        label: "Filter by name pattern",
        expr: '?cells where (domain == "memory") and (name matches "feedback_*")',
        showcases: "Composable predicates — boolean combinators + glob matching.",
      },
      {
        label: "Filter by shape",
        expr: "?cells where shape == @memory",
        showcases: "Cell-ref on the right of == — signature-aware filtering.",
      },
    ],
  },
  {
    heading: "Views — BML dual-pointer projection",
    blurb:
      "A View projects a cell through a different Blueprint. The cell's data stays canonical; the View is a virtual perspective. Hallucination-bounded interface attachment.",
    examples: [
      {
        label: "Project a memory through @presence",
        expr: "@memory(presences_of_the_field) |> @presence",
        showcases:
          "The |> projection operator. Reads right-to-left: view this cell through that interface.",
      },
      {
        label: "Every cell compatible with @presence",
        expr: "?cells |> @presence",
        showcases: "Set-valued projection — every cell the body can view through this interface.",
      },
    ],
  },
  {
    heading: "Resonance walks — cross-discipline weaving",
    blurb:
      "The dimensional vocabulary (geometric form, polarity, topology, spectrum, harmonic) makes structurally-kin teachings findable across discipline-vocabularies.",
    examples: [
      {
        label: "Concepts shaped by ~Triad",
        expr: "?shaped_by @geometric_form(triad)",
        showcases:
          "Walk SHAPES edges in reverse — every concept whose geometric signature points at this form.",
      },
      {
        label: "Cells harmonic at 174 Hz",
        expr: "?harmonic_at @spectrum(Hz-174)",
        showcases: "Walk HARMONIC_AT edges — the foundation Solfeggio band's resonance cluster.",
      },
    ],
  },
  {
    heading: "Code expressions — recipes",
    blurb:
      "Form expresses code, not just data. Each expression interns as a Recipe NodeID. Two structurally-identical expressions hash to the same NodeID — content-addressed code.",
    examples: [
      {
        label: "Arithmetic",
        expr: "1 + 2 * 3",
        showcases:
          "Math recipe with operator precedence. Returns the Recipe NodeID — not the value 7, the structure.",
      },
      {
        label: "Comparison",
        expr: "5 > 3",
        showcases: "Compare.GREATER recipe — comparison as interned structure.",
      },
      {
        label: "Logic",
        expr: "true && false || !true",
        showcases: "Logic recipes — precedence: ! > && > ||.",
      },
      {
        label: "Conditional (three-arm)",
        expr: "if 5 > 3 then 10 else 20",
        showcases:
          "Cond.IF_THEN_ELSE recipe — distinct NodeID category from the two-arm form.",
      },
      {
        label: "Block + let",
        expr: "do { let x = 5; let y = x + 3; y * 2 }",
        showcases:
          "Block.DO recipe with Block.LET children. The last expression is the block's value.",
      },
      {
        label: "Match",
        expr: 'match "ready" { "ready" => 1, "blocked" => 2, _ => 0 }',
        showcases: "Match.SWITCH recipe — scrutinee + pattern/body pairs. Underscore is default.",
      },
      {
        label: "Angelic choice",
        expr: "choose [1, 2, 3]",
        showcases:
          "Choice.CHOOSE — speculation primitive from the BML lineage. Pairs with fail and stop.",
      },
      {
        label: "fail",
        expr: "fail",
        showcases:
          "Choice.FAIL leaf — signal failure; unwinds to nearest choose. Backtracking without sediment.",
      },
      {
        label: "stop",
        expr: "stop",
        showcases: "Choice.STOP leaf — commit current speculation; no more backtracking.",
      },
    ],
  },
  {
    heading: "BML scoped reference — with / .self",
    blurb:
      "From BML's master thesis: a block that binds X as the implicit subject. The structural primitive for resonance-as-language.",
    examples: [
      {
        label: "with subject { .self }",
        expr: "with @concept(lc-trust-over-fear) { .self }",
        showcases:
          "RBlock.WITH recipe with the subject and body composed. .self resolves to the subject at runtime.",
      },
    ],
  },
  {
    heading: "BML form-layer parity",
    blurb:
      "Six constructs the master thesis named, now interned as Recipe NodeIDs under their own RBasic categories.",
    examples: [
      {
        label: "State stack — save / restore / discard",
        expr: "do { save; 1 + 2; restore }",
        showcases: "RBasic.STATE leaves composed in a block. The runtime walks the state stack.",
      },
      {
        label: "Exception flow — raise / resume",
        expr: "raise",
        showcases: "RBasic.EXCEPTION leaf. raise unwinds; resume returns from the handler.",
      },
      {
        label: "Delegation inheritance",
        expr:
          "delegate @concept(lc-trust-over-fear) to @concept(lc-permission-is-interior)",
        showcases:
          "RBasic.DELEGATE — invoke walks the chain when the method isn't on the original target.",
      },
      {
        label: "Reverse semantics — undo",
        expr: "undo (1 + 2)",
        showcases: "RBasic.REVERSE.UNDO — re-runs the inner expression as its inverse.",
      },
      {
        label: "Reverse semantics — inverse",
        expr: "inverse(1 + 2)",
        showcases:
          "Returns the inverse Recipe NodeID — structural inversion, not value-level negation.",
      },
      {
        label: "Common Objects",
        expr: "common @concept(lc-trust-over-fear) @concept(lc-whole-vitality)",
        showcases:
          "RBasic.COMMON — shared-base multi-inheritance. invoke falls back to peers in the equivalence group.",
      },
      {
        label: "Method definition",
        expr:
          "method greet on @concept(lc-trust-over-fear) { save; 1 + 2; restore }",
        showcases:
          "RBasic.METHOD — registers a method on a target. Composes with state and exception flow.",
      },
      {
        label: "Method invocation",
        expr: "invoke greet on @concept(lc-trust-over-fear)",
        showcases:
          "Dispatches through delegation + common-object chains with .self bound to the original target.",
      },
    ],
  },
  {
    heading: "Reactive + spatial lenses",
    blurb:
      "Lenses that read the substrate without disturbing the flow. The same pattern memory-as-framebuffer uses at the heap level.",
    examples: [
      {
        label: "Reactive lens",
        expr:
          "?on_change @concept(lc-trust-over-fear) { invoke notify on @presence(claude) }",
        showcases:
          "RBasic.REACTIVE.ON_CHANGE — fires the body when the watched recipe's value changes.",
      },
      {
        label: "Spatial-projection lens",
        expr: "?project @geometric_form(triad) @concept(coord-radial)",
        showcases:
          "RBasic.PROJECTION.PROJECT — renders the cell through a coordinate function.",
      },
    ],
  },
  {
    heading: "Self-reflection lenses",
    blurb:
      "Form sees itself. The body senses its own shape — the verb histogram is itself a wellness signal.",
    examples: [
      {
        label: "?lattice — substrate snapshot",
        expr: "?lattice",
        showcases:
          "Count of every interned blueprint, recipe, and cell. The framebuffer-analog at the count level.",
      },
      {
        label: "?keywords — grammar introspection",
        expr: "?keywords",
        showcases:
          "Names of every runtime-registered keyword. The parser knows its own rules.",
      },
      {
        label: "?vocabulary — verb-cluster histogram",
        expr: "?vocabulary",
        showcases:
          "Recipe-type counts grouped by RBasic category. Reveals which language layers the body actually circulates through.",
      },
    ],
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

function KeyValueGrid({ data, label }: { data: Record<string, number>; label: string }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-stone-500 mb-2">{label}</div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 font-mono text-sm">
        {entries.map(([k, v]) => (
          <div key={k} className="flex justify-between">
            <span className="text-stone-300">{k}</span>
            <span className="text-amber-300/90">{v}</span>
          </div>
        ))}
      </div>
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

  if (result.kind === "lattice" && result.lattice) {
    return (
      <div className="rounded border border-stone-800/40 bg-stone-900/30 p-3">
        <KeyValueGrid data={result.lattice} label="Lattice snapshot" />
      </div>
    );
  }

  if (result.kind === "keywords" && result.keywords) {
    return (
      <div className="rounded border border-stone-800/40 bg-stone-900/30 p-3">
        <div className="text-xs uppercase tracking-wide text-stone-500 mb-2">
          {result.keywords.length} runtime-registered keyword
          {result.keywords.length !== 1 ? "s" : ""}
        </div>
        {result.keywords.length === 0 ? (
          <div className="text-sm text-stone-400">
            None yet — the parser runs its bootstrap grammar. Keywords appear here when
            <code className="mx-1">register_form_keyword</code>
            is called.
          </div>
        ) : (
          <ul className="grid grid-cols-3 gap-1 font-mono text-sm text-amber-300/90">
            {result.keywords.map((k) => (
              <li key={k}>{k}</li>
            ))}
          </ul>
        )}
      </div>
    );
  }

  if (result.kind === "vocabulary" && result.vocabulary) {
    return (
      <div className="space-y-4 rounded border border-stone-800/40 bg-stone-900/30 p-3">
        <KeyValueGrid data={result.vocabulary.recipes} label="Recipes by RBasic category" />
        <KeyValueGrid
          data={result.vocabulary.blueprints}
          label="Blueprints by BBasic category"
        />
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
  const firstExample = GROUPS[0].examples[0];
  const [expression, setExpression] = useState(firstExample.expr);
  const [activeShowcase, setActiveShowcase] = useState(firstExample.showcases);
  const [evaluating, setEvaluating] = useState(false);
  const [result, setResult] = useState<FormResultOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  const pickExample = (ex: Example) => {
    setExpression(ex.expr);
    setActiveShowcase(ex.showcases);
    setResult(null);
    setError(null);
  };

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
    <div className="space-y-6">
      <div className="space-y-4">
        {GROUPS.map((group) => (
          <div key={group.heading} className="space-y-2">
            <div>
              <h2 className="text-sm font-semibold text-stone-200">{group.heading}</h2>
              <p className="text-xs text-stone-500">{group.blurb}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              {group.examples.map((ex) => (
                <button
                  key={ex.expr}
                  onClick={() => pickExample(ex)}
                  className={`rounded border px-3 py-1 text-xs transition-colors ${
                    expression === ex.expr
                      ? "border-amber-500/50 bg-amber-500/10 text-amber-200"
                      : "border-stone-800/40 bg-stone-900/30 text-stone-400 hover:text-amber-300 hover:border-amber-500/30"
                  }`}
                  title={ex.showcases}
                >
                  {ex.label}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="space-y-2">
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
        {activeShowcase && (
          <p className="text-xs text-stone-500 italic">{activeShowcase}</p>
        )}
      </div>

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
