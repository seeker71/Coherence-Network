# JIT Gap Ledger — the book of gaps, kept as they are discovered

Working ledger for the Go kernel's in-process JIT (`form/form-kernel-go/jit.go`
+ the dispatch arm in `main.go`). Every row is a gap **measured or read from the
code**, with its evidence and status. The JIT is Go-only — the three-way bands
run on the walker, so JIT fixes carry no parity risk; the walker stays
canonical truth. Companion finding records:
`docs/system_audit/commit_evidence_2026-06-11_jit_realization_gap.json` (the gap),
`docs/system_audit/commit_evidence_2026-06-11_jit_dispatch_fix.json` (the fix).

Status: `OPEN` · `AGENT-ASSIGNED` (a sub-agent is on it) · `FIXED (PR)` ·
`BY-DESIGN` (named refusal, honest fallback to the walker).

| # | Gap | Evidence | Status |
|---|-----|----------|--------|
| 1 | **Dispatch realization: compiled native not carrying recursive int workloads.** Was: JIT fib38 7.92s ≈ walker 8.10s. Root cause (instrumented): `jitRecipeNeedsValueABI` read the recipe's structural name slots — an IDENT's name child, an FNCALL's static callee, a LET's binding name — as runtime string values; every real body contains one, so EVERY compile was forced onto the boxed Value-only ABI (`jc.I64` never built; guard 3 ran the boxed native at walker speed). Fix: pre-filter skips name slots; f64 leg refuses float `mod` so mod-using int recipes keep their typed build (Go has no float `%`). After: fib38 compute **0.13s (62×)**, within 1.4× of handwritten Go's 0.095s; end-to-end 1.48s incl. the one-time plugin build; guard 1 (i64) crossed exactly once. | measured 2026-06-11 before/after; fix evidence JSON above; regression pinned by `form/form-kernel-go/jit_test.go` | FIXED (PR #2825) |
| 2 | **Per-call dispatch overhead even when routed**: `jitCompiledGo` map lookup + arg-kind scan + three ABI guards on *every* call (jit.go header notes "FNCALL closure dispatch checks the map on every call"). For hot recursive shapes the native carries inner recursion, but every *top-level* call repays the scan. | read 2026-06-11, jit.go:27 | OPEN on the recipe lane — the 2026-06-12 band heal composted the placeholder call-inlining pass (it rewrote every CALL into `0 + arg`); a real inlining rule in jit-lower.fk's generic engine is the named close. |
| 3 | **Logic ops not in the i64/f64 subset** (`jit: logic ops not in subset`, jit.go:436). Recipes with and/or/not fall back. | read 2026-06-11; Go reference via emitGoLogic 2026-06-12; portable proof 2026-06-12: jit-lower.fk's logic-recognition rule lowers the direct IF expansion to LOGIC-AND/OR/NOT (tags 44..46, walker arms in fourth-walker.fk), proven three-way by jit-lower-band.fk (15) + full-jit-lower-band.fk (63) — including the IF-expansion guard lowering to the SAME content-addressed cell the explicit LOGIC-AND constructor builds. | FIXED (portable Form recipe on the fourth/host-kernel lane; Go emitGoLogic is reference parity) |
| 4 | **Nested defn refused** (`jit: nested defn not in subset`, jit.go:463). Any recipe with an inner helper falls back entirely. | read 2026-06-11; carrier proof 2026-06-12: CLOSURE-LIFTED (tag 51) keeps its index leaf and folds/walks its body, full-jit-lower-band.fk piece 16 | OPEN on the recipe lane — the carrier tag is proven transparent; a real lift pass (detect capture-free inner defns, hoist into the fn table) is the named close. Go-side sketch below. |
| 5 | **String literals require Value ABI** (jit.go:491); **floats require f64 ABI** (jit.go:497) — fine as routing, but combined int+string shapes drop to boxing. | read 2026-06-11; carrier proof 2026-06-12: unbox tags 48..50 are transparent to the lowering engine and the walker (full-jit-lower-band.fk piece 8) | PARTIAL on the recipe lane — the unbox carriers are proven; payload-level string/float unboxing (pool/arena direct ops) arrives with the emit lane. |
| 6 | **Plugin `.so` rebuilt per process; temp dirs accumulate.** Every kernel process `MkdirTemp`s a fresh `form-jit-*` dir and re-runs `go build` (~1.3s) even for an already-seen bodyKey; 55,559 stale dirs found in `$TMPDIR` on the dev machine. The bodyKey is content-addressed — a durable on-disk cache keyed by bodyKey + toolchain version would make warm compiles ~0 and stop the accumulation. | measured 2026-06-11 during the gap-1 fix | LIFTED (fourth lane uses one-time emit of lowered recipe; no per-process rebuild for the proven binary. The portable recipe is the cache.) |
| 7 | **Emitted i64 native ~1.4× handwritten Go.** fib38: emitted native 0.13s vs handwritten 0.095s. The IIFE-wrapped cond/compare emission is largely inlined by the Go compiler (a direct-bool cond peephole landed with gap #1 and measured neutral); the remaining delta (plugin PIC codegen? exported wrapper?) is unexplored. Matters only once workloads saturate the native path. | measured 2026-06-11 | PARTIAL on the recipe lane — const folding + dead-branch are proven in jit-lower.fk (full-jit-lower-band.fk piece 4); emit-lane direct C for the lowered tags (44..59 arms in fourth-walker-emit.fk) is the named close. |
| 8 | **Auto-compile (2000-hit threshold) builds synchronously mid-walk.** The hot-path promotion in the FNCALL dispatch arm calls `jitCompileClosureGo` inline, so the first hot crossing pays the full ~1.3s plugin build inside the user's call. Now that the artifact is realized (gap #1), an async build that lets the walker continue until the artifact lands would remove the stall. | read 2026-06-11; visible in any un-annotated hot run | LIFTED (fourth m4e-jit "self-JIT on heat" + crystallize already uses the portable lowerer recipe at "compile" time of the binary; no runtime stall for the emitted case. The recipe is the plan.) |
| 9 | **Full BMF compiler + engine/grammar not portable (apply-object-rule, cap-get/set, mk-*, bmf-compile/grammar ref-rep as recipe, only Go jit.go hardcode).** Remaining engine pieces (match-pattern + template, buckets, rule application) + grammar (cursor direct, rep) lived only in host Go lowering or Python; no lowered recipe for any minimal kernel to crystallize full folded/unboxed BMF compiler. | read 2026-06-11 from engine.fk:2175 (apply-object-rule), bmf-grammar.fk; the #2944 recipe extensions (jit-lower-engine-full / apply-object-rule / cap-get / bmf-compile-step) never validated — their bands had never passed three-way — and were composted in the 2026-06-12 band heal | OPEN — the BMF-lowered vocabulary (tags 52, 54..59) and walker arms remain the named lane (tag 52's carrier transparency is proven, full-jit-lower-band.fk piece 32); real engine/grammar lowering passes through jit-lower.fk's generic engine are the close. |

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
float compute, vectors, cross-calls, and let all lower today. Gap #1 landed
(PR #2825): the typed natives are realized at dispatch. Next: re-run these
probes with timing — float and list workloads should drop to native speed in
the same breath. Then gaps #3/#4 widen coverage further (masks/gating need
logic; inner helpers need nested-defn lift), and gap #6 (durable plugin cache)
turns the ~1.3s per-process compile into a one-time cost per recipe shape.

### Turn-key fix-sketches for the follow-on gaps (read from jit.go, 2026-06-11)

Each names the exact site and the lowering. These are SMALL, Go-only, no
parity risk.

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
  top-level call). With gap #1 landed, profile whether this matters: for
  deep-recursive shapes the native carries the inner loop so it's a one-time
  cost; for many-distinct-top-level-calls (a model's per-token loop) it could
  add up. Lift only with a measured row showing it dominates — otherwise leave
  it (the scan is cheap relative to any real compute). Don't pre-optimize.

- **Gap #6 — durable plugin cache.** `jitCompileClosureGo` already keys
  in-memory reuse by the content-addressed bodyKey; persist the same key on
  disk (`~/.cache/form-jit/<toolchain>/<bodyKey>/plugin.so`), `plugin.Open` an
  existing artifact before invoking `go build`, and the per-process MkdirTemp
  (and its accumulation) composts away.
