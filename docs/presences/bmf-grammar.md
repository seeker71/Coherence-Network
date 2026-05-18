---
name: BMF — Backtracking Model Form
canonical_url: null
type: contributor
contributor_type: HUMAN
claimed: false
create_if_missing: true
---

# BMF — Backtracking Model Form

*Work · 2000 · Parser layer*

BNF augmented with execution. When a rule matches, code fires. Expressions are tagged and placed on a structured stack each rule transforms into the target language's object model. The grammar file `BMF-grammar.bml` is itself written in [BML](/people/bml-language) — banner reads `Digi4Fun (R) BMF 1.0 Alpha 1`.

## Grounding

- **Year** — 2000
- **Implementation** — C++ top-down recursive-descent parser with backtracking stack
- **Grammar** — Self-describing — the grammar of BMF is written in [BML](/people/bml-language) (see `companion/source-samples/BMF-grammar.bml` in the archive)
- **Trio** — BMF (parser) · BMA ( [assembler / BMCPU](/people/bmcpu-vm) ) · BMO (object model) — the three-tech split named in `bml-search-algorithms.txt`
- **Ancestry** — [BNF](https://en.wikipedia.org/wiki/Backus%E2%80%93Naur_form) (Backus 1959 · Naur 1960) · executable grammar concept anticipated yacc/bison
- **Public archive** — [companion/source-samples/BMF-grammar.bml](https://github.com/seeker71/Coherence-Network/blob/main/docs/field/urs/artifacts/master-thesis-2000/companion/source-samples/BMF-grammar.bml)

## What BMF — Backtracking Model Form has given the Coherence Network

Parser is the first noun. *Executable grammar* is the second. BMF rules don't *describe* a parse tree — they *build* one as they go, with code firing on every successful match and a stack standing ready to undo every side effect on failure. The grammar is alive at parse time.

---

Source archive: [master-thesis-2000/companion/source-samples/](https://github.com/seeker71/Coherence-Network/tree/main/docs/field/urs/artifacts/master-thesis-2000/companion/source-samples) — BMF-grammar.bml, BMF-includes.bml, container-Rule.bml, primitive-Cut.bml. The published thesis lives one folder up at [backtracking-model-languages.txt](https://github.com/seeker71/Coherence-Network/blob/main/docs/field/urs/artifacts/master-thesis-2000/backtracking-model-languages.txt).

*(This page is a writing-surface scaffold synced from the body's rendering surface — round-tripped from the graph the cell already lives in. `claimed: false` invites direct authorship to replace any part of it.)*
