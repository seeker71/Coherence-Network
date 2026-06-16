# form-cli offline — the air-gap self-improvement kit

The form-cli improves itself with no network: it senses its own surface, names
its own gaps, and closes them against a **local** oracle. Everything it needs
lives on disk — the Form kernel, the stdlib recipes, the specs, and sovereign
local models. This is the body keeping its breath when the air goes thin.

## One command to know the kit is whole

```bash
scripts/form_cli_preflight.sh
```

It proves, while the network is still reachable to fix anything: the Form kernel
builds and evaluates; the **surface membrane** is legible (Form-native); local
oracles are present; the recipes and specs are on disk; and the agent loop runs
end-to-end against a local oracle. Exit 0 = `READY` — you can lose the network
and keep improving.

## The surface membrane

The boundary axiom (`core-axioms.form`, axiom-4) says a cell meets the world
only through an interface it offers, and every passage is observable. The
form-cli makes that interface legible and ledgers every crossing of it.

A **crossing** is the form-cli leaving its own Form body to reach one of four
surfaces:

| surface | meaning | needs network |
|---|---|---|
| `native-recipe` | stayed in the Form body — no OS membrane crossed | no |
| `os-kernel` | crossed to the OS kernel (host:exec / host:file) | no |
| `local-oracle` | via the OS kernel to a **local** model (sovereign) | no |
| `remote-oracle` | via the OS kernel to a **remote** model | **yes** |

Each crossing is a `choice-receipt` (the choice of *which surface*), so the
ledger inherits proven four-way validation. Each is tagged:

- **gap** — crossed out with no native recipe available → an idea→form-spec
  opening to close.
- **retirable** — crossed out though a native recipe existed → the flywheel's
  work: learn to keep it in the body next time.
- **air-gap-clean?** — zero `remote-oracle` crossings. The offline-readiness
  number; on a plane it must be 0.

## The open-gap catalog

The membrane shows gaps *per crossing* — what one run hit. The catalog is the
*standing inventory* of everything open in the body, so you can see every gap at
rest and pick which to close:

```bash
scripts/form_cli_gaps.sh            # the full catalog
scripts/form_cli_gaps.sh --stage    # only what must be staged before the flight
```

Three lanes of openness:

- **open idea** — an idea no spec references → `author-form-spec`
- **open spec** — a non-draft spec with no `test:`/`proof:` → `write-validation-band`
- **open capability** — an oracle-catalog teacher lane, placed on the **closing
  ladder** by its `(trust, state)`

The capability ladder names, for each open capability, the cheapest next move and
whether it's **offline-closable** or needs the network **first**:

| rung | meaning | next move | offline |
|---|---|---|---|
| `samples` | samples on disk, no recipe | train a native recipe | yes |
| `local-oracle` | a local oracle is installed | distill samples | yes |
| `source-local` | local oracle source on disk, needs building | build the source | yes |
| `remote-only` | only a remote oracle | **stage remote→local** | **no — ⚑ before flight** |
| `none` | no oracle at all | find/stage an oracle | **no** |

The catalog tallies `open / offline-closable / stage-before-flight` and reads
**flight-ready** iff nothing needs the network first — the membrane's
air-gap-clean notion at body scale. A membrane crossing tagged `gap=1`
corresponds to a catalog item. Recipe:
[`form-cli-gaps.fk`](../../form/form-stdlib/form-cli-gaps.fk) — proven four-way
(`form-cli-gaps-band` → 4095). Measured on the body today: 27 open, 26
offline-closable, 1 stage-before-flight (`remote-llm`).

Recipe: [`form-cli-membrane.fk`](../../form/form-stdlib/form-cli-membrane.fk) —
proven four-way (`form-cli-membrane-band`, verdict 1023, go/rust/ts/fkwu).

## The local oracles (sovereign)

Already on disk — no download race:

- **fast** — `ollama run llama3.2:3b` (proves the loop quickly)
- **reasoners** — `qwen2.5:72b`, `llama3.3:70b`, `deepseek-r1:32b` in ollama
- **coder** — `qwen2.5-coder-32b/14b`, `devstral-small` GGUFs in
  `~/mentor-install/.models`. Stage one into ollama with no internet:
  ```bash
  ollama create coder -f <(echo "FROM ~/mentor-install/.models/qwen2.5-coder-32b-instruct-q5_k_m.gguf")
  ```

The runner picks `local` over `remote` by surface; the preflight names which
oracles are staged.

## Closing a gap offline

Name a gap, let a local coder oracle draft the recipe, and validate it on the
kernel — all offline:

```bash
scripts/form_cli_close_gap.sh triangular \
  "(tri n) returns the nth triangular number n*(n+1)/2" \
  "(tri 5)" 15 "ollama run coder"
```

The loop ([`scripts/form_cli_close_gap.sh`](../../scripts/form_cli_close_gap.sh)):
the coder drafts the recipe in the Form `.fk` dialect → the kernel **validates**
it against the assertion → the crossing is **ledgered** through the membrane
recipe (`surface=local-oracle`, `gap=1`, `receipt-valid=1`). A validated draft
lands in `form/form-stdlib/drafts/` (gitignored); promote it by writing an
assertion band and adding it to the manifest to make it four-way. Measured
offline: `(defn tri (n) (div (mul n (add n 1)) 2))` and a recursive list-sum,
each drafted in seconds and kernel-validated.

The general agent runner ([`form-native-run.fk`](../../form/form-stdlib/form-native-run.fk),
driven by [`scripts/form_native_run.sh`](../../scripts/form_native_run.sh)) is
the same shape for open-ended tasks — pure Form on the kernel, oracle call + tool
dispatch + recursion, host effects through the kernel's host-io builtins, every
step a membrane crossing.

## Native binary slices (zero clang)

The deepest surface of the membrane: a native binary stays fully in the Form
body — no oracle, no interpreter. Lower a recipe slice to machine code, run it,
and content-address it:

```bash
scripts/form_cli_slice.sh answer "(list (list 1 40 0 0) (list 1 2 0 0) (list 3 0 1 0))" 2 42
```

The Form recipes ([`form-lower.fk`](../../form/form-stdlib/form-lower.fk) +
[`form-macho.fk`](../../form/form-stdlib/form-macho.fk) on macOS,
[`form-elf-exec.fk`](../../form/form-stdlib/form-elf-exec.fk) on Linux/Android)
lower an op-tagged tree to arm64 bytes, wrap it in a Mach-O / ELF object; `ld`
links it; the binary **runs and its exit code is the program's value** — zero
clang. The binary's sha256 is its content address — the stable identity the
substrate interns as an `ARTIFACT` cell (`BDomain.ARTIFACT=16`) with a NodeID, so
it is addressable. Measured offline: `((40+2))=42` → 243-byte Mach-O, ran exit
42; `((40+5)-3)=42` and `(7+8)=15` each a distinct binary + content address. The
slice is ledgered as a `native-recipe` crossing (os-membrane-crossed=0).

The slice spec is the lowered IR (op-tagged nodes; tags 1=LIT 2=ARG 3=ADD 4=SUB).
A recipe→IR front-end is a separate cell; the lowered subset (LIT/ADD/SUB/COND/
ARG/recursion) is what compiles to native today.

## Shell commands are recipes — lowered to native asm

The carriers used to shell out to `tr`, `cat`, `grep`. **The north star is direct
Form → asm** — the Form recipe emitting machine code on its own, no compiler in the
lowering path. clang is **one oracle** (it assembles the same instructions so we
can check our bytes against the assembler); understanding the **LLVM / ARM encoding
spec** is a **second oracle** (independent of clang, it grounds an encoding in the
documented bitfields — e.g. the two's-complement branch fold). Neither oracle is
the lane; the four-way band is the truth and stands without either.

The encoder itself is a **table** ([`form-asm.fk`](../../form/form-stdlib/form-asm.fk)):
one generic packer `fa-asm` over per-instruction `(base, multipliers)` data rows, so
a new instruction is a row, not new code (`form-asm-table fks 7`, the ARM/LLVM
encoding table as a recipe). The **slice lane** (+ [`form-macho.fk`](../../form/form-stdlib/form-macho.fk))
carries real unix commands end to end, **zero clang**: the syscall / byte-I/O set
(`svc`, 64-bit `movz`/`movk`, `ldrb`/`strb`, stack frame), the read-loop control flow
(`cmp`, the EOF branch, the backward loop branch), and the branchless transform
(`cmp`+`csel`), a callee-saved line counter (`head`), and **argv** (`echo` reads
`argv[1]` via `ldr [x1,#8]`) — proven four-way at `form-asm-syscall`,
`form-asm-branch`, `form-asm-tr` (31), and `form-asm-rot13`, `form-asm-head`,
`form-asm-echo` (7).

```bash
scripts/form_cat_demo.sh    # a zero-clang `cat`
scripts/form_tr_demo.sh     # a zero-clang `tr A-Z a-z`
scripts/form_rot13_demo.sh  # a zero-clang `rot13`
scripts/form_head_demo.sh   # a zero-clang `head -3`
scripts/form_echo_demo.sh   # a zero-clang `echo $1` — reads argv
```

Form encodes the program (`cat` = loop `read(0)`→`write(1)`; `tr`/`rot13` = that
plus a branchless per-byte transform; `head` = that plus a line counter in a
callee-saved register), `ld` links it (**no clang**), and the binary runs through
the OS read/write syscalls. Measured: `cat` round-trips stdin→stdout, Form `tr`
matches the system `tr A-Z a-z`, Form `rot13` matches the system rot13 and is its
own inverse, and Form `head` matches `head -n 3` — all **byte-for-byte**. clang only
assembled the same instructions as the byte oracle; the ARM/LLVM spec derived the
encodings. `tr`/`rot13`/`head` each added **no new encoder** — only data rows.

`rot13` added **no new encoder** — its two-range rotation is `sub`/`add`/`cmp`/`csel`
data rows — so the earlier **C-emit byte-filter lane composted**: every common filter
now runs on Form's own bytes, clang only ever a check. (The whole-program C-emit lane,
[`hati-os-native-cli-emit.fk`](../../form/form-stdlib/hati-os-native-cli-emit.fk),
remains for programs not yet asm-lowered.)

These began as happy-path recipes from memory — toys. The real behavior surface is
now read from the **actual GNU source** (cached offline), enumerated in
[`coreutils-edge-surface.md`](coreutils-edge-surface.md), and the Form versions are
held honest by `scripts/form_coreutils_diff.sh` — a differential test against the
system tools over edge inputs (empty, NUL, UTF-8, >page-size, no-trailing-newline).
Measured: the implemented operations match **14/14 byte-for-byte**; the option/mode
surface (tr `-d`/`-s`/classes, cat `-n`/files, argv) is the named-from-source frontier.

## The training corpus — samples to try the native models on

Every slice and gap-close captures its request/response; the agent's own turns
(reasoning + tool use) are captured too. These become samples the native models
are tried on and measured against — champion (the oracle) vs challenger
(form-native).

```bash
# the agent's own turns from a session transcript
scripts/form_cli_capture.sh --from-transcript <session>.jsonl 10
# form_cli_close_gap.sh auto-captures every close (success AND fail teach)
```

Each line is a `form-cli-sample.fk` cell (four-way, `form-cli-sample-band` →
1023): task, oracle-id, reasoning, ordered tool-steps (each a membrane crossing),
answer, outcome. A turn with no remote-oracle step is **offline-reproducible** —
the native models replay it air-gapped. Corpus lives in
[`form/form-samples/agent-turns/`](../../form/form-samples/agent-turns/) — a
committed `seed.jsonl` of real exemplars, a gitignored `corpus.jsonl` that
accumulates.

**Cell sovereignty is structural:** the capture carrier refuses any turn touching
tender/personal markers — dropped whole, never scrubbed-and-kept — so the corpus
can never hold gated content by construction. (A turn that *read* a gated file is
dropped because its step-results carry that content.)

## Scoring — how the native models are doing

Replay measures the native models against the agent over the corpus. The first
scoreable lane is **tool selection** — the agentic core: given a task, which
tools to reach for.

```bash
scripts/form_cli_replay.sh 12 "ollama run coder"
```

For each task the local model predicts its tool sequence; the kernel scores the
prediction against the tools the agent actually used (`form-cli-score.fk` →
overlap → majority-match → tally; champion = the agent reference, challenger =
native). It reports native match rate vs an **always-Bash baseline**, so the
signal is honest: real skill, or just guessing the most common tool? Proven
four-way (`form-cli-score-band` → 255).

Snapshot (local coder, 8 tasks): native majority-match ~87%, full-cover ~37%,
above a 25% baseline — real skill, but it **systematically omits `Bash`** (the
model doesn't think to run shell commands) and over-predicts `Grep`/`Glob`. That
named gap is what the corpus then trains toward — the flywheel closing on real
work. Numbers drift run to run; the readout is the measurement, not a fixed score.

## The loop closed — a native model beats the oracle

The replay measured the LLM; this trains a **native** model from the corpus and
re-scores it — no LLM at the prediction step:

```bash
scripts/form_cli_train_predict.sh
```

It learns tool base-rates + Agent keyword-boosts from a **train** split and
scores on a **held-out** split (`form-cli-predict.fk` → predict → cover → match,
four-way `form-cli-predict-band` → 127). On held-out tasks:

| | majority-match | full-cover |
|---|---|---|
| **native-trained** (corpus) | **100%** | **95%** |
| LLM coder (oracle) | ~87% | ~37% |
| always-Bash baseline | ~42% | ~28% |

The corpus-trained native model beats both — especially full-cover — because it
learned the agent's real tool distribution (the frequent set always clears the
threshold, so **Bash is always predicted**, closing the LLM's gap) and triggers
the rare `Agent` from task keywords. **The oracle is retired on this lane.**

Honest frontier: this wins because tool *selection* (the set) is dominated by a
learnable prior + a keyword discriminator. The harder lanes — tool *order*, and
the reasoning lane (`task → answer`, which needs semantic judging) — are still
open. One lane retired; the rest is the road.

## The trained model improves the live model

Measuring is one thing; making the runner better is the payoff. The predictor
knows the local coder omits `Bash`, so it computes the likely tool set per task
and **injects it as a hint** into the local model's prompt:

```bash
scripts/form_cli_guided.sh 6 "ollama run coder"
```

Composes the two proven recipes — `form-cli-predict.fk` guides, `form-cli-score.fk`
judges — no new logic. Snapshot (local coder, 6 tasks):

| | majority | full-cover |
|---|---|---|
| unguided | 33% | 16% |
| **guided** | **100%** | **66%** |

The hint closes the exact gap the predictor knew about — e.g. a task where the
coder unguided answered `[Grep, Edit]` (no Bash) becomes `[Bash, Read, Write,
Edit]` once guided. The corpus-trained native model makes the live local model
better: the flywheel turning, not just measured.

**This is now permanent in the runner**, not a demo. `form_native_run.sh`
self-guides every call: it consults the predictor (`form-cli-predict.fk`) for the
task's likely tools, maps them to the runner's tool vocabulary, and feeds them to
the loop via `fnr-run-guided` (`form-native-run.fk`). So the local model's tool
selection is corrected on every real run — e.g. a read/validate/write task
auto-guides to `bash, read_file, write_file`. `FNR_NO_GUIDE=1` gives the bare
unguided runner. The runner uses its own trained model to guide itself.

## Tiered local-first — the remote oracle as last resort

The reasoning lane can't be won by a frequency table — it needs a capable model.
But "native" means *local silicon*, not "a Form recipe": so the runner escalates
**within local tiers** before ever crossing the network:

```bash
scripts/form_cli_tiered.sh "<task>"   # small-local → big-local → remote (last)
```

The self-guided runner tries a small local model first; on failure (reached
max-steps or no real answer) it escalates to a bigger local model; only if every
*local* tier fails does it cross to a remote oracle. Each served tier is ledgered
as a membrane crossing (`form-cli-membrane.fk`) — local tiers stay
**air-gap-clean**, a remote escalation is the one network crossing. **Remote
reliance = network crossings**, the flywheel's lever: as the bigger local tier
improves, tier-3 goes to zero and the remote oracle retires on reasoning too.
Proven both ways: the easy task is served by tier-1 offline; a failing tier-1
(unavailable model) correctly escalates to tier-2, still offline.

## The reasoning lane — measured, and wide open

Tool selection is a set problem; reasoning needs a *semantic* judge. So a local
model gives a one-shot answer and a local **oracle judges** how well it covers
the agent's captured answer (0–100); the Form judge recipe tallies — pass-rate +
grade distribution (`form-cli-judge.fk` → grade/pass/tally, four-way
`form-cli-judge-band` → 127).

```bash
scripts/form_cli_judge.sh 5 "ollama run coder" "ollama run coder" 60
```

Snapshot (local coder, threshold 60): native **~25% pass, avg ~25/100**, mostly
*poor* grades — the opposite of tool selection. So the two lanes read:

| lane | native vs agent |
|---|---|
| **tool selection** (set) | **100% / 95%** — won, oracle retired |
| **reasoning** (`task → answer`) | **~25%** — the open frontier |

That contrast *is* the finding: the easy lane is done; reasoning is the real
road. (The judge here is a local oracle — a membrane crossing — so this score
itself isn't yet offline-pure; a Form-native semantic judge is the next cell.)

## What is proven, and the honest frontier

- **Proven, four-way**: the surface membrane + crossing ledger; the agent loop
  running offline on the Go kernel; the oracle-distillation flywheel
  (`oracle-flywheel`, `champion-challenger`); native binary emit for the lowered
  subset (`form-macho`, `form-elf-exec`).
- **The frontier**: compiling the *whole* runner to a standalone native binary
  waits on `form-lower` covering strings + host-io. Until then the runner runs
  interpreted on the 21 MB Go kernel binary — which is itself on the laptop, so
  the offline loop is whole today. Naming the frontier honestly is part of the
  kit, not a gap in it.
