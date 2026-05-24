# Form Runtime

This is the stable entrypoint for the Form runtime work.

The active runtime lives here. New references should point here, and runnable
commands should use this address directly.

## Contents

- `form-kernel-go/` - Go sibling kernel.
- `form-kernel-rust/` - Rust sibling kernel.
- `form-kernel-ts/` - TypeScript sibling kernel.
- `form-stdlib/` - Form stdlib, BMF engine, source compiler, language/media/natural-language grammars, and tests.
- `form-samples/` - small runnable Form workloads.
- `validate.sh` - sibling-kernel source and binary parity runner.
- `kernel-roadmap.md` and `kernel-comparison.md` - current runtime roadmap and
  performance notes.

## Proof

```sh
cd form
./validate.sh form-stdlib/core.fk form-stdlib/engine.fk form-stdlib/source-compiler.fk form-stdlib/tests/form-action-bmf-rulebook.fk
./validate.sh --binary form-stdlib/core.fk form-stdlib/engine.fk form-stdlib/source-compiler.fk form-stdlib/tests/form-action-bmf-rulebook.fk
```

The kernel stays small: source sections, BMF rules, dialect migration,
reverse emission, module bundling, locale/context lenses, and language/media
support live above it in Form runtime modules.
