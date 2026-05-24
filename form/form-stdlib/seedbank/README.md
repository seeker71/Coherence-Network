# Form Stdlib Seedbank

This directory preserves useful Form work that is not part of the current
default sibling-kernel surface.

The active surface is the one exercised by `../tests/*.fk` through
`../../validate.sh`. A file moves out of this seedbank only when
it has a paired proof across Go, Rust, and TypeScript and fits the current
object-BMF direction.

## Purpose Groups

- `grammar-bnf.fk`, `grammars/*.bnf.fk`, and related tests carry the compact
  grammar-authoring idea. Their next living form is not a pre-scanned stream;
  it is BMF rule objects and character/source sensing that can undo itself.
- `parser.fk` and `tests/parser.fk` carry the Form self-reader direction. Their
  next living form should read source through reversible cells or BMF objects.
- `cell-stream.fk`, `cell-trace.fk`, `tracer.fk`, and related tests carry source
  provenance, observation, and explainability. Their next living form should
  merge with `core.fk` cells and `engine.fk` BMF object undo.
- `emit.fk`, `emits/*`, translator tests, and language surface grammars carry
  multi-target rendering and roundtrip intent. Their next living form should
  consume Form objects produced by BMF rules, not host-language adapters.
- markdown, JSON, YAML, PNG, and conversion surfaces carry sensing/transcoding
  intent. Their next living form should be object-first, with focused paired
  proofs before returning to the default sweep.

Nothing here is abandoned. Nothing here is counted as active proof.
