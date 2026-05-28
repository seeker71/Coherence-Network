"use client";

// XPath teaching demo — a browser-side simulator that walks a synthetic
// substrate tree against a path string. The implementation in form-stdlib
// (form/form-stdlib/xpath.fk) is what runs against the real lattice;
// this demo carries the shape of the language faithfully so a visitor
// can feel how path selectors traverse the holographic structure.

import { useMemo, useState } from "react";
import { Play, Search } from "lucide-react";

type SynthNode = {
  // Render-only NodeID — package.level.type.instance
  nid: string;
  // category.instance — what kind of node this is (cat:N in path syntax)
  catInst: number;
  // For trivial-string nodes, the interned value
  text?: string;
  // For named cell-refs or struct-fields
  name?: string;
  // Holographic descent
  children?: SynthNode[];
};

// Children with a stable empty default so the walker doesn't branch on undefined.
function kids(n: SynthNode): SynthNode[] {
  return n.children ?? [];
}

// A small illustrative tree: a Memory cell with its Blueprint and CTOR
// hung off it. Matches the fractal-tree explanation in form-language.md
// (the {name: ~String, ...} that looks flat but is a tree).
const SYNTH_ROOT: SynthNode = {
  nid: "@1.5.4.1",
  catInst: 4, // B_Domain.MEMORY blueprint, cat.inst=4
  name: "memory:presences_of_the_field",
  children: [
    {
      // .blueprint — composite Blueprint
      nid: "@1.5.4.1#bp",
      catInst: 9, // B_Container.OBJECT
      name: "blueprint",
      children: [
        {
          nid: "@1.4.1.1",
          catInst: 9,
          name: "name",
          children: [{ nid: "@1.1.2.4#str", catInst: 5, text: "presences_of_the_field" }],
        },
        {
          nid: "@1.4.1.2",
          catInst: 9,
          name: "description",
          children: [
            { nid: "@1.1.2.4#desc", catInst: 5, text: "Field of presences interweaving" },
          ],
        },
        {
          nid: "@1.4.1.3",
          catInst: 9,
          name: "type",
          children: [{ nid: "@1.1.2.4#type", catInst: 5, text: "memory" }],
        },
      ],
    },
    {
      // .ctor — composed values under R_Block.DO
      nid: "@1.3.9.1",
      catInst: 11, // R_Block.DO
      name: "ctor",
      children: [
        { nid: "@1.1.5.5", catInst: 5, text: "presences_of_the_field" },
        { nid: "@1.1.5.6", catInst: 5, text: "Field of presences interweaving" },
        { nid: "@1.1.5.7", catInst: 5, text: "memory" },
      ],
    },
  ],
};

// Parse a path step. Returns null if the step is malformed.
type Selector =
  | { kind: "wildcard" }
  | { kind: "cat"; value: number }
  | { kind: "name"; value: string }
  | { kind: "text"; value: string };

function parseStep(raw: string): Selector | null {
  const s = raw.trim();
  if (!s) return null;
  if (s === "*") return { kind: "wildcard" };
  if (s.startsWith("cat:")) {
    const n = Number(s.slice(4));
    return Number.isNaN(n) ? null : { kind: "cat", value: n };
  }
  if (s.startsWith("name:")) return { kind: "name", value: s.slice(5) };
  if (s.startsWith("text:")) return { kind: "text", value: s.slice(5) };
  return null;
}

function nodeMatches(n: SynthNode, sel: Selector): boolean {
  switch (sel.kind) {
    case "wildcard":
      return true;
    case "cat":
      return n.catInst === sel.value;
    case "name":
      return n.name === sel.value;
    case "text":
      return n.text === sel.value;
  }
}

// xpath evaluator — supports /, //, *, cat:N, name:s, text:s, and a
// positional [N] predicate. Faithful subset of the form-stdlib evaluator.
function evaluatePath(path: string, root: SynthNode): SynthNode[] {
  const trimmed = path.trim();
  if (!trimmed || trimmed === "/") return [root];
  if (!trimmed.startsWith("/")) return [];

  // Split on / but keep // as a marker. Walk left-to-right.
  const tokens: Array<{ descend: boolean; step: string }> = [];
  let i = 1; // skip leading /
  while (i <= trimmed.length) {
    const isDouble = trimmed[i] === "/";
    if (isDouble) i += 1;
    // Read until next / (but not past a [ predicate)
    let j = i;
    let inBracket = false;
    while (j < trimmed.length) {
      const ch = trimmed[j];
      if (ch === "[") inBracket = true;
      else if (ch === "]") inBracket = false;
      else if (ch === "/" && !inBracket) break;
      j += 1;
    }
    const piece = trimmed.slice(i, j);
    if (piece) tokens.push({ descend: isDouble, step: piece });
    i = j + 1;
  }

  let current: SynthNode[] = [root];
  for (const tok of tokens) {
    // Parse predicate [N]
    const predMatch = tok.step.match(/^([^[]+)\[(\d+)\]$/);
    const stepText = predMatch ? predMatch[1] : tok.step;
    const predIndex = predMatch ? Number(predMatch[2]) : null;

    const sel = parseStep(stepText);
    if (!sel) return [];

    const next: SynthNode[] = [];
    for (const node of current) {
      if (tok.descend) {
        // // — descendant-or-self
        const stack = [node];
        while (stack.length) {
          const n = stack.shift()!;
          if (nodeMatches(n, sel)) next.push(n);
          stack.push(...kids(n));
        }
      } else {
        // / — immediate children
        for (const c of kids(node)) {
          if (nodeMatches(c, sel)) next.push(c);
        }
      }
    }

    current =
      predIndex !== null && predIndex >= 0 && predIndex < next.length
        ? [next[predIndex]]
        : next;
  }
  return current;
}

function TreeNodeView({ node, depth }: { node: SynthNode; depth: number }) {
  return (
    <div style={{ paddingLeft: depth * 12 }} className="text-xs font-mono">
      <span className="text-stone-500">{node.nid}</span>
      <span className="text-stone-600"> · cat.inst={node.catInst}</span>
      {node.name && <span className="text-amber-300/80"> · {node.name}</span>}
      {node.text && <span className="text-teal-300/80"> · "{node.text}"</span>}
      {kids(node).map((c) => (
        <TreeNodeView key={c.nid} node={c} depth={depth + 1} />
      ))}
    </div>
  );
}

const PRESET_PATHS: Array<{ label: string; path: string; teaching: string }> = [
  {
    label: "/* — all children of root",
    path: "/*",
    teaching: "Wildcard at depth 1. Returns .blueprint and .ctor.",
  },
  {
    label: "/cat:9 — Object-category children",
    path: "/cat:9",
    teaching:
      "Filter by category instance. Both .blueprint and .ctor pass through OBJECT-shaped wrappers in this synthetic tree.",
  },
  {
    label: "//name:type — descendant by name",
    path: "//name:type",
    teaching: "Walk the whole tree looking for the type field-Blueprint.",
  },
  {
    label: "/cat:9/cat:9/cat:5 — nested descent to leaves",
    path: "/cat:9/cat:9/cat:5",
    teaching:
      "Three steps: blueprint container → field-Blueprint → STRING leaf. Composes per-step.",
  },
  {
    label: '//text:"memory" — find a specific value',
    path: '//text:memory',
    teaching: "Find every trivial-string leaf with this exact value.",
  },
  {
    label: "/cat:11[0] — positional predicate",
    path: "/cat:11[0]",
    teaching:
      "First child of category 11 (R_Block.DO) at depth 1. [N] is 0-based positional.",
  },
];

export function XPathDemo() {
  const [path, setPath] = useState("//name:type");
  const [teaching, setTeaching] = useState(
    "Walk the whole tree looking for the type field-Blueprint.",
  );

  const matches = useMemo(() => evaluatePath(path, SYNTH_ROOT), [path]);

  const pickPreset = (p: (typeof PRESET_PATHS)[number]) => {
    setPath(p.path);
    setTeaching(p.teaching);
  };

  return (
    <section
      className="grid gap-5 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 lg:grid-cols-[0.9fr_1.1fr]"
      aria-labelledby="xpath-demo-heading"
    >
      <div className="space-y-4">
        <div className="space-y-2">
          <p className="text-xs uppercase tracking-[0.22em] text-emerald-300/75">
            XPath demo
          </p>
          <h2 id="xpath-demo-heading" className="text-2xl font-light text-stone-100">
            Walk a substrate tree with a path string.
          </h2>
          <p className="text-sm leading-relaxed text-stone-400">
            The full implementation lives in{" "}
            <code className="text-emerald-300/80">form/form-stdlib/xpath.fk</code>{" "}
            and runs against the real lattice. This demo carries the path
            language honestly against a small synthetic Memory tree so the
            selectors are tangible. Each preset below teaches one shape.
          </p>
        </div>

        <div className="grid gap-2">
          {PRESET_PATHS.map((p) => (
            <button
              key={p.label}
              type="button"
              onClick={() => pickPreset(p)}
              className={`rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                path === p.path
                  ? "border-emerald-400/50 bg-emerald-500/10 text-emerald-100"
                  : "border-stone-800/50 bg-stone-950/35 text-stone-300 hover:border-emerald-500/35 hover:text-emerald-200"
              }`}
            >
              <span className="flex items-center gap-2 font-mono text-xs">
                <Search className="h-3.5 w-3.5 text-emerald-300/75" aria-hidden="true" />
                {p.label}
              </span>
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-4 rounded-xl border border-stone-800/50 bg-stone-950/35 p-4">
        <div className="space-y-2">
          <label
            htmlFor="xpath-input"
            className="text-xs uppercase tracking-[0.18em] text-stone-500"
          >
            Path
          </label>
          <input
            id="xpath-input"
            value={path}
            onChange={(e) => {
              setPath(e.target.value);
              setTeaching("Walk the synthetic tree and see which nodes the selector picks.");
            }}
            className="w-full rounded-xl border border-stone-800/50 bg-stone-950/80 p-3 font-mono text-sm text-stone-300 transition-colors focus:border-emerald-500/40 focus:outline-none"
            placeholder="/cat:9/name:type"
            spellCheck={false}
          />
          <p className="text-xs leading-relaxed text-stone-500">{teaching}</p>
        </div>

        <div>
          <div className="text-xs uppercase tracking-wide text-stone-500 mb-2">
            Synthetic tree
          </div>
          <div className="rounded-lg border border-stone-800/40 bg-stone-950/50 p-3 max-h-56 overflow-auto">
            <TreeNodeView node={SYNTH_ROOT} depth={0} />
          </div>
        </div>

        <div>
          <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-stone-500 mb-2">
            <Play className="h-3.5 w-3.5 text-emerald-300/75" aria-hidden="true" />
            <span>
              {matches.length} match{matches.length !== 1 ? "es" : ""}
            </span>
          </div>
          {matches.length === 0 ? (
            <div className="rounded-lg border border-stone-800/40 bg-stone-950/50 p-3 text-xs text-stone-500">
              No nodes matched. Try one of the presets to see a valid path shape.
            </div>
          ) : (
            <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3 space-y-1 font-mono text-xs">
              {matches.map((m, idx) => (
                <div key={`${m.nid}-${idx}`} className="flex gap-3">
                  <span className="text-emerald-300/90">{m.nid}</span>
                  {m.name && <span className="text-amber-300/70">{m.name}</span>}
                  {m.text && <span className="text-teal-300/70">"{m.text}"</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
