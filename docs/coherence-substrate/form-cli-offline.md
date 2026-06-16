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
