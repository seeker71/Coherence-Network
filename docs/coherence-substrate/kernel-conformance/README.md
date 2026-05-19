# Kernel Conformance

Kernel conformance vectors describe Form-visible behavior that every substrate kernel must match. They are not implementation claims. A kernel is only `implemented` when the vector names an executable runner and proof file.

`agent-question-effects.json` covers the host-bound question effects:

```bash
python3 scripts/verify_kernel_conformance.py --kernel python
python3 scripts/verify_kernel_conformance.py --kernel rust
python3 scripts/verify_kernel_conformance.py --kernel go
```

Python, Rust, and Go all run the question-effect vector today. The Rust and Go runners are deliberately narrow question-effect kernels, not full Form runtimes: they parse the `ask(...)` and `await_answer(...)` forms used by this host-bound vector, emit the same question transcript, and let the Python harness compare actual values/events against the shared contract.

Future kernels become `implemented` only when their vector entry names an executable runner and proof file. Target-only kernels remain explicit: without `--allow-targets`, the harness fails so CI cannot mistake a named target for shipped behavior.
