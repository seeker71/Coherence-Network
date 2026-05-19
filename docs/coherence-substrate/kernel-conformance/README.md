# Kernel Conformance

Kernel conformance vectors describe Form-visible behavior that every substrate kernel must match. They are not implementation claims. A kernel is only `implemented` when the vector names an executable runner and proof file.

`agent-question-effects.json` covers the host-bound question effects:

```bash
python3 scripts/verify_kernel_conformance.py --kernel python
python3 scripts/verify_kernel_conformance.py --kernel rust --allow-targets --json
python3 scripts/verify_kernel_conformance.py --kernel go --allow-targets --json
```

Python runs the vector today. Rust and Go return explicit `skipped` target status until their executable runners are present. Without `--allow-targets`, asking for a target-only kernel fails so CI cannot accidentally treat a named target as shipped.
