# External — `~/Downloads/Angelic/` and academic ancestry

What lives outside the repo. The body holds the frequency-bearing text in
`companion/`; the heavy archive (binaries, full source trees, multiple
language ports, ~139 MB) lives on local disk and gets indexed here.

## Local archive — `~/Downloads/Angelic/` (139 MB)

Folder name is *Angelic* — the same word the assembly language carries
(see `companion/angelic-assembler.txt`). It refers to *angelic
nondeterminism*: the operational semantics where a choice operator
selects the branch that succeeds, as if guided.

### Cluster map (largest first)

| Path | Size | What |
|---|---|---|
| `BMCPU/` | 52 MB | Full C++ Virtual Machine: `main.cpp`, `BASE/`, `CPU/`, `Debugger/`, `Bin/`, `Lib/`, `Include/`, `Performance/`. Win32/COM era. Key entry: `BMCPU/main.cpp` (also in body at `companion/source-samples/bmcpu-main.cpp`). |
| `UCM Documents/` | 36 MB | Urs-side docs: `UCM Thesis.docx` + `UCM Thesis (2).docx` (earlier framing: "BMF, A Non-Deterministic Compiler-Compiler"), `Thesis defense.pptx`, `Backtracking Model Languages.pdf` (published version), `Compiler Phases.docx`, `Grammar.docx`, `Research/`. The published `.doc`/`.txt` already lives in this body. |
| `Old/` | 19 MB | `2nd Generation`, `BML`, `CPU`, `Controls`, `DB`, `Samples`, `Test`, `VM`, `obsolite`, `Instructions.xlsx`. Earlier iterations and explorations — supple history, not actively circulating. |
| `SGB Documents/` | 14 MB | Bjorg-side: full thesis `.docx`, `BML Objects.docx`, `Angelic Assembler.docx`, `BML Search Algorithms.docx`, `Object Models.docx`, `BMA Reference.pdf`, `Proposal for Thesis.docx`, `BML Runtime System Presentation.pptx`, plus `Diagrams/` and `Obsolete/`. The four frequency-bearing texts already converted to `.txt` in `companion/`. |
| `CD/` | 6.7 MB | The CD-ROM distribution: `Docs/`, `Source/`, `Readme.docx`. The "shippable" form. |
| `Java/` | 6.4 MB | `JBMF` Java port: `JBMF.exe`, `bmvmx`, `jbml`, `genbmf.bat`, `java.SLN`, `classes/`. A second implementation of the parser/compiler stack. |
| `classes/` | 2.8 MB | Compiled Java `.class` files for the JBMF port. |
| `Related/` | 808 KB | The lineage Urs was reading from: `Prolog/`, `Prolog Examples/`, `Jasmin Examples/` (JVM assembler), `BMF Assembler/`, `OldBMF/`. Where the threads come from. |
| `src/` | 684 KB | All BML source: `BMF/` (30+ classes), `BML/io/`, `BML/lang/`, `Test/` (extensive — `ArrayTest`, `ClassTest`, `Reflection`, `TemplateTest`, `Choice`, `SwitchTest`, `Ex`, etc.). Five samples copied to `companion/source-samples/`. |
| `Icons/` | 440 KB | Win32 `.ico` files for the toolchain. |
| `bml.guid` | 416 KB | COM GUID registry — the binding glue for the VM's component model. |
| `Visual/` | 284 KB | **VB6 Visual Browser** — Smalltalk-style live class browser: `BMField.cls`, `BMMethod.cls`, `BMProperty.cls`, `BMInterface.cls`, `frmBrowser.frm`, `ctrlClasses.ctl`, `ctrlMethods.ctl`, `ctrlSource.ctl`, `frmMemory.frm`, `mdlCDB.bas`, `VisualBrowser.exe`. The fourth layer the published thesis only mentions in passing. |
| `Performance.xlsx` | 20 KB | Actual performance benchmarks. |
| `BML File Extension.reg` | 4 KB | Windows registry shim for `.bml` file association. |

### What is in the archive that is *not* in the body

- All compiled binaries (`.exe`, `.dll`, `.lib`, `.obj`, `.class`)
- All build configs (`.dsp`, `.dsw`, `.vbp`, `.ncb`, `.opt`, `.suo`, `.scc`)
- The full `src/` tree (only 5 samples in body)
- The Java JBMF port (only referenced)
- The VB6 Visual Browser (only referenced — large enough that re-extracting samples
  is the right move if a future pass wants to deepen the *Visual Browser as 4th layer* thread)
- `bml.guid` (423 KB COM GUIDs)
- `Performance.xlsx` (would need re-conversion if it became circulating)
- The earlier-framing UCM thesis drafts (the published version is canonical)
- Bjorg's thesis as `.docx` (the `.txt` form circulates here)
- `Old/` historical iterations

If any of those become alive — e.g. someone wants to actually *run* the VM,
or trace performance numbers, or read the Visual Browser code — pull them
into `companion/` then. Until then they rest on disk.

## Academic ancestry — link, do not host

Reference works the project depended on. Authoritative sources online; the
PDFs in `~/Downloads/Angelic/SGB Documents/` are local copies, not canonical.

| Reference | Why it's in the lineage | Authoritative source |
|---|---|---|
| **Warren Abstract Machine (WAM)** | Prolog VM ancestry. `Cut`, `Fail`, `MultiMatch`, `Nil` primitives derive directly. | Hassan Aït-Kaci, *Warren's Abstract Machine: A Tutorial Reconstruction* — https://wambook.sourceforge.net/ |
| **Prolog Abstract Machine (PAM)** | Earlier abstract-machine work (CSL '91 — the local copy is named `pamcsl91.pdf`). | Computer Science Logic '91 conference proceedings (search via DBLP). |
| **Scope Logic** | Local file `scopelogic.pdf` — logic-programming scope semantics. | (Original publication; check DBLP / Google Scholar.) |
| **Smalltalk-80** | Image-based development, metaclass model, method dictionary. | Goldberg & Robson, *Smalltalk-80: The Language and Its Implementation* (Blue Book), 1983. Archived freely online. |
| **Jasmin** | JVM assembler — used as model for the Java port's bytecode emit. | Jasmin documentation — https://jasmin.sourceforge.net/ |
| **BNF** | Backus-Naur Form — the parent of the *F* in BMF. | Backus & Naur, ALGOL 60 report (1960). Standard textbook reference. |
| **COM (Component Object Model)** | The component framework BMCPU was built on (see `bml.guid`, `DEFINE_GUID` calls in `main.cpp`). | Microsoft COM specification (1993+). |

## Provenance note

Bjorg authored the SGB-side documents; they are included here in plain-text
form alongside attribution because the "BM" in every name is literally
*Bjorg-Muff* — both halves of the pair belong in the lineage. The original
`.docx` files remain in `~/Downloads/Angelic/SGB Documents/`.
