// Browser-facing bridge into the canonical TypeScript Form kernel.
export {
  runLocalFormBinary,
  type LocalFormRun,
  type LocalFormTrace,
} from "../../../form/form-kernel-ts/src/browser.ts";
import {
  FIELD_AUTO_RESEARCH_BML_MARKER,
  FIELD_AUTO_RESEARCH_PERTURBATION_MARKER,
  FIELD_MODEL_FORM_BML_RUNTIME_MARKER,
  FIELD_MODEL_FORM_DEMO_SOURCE,
  FIELD_MODEL_FORM_PUBLIC_MARKER,
} from "./field-model-form";
import { runFieldRuntimeProof } from "./field-runtime";

export type LocalFormExample = {
  label: string;
  source: string;
  note: string;
  proofMarker?: string;
};

export const LOCAL_FIELD_RUNTIME_PROOF = runFieldRuntimeProof();
export const LOCAL_FORM_PROOF_MARKERS = [
  FIELD_MODEL_FORM_PUBLIC_MARKER,
  FIELD_MODEL_FORM_BML_RUNTIME_MARKER,
  FIELD_AUTO_RESEARCH_BML_MARKER,
  FIELD_AUTO_RESEARCH_PERTURBATION_MARKER,
  LOCAL_FIELD_RUNTIME_PROOF.marker,
];

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
    note: "Runs a 115-point FMF proof over every primitive constructor, nine domain grammars, lineage lenses, quantum rain, observer receipts, and residuals. The canonical BML runtime proof is shipped as field-model-form-bml-runtime-proof:63, with auto-research compiled into FMF as field-auto-research-bml-proof:127 and perturbation observation as field-auto-research-perturbation-proof:255.",
    proofMarker: FIELD_MODEL_FORM_PUBLIC_MARKER,
  },
];
