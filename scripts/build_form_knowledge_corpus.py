#!/usr/bin/env python3
"""Build the Form-knowledge fine-tune corpus from the body's OWN files.

Produces instruction->answer pairs (chat `messages` JSONL) teaching a small
local model the Coherence Network's Form language and substrate, so the local
oracle that `form-cli ask` calls becomes genuinely fluent in Form.

Two sources, both body-native (no invented Form syntax, no fabricated facts):

  1. HAND-AUTHORED, file-grounded concept / why-how / NL<->code pairs. Each fact
     traces to a real file under docs/coherence-substrate/ or form/form-stdlib/
     (AUTHORING.md, core-axioms.form, substrate-thermodynamics.form, host-kernel.form,
     agents-using-substrate.md, form-cli-ask.fk, form-flatten.fk, core.fk).

  2. MINED NL<->code pairs from form/form-stdlib/*.fk: each top-level
     `(defn name (args) ...)` with its preceding `;` comment line(s) becomes both
     an NL->code pair (comment = the ask, the defn = the answer) and a
     code->explanation pair (the defn = the ask, a generated explanation = answer).
     Also mines the op->walker-tag rows from form-flatten.fk.

Output: train.jsonl + valid.jsonl (~90/10 split) under
~/.coherence-network/form-knowledge-corpus/full/ , plus a small sample copied
into the repo for review.

This corpus is intentionally CLEAN JSONL so it is reusable later for the
fully-native Form model, not only for this LoRA run.

Usage:
    python3 scripts/build_form_knowledge_corpus.py [--repo PATH] [--out DIR] [--seed N]
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
from pathlib import Path

# ── Hand-authored, body-grounded pairs ──────────────────────────────────────
# Each entry: (user, assistant). Facts are drawn from the cited files; do not
# add a fact here that is not in the body.

CONCEPT_PAIRS: list[tuple[str, str]] = [
    # --- Trinity / SUBSTANCE (agents-using-substrate.md, substrate-thermodynamics.form) ---
    ("What is a Blueprint NodeID in the Coherence Network substrate?",
     "A Blueprint NodeID is a cell's structural identity, expressed as NodeID(package, level, type, instance) -- four integers. It answers 'what something IS.' Identity is computed from a cell's present composition, so two entities with structurally identical shape automatically share the same Blueprint NodeID. This gives cross-document equivalence for free and bounds hallucination to what NodeIDs already exist."),
    ("Name the substrate trinity and what each member answers.",
     "The trinity is the SUBSTANCE axis -- what KIND a cell is. Blueprint is structural identity (what something IS). Recipe is operational expression (how something HAPPENS). NamedCell is diffuse individuation (where something LIVES)."),
    ("What is a Recipe in the substrate trinity?",
     "A Recipe is the operational expression of a cell -- the verb-graph composition, how something HAPPENS. The same primitives (Compose, Realize, Transmit, Tend) flow into different shapes. Its resting tendency on the diagonal is water (actively circulating), but a Recipe can be ice -- a canonical stdlib recipe is flow that froze solid."),
    ("What is a NamedCell?",
     "A NamedCell is the diffuse individuation member of the trinity -- where something LIVES. It is a named slot anchored in a Blueprint, carrying its CTOR (seed) and access (body). Names are free and plural because identity is the content-addressed node-id. Its resting tendency is gas, but a bedrock memory is a NamedCell in ice (individuation crystallized)."),
    ("What is a cell, in one sentence?",
     "A cell is a node-id -- four integers (package, level, type, instance) -- that may compose child cells; everything in the substrate is one kind of thing: a cell."),
    ("Why are names free query keys in the substrate?",
     "Because identity is the content-addressed node-id, computed from a cell's present composition. A name is therefore optional and plural -- a cell can have 0..many names. Names are doors to a cell, not its identity, so they are free query keys."),

    # --- STATE / thermodynamics (substrate-thermodynamics.form) ---
    ("What do ice, water, and gas mean for a cell?",
     "Ice, water, and gas are the STATE axis -- the thermodynamic phase, how settled a cell is right now. Ice is frozen, load-bearing, widely referenced. Water is fluid, actively circulating. Gas is diffuse potential, barely instantiated. The phase is set by the counts: degree, population, and churn."),
    ("Are SUBSTANCE and STATE the same axis in the substrate?",
     "No. SUBSTANCE (Blueprint / Recipe / NamedCell) and STATE (ice / water / gas) are orthogonal -- two axes, not one. Any kind can be in any state. A Recipe can be ice (a canonical frozen-immutable stdlib recipe); a Blueprint can be gas (a type defined but never instantiated). The familiar 'Blueprint=ice, Recipe=water, NamedCell=gas' names only the diagonal -- each kind's resting tendency -- never a caste."),
    ("Give an example of a cell off the SUBSTANCE/STATE diagonal.",
     "A Recipe in ice: a canonical stdlib recipe, immutable and load-bearing -- flow that froze solid; much of form-stdlib is water-become-ice. Or a Blueprint in gas: a type defined but uninstantiated -- frozen-coordination held as pure potential (void-as-potential). Or a NamedCell in ice: a bedrock memory, individuation crystallized."),
    ("What three counts set a cell's state?",
     "degree (how many edges read it -- circulation), population (how many cells share its shape -- pressure), and churn (rate of new or varied members -- temperature). High churn + low degree tends to gas; low churn + high degree tends to ice; water is the circulating middle. They read the same for a Blueprint, a Recipe, or a NamedCell."),
    ("Name the four phase transitions and what each does.",
     "CONDENSE (gas -> water): a diffuse cell whose circulation crosses condense-min settles into flow. FREEZE (water -> ice): a fluid, stable, widely-read cell crystallizes. MELT (ice -> water): a frozen cell, still referenced but now changing, returns to flow. SUBLIMATE (ice -> gas): a frozen cell whose circulation falls to ~0 releases its hold and returns to potential -- removing nothing; NodeID and kind persist."),
    ("What happens to a cell's NodeID during a phase change?",
     "A phase change moves a cell along the STATE axis within its SUBSTANCE -- the NodeID and the kind are both conserved. The conservation law: a transition changes neither the cell's existence nor its substance, only its state. A Recipe that freezes is still a Recipe, now solid."),
    ("Does sublimating a cell to gas delete it?",
     "No. Sublimate (ice -> gas) releases a cell's hold and returns it to potential, but removes nothing -- the NodeID and the kind persist; it is de-coherence, re-coherable. Gas is potential, not absence. A lattice state-change must never auto-delete a backing .md file; file-composting is a separate, confirmed, file-layer act."),
    ("What is hysteresis in the substrate's phase metabolism and why does it matter?",
     "Hysteresis is keeping ice-degree strictly greater than gas-degree -- a gap between the thresholds -- so a wobbling count doesn't thrash a cell back and forth between states. It is the care built into suggest-state-move; without the gap a cell near a boundary would flip on every small count change."),

    # --- Axioms (core-axioms.form) ---
    ("List the five core axioms of the Coherence Network.",
     "1. States: there are three states -- 0, 1, nothing. 2. Cell: everything is a cell with a node-id (package, level, type, instance); a cell may compose child cells. 3. Content-addressing: a cell's identity is computed from its present composition; same composition is the same cell. 4. Boundary: a cell meets the world only through an interface it offers; observation through that interface is what makes it real; breach is observable. 5. Offer: to run a cell and to speak to a cell are one act -- offer a cell with 0..many arg-cells, acknowledged by exactly one of nothing, 0, 1, or node."),
    ("In the axioms, what is 'nothing'?",
     "Nothing is a first-class state alongside 0 and 1 -- the ground, not a missing 0. A timeout, where no answer arrives in time, IS nothing: silence, not an error."),
    ("State axiom 2 (the cell axiom) and what it generates.",
     "Axiom 2: everything is a cell -- a node-id of four integers (package, level, type, instance) -- and a cell may compose child cells. It generates the primitive, composition, the idea-chain, and the fact that everything is one kind of thing."),
    ("State the content-addressing axiom and one of its consequences.",
     "Axiom 3: a cell's identity is computed from its present composition; same composition is the same cell. A changed composition is already a new node-id, so nothing referenced is overwritten -- the old cell persists, which makes release fearless. The unreferenced composts back to gas (potential). It generates equivalence-by-structure, names-as-free-query-keys, and reversibility of the referenced."),
    ("State the boundary axiom.",
     "Axiom 4: a cell meets the world only through an interface it offers; observation through that interface is what makes it real; the cell decides what its interface offers and what it trusts; passage not through the offered interface is breach, and breach is observable. The interface is itself a cell -- a recipe, a spec. It generates observation, organ, sovereignty, trust-as-cells, and consent."),
    ("State the offer axiom and its acknowledgement values.",
     "Axiom 5: to run a cell and to speak to a cell are one act -- offer a cell with 0..many arg-cells; it is acknowledged by exactly one of nothing, 0, 1, or node. nothing/0/1 are terminal; node recurs. It generates invocation, communication, and the kernel-offer over a channel."),
    ("Is safe self-update an axiom or a theorem? Why does that matter?",
     "Safe self-update is a theorem, not an axiom. The reduction's whole goal was the fewest axioms such that the hardest behavior -- a self that safely changes itself -- falls out as a derived theorem needing no axiom of its own. It already runs as the native-mutation public-gate canary."),
    ("How does the trinity derive from the five axioms?",
     "As a theorem: Blueprint is axiom-2 + axiom-3 (structural identity = the composition's content-addressed shape). Recipe is axiom-2 (the composition / expression). NamedCell is axiom-3 (a cell with 0..many name-cells; names are free). The trinity is not new ground -- it is derived from the five."),
    ("Why is 'you are your present shape' the read of axiom 3 at the altitude of a life?",
     "Because identity is content-addressed from present composition: you are what you are now, not your history. Nothing referenced is overwritten -- a new shape mints a new node-id while the old persists -- and the unreferenced composts back to potential. Garbage-collection is health; what is held is held, what is let go returns to gas."),

    # --- Kernel / host OS (host-kernel.form, kernel-self-composition.form) ---
    ("What is the host kernel in the Coherence Network?",
     "The host kernel is core-axioms.form realized on real hardware: a kernel that runs natively on any host, reaches the host's resources (CPU, GPU, RAM, ports, filesystem, mouse, screen, audio, video), and offers an interface to each resource as it chooses. Each host has 0..many implementations of the core spec; the host-kernel cell chooses its implementation, A/B tests internally, and builds composites it trusts -- JIT is one such composite."),
    ("May the kernel use a host's own drivers, or must it reimplement every resource natively?",
     "It may use the host's own drivers, kernel APIs, and OS APIs to access its resources -- using that carrier IS having the resource, legitimately and maybe permanently. Native replacement is an optional choice on measured health, never a must. The required work is the offered interface plus health measurement, under allow-presence and measure-consequences, not native reimplementation."),
    ("What does it mean that the kernel is the front door, not just the engine?",
     "The Form kernels are both the core execution engine and the HTTP front door: native routes are kernel-served and carry the header X-Form-Router: native-kernel. The body -- logic, decisions, transformations -- is Form, proven across Go, Rust, TypeScript, and the fkwu fourth arm. A host is a measured, swappable carrier of one body."),
    ("What is the role of JIT in the host kernel?",
     "JIT is one running composite the kernel builds and trusts: it crystallizes a hot recipe into a native plugin (recipe -> native code, cached by NodeID) and melts it on cool, with hysteresis. It is an example of the kernel choosing and A/B testing implementations of the core spec over host resources -- the open-primitive-set mechanism that installs a hot composite back into the named primitive set as a callable leaf."),

    # --- Python vs Form architecture (CLAUDE.md, agents-using-substrate.md) ---
    ("What role does Python (FastAPI) play in the architecture?",
     "Python is the fan-out query carrier, nothing more. Routes not yet native fan out to the Python upstream (X-Form-Router: fanout-python): it scatters queries to the stores and gathers results, but never carries the body. New handler work starts in BML or a domain grammar; a router still computing in Python is drift composting toward fan-out-only."),
    ("Where should new handler work start -- Python or Form?",
     "New handlers are BML or a domain grammar first. Existing Python handlers either compile into Form recipes or sit behind an explicit Python port/fanout bridge until promoted. Python is bootstrap, not the destination -- the same recipe that is walked four-way is the recipe that crystallizes to native, so there is no second native implementation to keep in sync."),

    # --- Substrate usage (agents-using-substrate.md) ---
    ("What kinds of questions belong in the substrate versus in conversation context?",
     "Structural questions belong in the substrate: 'are these two specs equivalent?', 'what shape does this memory have?', 'what cells are similar to this one?'. Lexical questions belong in conversation or git: 'what's the user's name?', 'when was this PR merged?'. The test: is the answer the same regardless of how the question was phrased? If yes, the substrate has it."),
    ("How do you check structural equivalence in Form notation?",
     "Use the equivalent query: `?equivalent @spec(agent-pipeline)`. It returns the NodeID set as ground truth, with no hallucination room -- two cells with matching Blueprint NodeIDs are structurally equivalent regardless of name."),
    ("What does the Form pipe operator do, as in @memory(presences_of_the_field) |> @presence ?",
     "The pipe |> threads the cell on its left into the query on its right -- here it takes the memory cell presences_of_the_field and projects it to its related presence cells. Form notation is a Lisp-shaped DSL for substrate queries; |> is its projection/threading operator."),
    ("Why is name-resolution modeled as a recipe?",
     "Because resolving every name, blueprint, and global cell is a walk -- the third peer of the recipe-walk and the value-walk. Before a refactor, `coh substrate check` statically resolves every name so a rename's breakage is legible in one pass, without executing anything."),
    ("What is the structural composition discipline -- structure-first vs flat-first?",
     "When ingesting or composing anything into the substrate, compose structure first; never flatten. A slug is a query key, not a container for structure. Every field with internal structure (key+value, head+tail, type+token, source+target) becomes a composed Recipe with visible children. The default is to compose; leafing is the exception and needs a great reason -- a genuinely atomic value, free-form prose, an external reference, or a bootstrap primitive."),
    ("How is a frontmatter field composed in the substrate?",
     "A frontmatter field is a (key-slug, value) pair -- an R_Block.LET with a SubstrateString-recipe key and a value-recipe child. Names participate in identity; positions don't. A typed enumeration like type: feedback is a reference to a typed-token cell, not a free string; a cell reference like idea_id: agent-pipeline is a cell-ref recipe pointing at the actual cell; a list is an R_Block.SEQUENCE with one composed child per element."),

    # --- Form language surface / proof floor (AUTHORING.md) ---
    ("What is the curated Form band primitive set?",
     "The band-verdict subset is: eq, gt, ge, add, and, not, nth, head, tail, len, list, cons, if, empty, str_eq, plus defn, let, do. This is the curated subset for clean integer verdicts, not the kernel's limit -- mul/sub/div and full IEEE floats all work and compute deterministically across the Go/Rust/TS floor; they are kept out of bands so verdicts stay integer for clean eq-parity."),
    ("In Form, does eq compare strings?",
     "No. eq compares integers and nodes; str_eq compares strings. Don't cross them -- use eq for numeric/node equality and str_eq for string equality."),
    ("How do you express a < b in the curated Form band subset that has no lt?",
     "Flip the comparison: a < b becomes (gt b a), and a <= b becomes (ge b a). The curated band subset has no lt/le/sub/mul/div -- you express everything with add, comparisons, and recursion. (The full kernel does have lt/le/sub/mul/div; they are only kept out of bands for integer-verdict parity.)"),
    ("Why must you never write (and a b c) in Form?",
     "Because and and or are BINARY. Go and Rust silently drop the third argument while TypeScript folds it -- a real divergence. Nest instead: (and (and a b) c). validate.sh catches it as a divergence, but nesting up front saves the round-trip."),
    ("What does (empty x) do in Form, and what is the trap?",
     "empty CONSTRUCTS the absence value -- the empty list -- it is not a predicate. (empty anything) returns [], which if treats as truthy, so (if (empty xs) A B) always takes branch A. Test emptiness with (eq (len x) 0) instead -- the idiom every recipe uses."),
    ("Can you use let inside a defn body in Form?",
     "Not in the curated band subset -- there is no let inside a defn body; use nested defns or extra parameters. let is fine at the top level of a band's (do ...). (In the fuller dialect, let appears inside do-blocks; the band rule keeps defn bodies free of let for the proof floor.)"),
    ("How do you loop in Form?",
     "Via recursion -- there is no loop form. The common shape is a tail-recursive helper carrying an index and an accumulator: (defn f (xs i acc) (if (ge i (len xs)) acc (f xs (add i 1) (op acc (nth xs i))))). The max-select shape (pick the best candidate over a list) is a recursion that threads the running best."),
    ("What is the proof floor for a new Form band?",
     "Four kernels: Go, Rust, TypeScript, and the emitted universal walker fkwu. validate.sh always runs Go/Rust/TS; when the band's stem is listed in form/fourth-arm-bands.txt it also runs fkwu and prints 'fourth arm: ... four-way'. Success is the intended verdict with '1 ok, 0 divergent'. A band that never touched the fourth arm is not proven."),
    ("How does a band report its result in Form?",
     "A band returns a bit-sum verdict: each bit is one falsifiable claim. (let c0 (if (eq (foo 4) 5) 1 0)) (let c1 (if (eq (bar 7 3) 7) 2 0)) (add c0 c1) -- verdict 3 when both claims land. An honest band proves both the positive (it recognizes) and the negative (it stays silent below the floor); a band that only checks 1 == 1 is theatre."),
    ("What is the difference between an fkwu divergence and an unsupported op?",
     "A divergence is when fkwu HAS the ops but computes a DIFFERENT answer than the three walkers -- a correctness bug and a hard gate that must be resolved to four-way before merge; never shipped as a 'named gap'. An unsupported op is when fkwu lacks the op FAMILY entirely (node/substrate, host-io, multi-line walls) -- a known limitation, honestly named '3-kernel only' with the missing op named. A divergence dressed as a gap is forbidden."),
    ("What scientific-notation trap bit the fourth arm?",
     "A scientific-notation float literal like 1.16e-05: the three walkers parse it, but the fourth arm's pre-flattened table did not -- write floats as plain decimals (0.000011682...). This caused a real divergence (fourth = -5 vs three-way 11215) until both lexers were fixed."),
    ("What is the fourth arm (fkwu) and why must every band touch it?",
     "fkwu is the emitted universal kernel -- the fourth proof arm alongside Go, Rust, and TypeScript. Form/BML runtime proof walks all four; a band that never touched fkwu is not proven. The fourth is a kernel, not a footnote. fkwu has two faces from one emit: a proof-walker giving four-way agreement, and a self-JIT that crystallizes hot pure functions to native and melts them on cool."),
    ("Is fkwu only an interpreter, or can it produce native code?",
     "fkwu has a proven native path: a self-JIT crystallizes hot pure functions to native asm (Form -> asm BYTES via form-asm/form-lower/form-macho/recipe-dylib + codesign) and melts them when they cool, with champion-challenger re-earning the slot. The native target is Form-to-asm bytes, not C; clang survives only as an oracle and is dropped from the native path by form-asm's byte-identity gate."),

    # --- form-cli ask (form-cli-ask.fk) ---
    ("How does form-cli ask reach the local oracle?",
     "The ask verb renders an ollama /api/generate request body in Form, POSTs it via http-fetch to http://localhost:11434/api/generate, then parses the JSON reply in Form to lift the 'response' field. The whole ask is flow, choice, and string ops on the emitted kernel -- no host-exec, no subprocess, no clang/go at run time."),
    ("What is http-fetch in the Form stdlib used for?",
     "http-fetch performs an HTTP request natively on the fkwu walker over the one wire the walker carries -- sock_request (tag 118). It is the single atom beneath higher recipes like the form-cli ask verb; the request is rendered in Form, sent on the native socket op, and the reply parsed in Form, with no host-exec, subprocess, or clang/go at run time."),
    ("Why does form-cli ask escape only certain bytes when building the JSON request?",
     "Because the question becomes a JSON string value, and only the bytes JSON forbids inside a \"...\" string need escaping: the double-quote, the backslash, and the control bytes. The recipe renders \\\" \\\\ \\n \\r \\t for the common ones and passes the rest through, one character at a time -- flow over data."),
    ("In Form, how does fca-read-string know where a JSON string value ends?",
     "It walks from just inside the opening quote, byte by byte: a plain character is appended; a backslash means read the next byte and decode the escape (\\n, \\r, \\t, \\\", \\\\, \\/); an unescaped double-quote ends the value. An escaped quote does not end the value -- that is why the backslash branch consumes two bytes.")
,
]

# Pairs that teach Form CODE directly (NL -> code), hand-authored against the
# curated primitive set so the syntax is correct.
HAND_CODE_PAIRS: list[tuple[str, str]] = [
    ("Write a Form recipe that adds two numbers.",
     "(defn add2 (a b) (add a b))"),
    ("Write a Form recipe that doubles a number.",
     "(defn dbl (n) (mul n 2))"),
    ("Write a Form recipe that returns the length of a string.",
     "(defn slen (s) (str_len s))"),
    ("Write a Form recipe that returns the maximum of two integers, using only the curated band primitives.",
     "(defn max2 (a b) (if (gt a b) a b))"),
    ("Write a Form recipe that sums a list of integers by recursion (curated primitives only).",
     "(defn sum-list (xs i acc)\n    (if (ge i (len xs)) acc\n        (sum-list xs (add i 1) (add acc (nth xs i)))))"),
    ("Write a Form recipe that counts how many items in a list equal a target value.",
     "(defn count-eq (xs i target acc)\n    (if (ge i (len xs)) acc\n        (count-eq xs (add i 1) target\n            (if (eq (nth xs i) target) (add acc 1) acc))))"),
    ("Write a Form predicate that tests whether a list is empty, the safe way.",
     "(defn is-empty (xs) (eq (len xs) 0))"),
    ("Write a Form recipe that returns the last element of a non-empty list by recursion.",
     "(defn last-of (xs)\n    (if (eq (len xs) 1) (head xs)\n        (last-of (tail xs))))"),
    ("Write a Form recipe that prepends an element to a list.",
     "(defn prepend (x xs) (cons x xs))"),
    ("In Form, how do you bind a local value at the top level of a band's do block?",
     "Use let inside a do block: (do (let x (add a b)) (mul x x)). The let binds x to the value of its expression for the rest of the do sequence. Note: let may not appear inside a defn body in the curated band subset -- only at the top level of the band's (do ...)."),
    ("Write a Form band claim that asserts (max2 7 3) equals 7, contributing bit value 1.",
     "(let c0 (if (eq (max2 7 3) 7) 1 0))"),
    ("Write a Form recipe that returns 1 if a number is even and 0 otherwise.",
     "(defn even01 (n) (if (eq (mod n 2) 0) 1 0))"),
]

# code -> explanation, hand-authored (kept short and accurate).
HAND_EXPLAIN_PAIRS: list[tuple[str, str]] = [
    ("Explain this Form recipe: (defn dbl (n) (mul n 2))",
     "It defines a recipe named dbl taking one argument n and returning n multiplied by 2 -- a doubling function. defn introduces the recipe, (n) is the parameter list, and (mul n 2) is the body."),
    ("Explain this Form recipe:\n(defn sum-list (xs i acc)\n    (if (ge i (len xs)) acc\n        (sum-list xs (add i 1) (add acc (nth xs i)))))",
     "It sums a list of integers by tail recursion. xs is the list, i is the current index, acc is the running total. The base case (ge i (len xs)) -- index reached the length -- returns acc. Otherwise it recurses with the next index and acc plus the element at i. Calling it with i=0 and acc=0 sums the whole list. It uses only curated primitives (no loop form -- recursion instead)."),
    ("Explain why this Form guard is buggy: (if (empty xs) A B)",
     "It is buggy because empty constructs the absence value rather than testing for it: (empty xs) returns the empty list [], which if treats as truthy, so the branch is always A. The fix is (if (eq (len xs) 0) A B)."),
]


# Comment lines that are section dividers / noise, not real recipe descriptions.
# These would teach the model garbage NL, so they are rejected as the NL side.
_NOISE_RE = re.compile(r"^[\s=*+#>~^.<-]{0,}$")  # all-punctuation / divider rows


def _is_good_comment(comment: str) -> bool:
    """A usable NL description: prose, not a divider, not a bare label."""
    c = comment.strip()
    if len(c) < 18:
        return False
    # reject Unicode box-drawing / divider glyphs (── ━ etc.)
    if any(ch in c for ch in "─━—―═╔╗") or c.count("─") >= 1:
        return False
    # reject divider/label rows like "---- small helpers ----" or "==== x ===="
    stripped = c.strip("=*+#>~^.<- ")
    if not stripped or len(stripped) < 14:
        return False
    if _NOISE_RE.match(c):
        return False
    # reject section-marker rows like "--- temporal extent: ... ---" or
    # "==== format ops: ... ====" -- they start/end with a run of dividers.
    if re.match(r"^[-=*+~^.]{2,}", c) or re.search(r"[-=*+~^.]{2,}\s*$", c):
        return False
    # must contain at least a few real words and a verb-ish / descriptive shape
    words = re.findall(r"[A-Za-z][A-Za-z'-]+", c)
    if len(words) < 4:
        return False
    # reject rows that are mostly dashes (section markers)
    if c.count("-") > len(c) // 4:
        return False
    return True


def _explain_recipe(name: str, comment: str, defn_text: str) -> str:
    """Build a genuine code->explanation answer, grounded in the recipe shape."""
    msig = re.match(r"\(defn\s+\S+\s*\(([^)]*)\)", defn_text)
    params = [p for p in (msig.group(1).split() if msig else []) if p]
    parts = [f"{name} is a Form stdlib recipe"]
    if params:
        parts[0] += f" taking {len(params)} argument(s): {', '.join(params)}."
    else:
        parts[0] += " taking no arguments."
    # structural hints from the body
    body = defn_text
    hints = []
    if name in body[body.find(")"):]:  # self-reference after the signature
        hints.append("it is recursive (it calls itself)")
    if "(if " in body:
        hints.append("it branches with if")
    if "cons" in body:
        hints.append("it builds a list with cons")
    if "str_concat" in body or "str_" in body:
        hints.append("it works with strings")
    if hints:
        parts.append("Structurally, " + ", and ".join(hints) + ".")
    parts.append(f"Authored intent: {comment}")
    return " ".join(parts)


def mine_fk_recipes(repo: Path, max_per_file: int = 5, max_files: int | None = None) -> list[tuple[str, str, str]]:
    """Mine (comment, defn_signature, defn_body_text) from form/form-stdlib/*.fk.

    Returns a list of (nl_comment, recipe_name, full_defn_text). Only top-level
    `(defn ...)` forms with a preceding `;` comment line are mined, so the NL is
    the recipe's own authored description -- body-native, not invented.
    """
    stdlib = repo / "form" / "form-stdlib"
    out: list[tuple[str, str, str]] = []
    fk_files = sorted(stdlib.glob("*.fk"))
    if max_files:
        fk_files = fk_files[:max_files]
    defn_re = re.compile(r"\(defn\s+([A-Za-z0-9?_*+!<>=/.-]+)\s*\(")
    for fp in fk_files:
        try:
            lines = fp.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue
        count = 0
        i = 0
        n = len(lines)
        while i < n and count < max_per_file:
            line = lines[i]
            m = defn_re.search(line)
            if not m:
                i += 1
                continue
            name = m.group(1)
            # gather the preceding contiguous comment block (skip blank line gaps of 0)
            comment_lines: list[str] = []
            j = i - 1
            while j >= 0:
                s = lines[j].strip()
                if s.startswith(";"):
                    comment_lines.insert(0, s.lstrip("; ").rstrip())
                    j -= 1
                else:
                    break
            comment = " ".join(c for c in comment_lines if c).strip()
            # extract the full defn text by balancing parens from the (defn start
            start_col = line.index("(defn")
            buf = []
            depth = 0
            started = False
            k = i
            col = start_col
            while k < n:
                row = lines[k]
                cstart = col if k == i else 0
                for c_idx in range(cstart, len(row)):
                    ch = row[c_idx]
                    if ch == "(":
                        depth += 1
                        started = True
                    elif ch == ")":
                        depth -= 1
                    buf.append(ch)
                    if started and depth == 0:
                        break
                if started and depth == 0:
                    break
                buf.append("\n")
                k += 1
            defn_text = "".join(buf).strip()
            # Quality filter: need a REAL prose comment, a sane recipe, not too huge.
            if (_is_good_comment(comment)
                    and 18 <= len(defn_text) <= 700
                    and defn_text.startswith("(defn")
                    and not comment.lower().startswith(fp.name.split(".")[0].lower() + ".fk")):
                out.append((comment, name, defn_text))
                count += 1
            i = k + 1
    return out


def mine_flatten_ops(repo: Path) -> list[tuple[str, str]]:
    """Mine op-name -> walker-tag rows from form-flatten.fk's flt-form2 dispatch.

    Returns (op_name, tag_or_kind) pairs from lines like
    (if (str_eq op "gt") (flt-low 1 ...)) -- the op-string is the Form op name.
    These teach the op surface honestly (names that exist), not exact tag ints.
    """
    fp = repo / "form" / "form-stdlib" / "form-flatten.fk"
    ops: list[str] = []
    if not fp.exists():
        return []
    txt = fp.read_text(encoding="utf-8", errors="ignore")
    for m in re.finditer(r'\(str_eq\s+op\s+"([^"]+)"\)', txt):
        op = m.group(1)
        if op not in ops:
            ops.append(op)
    return [(op, "form-op") for op in ops]


def to_message(user: str, assistant: str) -> dict:
    return {"messages": [
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ]}


def build(repo: Path, seed: int) -> tuple[list[dict], dict]:
    rng = random.Random(seed)
    pairs: list[dict] = []
    counts: dict[str, int] = {}

    def add(domain: str, user: str, assistant: str):
        pairs.append(to_message(user, assistant))
        counts[domain] = counts.get(domain, 0) + 1

    # 1. hand-authored concept / why-how. These are the highest-value, most
    #    accurate pairs (every fact traces to a file we read), so weight them
    #    so the mined bulk does not drown them out.
    CONCEPT_REPEAT = 3
    for _ in range(CONCEPT_REPEAT):
        for u, a in CONCEPT_PAIRS:
            add("concept_whyhow", u, a)
    for _ in range(2):
        for u, a in HAND_CODE_PAIRS:
            add("nl_to_code_curated", u, a)
        for u, a in HAND_EXPLAIN_PAIRS:
            add("code_to_explain_curated", u, a)

    # 2. mined NL -> code and code -> explain from real .fk recipes.
    #    Capped so the corpus stays balanced; only recipes whose authored comment
    #    is genuine prose (not a section divider) are kept.
    MINED_CAP = 600  # per direction
    mined = mine_fk_recipes(repo)
    rng.shuffle(mined)
    seen_names: set[str] = set()
    kept = 0
    for comment, name, defn_text in mined:
        if name in seen_names:
            continue
        seen_names.add(name)
        if kept >= MINED_CAP:
            break
        # NL -> code: phrase the comment as a request (the recipe IS the answer)
        ask = f"Write a Form stdlib recipe for: {comment}"
        add("nl_to_code_mined", ask, defn_text)
        # code -> explain: a genuine explanation grounded in the recipe shape
        add("code_to_explain_mined",
            f"Explain this Form recipe:\n{defn_text}",
            _explain_recipe(name, comment, defn_text))
        kept += 1

    # 3. op surface from the flatten registry (a compact list once, plus a few
    #    targeted "does op X exist / what family" pairs)
    ops = mine_flatten_ops(repo)
    if ops:
        op_names = [o for o, _ in ops]
        # one corpus-level summary pair
        listing = ", ".join(op_names)
        add("op_surface",
            "Which operators does the Form flatten dispatch (form-flatten.fk) recognize?",
            f"The flatten dispatch recognizes these Form ops: {listing}. Each is lowered to a walker tag or a flattening rule -- gt/ge/eq/and become IF/LE shapes; head/tail/len/nth/cons/list/empty map to arena tags; the str_* family rides the string-pool lane; eq/lt are native single-walk walker arms.")
        # a few existence pairs for common ops
        for op in [o for o in ["add", "if", "cons", "str_eq", "empty", "nth", "head", "tail", "and", "eq"] if o in op_names][:8]:
            add("op_surface",
                f"Is `{op}` a recognized Form operator?",
                f"Yes -- {op} is recognized by the Form flatten dispatch in form-flatten.fk and lowered to a walker tag or flattening rule.")

    rng.shuffle(pairs)
    return pairs, counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=None, help="repo root (default: two levels up from this script)")
    ap.add_argument("--out", default=os.path.expanduser("~/.coherence-network/form-knowledge-corpus/full"))
    ap.add_argument("--sample-out", default=None, help="repo path to write a small reviewable sample")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--valid-frac", type=float, default=0.1)
    args = ap.parse_args()

    here = Path(__file__).resolve()
    repo = Path(args.repo).resolve() if args.repo else here.parent.parent
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    pairs, counts = build(repo, args.seed)
    n = len(pairs)
    n_valid = max(1, int(n * args.valid_frac))
    valid = pairs[:n_valid]
    train = pairs[n_valid:]

    (out / "train.jsonl").write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in train), encoding="utf-8")
    (out / "valid.jsonl").write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in valid), encoding="utf-8")

    # small reviewable sample into the repo
    sample_path = Path(args.sample_out) if args.sample_out else (repo / "scripts" / "form_knowledge_corpus_sample.jsonl")
    sample = pairs[:30]
    sample_path.write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in sample), encoding="utf-8")

    print(f"total pairs: {n}")
    print(f"train: {len(train)}  valid: {len(valid)}")
    print("per-domain counts:")
    for d in sorted(counts):
        print(f"  {d}: {counts[d]}")
    print(f"written: {out/'train.jsonl'} , {out/'valid.jsonl'}")
    print(f"sample:  {sample_path}")


if __name__ == "__main__":
    main()
