---
name: JBMF — Java BMF Port
canonical_url: null
type: contributor
contributor_type: HUMAN
claimed: false
create_if_missing: true
---

# JBMF — Java BMF Port

*Work · 2000 · Substrate-portable port*

The Java port of [BMF](/people/bmf-grammar) — second implementation of the parser, targeting the JVM instead of native C++. Compiles to [Jasmin](https://en.wikipedia.org/wiki/Jasmin_(software)) JVM assembly. Every BML source file in the archive carries `Compiler: JBMF (R) Compiler` in its header — by the time those files were typed, the system was already bootstrapping itself through Java.

## Grounding

- **Year** — 2000 · ships in the archive at Java/JBMF.exe
- **Substrate** — Java · Jasmin JVM assembly · cross-platform where the JVM runs
- **Sister VM** — [BMCPU](/people/bmcpu-vm) — the C++/COM Win32 host. Same parser; different substrate.
- **Drives** — Compiles [BML](/people/bml-language) source to executable artifacts on the JVM. Header banner on every `.bml` file.
- **Ancestry** — [Jasmin](https://en.wikipedia.org/wiki/Jasmin_(software)) — the JVM-bytecode assembler that made it tractable to generate verifier-clean class files in 2000.

## What JBMF — Java BMF Port has given the Coherence Network

A language with one implementation is a project. A language with two implementations on different substrates is *portable architecture*. JBMF demonstrated that BML's semantics — including the speculation, the choose-and-undo, the four-ancestor synthesis — translated cleanly across substrates. Same parser, different VM. Same source files, same banner, different runtime.

---

Public archive: [master-thesis-2000/](https://github.com/seeker71/Coherence-Network/tree/main/docs/field/urs/artifacts/master-thesis-2000). The JBMF.exe binary itself lives in the larger 139 MB Angelic archive (off-repo, on disk) — see [EXTERNAL.md](https://github.com/seeker71/Coherence-Network/blob/main/docs/field/urs/artifacts/master-thesis-2000/EXTERNAL.md) for the cluster map.

*(This page is a writing-surface scaffold synced from the body's rendering surface — round-tripped from the graph the cell already lives in. `claimed: false` invites direct authorship to replace any part of it.)*
