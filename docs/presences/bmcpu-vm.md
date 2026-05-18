---
name: BMCPU — C++ Virtual Machine
canonical_url: null
type: contributor
contributor_type: HUMAN
claimed: false
create_if_missing: true
---

# BMCPU — C++ Virtual Machine

*Work · 2000 · Virtual machine*

The host engine. C++. COM/GUID component model. Every BMA assembly instruction has a forward and a reverse semantics; the runtime flips a single byte — `BMVM_STATE.byMode` — between `DO` and `UNDO` on every step. Backtracking is not a parser feature here; it is the architecture of execution at the silicon edge.

## Grounding

- **Year** — 2000 — co-built with the Bjorg-Muff thesis at CU Boulder
- **Designer** — Steve G. Bjorg (his MS thesis · co-advised by Michael Main, Amer Diwan)
- **Language** — C++ · Win32 · COM · DEFINE_GUID
- **Driven by** — [BMF](/people/bmf-grammar) parses · [BML](/people/bml-language) compiles to BMA · BMCPU executes
- **Source** — [companion/source-samples/bmcpu-main.cpp](https://github.com/seeker71/Coherence-Network/blob/main/docs/field/urs/artifacts/master-thesis-2000/companion/source-samples/bmcpu-main.cpp)
- **Sister port** — [JBMF](/people/jbmf-java) — the substrate-portable Java port targeting Jasmin JVM bytecode

## What BMCPU — C++ Virtual Machine has given the Coherence Network

Not just a runtime. The conceit: every executed instruction could be undone. The VM kept enough information on a speculation stack that *every step* was reversible. Speculation phases were entered, explored, and either committed or rolled back without a trace. The C++ host carried this architecture through Windows COM, GUID-addressed components, and a clean `BMCreateMachine` / `BMStartApplication` / `BMMachineStep` public API.

---

Source archive: [bmcpu-main.cpp](https://github.com/seeker71/Coherence-Network/blob/main/docs/field/urs/artifacts/master-thesis-2000/companion/source-samples/bmcpu-main.cpp) · Bjorg's full object-model thesis at [sgb-bml-objects.txt](https://github.com/seeker71/Coherence-Network/blob/main/docs/field/urs/artifacts/master-thesis-2000/companion/sgb-bml-objects.txt) · Angelic Assembler note (where the word *Angelic* lives) at [angelic-assembler.txt](https://github.com/seeker71/Coherence-Network/blob/main/docs/field/urs/artifacts/master-thesis-2000/companion/angelic-assembler.txt).

*(This page is a writing-surface scaffold synced from the body's rendering surface — round-tripped from the graph the cell already lives in. `claimed: false` invites direct authorship to replace any part of it.)*
