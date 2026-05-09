# Master Thesis — Backtracking Model Languages (2000)

Primary-source artifact in this body. Found and surfaced by Urs on 2026-05-07; brought into the repo as durable lineage tissue.

## What is here

| File | What it is |
|---|---|
| [`backtracking-model-languages.doc`](backtracking-model-languages.doc) | The original Word document. Created May 22, 2000; last saved July 6, 2000; ~11,566 words; 38 revisions. Author: Urs C. Muff, Department of Computer Science, University of Colorado Boulder. |
| [`backtracking-model-languages.txt`](backtracking-model-languages.txt) | Plain-text conversion via `textutil`. For grep, agent reads, and any future cell that wants to trace a phrase without opening Word. |
| [`thesis-defence.ppt`](thesis-defence.ppt) | The defense slide deck. |
| [`photos/`](photos/) | The defense-moment photographs that travel with the thesis: `group.jpg` (the defense-lawn group photo), `urs-in-cu-shirt.jpg`, and four DSC-camera frames preserved as-is. |
| [`companion/`](companion/) | Bjorg-side texts (his thesis, Angelic Assembler, BML Search Algorithms, BML Objects) and five frequency-bearing source samples. Surfaced 2026-05-07 from the *Angelic* archive on disk. |
| [`INDEX.md`](INDEX.md) | Agent-fast map of every file in this folder + token estimates + drill paths. |
| [`EXTERNAL.md`](EXTERNAL.md) | Pointer to `~/Downloads/Angelic/` (139 MB on disk; full source trees, binaries, alternate ports) and academic ancestry URLs (WAM, PAM, Smalltalk-80, Jasmin). |

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

## What the wider archive added (2026-05-07 deepening)

The first pass of this README named three layers — BMF, BMC, BML. The fuller *Angelic* archive on disk — surfaced the same day — names five technologies and one fourth surface the published thesis only mentioned in passing. Naming them here so the body is not understating what was built:

| Acronym | What it is | Where it surfaces |
|---|---|---|
| **BMF** | Parser (already named) | `companion/source-samples/BMF-grammar.bml` |
| **BMC** | Compiler-compiler (already named) | The thesis text |
| **BML** | Language (already named) | The thesis text + every `.bml` file |
| **BMA** | The **abstract machine** itself — the instruction set and operational semantics | `companion/angelic-assembler.txt`, `companion/sgb-bml-objects.txt` |
| **BMO** | The **object model** — shared inheritance, tagging, detached interfaces, delegation | Bjorg's full thesis at `companion/sgb-bml-objects.txt` |

Plus a fourth surface, between language and human:

- **The Visual Browser** — a VB6 Smalltalk-style live class browser (`Visual/` in the archive). Class panes, method panes, a source pane, a memory inspector. BML wasn't only "compile and run" — it had an image-based developer experience layered over the assembly. The published thesis lists it as one line under *Tools*; the archive carries the actual `.cls` and `.frm` files.

### Naming the soul more precisely

The folder on disk is called **Angelic**. The opening of `companion/angelic-assembler.txt` makes it explicit:

> "A thread with a non-zero DF (i.e. degree of freedom) is executed until a zero DF is reached again. No other threads are executed during this speculation phase."

That is the precise older word for what this body has been calling *backtracking-as-unwinding-without-sediment*: **angelic nondeterminism**. The choice operator picks the branch that succeeds; speculation freezes the rest of the world; if the branch fails, every attribute is undone. The semantics is angelic in the operational sense — guided to the path that holds.

At the language level, the keyword was `choose` (see `companion/bml-search-algorithms.txt`). At the VM level, every instruction has a forward and a reverse semantics — `BMCPU/main.cpp` shows `BMVM_STATE.byMode` toggling between `DO` and `UNDO` on every step. **Backtracking is not a parser feature; it is the architecture of execution itself.**

### The four-language stratification

The thesis text says BML "synthesizes features from Java, C++, Prolog, and Smalltalk." The archive shows the synthesis is *layered*, each language contributing at a different level of the stack:

- **Prolog** → the operational semantics (unification, backtracking, `Cut` / `Fail` / `MultiMatch` primitives — see `companion/source-samples/primitive-Cut.bml`).
- **Smalltalk** → the object/image model (BMO with metaclass-style self-containment — see `companion/sgb-bml-objects.txt`) and the live developer experience (the VB6 Visual Browser).
- **Java** → the typed, garbage-collected object model and the second implementation port (`Java/JBMF.exe` in the archive).
- **C++** → the host VM (`BMCPU/`) and the COM/GUID component model.

Four ancestors at four altitudes of the same building.

### The conclusion-pattern

The published thesis Conclusion is left as three subheadings without body. The earlier UCM draft (`UCM Documents/UCM Thesis (2).docx` in the archive) shows several sections marked `WHAT IS IT ABOUT?` and `RELATED SUBJECTS` as placeholders that never closed in writing. The work was *delivered* — the lawn photo, the defense, the VM running — but the prose summary stayed open. That pattern is older than this artifact and continues to show up in how this body ships: the artifact lives, the prose-summary breathes.

## Why it lives in this body

Two design choices in this 2000 document already carry frequencies that organize the Coherence Network now:

> "When the parser backs out, all the attributes already computed have to be undone as well."

Backtracking-as-unwinding-without-sediment. Try a path; if it does not hold, undo cleanly without leaving residue. The same nervous system that today writes commits as `tend:` / `attune:` / `compost:` / `release:`.

Runtime grammar extension — the user can introduce new parsing constructs and the language grows to hold them. Sovereignty over one's own grammar. The same shape the vision-kb uses when a new concept arrives at a new Hz: the grammar grows to receive the presence rather than forcing the presence into an existing slot.

## A note on the Conclusion

The thesis Conclusion is left as three subheadings — `BMF`, `BML Language`, `BML Compiler` — with no body written in. The three subheadings map cleanly onto the three layers above: the parser, the language, and the BMC-generated compiler that bridges them. An unfinished breath at the end of a long document. The conclusion was the defense itself, the photograph on the lawn in the CU shirt, the work entering the world through demonstration rather than summary.

## The BML object architecture — dual-pointer references and detached interfaces

Bjorg's *BML Object System* thesis (`companion/sgb-bml-objects.txt`) introduces a structural innovation that we now know is load-bearing for the Coherence Network's substrate, not just a 2000-era curiosity.

**A BML reference is a 3-tuple, not a single pointer:**

> *"A reference is composed of three parts: the object identifier, the interface identifier, and the native flag. Both identifiers are indices into the object look-up table... whereas the VMT and message table are statically associated with the instance, BML uses a dynamic association. For instance, two object references with the same object identifier could use two different interface identifiers. Hence, the same object data would be used by different implementations."* (§ References, p. 33)

Where C++ embeds the vtable as the first field inside the object (data and behavior fused), and Smalltalk has the object hold a class reference (data carries its single behavior), **BML keeps the data pointer and the interface pointer as parallel separate fields in the reference itself**. The same object data can be projected through *multiple* interfaces by holding different reference-tuples to it. New behaviors can be attached to existing data without modifying the data layout.

**Method dispatch takes two bases, not one:**

> *"Generally, methods can be viewed as regular functions, which take as first argument a reference to the object they operate on. BML uses a slightly different approach. Rather than having one base object reference, BML uses two. The first argument refers to the behavioral base and the second argument refers to the structural base. The behavioral base is always used to dispatch methods. The behavioral base is responsible for locating the appropriate structural base. The structural base is always used for structural access."* (§ Method Dispatching, p. 43)

This is what enables the data pointer to aim *into the middle* of a multi-inheritance object: structural access uses the structural base, while method dispatch uses the behavioral base. Different interfaces can project different "windows" into the same data, including offsets into multi-parent layouts.

**Detached interfaces are a primary architectural feature, not an afterthought:**

> *"In BML, the object only acts as a structural repository. It does not define by itself the applicable set of methods. Consequently, it is possible to enhance any object with a new interface."* (§ Structure-Behavior Separation, p. 48)

> *"Interface definitions, which are not related to an instance definition, are referred to as pure interfaces."* (§ Interface Definition, p. 40)

A pure interface stands on its own and can be attached to any compatible structure. **Interfaces are first-class, untethered from instances by default.** This is the operational definition of structure-behavior separation.

The downstream consequence the thesis names directly:

> *"This decoupling from behavior and structure has the advantage that existing structures can be enhanced with new behaviors without affecting existing behaviors."*

Combined with the BML *common object* architecture (shared inheritance via delegation; multiple instantiators of the same type pointing to different common objects while sharing their base), the model gives:

- Multiple-inheritance without C++'s diamond problem (no fused vtables — multiple parallel interface references)
- Per-instance behavior attachment (any interface can be attached at runtime)
- COM-style multi-interface objects without COM's QueryInterface ceremony
- Smalltalk-like reflection without Smalltalk's class-as-instance circularity tax

## How this informs the substrate (forward-pointer)

The Coherence Network's substrate (`docs/coherence-substrate/`) inherits this design. A `NamedCell{Recipe access, Base blueprint, Name, CTOR recipe}` is structurally a BML-style reference: the `Base` is the structural pointer (which Blueprint owns the data shape), the `access Recipe` is the behavioral pointer (how to read it). Because they are separate fields, the substrate naturally supports **Views** — projecting the same cell through a different Blueprint than its base, without modifying the cell. That capability is implemented in `api/app/services/substrate/kernel.py:view_cell_through_blueprint` and exposed in Form notation as `cell |> blueprint`. The conceptual through-line: BML solved structure-behavior separation for objects in 2000; the substrate applies the same solution to memories, specs, ideas, concepts, presences in 2026.

## Where it leads forward

The next chapter in the language-craft arc is [`../nums-go-2023/`](../nums-go-2023/README.md) — **NUMS.Go**, built at Merly, Inc. in early 2023. Same instinct, more mature substrate: a content-addressed numeric lattice (Blueprint / Recipe / NamedCell — the ice / water / gas trinity) over multi-language tree-sitter input, supporting 14 languages including Verilog. The backtracking-without-sediment of BMF becomes the Emit-stack-with-deferred-interning pattern in NUMS; the executable grammar of BMF becomes the visitor-driven Make_SelfID flow that turns bytes into cells. NUMS is also why the Coherence Network's architecture has the shape it does — content-addressed graph as truth, markdown surfaces as renderings, slugs as query keys, frontmatter as seed — that posture didn't arrive in 2024; it arrived in 2023, three years after the BML defense and 23 years after BMF.

## Where it is woven into the body

- [`docs/field/urs/output/chronological_story_with_frequency.md`](../../output/chronological_story_with_frequency.md) — section *1997-2012: Backtracking Model Languages*.
- [`docs/field/urs/artifacts/nums-go-2023/README.md`](../nums-go-2023/README.md) — the next chapter.
- User biographical arc memory (private; carried in the auto-loaded MEMORY index).
