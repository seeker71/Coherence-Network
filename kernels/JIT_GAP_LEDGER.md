# JIT Gap Ledger — the book of gaps, kept as they are discovered

Working ledger for the Go kernel's in-process JIT (`form/form-kernel-go/jit.go`
+ the dispatch arm in `main.go`). Every row is a gap **measured or read from the
code**, with its evidence and status. The JIT is Go-only — the three-way bands
run on the walker, so JIT fixes carry no parity risk; the walker stays
canonical truth. Companion finding record:
`docs/system_audit/commit_evidence_2026-06-11_jit_realization_gap.json`.

Status: `OPEN` · `AGENT-ASSIGNED` (a sub-agent is on it) · `FIXED (PR)` ·
`BY-DESIGN` (named refusal, honest fallback to the walker).

| # | Gap | Evidence | Status |
|---|-----|----------|--------|
| 1 | **Dispatch realization: compiled native not carrying recursive int workloads.** `jit_compile fib` returns 1, the emitted C self-recurses natively, yet JIT fib38 7.92s ≈ walker 8.10s (routed native would be 100×+). Suspects: (a) i64 plugin build silently failing → Value-ABI boxing per call; (b) `jc.I64` nil → guard miss → walker fallthrough; (c) top-level call not reaching the dispatch arm. | measured 2026-06-11; main.go ~4255–4331; evidence JSON above | AGENT-ASSIGNED (fable, worktree) |
| 2 | **Per-call dispatch overhead even when routed**: `jitCompiledGo` map lookup + arg-kind scan + three ABI guards on *every* call (jit.go header notes "FNCALL closure dispatch checks the map on every call"). For hot recursive shapes the native carries inner recursion, but every *top-level* call repays the scan. | read 2026-06-11, jit.go:27 | OPEN |
| 3 | **Logic ops not in the i64/f64 subset** (`jit: logic ops not in subset`, jit.go:436). Recipes with and/or/not fall back. | read 2026-06-11 | OPEN — lower to C `&&`/`!`-style branchless ints |
| 4 | **Nested defn refused** (`jit: nested defn not in subset`, jit.go:463). Any recipe with an inner helper falls back entirely. | read 2026-06-11 | OPEN — lift nested defns as siblings in the plugin (the emitter already has `plan.helpers`) |
| 5 | **String literals require Value ABI** (jit.go:491); **floats require f64 ABI** (jit.go:497) — fine as routing, but combined int+string shapes drop to boxing. | read 2026-06-11 | BY-DESIGN today; revisit with tagged ABI learn
## Exercise log — measured coverage probes (2026-06-11, claude, worktree)

Exercised `jit_compile` / `jit_compile_value` across shapes to map what the
EMITTER covers vs refuses (read-only, no kernel edits). The headline: the
emitter's coverage is BROAD — gap #1 (dispatch realization) is the keystone,
because fixing it realizes every COMPILES row below at once.

| shape | probe | result |
|-------|-------|--------|
| float scalar compute | `(add (mul x 0.5) 0.25)` | **COMPILES** (f64 ABI) — model arithmetic JITs |
| list / vector arg | `vsum` over `head`/`tail`/`len` | **COMPILES** (i64 + value ABI) — the matvec-shaped path |
| cross-function sibling call | `withhelper` calls `outer` | **COMPILES** |
| let binding | `(let x ... )` | **COMPILES** |
| mul / div | `(mul x x)`, `(div a b)` | **COMPILES** |
| logic ops (and/or/not) | `(and (le a b) (le b a))` | **REFUSED** → gap #3 (confirmed by measurement) |
| nested INNER defn | `(do (defn inner ...) (inner n))` | **REFUSED** → gap #4 (confirmed by measurement) |

**Strategic read:** the emitter is not the bottleneck for model arithmetic —
float compute, vectors, cross-calls, and let all lower today. The single
keystone is gap #1: the compiled native is not realized at runtime. When the
sub-agent lands gap #1, re-run these probes with timing — float and list
workloads should drop to native speed in the same breath. Then gaps #3/#4 widen
coverage further (masks/gating need logic; inner helpers need nested-defn lift).
