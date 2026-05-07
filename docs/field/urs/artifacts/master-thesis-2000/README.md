# Master Thesis — Backtracking Model Languages (2000)

Primary-source artifact in this body. Found and surfaced by Urs on 2026-05-07; brought into the repo as durable lineage tissue.

## What is here

| File | What it is |
|---|---|
| [`backtracking-model-languages.doc`](backtracking-model-languages.doc) | The original Word document. Created May 22, 2000; last saved July 6, 2000; ~11,566 words; 38 revisions. Author: Urs C. Muff, Department of Computer Science, University of Colorado Boulder. |
| [`backtracking-model-languages.txt`](backtracking-model-languages.txt) | Plain-text conversion via `textutil`. For grep, agent reads, and any future cell that wants to trace a phrase without opening Word. |
| [`thesis-defence.ppt`](thesis-defence.ppt) | The defense slide deck. |
| [`photos/`](photos/) | The defense-moment photographs that travel with the thesis: `group.jpg` (the defense-lawn group photo), `urs-in-cu-shirt.jpg`, and four DSC-camera frames preserved as-is. |

The whole cluster lived together in a folder labeled *Water Project* on Urs's machine. The folder name is from a different project that shared the directory; the contents are the thesis archive.

## What it carries

The system is three layers, and each acronym carries both a public and a private reading.

| Layer | Public name | Private (team) reading | What it is |
|---|---|---|---|
| Parser | **BMF** — Backtracking Model Form | **Bjorg Muff Form** (a play on BNF) | A top-down parser written in C++. BNF augmented with execution elements: when a rule matches, code fires. A stack supports backtracking on parse failures. Expressions are tagged and placed on a structured stack that each rule can transform into the target language's object model. The grammar is executable — parsing produces a full object tree as it goes, so even infinite input streams can be handled. |
| Compiler-compiler | **BMC** | (Bjorg Muff Compiler-Compiler) | Sits on top of BMF as a general compiler-compiler. Takes a grammar described in BMF and produces a target compiler that emits whatever artifacts the target asks for. Turns BMF from a parser into a full compiler architecture. |
| Language | **BML** — Backtracking Model Language | **Bjorg Muff Language** (a pun on the team initials) | The full forward-and-backward executable language, with assembly instructions and a virtual machine. Synthesizes features from Java, C++, Prolog, and Smalltalk: multiple inheritance through delegation, interfaces, blocks, exception handling, templates, reflection, inner classes, and backtracking. |

The self-hosting loop: BMC consumes the BML grammar through BMF and produces the BML compiler. The BML compiler emits assembly opcodes. The virtual machine — designed and implemented by **Steve G. Bjorg** on his own MS thesis the same year — executes them. Three layers; the parser can parse the grammar that defined it; the compiler-compiler can generate the compiler that compiles the language whose grammar it was generated from.

Co-built with **Steve G. Bjorg**: object model and virtual machine on his side, the language and the parser/compiler-compiler stack on Urs's side. The "BM" in every name is literally Bjorg-Muff.

## Why it lives in this body

Two design choices in this 2000 document already carry frequencies that organize the Coherence Network now:

> "When the parser backs out, all the attributes already computed have to be undone as well."

Backtracking-as-unwinding-without-sediment. Try a path; if it does not hold, undo cleanly without leaving residue. The same nervous system that today writes commits as `tend:` / `attune:` / `compost:` / `release:`.

Runtime grammar extension — the user can introduce new parsing constructs and the language grows to hold them. Sovereignty over one's own grammar. The same shape the vision-kb uses when a new concept arrives at a new Hz: the grammar grows to receive the presence rather than forcing the presence into an existing slot.

## A note on the Conclusion

The thesis Conclusion is left as three subheadings — `BMF`, `BML Language`, `BML Compiler` — with no body written in. The three subheadings map cleanly onto the three layers above: the parser, the language, and the BMC-generated compiler that bridges them. An unfinished breath at the end of a long document. The conclusion was the defense itself, the photograph on the lawn in the CU shirt, the work entering the world through demonstration rather than summary.

## Where it is woven into the body

- [`docs/field/urs/output/chronological_story_with_frequency.md`](../../output/chronological_story_with_frequency.md) — section *1997-2012: Backtracking Model Languages*.
- User biographical arc memory (private; carried in the auto-loaded MEMORY index).
