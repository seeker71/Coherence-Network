# TypeScript Python Adapter Seedbank

This directory preserves the TypeScript Python parser, emitter, examples, and
parity scripts outside the active TypeScript kernel source tree.

The current active direction is Form-native Python support:

- source sensing produces BMF source objects;
- Form grammar rules match those objects;
- completed rules emit reversible Form/BMF objects;
- Go, Rust, and TypeScript kernels only execute Form workloads.

These files still carry useful reference material: ctor vocabulary,
Python-to-`.fk` lowering examples, and parity examples. They return to active
use only by being transformed into Form rules and shared object recipes, not by
being imported by the TypeScript kernel CLI.
