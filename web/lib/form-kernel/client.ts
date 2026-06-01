// Browser-facing bridge into the TypeScript Form kernel.
import {
  Frame,
  Kernel,
  Trace,
  nodeKey,
  walk,
  type NodeID,
} from "./vendor/kernel.ts";
import { readAll } from "./vendor/reader.ts";
import {
  FIELD_MODEL_FORM_DEMO_SOURCE,
  FIELD_MODEL_FORM_PUBLIC_MARKER,
} from "./field-model-form";

export type LocalFormRun = {
  source: string;
  result: string;
  root: string;
  rootCategory: string;
  stdout: string;
  stderr: string;
  elapsedMs: number;
  trace: LocalFormTrace;
};

export type LocalFormTrace = {
  total_walks: number;
  arms: Array<{ arm_ty: number; arm_name: string; count: number }>;
  variants: Array<{
    arm_ty: number;
    arm_inst: number;
    arm_name: string;
    arm_variant_name: string;
    count: number;
  }>;
  choice_attempts: number;
  choice_successes: number;
  choice_failures: number;
  choice_success_rate: number;
};

export type LocalFormExample = {
  label: string;
  source: string;
  note: string;
  proofMarker?: string;
};

export const LOCAL_FORM_EXAMPLES: LocalFormExample[] = [
  {
    label: "Arithmetic binary",
    source: "(add 1 (mul 2 3))",
    note: "Walks a tiny .fk binary locally and returns 7 without the API.",
  },
  {
    label: "Recursive recipe",
    source: `(do
  (defn fact (n)
    (if (le n 1)
      1
      (mul n (fact (sub n 1)))))
  (fact 8))`,
    note: "Defines and executes a recursive Form function inside the browser kernel.",
  },
  {
    label: "Binary codec shape",
    source: `(do
  (let bytes (list 70 111 114 109))
  (add (len bytes) (nth bytes 0)))`,
    note: "Treats bytes as a Form list, the path used by file grammars and local codecs.",
  },
  {
    label: "Kernel self-witness",
    source: `(do
  (let n (make_nodeid 1 5 4 1))
  (if (node_eq n (make_nodeid 1 5 4 1)) 1 0))`,
    note: "Creates NodeIDs in local memory and asks the kernel to compare them structurally.",
  },
  {
    label: "Field Model Form proof",
    source: FIELD_MODEL_FORM_DEMO_SOURCE,
    note: "Runs a 93-point FMF proof over every primitive constructor, seven domain grammars, lineage lenses, quantum rain, observer receipts, and residuals.",
    proofMarker: FIELD_MODEL_FORM_PUBLIC_MARKER,
  },
];

function formatNodeId(n: NodeID): string {
  return `@${nodeKey(n)}`;
}

export function runLocalFormBinary(source: string): LocalFormRun {
  const stdout: string[] = [];
  const stderr: string[] = [];
  const kernel = new Kernel({
    writeStdout: (text) => stdout.push(text),
    writeStderr: (text) => stderr.push(text),
  });
  kernel.trace = new Trace();
  const start = performance.now();
  const root = readAll(kernel, source);
  const value = walk(kernel, root, new Frame(null));
  const elapsedMs = performance.now() - start;
  return {
    source,
    result: kernel.render(value),
    root: formatNodeId(root),
    rootCategory: formatNodeId(kernel.category(root)),
    stdout: stdout.join(""),
    stderr: stderr.join(""),
    elapsedMs,
    trace: kernel.trace.toJSON() as LocalFormTrace,
  };
}
