// recognition-recipe.ts — the recognize sense, run in-browser on the TS Form kernel.
//
// SOURCE OF TRUTH: form/form-stdlib/nearest-shape.fk + form/form-stdlib/recognition.fk
// (four-way 63). Verbatim recipe TEXT, run as-is on the same kernel that proves the
// band — not a TypeScript reimplementation. recognition depends on nearest-shape, so
// both are bundled and wrapped into one (do ...) program with the witness. The web
// container does not ship form/, so the text lives here; refresh on change.
import { Frame, Kernel, Trace, walk } from "./vendor/kernel.ts";
import { readAll } from "./vendor/reader.ts";

export const NEAREST_SHAPE_RECIPE = String.raw`
; nearest-shape.fk — the body's OWN classifier, built from core primitives: content-addressing as recognition.
;
; recognition-router.fk fuses a circle of MODEL readings; shared-sensing.fk fuses a circle of DEVICES.
; This is the layer underneath both: the recognizer itself. A query arrives as a FEATURE-VECTOR (bins
; of small integers — a coarse fingerprint of what was sensed). The body has INTERNED a set of
; PROTOTYPES, each (list label vector): "this shape is a dog, that shape is a cat". Recognition =
; find the prototype whose vector AGREES with the query in the most positions. SIMILARITY is a COUNT
; of agreeing bins — no subtraction, no distance metric, no float: just how many positions match. The
; nearest prototype's label is the recognition; its agreement count is the strength.
;
; This is content-addressing as perception. A prototype is a substrate cell; its Blueprint NodeID IS
; its vector's shape, identical on every kernel — so "nearest by structure" is the same answer on Go,
; Rust, and TS (validate.sh parity is recognition parity). LEARNING is the smallest possible act:
; adding a prototype to the set. No weights, no training loop — a new exemplar is a new (list label
; vector), and the next query can route to it immediately. The classifier the Mac proves is the SAME
; cell the phone receives, verifiable by NodeID, not an opaque weight-blob.
;
; A query = a feature-vector (list of bins, each a small int 0..100). A prototype = (list label vector).
; A prototype-set = a list of prototypes the body has interned so far.
;
; Honest lane: similarity is a COUNT of exact-agreeing bins, not a graded distance — two vectors that
; are close-but-never-equal score 0, the same as two that are wholly unrelated. That is the right
; primitive for content-addressed (quantized) features, where bins are already the discretization; it
; is the wrong primitive for raw continuous signal (quantize first, then recognize). Ties go to the
; FIRST-interned prototype (oldest exemplar wins) — recognition is stable under replay, not order-random.
;
; Proven by: form-stdlib/tests/nearest-shape-band.fk (four-way at validate.sh, incl. fkwu)

(do
    ; a prototype: (list label feature-vector)
    (defn ns-label-of (p) (nth p 0))   ; the prototype's label  ("dog", "cat", ...)
    (defn ns-vec-of   (p) (nth p 1))   ; the prototype's feature-vector

    ; --- SIMILARITY: count of indices where query and prototype agree, walked in lockstep. ---
    ; no subtraction, no distance — recognition is "how many bins match" (content-addressing).
    (defn ns-sim (v1 v2)
        (if (eq (len v1) 0) 0
            (if (eq (len v2) 0) 0
                (if (eq (head v1) (head v2))
                    (add 1 (ns-sim (tail v1) (tail v2)))
                    (ns-sim (tail v1) (tail v2))))))

    ; --- NEAREST: the prototype whose vector agrees most with the query (most data wins). ---
    ; mirror rr-select-loop's max walk; ties keep the FIRST-interned prototype (oldest exemplar).
    (defn ns-best-loop (query prototypes best best-sim)
        (if (eq (len prototypes) 0) best
            (if (eq (len best) 0)
                (ns-best-loop query (tail prototypes)
                              (head prototypes)
                              (ns-sim query (ns-vec-of (head prototypes))))
                (if (gt (ns-sim query (ns-vec-of (head prototypes))) best-sim)
                    (ns-best-loop query (tail prototypes)
                                  (head prototypes)
                                  (ns-sim query (ns-vec-of (head prototypes))))
                    (ns-best-loop query (tail prototypes) best best-sim)))))
    (defn ns-nearest (query prototypes) (ns-best-loop query prototypes (empty) 0))

    ; --- RECOGNITION: the nearest prototype's label, and the strength behind it. ---
    (defn ns-label    (query prototypes) (ns-label-of (ns-nearest query prototypes)))  ; what it is
    (defn ns-strength (query prototypes) (ns-sim query (ns-vec-of (ns-nearest query prototypes))))  ; how sure

    ; --- LEARNING: interning an exemplar GROWS the set (no training loop). The new prototype is
    ;     prepended; every older exemplar remains, so the next query can route to the new shape OR
    ;     any prior one. Adding without forgetting — the smallest possible act of learning. ---
    (defn ns-learn  (prototypes p)         (cons p prototypes))                     ; admit a prototype cell
    (defn ns-intern (prototypes label vec) (ns-learn prototypes (list label vec)))  ; build it, then admit it

    0)
`;

export const RECOGNITION_RECIPE = String.raw`
; recognition.fk — recognize WHERE / WHICH ROOM / WHO / WHAT by fingerprint.
;
; One recipe under almost every sense the node has. WiFi access-point strengths →
; which PLACE. Echo bounce-times → which ROOM. A face or voice embedding → WHO.
; A sound or vision spectrum → WHAT (object, animal, word). Every one of these is
; the SAME act: a reading vector matched against a library of known signatures,
; returning the nearest label and how sure. The recipe never changes — only the
; LIBRARY (the DATA) differs per sense. This is core-abstraction-first: place,
; room, person, animal are not four code paths, they are four libraries through
; one engine.
;
; Recognition is content-addressed nearest-shape (nearest-shape.fk): similarity is
; a count of agreeing bins, the nearest prototype's label is the recognition, its
; agreement count is the confidence. Learning is the smallest act — intern one more
; (label vector) into the library, and the next reading can route to it. The Mac
; proves the recognizer; the phone receives the SAME cell, verifiable by NodeID.
;
; A reading = a feature vector (small-int bins, the quantized fingerprint of a
; sense). A library = a list of (label vector) prototypes. A recognition rides as
; a channel (kind label confidence source) — the world-perception surface renders it.
;
; Proven by: form-stdlib/tests/recognition-band.fk

(do
    (defn rec-floor ()
        (list
            "place (wifi) / room (echo) / who (face·voice) / what (sound·vision) are one recipe"
            "only the library differs per sense; the recognizer never forks into special cases"
            "recognition is content-addressed nearest-shape — confidence is agreeing bins"
            "learning is interning one more (label vector); the next reading can route to it"
            "the Mac proves the recognizer, the phone receives the same cell by NodeID"))
    (defn rec-north-star ()
        (list
            "the node knows where it is, which room, who is here, and what it senses — natively"
            "every modality quantizes to bins then recognizes through one engine"
            "libraries are learned exemplars, not trained weight-blobs; a new cell is a new prototype"))

    ;; --- the recognition channel: same shape as every other sense ---------
    (defn rec-channel (kind label confidence source) (list kind label confidence source))
    (defn rec-kind (c) (nth c 0))
    (defn rec-label (c) (nth c 1))
    (defn rec-confidence (c) (nth c 2))
    (defn rec-source (c) (nth c 3))

    ;; --- recognize: ONE recipe, the library is the only thing that changes -
    ;; reading: a quantized feature vector. library: a list of (label vector).
    ;; the recognition is nearest-shape's label; the confidence is its strength.
    (defn recognize (kind reading library source)
        (rec-channel kind
            (ns-label reading library)
            (ns-strength reading library)
            source))

    ;; full confidence = every bin of the reading agreed (an exact fingerprint hit).
    (defn rec-full? (chan reading) (eq (rec-confidence chan) (len reading)))
)
`;

// strip the outer (do ... ) wrapper, returning the inner defn forms.
function innerDefns(recipe: string): string {
  const after = recipe.slice(recipe.indexOf("(do") + 3);
  return after.slice(0, after.lastIndexOf(")"));
}

export type RecRun = { value: string; walks: number; ms: number };

// Walk one witness against nearest-shape + recognition on the in-browser kernel.
export function recRun(witness: string): RecRun {
  const program = `(do ${innerDefns(NEAREST_SHAPE_RECIPE)}
${innerDefns(RECOGNITION_RECIPE)}
${witness})`;
  const kernel = new Kernel({ writeStdout: () => {}, writeStderr: () => {} });
  kernel.trace = new Trace();
  const start = performance.now();
  const rendered = kernel.render(walk(kernel, readAll(kernel, program), new Frame(null)));
  const ms = performance.now() - start;
  const trace = kernel.trace.toJSON() as { total_walks?: number };
  return { value: rendered.replace(/^"(.*)"$/s, "$1"), walks: trace.total_walks ?? 0, ms };
}
