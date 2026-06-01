# Runtime Shared Native Representation - 2026-06-01

This note records the common compiler/runtime surface that BML and Python BMF
now share. BML and Python are proof fixtures, not the boundary of the design.
The target is a reusable ingestion lane for any grammar: programming languages
such as TypeScript, C#, and Java, plus non-code domains such as documents,
media, and natural-language recipe surfaces.

## Shared Shape

The common runtime path is:

1. Source objects: each dialect defines typed source atoms such as keyword,
   name, operator, int, and string cells.
2. BMF rules: source atoms match through a dialect rulebook.
3. Native emitters: matched captures lower into native Form objects or AST
   nodes, with optional reverse emitters back to source objects.
4. `bmf-dialect`: the dialect packages its rulebook, native emitter manifest,
   and rule list.
5. Runtime capsule: `bmf-runtime-dialect-capsule` exposes the dialect through
   the shared recipe registry with parse and emit capabilities.
6. Native execution: executable dialect objects can lower into Form/BMA
   programs and run through the native kernels.

## Current Proof

`form/form-stdlib/tests/runtime-shared-native-representation-band.fk` proves
this path with two different language shapes:

- BML parses `return 13;` through `bml-bmf-dialect`, reverses it back to BML
  source objects, lowers the parsed object into a BMA program, and runs it to
  return `13`.
- Python parses `return 13` through `python-bmf-dialect` and reverses it back
  to Python source objects through the same runtime request/capsule path.
- Both dialect capsules live in the same registry and use the same parse/emit
  request structures.

The proof result is `30000` across the Form validation kernels.

`form/form-stdlib/tests/runtime-real-grammar-capsules-band.fk` also registers
BML in the existing multi-domain runtime capsule proof beside Python,
TypeScript, Go, Rust, natural language, image, audio, video, and document
grammars. That wider proof result is `35100`.

## Reuse Contract For New Grammars

A new grammar should implement this minimal surface:

- `*-src-*` constructors for source atoms.
- A `section [*.bmf]` rulebook with semantic emitters where native meaning is
  known.
- Reverse emitters for rules that should be source-roundtrippable.
- A `*-bmf-native-section` manifest of native emitters and output categories.
- A `*-bmf-dialect` value built with `bmf-dialect`.
- A runtime capsule proof that parses and emits through
  `bmf-runtime-dialect-capsule`.
- Native execution proof when the dialect claims executable meaning.

This is the common ground that should make TypeScript, C#, Java, and future
languages faster to ingest without rebuilding the registry, request, capsule,
or execution plumbing.
