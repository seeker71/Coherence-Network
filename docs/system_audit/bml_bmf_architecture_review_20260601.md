# BML/BMF Architecture Review - 2026-06-01

## Direct Answers

### Did non-primitive BMF/BML code enter the kernels?

Previously yes. The kernels now contain one generic source-scanning surface and
no BMF-named rule matcher:

- `source_scan_file` in Go, Rust, and TypeScript is generic scanner plumbing
  driven by a Form-owned lexicon. BML keyword/property/operator tables now live
  in `form/form-stdlib/grammars/bml.fk`.
- The former BMF rule matcher native has been removed from Go, Rust, and
  TypeScript. BMF object rules execute through `engine.fk` and shared
  compiler/runtime forms.

The current large-body retention slice did not add new non-primitive BMF code
to the kernels. It removed a BML grammar shortcut and fixed `form/validate.sh`
so the TypeScript runner fallback receives the same stack budget as the
prepared `node_modules` path.

The clean architecture should not grow BML or BMF semantics in host kernels.
The kernel boundary should stay at universal primitives: data,
records, lists, binary recipe load/write, source bytes/text access, and generic
cursor/step mechanics. Language grammars, parse rules, source objects, emitters,
and reversibility belong in BML/Form source.

## Code Review Findings

### 1. BMF semantics were duplicated in host kernels

The retired BMF native mirrored `engine.fk` rule matching in host code:

- Canonical Form path: `form/form-stdlib/engine.fk:1837`

That was the wrong long-term shape. It created four meanings for BMF:

- one in `engine.fk`
- one in Go
- one in Rust
- one in TypeScript

It already drifted: Go supported `capture`, `choice`, `star`, and `opt`, while
Rust and TypeScript only implemented the flat object-sequence POC. That made
the sibling kernels less like independent witnesses and more like competing
implementations.

Current boundary: the host-native BMF matcher is removed and the audit forbids
re-registering it. If speed is needed, compile the BMF rule graph into a generic
Form-native automaton/bytecode and let kernels execute universal VM steps. The
BMF rules still live in BML/Form source.

### 2. BML scanning is language-specific host code

The former `bml_scan_file` was replaced by `source_scan_file(path, lexicon)`.
This was a pragmatic fix for source-size and stack pressure without embedding
BML keyword/property/operator tables in each host.

Direction: keep the scanner generic and move toward a compiled scanner recipe
whose lexicon is declared in `.bml`.

### 3. Sequential work is encoded as recursion

The repeated stack problem comes from using recursive functions where the
operation is conceptually a cursor loop.

Examples:

- BML method body retention walks every body token recursively:
  `form/form-stdlib/grammars/bml.fk:2119`
- Executable/declaration stream parsing recurses over source objects:
  `form/form-stdlib/grammars/bml.fk:2623` and `:2669`
- BMF object matching recurses through sequence/choice/star:
  `form/form-stdlib/engine.fk:1870`, `:1887`, and `:1911`
- The source compiler still has many recursive string/list loops, even after
  the major recipe-sidecar improvement:
  `form/form-stdlib/source-compiler.fk:492`, `:757`

This is not a thesis-language limitation. It is a representation issue.
Balanced body collection, stream matching, rule scanning, and emitter walks are
state machines. They should be represented as explicit `state -> state` steps
over a cursor.

Direction: add and use a Form/BML-level sequential cursor abstraction:

- `source-cursor`: path/text, index, line, column
- `token-cursor`: token list or token stream plus index
- `parse-state`: cursor, stack, captures, mode, committed/cut flag
- `emit-state`: output recipe/list builder, source map, diagnostics
- `step`: a pure transition returning the next state
- `run-until`: an iterative runner or compiled loop target

### 4. BML grammar and emitter coverage still mix manifest and semantics

`bml.fk` carries BMF/native-section declarations and a recipe section:

- `form/form-stdlib/grammars/bml.fk:2736`
- `form/form-stdlib/grammars/bml.fk:2744`

Only a focused set of BML rules has semantic emitters into BMA/native program
ops. The rest is recorded as grammar surface or source components. That is
honest, but it means “BML in BML” should become the next architecture boundary:
the BML language definition should be a BML source artifact with sections for
lexicon, grammar, AST/model, lowering, reverse emitters, and proofs.

Direction: stop adding ad hoc `bml-source-*` direct parsers as the primary path.
Use them only as migration scaffolding while moving the language definition into
`.bml` sections compiled by the shared source compiler.

## Clean Target Architecture

### Layer 0: Kernel

Kernel code should be language-neutral.

Allowed kernel surfaces:

- value primitives: ints, strings, bools, lists, records
- record/method dispatch primitives
- recipe intern/load/write primitives
- source IO primitives: read text/bytes by path
- generic cursor/automaton runners
- generic binary Form execution

Disallowed long-term kernel surfaces:

- BML keyword tables
- BMF pattern semantics
- language-specific scanner/parser/emitter code
- special cases for Python, TypeScript, C#, Java, or BML grammar meanings

### Layer 1: Universal Source Runtime

This layer is written in Form/BML and reused by every language ingest path.

It should provide:

- lexical table model
- source cursor and token cursor
- iterative balanced-region collection
- parser state machine protocol
- capture/source-span model
- reversible object cells
- diagnostics and source maps

### Layer 2: BMF Rule Runtime

BMF should be defined as objects and executed by a sequential machine:

- compile BMF patterns into a rule graph or bytecode
- execute rule graph with explicit parse state
- represent `cut`, `fail`, `choice`, `star`, `opt`, captures, and spans as
  state transitions
- provide a reverse emitter path from the same rule object

This keeps BMF semantics out of host kernels.

### Layer 3: BML Language Definition In BML

BML should define itself through sections:

- `section [bml.lexicon]`: keywords, properties, operators, literal rules
- `section [bml.bmf]`: grammar rules
- `section [bml.model]`: classes/sections/interfaces/AST object model
- `section [bml.lowering]`: BML AST/component to BMA/Form-native recipes
- `section [bml.reverse]`: BMF reverse emitters and source reconstruction
- `section [bml.proof]`: executable proof declarations

The existing `form/form-stdlib/grammars/bml.fk` becomes a bootstrap loader and
compatibility shell, not the permanent home of the language.

### Layer 4: Language Adapters

Python, TypeScript, C#, Java, and other languages should plug into the same
model:

- lexicon
- grammar
- source object model
- lowering to Form-native representation
- reverse/source-map proof

No new language should require host-kernel code. If it does, the missing piece
belongs in the universal source runtime, not in the language adapter.

## Engineering Path

### Phase 1: Freeze and prove the boundary

1. Keep the generic scanner boundary explicit.
2. Add an audit gate that lists every native name beginning with `bml_` or
   `bmf_`.
3. Fail if BMF/BML semantic natives re-enter the kernels.
4. Require every new BML/BMF feature proof to run without adding host-kernel
   BML/BMF semantics.

Exit proof:

- native inventory test passes with no BML/BMF semantic natives
- current BML thesis proof band still passes
- no new `bml_` or `bmf_` native appears without an architecture note

### Phase 2: Build the sequential source runtime

1. Add cursor/state objects in Form/BML.
2. Rewrite balanced brace/paren collection as sequential state transitions.
3. Move BML body retention to cursor spans instead of recursive token-list
   collection.
4. Preserve current body-source proof: `BMF-grammar.bml` still retains all
   formerly skipped helper bodies.

Exit proof:

- the large BMF body proof passes without relying on a larger TypeScript host
  stack
- source spans prove exact body start/end and reversible token values

### Phase 3: Replace host BMF matcher with a Form/BML compiled automaton

1. Compile BMF rules to a Form-native rule graph/bytecode.
2. Run the graph with explicit parse state.
3. Port `sequence`, `object`, `capture`, `choice`, `star`, `opt`, `cut`, and
   `stop`.
4. Make the Go/Rust/TypeScript kernels execute only generic VM steps.
5. Keep BMF execution in Form/runtime code and generic compiled steps only.

Exit proof:

- interpreted `engine.fk`, compiled BMF automaton, and binary artifact execution
  produce the same captures/rest/result/source-span
- Go/Rust/TypeScript agree
- no BMF/BML semantic native is needed by BML thesis proofs

### Phase 4: Move BML grammar definition into `.bml`

1. Create `form/form-stdlib/grammars/bml-language.bml`.
2. Define BML lexicon, BMF grammar rules, model classes, emitters, reverse
   emitters, and proof sections in that file.
3. Teach the source compiler to compile this `.bml` language file into the same
   runtime structures currently built in `bml.fk`.
4. Keep `bml.fk` as the bootstrap bridge until the `.bml` artifact proves
   equivalence.

Exit proof:

- `.bml` language definition compiles into BMF rules and native recipe sections
- rule counts match the existing BML manifest
- reverse emitters reconstruct the supported source slices

### Phase 5: Full thesis companion parity

1. Use the `.bml` BML definition to compile the companion corpus:
   `BMF-grammar.bml`, `container-Rule.bml`, `primitive-Cut.bml`,
   `BMF-includes.bml`, and an application sample.
2. Lower classes, sections, methods, properties, exceptions, expressions,
   statements, backtracking primitives, and dispatch into Form-native
   representation.
3. Execute source-originated programs forward and backward.
4. Prove reversible source reconstruction where BMF rules declare reverse
   emitters.

Exit proof:

- companion corpus compiles from `.bml` source through BML/BMF into Form-native
  representation
- source-originated methods execute in native kernels
- forward and backward execution traces restore state
- binary artifacts execute identically across Go/Rust/TypeScript
- production deploy verifies the merged commit

## Immediate Next Slice

The next implementation slice should not add kernel BMF behavior. It should
start Phase 1 and Phase 2 together:

1. Add the native inventory proof for `bml_`/`bmf_` host surfaces.
2. Introduce BML/Form source cursor and token cursor objects.
3. Replace `bml-source-collect-balanced-brace-loop` with a sequential cursor
   collector.
4. Keep the large `BMF-grammar.bml` body proof green.
5. Add a proof that the collector handles the full `Compile` and `HandleArgs`
   body spans without needing signature-only skips.

What loosened: the current blocker is not semantic impossibility; it is a
runtime shape problem. What stayed tight: the kernel still carries BMF/BML
knowledge that should be migrated upward into BML/Form source.
