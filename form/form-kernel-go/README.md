# form-kernel-go

Vertical-slice Go host for Form-on-top. Executes Form recipe trees and binary artifacts. Carries the substrate (content-addressed intern), the walker (22 RBasic arms), frames + closures, native primitives (strings, lists, file I/O), and the Form binary artifact loader.

```bash
go run main.go ../form-samples/fact.fk        # → 3628800
go run main.go --expr "(add 2 (mul 3 4))"     # → 14
go run main.go --bench                         # benchmark suite
```

Sibling: [`../form-kernel-rust/`](../form-kernel-rust/). Comparison + runtime numbers: [`../kernel-comparison.md`](../kernel-comparison.md).

Source upstream:
- Floor scope named in [`docs/coherence-substrate/form-runtime-in-form.form`](../../docs/coherence-substrate/form-runtime-in-form.form).
- Category numbering aligned with [`api/app/services/substrate/category.py`](../../api/app/services/substrate/category.py).
- Sample `.fk` source files in [`../form-samples/`](../form-samples/).
