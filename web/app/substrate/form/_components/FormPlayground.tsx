"use client";

import { useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { ArrowRight, Cpu, Play, RotateCcw, Sparkles } from "lucide-react";
import {
  LOCAL_FORM_EXAMPLES,
  runLocalFormBinary,
  type LocalFormRun,
} from "@/lib/form-kernel/client";
import {
  ACTION_LANGUAGE_STARTER,
  CROSS_MODALITY_STARTER,
  GRAMMAR_ACTION_STARTER,
  GRAMMAR_CAPTURES_STARTER,
  GRAMMAR_PATTERN_STARTER,
  PYTHON_FORM_STARTER,
  compileActionLanguage,
  compileCrossModalityRecipe,
  compileGrammarBuilder,
  compilePythonToForm,
  type GrammarLaneId,
} from "@/lib/form-kernel/grammar-lanes";

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

type Quest = {
  label: string;
  audience: string;
  expr: string;
  showcases: string;
  nextMove: string;
};

const QUESTS: Quest[] = [
  {
    label: "Ask what a teaching is shaped like",
    audience: "first-time visitor",
    expr: "@concept(lc-trust-over-fear).blueprint",
    showcases:
      "A concept's Blueprint NodeID is its structural identity. This is the quickest way to see that the substrate is answering with shape, not prose.",
    nextMove: "Change the concept id, then ask ?equivalent on the same cell.",
  },
  {
    label: "Find structural kin",
    audience: "researcher",
    expr: "?equivalent @concept(lc-trust-over-fear)",
    showcases:
      "Structural equivalents share a Blueprint NodeID even when their names, domains, or words differ.",
    nextMove: "Open any returned cell and ask for its .ctor.",
  },
  {
    label: "Read the body's count",
    audience: "steward",
    expr: "?lattice",
    showcases:
      "A lattice snapshot gives the count-level framebuffer: blueprints, recipes, cells, and relationships currently interned.",
    nextMove: "Run ?vocabulary next to see which recipe categories are circulating.",
  },
  {
    label: "Make code become a recipe",
    audience: "builder",
    expr: "do { let x = 5; let y = x + 3; y * 2 }",
    showcases:
      "Form interns code as a Recipe NodeID. Two expressions with the same structure converge on the same identity.",
    nextMove: "Change one number and watch the recipe identity change.",
  },
];

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

function LocalKernelPanel() {
  const firstExample = LOCAL_FORM_EXAMPLES[0];
  const [binary, setBinary] = useState(firstExample.source);
  const [activeNote, setActiveNote] = useState(firstExample.note);
  const [localRun, setLocalRun] = useState<LocalFormRun | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);

  const pickLocalExample = (example: (typeof LOCAL_FORM_EXAMPLES)[number]) => {
    setBinary(example.source);
    setActiveNote(example.note);
    setLocalRun(null);
    setLocalError(null);
  };

  const runLocal = () => {
    if (!binary.trim()) return;
    setLocalError(null);
    setLocalRun(null);
    try {
      setLocalRun(runLocalFormBinary(binary));
    } catch (e: unknown) {
      setLocalError(e instanceof Error ? e.message : "Local kernel failed");
    }
  };

  const hotArms = localRun ? localRun.trace.arms.slice(0, 5) : [];

  return (
    <section
      className="grid gap-5 rounded-xl border border-teal-500/20 bg-teal-500/5 p-4 lg:grid-cols-[0.9fr_1.1fr]"
      aria-labelledby="local-kernel-heading"
    >
      <div className="space-y-4">
        <div className="space-y-2">
          <p className="text-xs uppercase tracking-[0.22em] text-teal-300/75">
            Local TS kernel
          </p>
          <h2 id="local-kernel-heading" className="text-2xl font-light text-stone-100">
            Run a Form binary in this browser.
          </h2>
          <p className="text-sm leading-relaxed text-stone-400">
            This lane does not call the API. The TypeScript kernel parses the text-encoded
            <code className="mx-1">.fk</code>
            binary, walks the recipe, and reports the local trace from this tab.
          </p>
        </div>

        <div className="grid gap-2">
          {LOCAL_FORM_EXAMPLES.map((example) => (
            <button
              key={example.label}
              type="button"
              onClick={() => pickLocalExample(example)}
              className={`rounded-lg border px-3 py-3 text-left transition-colors ${
                binary === example.source
                  ? "border-teal-400/50 bg-teal-500/10 text-teal-100"
                  : "border-stone-800/50 bg-stone-950/35 text-stone-300 hover:border-teal-500/35 hover:text-teal-200"
              }`}
            >
              <span className="flex items-center gap-2 text-sm font-medium">
                <Cpu className="h-4 w-4 text-teal-300/80" aria-hidden="true" />
                {example.label}
              </span>
              <span className="mt-1 block text-xs leading-relaxed text-stone-500">
                {example.note}
              </span>
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-4 rounded-xl border border-stone-800/50 bg-stone-950/35 p-4">
        <div className="space-y-2">
          <label htmlFor="local-form-binary" className="text-xs uppercase tracking-[0.18em] text-stone-500">
            .fk binary
          </label>
          <textarea
            id="local-form-binary"
            value={binary}
            onChange={(e) => {
              setBinary(e.target.value);
              setActiveNote("Run the edited binary locally and compare the trace.");
            }}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                e.preventDefault();
                runLocal();
              }
            }}
            className="h-44 w-full resize-y rounded-xl border border-stone-800/50 bg-stone-950/80 p-3 font-mono text-sm leading-relaxed text-stone-300 transition-colors focus:border-teal-500/40 focus:outline-none"
            spellCheck={false}
          />
          <p className="text-xs leading-relaxed text-stone-500">{activeNote}</p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={runLocal}
            disabled={!binary.trim()}
            className="inline-flex items-center gap-2 rounded-xl border border-teal-500/20 bg-teal-500/10 px-5 py-2.5 text-sm font-medium text-teal-200 transition-all hover:border-teal-500/30 hover:bg-teal-500/20 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Play className="h-4 w-4" aria-hidden="true" />
            Run locally
          </button>
          <span className="text-xs text-stone-600">⌘↩ to run in-tab</span>
        </div>

        {localError && (
          <div className="whitespace-pre-wrap rounded-xl border border-red-800/30 bg-red-900/10 p-3 text-sm text-red-300">
            {localError}
          </div>
        )}

        {localRun && (
          <div className="space-y-3 rounded-xl border border-stone-800/50 bg-stone-900/25 p-3">
            <div className="grid gap-3 sm:grid-cols-3">
              <div>
                <div className="text-xs uppercase tracking-wide text-stone-500">Result</div>
                <div className="mt-1 font-mono text-lg text-teal-200">{localRun.result}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wide text-stone-500">Root</div>
                <div className="mt-1 font-mono text-sm text-stone-300">{localRun.root}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wide text-stone-500">Walks</div>
                <div className="mt-1 font-mono text-sm text-stone-300">
                  {localRun.trace.total_walks} · {localRun.elapsedMs.toFixed(2)} ms
                </div>
              </div>
            </div>

            <div className="rounded-lg border border-stone-800/40 bg-stone-950/45 p-3">
              <div className="mb-2 text-xs uppercase tracking-wide text-stone-500">
                Hot dispatch arms
              </div>
              <div className="grid gap-1 font-mono text-xs text-stone-300 sm:grid-cols-2">
                {hotArms.map((arm) => (
                  <div key={arm.arm_ty} className="flex justify-between gap-3">
                    <span>RBasic.{arm.arm_name}</span>
                    <span className="text-teal-200">{arm.count}</span>
                  </div>
                ))}
              </div>
            </div>

            {(localRun.stdout || localRun.stderr) && (
              <pre className="max-h-40 overflow-auto rounded-lg border border-stone-800/40 bg-stone-950/45 p-3 text-xs text-stone-400">
                {localRun.stdout}
                {localRun.stderr}
              </pre>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

const GRAMMAR_LANES: Array<{
  id: GrammarLaneId;
  label: string;
  audience: string;
  description: string;
}> = [
  {
    id: "action",
    label: "BML / Action Language",
    audience: "embodied command",
    description: "Run delegate, raise, undo, with, and invoke as action-shaped Form.",
  },
  {
    id: "python",
    label: "Python => Form",
    audience: "code translation",
    description: "Paste a tiny Python function and watch the recipe skeleton appear.",
  },
  {
    id: "builder",
    label: "Grammar Builder",
    audience: "new grammar",
    description: "Define a pattern, captures, and semantic action in one living rule.",
  },
  {
    id: "modality",
    label: "Cross-Modality Recipe",
    audience: "source extraction",
    description: "Turn story, song, video, or source into a transferable recipe.",
  },
];

const RECIPE_KINDS = [
  "teaching recipe",
  "movement recipe",
  "implementation recipe",
  "verification recipe",
];

function GrammarLanesPanel({
  onLoadExpression,
}: {
  onLoadExpression: (expr: string, showcases: string, nextMove: string) => void;
}) {
  const [activeLane, setActiveLane] = useState<GrammarLaneId>("action");
  const [actionCommand, setActionCommand] = useState(ACTION_LANGUAGE_STARTER);
  const [pythonSource, setPythonSource] = useState(PYTHON_FORM_STARTER);
  const [pattern, setPattern] = useState(GRAMMAR_PATTERN_STARTER);
  const [captures, setCaptures] = useState(GRAMMAR_CAPTURES_STARTER);
  const [semanticAction, setSemanticAction] = useState(GRAMMAR_ACTION_STARTER);
  const [modalitySource, setModalitySource] = useState(CROSS_MODALITY_STARTER);
  const [recipeKind, setRecipeKind] = useState(RECIPE_KINDS[0]);

  const output = useMemo(() => {
    if (activeLane === "python") return compilePythonToForm(pythonSource);
    if (activeLane === "builder") {
      return compileGrammarBuilder(pattern, captures, semanticAction);
    }
    if (activeLane === "modality") {
      return compileCrossModalityRecipe(modalitySource, recipeKind);
    }
    return compileActionLanguage(actionCommand);
  }, [
    activeLane,
    actionCommand,
    captures,
    modalitySource,
    pattern,
    pythonSource,
    recipeKind,
    semanticAction,
  ]);

  return (
    <section
      className="grid max-w-full gap-5 overflow-hidden rounded-xl border border-violet-300/70 bg-violet-50/80 p-4 dark:border-violet-500/20 dark:bg-violet-500/5 lg:grid-cols-[0.85fr_1.15fr]"
      aria-labelledby="grammar-lanes-heading"
    >
      <div className="min-w-0 space-y-4">
        <div className="space-y-2">
          <p className="text-xs uppercase tracking-[0.22em] text-violet-600 dark:text-violet-300/75">
            Grammar lanes
          </p>
          <h2 id="grammar-lanes-heading" className="text-2xl font-light text-stone-950 dark:text-stone-100">
            Let new grammars surface here.
          </h2>
          <p className="text-sm leading-relaxed text-stone-700 dark:text-stone-400">
            Each lane turns a different source shape into a Form-facing recipe. Edit the
            input, read the generated payload, then load the pieces that already execute
            through the evaluator.
          </p>
        </div>

        <div className="grid gap-2">
          {GRAMMAR_LANES.map((lane) => (
            <button
              key={lane.id}
              type="button"
              onClick={() => setActiveLane(lane.id)}
              className={`rounded-lg border px-3 py-3 text-left transition-colors ${
                activeLane === lane.id
                  ? "border-violet-500/60 bg-violet-100/80 text-stone-950 dark:border-violet-400/50 dark:bg-violet-500/10 dark:text-violet-100"
                  : "border-stone-300/70 bg-white/75 text-stone-800 hover:border-violet-400/60 hover:text-violet-800 dark:border-stone-800/50 dark:bg-stone-950/35 dark:text-stone-300 dark:hover:border-violet-500/35 dark:hover:text-violet-200"
              }`}
            >
              <span className="flex items-center gap-2 text-sm font-medium">
                <Sparkles className="h-4 w-4 text-violet-600 dark:text-violet-300/80" aria-hidden="true" />
                {lane.label}
              </span>
              <span className="mt-1 block text-xs uppercase tracking-[0.16em] text-stone-600 dark:text-stone-500">
                {lane.audience}
              </span>
              <span className="mt-1 block text-xs leading-relaxed text-stone-700 dark:text-stone-500">
                {lane.description}
              </span>
            </button>
          ))}
        </div>
      </div>

      <div className="min-w-0 space-y-4 rounded-xl border border-stone-300/70 bg-white/75 p-4 dark:border-stone-800/50 dark:bg-stone-950/35">
        {activeLane === "action" && (
          <div className="space-y-2">
            <label htmlFor="grammar-action" className="text-xs uppercase tracking-[0.18em] text-stone-600 dark:text-stone-500">
              Embodied command
            </label>
            <textarea
              id="grammar-action"
              value={actionCommand}
              onChange={(e) => setActionCommand(e.target.value)}
              className="h-28 w-full min-w-0 resize-y rounded-xl border border-stone-300 bg-white p-3 font-mono text-sm leading-relaxed text-stone-900 transition-colors focus:border-violet-500/60 focus:outline-none dark:border-stone-800/50 dark:bg-stone-950/80 dark:text-stone-300 dark:focus:border-violet-500/40"
              spellCheck={false}
            />
          </div>
        )}

        {activeLane === "python" && (
          <div className="space-y-2">
            <label htmlFor="grammar-python" className="text-xs uppercase tracking-[0.18em] text-stone-600 dark:text-stone-500">
              Python function
            </label>
            <textarea
              id="grammar-python"
              value={pythonSource}
              onChange={(e) => setPythonSource(e.target.value)}
              className="h-40 w-full min-w-0 resize-y rounded-xl border border-stone-300 bg-white p-3 font-mono text-sm leading-relaxed text-stone-900 transition-colors focus:border-violet-500/60 focus:outline-none dark:border-stone-800/50 dark:bg-stone-950/80 dark:text-stone-300 dark:focus:border-violet-500/40"
              spellCheck={false}
            />
          </div>
        )}

        {activeLane === "builder" && (
          <div className="space-y-3">
            <div className="space-y-2">
              <label htmlFor="grammar-pattern" className="text-xs uppercase tracking-[0.18em] text-stone-600 dark:text-stone-500">
                Pattern
              </label>
              <input
                id="grammar-pattern"
                value={pattern}
                onChange={(e) => setPattern(e.target.value)}
                className="w-full min-w-0 rounded-xl border border-stone-300 bg-white p-3 font-mono text-sm text-stone-900 transition-colors focus:border-violet-500/60 focus:outline-none dark:border-stone-800/50 dark:bg-stone-950/80 dark:text-stone-300 dark:focus:border-violet-500/40"
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="grammar-captures" className="text-xs uppercase tracking-[0.18em] text-stone-600 dark:text-stone-500">
                Captures
              </label>
              <input
                id="grammar-captures"
                value={captures}
                onChange={(e) => setCaptures(e.target.value)}
                className="w-full min-w-0 rounded-xl border border-stone-300 bg-white p-3 font-mono text-sm text-stone-900 transition-colors focus:border-violet-500/60 focus:outline-none dark:border-stone-800/50 dark:bg-stone-950/80 dark:text-stone-300 dark:focus:border-violet-500/40"
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="grammar-action-builder" className="text-xs uppercase tracking-[0.18em] text-stone-600 dark:text-stone-500">
                Semantic action
              </label>
              <input
                id="grammar-action-builder"
                value={semanticAction}
                onChange={(e) => setSemanticAction(e.target.value)}
                className="w-full min-w-0 rounded-xl border border-stone-300 bg-white p-3 font-mono text-sm text-stone-900 transition-colors focus:border-violet-500/60 focus:outline-none dark:border-stone-800/50 dark:bg-stone-950/80 dark:text-stone-300 dark:focus:border-violet-500/40"
              />
            </div>
          </div>
        )}

        {activeLane === "modality" && (
          <div className="space-y-3">
            <div className="space-y-2">
              <label htmlFor="recipe-kind" className="text-xs uppercase tracking-[0.18em] text-stone-600 dark:text-stone-500">
                Recipe kind
              </label>
              <select
                id="recipe-kind"
                value={recipeKind}
                onChange={(e) => setRecipeKind(e.target.value)}
                className="w-full min-w-0 rounded-xl border border-stone-300 bg-white p-3 text-sm text-stone-900 transition-colors focus:border-violet-500/60 focus:outline-none dark:border-stone-800/50 dark:bg-stone-950/80 dark:text-stone-300 dark:focus:border-violet-500/40"
              >
                {RECIPE_KINDS.map((kind) => (
                  <option key={kind} value={kind}>
                    {kind}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <label htmlFor="modality-source" className="text-xs uppercase tracking-[0.18em] text-stone-600 dark:text-stone-500">
                Source fragment
              </label>
              <textarea
                id="modality-source"
                value={modalitySource}
                onChange={(e) => setModalitySource(e.target.value)}
                className="h-36 w-full min-w-0 resize-y rounded-xl border border-stone-300 bg-white p-3 text-sm leading-relaxed text-stone-900 transition-colors focus:border-violet-500/60 focus:outline-none dark:border-stone-800/50 dark:bg-stone-950/80 dark:text-stone-300 dark:focus:border-violet-500/40"
              />
            </div>
          </div>
        )}

        <div className="space-y-3 rounded-xl border border-stone-300/70 bg-white/70 p-3 dark:border-stone-800/50 dark:bg-stone-900/25">
          <div>
            <div className="text-xs uppercase tracking-wide text-stone-600 dark:text-stone-500">
              {output.title}
            </div>
            <p className="mt-1 text-sm leading-relaxed text-stone-700 dark:text-stone-400">{output.summary}</p>
          </div>
          <pre className="max-h-72 max-w-full overflow-auto whitespace-pre-wrap break-words rounded-lg border border-stone-800/40 bg-stone-950/60 p-3 text-xs leading-relaxed text-violet-100/90">
            {output.form}
          </pre>
          <div className="grid gap-2 sm:grid-cols-2">
            {output.steps.map((step) => (
              <div
                key={step}
                className="rounded-lg border border-stone-300/70 bg-stone-50 px-3 py-2 text-xs text-stone-700 dark:border-stone-800/40 dark:bg-stone-950/45 dark:text-stone-400"
              >
                {step}
              </div>
            ))}
          </div>
          {output.loadableExpression && (
            <button
              type="button"
              onClick={() =>
                onLoadExpression(
                  output.loadableExpression ?? output.form,
                  `${output.title} generated this Form expression. Run it, then edit one binding and compare the returned shape.`,
                  "Run it in the evaluator, then change one noun or verb and run again.",
                )
              }
              className="inline-flex items-center gap-2 rounded-xl border border-violet-500/30 bg-violet-100 px-4 py-2 text-sm font-medium text-violet-800 transition-all hover:border-violet-500/50 hover:bg-violet-200 dark:border-violet-500/20 dark:bg-violet-500/10 dark:text-violet-200 dark:hover:border-violet-500/30 dark:hover:bg-violet-500/20"
            >
              <Play className="h-4 w-4" aria-hidden="true" />
              Load into evaluator
            </button>
          )}
        </div>
      </div>
    </section>
  );
}

// Build a starter expression when the playground arrives bound to a cell.
// `?cell=@concept(lc-pulse)` becomes `@concept(lc-pulse).blueprint` — a
// useful first question to ask of any cell. The visitor lands inside a
// conversation already in progress, rather than at a blank textarea.
function starterFromCell(cellRef: string | null): {
  expr: string;
  showcases: string;
} | null {
  if (!cellRef) return null;
  const trimmed = cellRef.trim();
  if (!trimmed.startsWith("@")) return null;
  return {
    expr: `${trimmed}.blueprint`,
    showcases: `Reading ${trimmed}'s Blueprint NodeID — the cell's structural identity. Try .ctor for its CTOR recipe, or ?equivalent ${trimmed} for cells sharing its Blueprint.`,
  };
}

export function FormPlayground() {
  const searchParams = useSearchParams();
  const cellParam = searchParams.get("cell");
  const starter = starterFromCell(cellParam);
  const firstQuest = QUESTS[0];
  const [expression, setExpression] = useState(
    starter ? starter.expr : firstQuest.expr,
  );
  const [activeShowcase, setActiveShowcase] = useState(
    starter ? starter.showcases : firstQuest.showcases,
  );
  const [nextMove, setNextMove] = useState(
    starter ? "Run it, then replace .blueprint with .ctor or prepend ?equivalent." : firstQuest.nextMove,
  );
  const [evaluating, setEvaluating] = useState(false);
  const [result, setResult] = useState<FormResultOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  const pickQuest = (quest: Quest) => {
    setExpression(quest.expr);
    setActiveShowcase(quest.showcases);
    setNextMove(quest.nextMove);
    setResult(null);
    setError(null);
  };

  const pickExample = (ex: Example) => {
    setExpression(ex.expr);
    setActiveShowcase(ex.showcases);
    setNextMove("Edit one symbol, run it again, and compare the returned shape.");
    setResult(null);
    setError(null);
  };

  const loadGeneratedExpression = (expr: string, showcases: string, next: string) => {
    setExpression(expr);
    setActiveShowcase(showcases);
    setNextMove(next);
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
    <div className="space-y-8">
      <section className="grid gap-5 lg:grid-cols-[0.85fr_1.15fr]" aria-labelledby="form-play-heading">
        <div className="space-y-4 rounded-xl border border-amber-500/20 bg-amber-500/5 p-4">
          <div className="space-y-2">
            <p className="text-xs uppercase tracking-[0.22em] text-amber-300/75">Play first</p>
            <h2 id="form-play-heading" className="text-2xl font-light text-stone-100">
              Pick a question. Press Evaluate. Change one word.
            </h2>
            <p className="text-sm leading-relaxed text-stone-400">
              These are live substrate questions with a real answer. No setup, no repo clone, no grammar study first.
            </p>
          </div>
          <div className="grid gap-2">
            {QUESTS.map((quest) => (
              <button
                key={quest.expr}
                type="button"
                onClick={() => pickQuest(quest)}
                className={`rounded-lg border px-3 py-3 text-left transition-colors ${
                  expression === quest.expr
                    ? "border-amber-500/50 bg-amber-500/10 text-amber-100"
                    : "border-stone-800/50 bg-stone-950/35 text-stone-300 hover:border-amber-500/35 hover:text-amber-200"
                }`}
              >
                <span className="flex items-center gap-2 text-sm font-medium">
                  <Sparkles className="h-4 w-4 text-amber-300/75" aria-hidden="true" />
                  {quest.label}
                </span>
                <span className="mt-1 block text-xs uppercase tracking-[0.16em] text-stone-500">
                  {quest.audience}
                </span>
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-4 rounded-xl border border-stone-800/50 bg-stone-900/25 p-4">
          <div className="space-y-2">
            <label htmlFor="form-expression" className="text-xs uppercase tracking-[0.18em] text-stone-500">
              Expression
            </label>
            <textarea
              id="form-expression"
              value={expression}
              onChange={(e) => {
                setExpression(e.target.value);
                setNextMove("Run it, read the returned shape, then change one part and run again.");
              }}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                  e.preventDefault();
                  evaluate();
                }
              }}
              className="h-32 w-full resize-y rounded-xl border border-stone-800/50 bg-stone-950/60 p-3 font-mono text-sm leading-relaxed text-stone-300 transition-colors focus:border-amber-500/40 focus:outline-none"
              placeholder="@spec(agent-pipeline)"
              spellCheck={false}
            />
            {activeShowcase && <p className="text-xs leading-relaxed text-stone-500">{activeShowcase}</p>}
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={evaluate}
              disabled={evaluating || !expression.trim()}
              className="inline-flex items-center gap-2 rounded-xl border border-amber-500/20 bg-amber-500/10 px-5 py-2.5 text-sm font-medium text-amber-300/90 transition-all hover:border-amber-500/30 hover:bg-amber-500/20 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Play className="h-4 w-4" aria-hidden="true" />
              {evaluating ? "Evaluating..." : "Evaluate"}
            </button>
            <button
              type="button"
              onClick={() => {
                pickQuest(firstQuest);
              }}
              className="inline-flex items-center gap-2 rounded-xl border border-stone-800/60 bg-stone-950/35 px-4 py-2.5 text-sm text-stone-400 transition-colors hover:border-stone-700 hover:text-stone-200"
            >
              <RotateCcw className="h-4 w-4" aria-hidden="true" />
              Reset
            </button>
            <span className="text-xs text-stone-600">⌘↩ to evaluate</span>
          </div>

          {nextMove && (
            <div className="rounded-lg border border-teal-500/20 bg-teal-500/5 p-3 text-sm leading-relaxed text-teal-100/80">
              <span className="font-medium text-teal-200">Next move:</span> {nextMove}
            </div>
          )}

          {error && (
            <div className="whitespace-pre-wrap rounded-xl border border-red-800/30 bg-red-900/10 p-3 text-sm text-red-300">
              {error}
            </div>
          )}

          {result && <ResultPanel result={result} />}
        </div>
      </section>

      <LocalKernelPanel />

      <GrammarLanesPanel onLoadExpression={loadGeneratedExpression} />

      <section className="space-y-4" aria-labelledby="form-atlas-heading">
        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-stone-500">Expression atlas</p>
          <h2 id="form-atlas-heading" className="mt-2 text-xl font-light text-stone-200">
            Keep playing with the deeper grammar.
          </h2>
        </div>
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
      </section>

      <div className="rounded-xl border border-stone-800/50 bg-stone-900/25 p-4 text-sm leading-relaxed text-stone-400">
        <Link href="/vision/recipes" className="inline-flex items-center gap-2 text-amber-200 hover:text-amber-100">
          Turn this structural question into a transmission recipe
          <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </Link>
      </div>
    </div>
  );
}
