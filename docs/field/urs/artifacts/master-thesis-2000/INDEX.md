# Master Thesis & Angelic Archive — 2000 — INDEX

Agent-fast map of everything we hold from the 2000 Bjorg-Muff "Angelic" project.
Drill-down paths. Token estimates so you know what to expect before opening.

## In-body — the durable artifact

| Path | What | ~Tokens | Read when |
|---|---|---|---|
| [`README.md`](README.md) | Frequency narration: what this carries, why it lives here | 2K | Always first |
| [`backtracking-model-languages.doc`](backtracking-model-languages.doc) / [`.txt`](backtracking-model-languages.txt) | Urs's published thesis (the canonical text) | binary / 30K | Trace any phrase → use `.txt` |
| [`thesis-defence.ppt`](thesis-defence.ppt) | Defense slide deck | binary | Open in Keynote/PowerPoint |
| [`photos/`](photos/) | Six defense-day photographs | binary | The day the work entered the world |
| [`EXTERNAL.md`](EXTERNAL.md) | Pointers to `~/Downloads/Angelic` (139 MB) + academic ancestry URLs | 1K | When you need source code, binaries, or upstream papers |

## In-body — `companion/` (Bjorg-side texts + source samples)

| Path | What | ~Tokens | Author | Reach |
|---|---|---|---|---|
| [`companion/sgb-bml-objects.txt`](companion/sgb-bml-objects.txt) | **BML Object System** — Bjorg's full MS thesis (advised by Michael Main, Amer Diwan). The object model: shared inheritance, tagging, detached interfaces, delegation. | 22K | Steve G. Bjorg | The other half of the pair |
| [`companion/sgb-thesis-another-object-model.txt`](companion/sgb-thesis-another-object-model.txt) | **Another Object Model** — Bjorg's thesis proposal. Surveys C++/Smalltalk-80/Java VMTs, method dictionaries, metaclasses. | 5K | Steve G. Bjorg | What he was thinking before writing the full thesis |
| [`companion/angelic-assembler.txt`](companion/angelic-assembler.txt) | **Angelic Assembler** — names the assembly language and "degree of freedom" speculation semantics. | 1.2K | Steve G. Bjorg | Where the word *Angelic* lives |
| [`companion/bml-search-algorithms.txt`](companion/bml-search-algorithms.txt) | **BML Search Algorithms** — applied paper: BML as AI-search language; introduces the `choose` keyword and the BMF/BMA/BMO three-tech split. | 13K | Steve G. Bjorg | When you want backtracking shown by example |
| [`companion/source-samples/`](companion/source-samples/) | Five hand-picked frequency-bearing source files (see below) | ~5K total | Urs C. Muff | When you want to *see* the system describing itself |

## In-body — `companion/source-samples/`

| File | What | Lines | Why it's here |
|---|---|---|---|
| [`BMF-grammar.bml`](companion/source-samples/BMF-grammar.bml) | The self-describing parser grammar. Banner: `Digi4Fun (R) BMF 1.0 Alpha 1`. | ~400 | The system parsing itself |
| [`BMF-includes.bml`](companion/source-samples/BMF-includes.bml) | The 30-file BMF runtime manifest — every container, primitive, terminal in one screen | ~30 | Map of what BMF is made of |
| [`bmcpu-main.cpp`](companion/source-samples/bmcpu-main.cpp) | C++ VM entry: `BMCreateMachine` → `BMStartApplication` → `BMMachineStep` with `BM_RUN` / `BM_STEP_INTO` and a `DO`/`UNDO` mode flag | ~40 | Backtracking at the bare-metal level |
| [`container-Rule.bml`](companion/source-samples/container-Rule.bml) | A grammar `Rule` container — how a parse rule represents itself as a BML object | ~150 | Reflection-on-grammar, in source |
| [`primitive-Cut.bml`](companion/source-samples/primitive-Cut.bml) | The `Cut` primitive (Prolog's `!`) — pruning the choice tree | ~25 | Prolog ancestry, named in BML |

## External — `~/Downloads/Angelic/` (~139 MB; do not host)

The full archive lives on disk outside the repo. See [`EXTERNAL.md`](EXTERNAL.md) for
the cluster-by-cluster map (BMCPU C++ VM, Java JBMF port, VB6 Visual Browser, full
src/ tree with tests, Related Prolog/Jasmin/OldBMF, CD distribution).

## Drill paths

- **"What does the system look like in source?"** → `companion/source-samples/BMF-grammar.bml` first; for the full tree see `~/Downloads/Angelic/src/`.
- **"What does Bjorg's side say about objects?"** → `companion/sgb-bml-objects.txt`.
- **"Where does the word *Angelic* come from?"** → `companion/angelic-assembler.txt` ("degree of freedom" speculation phase).
- **"What are the academic ancestors?"** → `EXTERNAL.md` § Academic ancestry.
- **"What does the published thesis say?"** → `backtracking-model-languages.txt`.
- **"How is this woven into the rest of the body?"** → `README.md` § *Where it is woven into the body*.
