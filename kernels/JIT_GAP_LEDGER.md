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

### Turn-key fix-sketches for the follow-on gaps (read from jit.go, 2026-06-11)

Ready to pick up once gap #1 (dispatch realization) lands. Each names the exact
site and the lowering. These are SMALL, Go-only, no parity risk.

- **Gap #3 — logic ops** (`jit.go:436`, `case RBasicLogic`). Today: `unsupported`.
  Lowering: emit C/Go boolean expressions over the int subset. `and` →
  `(((a) != 0) && ((b) != 0)) ? 1 : 0`, `or` → `|| ... ? 1 : 0`, `not` →
  `((a) == 0) ? 1 : 0`. Read the op from `cat.Inst` (RLogicAnd/Or/Not) the same
  way `emitGoCompare`/`emitGoMath` read theirs. and/or are BINARY in the subset
  (the stdlib trap) — emit two-arg only; reject 3-arg with a clear unsupported.
  Unblocks: masks, gates, any recipe with a boolean guard (model attention masks).

- **Gap #4 — nested defn** (`jit.go:463`, `case RBasicFnDef`). Today: `unsupported`.
  Lowering: the emitter ALREADY lifts sibling functions via `plan.helpers` +
  `plan.emitting`/`plan.emitted` (see `emitGoFnCall` at jit.go ~725). A nested
  defn with NO free-variable capture (only its own params + globals) can be
  lifted as a plan-level sibling helper exactly like a top-level one. Refuse ONLY
  nested defns that capture an outer LOCAL (the documented closures-over-outer
  limit). Detect capture by walking the inner body's idents against the inner
  params + known helpers. Unblocks: any recipe factored with inner helpers.

- **Gap #2 — per-call dispatch overhead** (the map lookup + arg-kind scan on every
  top-level call). After gap #1, profile whether this matters: for deep-recursive
  shapes the native carries the inner loop so it's a one-time cost; for
  many-distinct-top-level-calls (a model's per-token loop) it could add up. Lift
  only with a measured row showing it dominates — otherwise leave it (the scan is
  cheap relative to any real compute). Don't pre-optimize.
