# form-lower extension reference — the G1 lever, offline

The one frontier that turns the tower native (`self-growing-machine.form`): extend
`form-lower` over the **string + host-io** op families. This is the offline working
reference — read alongside `form/form-stdlib/form-asm.fk` (the encoder) and
`form/form-stdlib/form-lower.fk` (the compiler). No network needed: the reasoning
oracle is a local model (`ollama run coder` / `qwen2.5:72b`), and `clang`
(`/usr/bin/clang`) is the offline byte cross-check (`scripts/form_lower_demo.sh`).

## The key finding: the instructions are already forged

`form-lower` today dispatches only on int arith / cond / map / recursion. But the
arm64 **encodings the lever needs already exist in `form-asm.fk`** — the work is
composing them in `form-lower`'s dispatch, not inventing encodings:

| Lever step (roadmap id) | form-asm primitives already present |
|---|---|
| `ll-buffer` (memory/buffer model) | `fa-stp-pre` / `fa-ldp-post` (frame), `fa-sub-x-imm`/`fa-add-x-imm` (sp alloc), `fa-ldr` |
| `ll-streq` (string ops → byte loops) | `fa-ldrb` / `fa-strb` (byte load/store), `fa-cmp-x`, `fa-bcond` / `fa-b-off` (loop), `fa-csel` |
| `ll-readfile` (host-io → syscalls) | `fa-svc` (the `svc` instruction), `fa-movz-x` (load syscall # into x16) |
| `ll-callconv` (multi-arg calls) | `fa-stp-fp` / `fa-ldp-fp` (frame), `fa-bl` (branch-link) |

So each lever step is a `form-lower` dispatch arm that *emits a sequence of existing
`fa-*` calls*, byte-verified through the conviction gate (`fa-conviction` /
`fa-may-drop`, `form-to-asm.form`).

## The only external rote facts — the macOS arm64 syscall ABI

Syscall # in `x16`; args in `x0..x5`; trap with `svc #0x80`. BSD syscall numbers
(arm64 macOS takes the bare number in x16, no 0x2000000 class offset):

| call | x16 | args |
|---|---|---|
| `exit` | 1 | x0 = code |
| `read` | 3 | x0 = fd, x1 = buf, x2 = count |
| `write` | 4 | x0 = fd, x1 = buf, x2 = count |
| `open` | 5 | x0 = path*, x1 = flags, x2 = mode |
| `close` | 6 | x0 = fd |

(The `form-asm-syscall` / `form-asm-echo` / `form-asm-wc` bands already emit working
`write`/`read` via `svc` — they are the worked examples to copy.)

## The proof shape per step

Each lever step ships like every other `form-lower-*` band: a recipe + a band that
checks the lowered bytes against a known reference, four-way (`form-lower-*` rows in
`fourth-arm-bands.txt`). Generate the recipe offline with
`form-cli close "<id>" "<spec>" "<assert>" "<expected>" "ollama run coder"` — a local
model drafts, the local kernel validates. Sequence: `ll-buffer` → `ll-streq` →
`ll-readfile` → `ll-callconv`, then `g3` (compile any recipe) and `g7` (self-host)
fall out by composition.

See the live plan any time, offline: `form-cli roadmap`.
