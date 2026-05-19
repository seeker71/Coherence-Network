# Kernel Conformance

Kernel conformance vectors describe Form-visible behavior that every substrate kernel must match. They are not implementation claims. A kernel is only `implemented` when the vector names an executable runner and proof file.

`agent-question-effects.json` covers the host-bound question effects:

```bash
python3 scripts/verify_kernel_conformance.py --kernel python
python3 scripts/verify_kernel_conformance.py --kernel rust
python3 scripts/verify_kernel_conformance.py --kernel go
```

`form-core-builtins.json` covers pure built-ins over literals and lists:

```bash
python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-core-builtins.json --kernel python
python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-core-builtins.json --kernel rust
python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-core-builtins.json --kernel go
```

`form-infix-operators.json` covers arithmetic, comparison, boolean, unary, and parenthesized infix expressions over literals:

```bash
python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-infix-operators.json --kernel python
python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-infix-operators.json --kernel rust
python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-infix-operators.json --kernel go
```

`form-control-flow.json` covers deterministic `if`, `do`, and `let` behavior over literals, local names, and existing expression/built-in slices:

```bash
python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-control-flow.json --kernel python
python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-control-flow.json --kernel rust
python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-control-flow.json --kernel go
```

`form-loop-mutation.json` covers deterministic `for`, `while`, and `set` behavior over local JSON-safe values:

```bash
python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-loop-mutation.json --kernel python
python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-loop-mutation.json --kernel rust
python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-loop-mutation.json --kernel go
```

Python, Rust, and Go all run these vectors today. The Rust and Go runners are deliberately narrow conformance kernels, not full Form runtimes: they parse the forms used by the vectors, return the same JSON-safe values, emit the same question transcript for host effects, and let the Python harness compare actual values/events against the shared contract.

Future kernels become `implemented` only when their vector entry names an executable runner and proof file. Target-only kernels remain explicit: without `--allow-targets`, the harness fails so CI cannot mistake a named target for shipped behavior.
