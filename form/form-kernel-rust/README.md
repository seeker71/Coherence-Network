# form-kernel-rust

Vertical-slice Rust host for Form-on-top. Executes Form recipe trees and binary artifacts. Carries the substrate (content-addressed intern), the walker (22 RBasic arms), frames + closures, native primitives (strings, lists, file I/O), and the Form binary artifact loader.

```bash
cargo run --release --quiet -- ../form-samples/fact.fk          # → 3628800
cargo run --release --quiet -- --expr "(add 2 (mul 3 4))"       # → 14
cargo run --release --quiet -- --bench                          # benchmark suite
```

Sibling: [`../form-kernel-go/`](../form-kernel-go/). Comparison + runtime numbers: [`../kernel-comparison.md`](../kernel-comparison.md).

Source upstream:
- Floor scope named in [`docs/coherence-substrate/form-runtime-in-form.form`](../../docs/coherence-substrate/form-runtime-in-form.form).
- Category numbering aligned with [`api/app/services/substrate/category.py`](../../api/app/services/substrate/category.py).
- Sample `.fk` source files in [`../form-samples/`](../form-samples/).
