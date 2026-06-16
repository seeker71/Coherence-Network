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

The agent runner ([`form-native-run.fk`](../../form/form-stdlib/form-native-run.fk),
driven by [`scripts/form_native_run.sh`](../../scripts/form_native_run.sh)) is
pure Form on the kernel — oracle call + tool dispatch + recursion, host effects
through the kernel's host-io builtins. Point it at a local coder oracle and it
drafts, runs, and reports — every step a membrane crossing in the ledger.

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
