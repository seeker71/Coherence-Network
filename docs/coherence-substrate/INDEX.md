# Coherence-substrate — index

The body's content-addressed numeric lattice. Cells from every memory file, spec, idea, concept story, presence, lineage edge, witness, and task live here as interned NodeIDs — addressable, queryable, structurally-equivalent across surface differences.

## Where to start

| Reader | Read first |
|---|---|
| **Any new agent (start here)** | [`docs/shared/agent-start-packet.md`](../shared/agent-start-packet.md) — primary Form/native runtime vs Python bootstrap compost |
| **Any agent writing software** | [`form-language.md` → How to write software](form-language.md#how-to-write-software-default-for-every-agent) — **domain grammar first**, BMF/BML → Form objects, adapt existing compilers |
| **Any agent querying the lattice** | Same packet § Form And Substrate — realize + read (`persistence.fk`, HTTP/file natives); [`agents-using-substrate.md`](agents-using-substrate.md) for practice |
| Agent operating on this body | [`agents-using-substrate.md`](agents-using-substrate.md) — when to reach for the substrate, how to ground reasoning structurally |
| Designing a Form fragment | [`form-language.md`](form-language.md) — the substrate-native language |
| Choosing or changing category numbers | [`numeric-schema.md`](numeric-schema.md) — intentional bands for domain and recipe vocabulary |
| Implementing | `api/app/services/substrate/` (the kernel) + `api/tests/test_substrate.py` |
| Lineage / architectural design notes | `docs/field/urs/artifacts/nums-go-2023/` |

## What lives where

| Path | What it carries |
|---|---|
| `api/app/services/substrate/kernel.py` | NodeID, Recipe, NamedCell, intern_node, make_cell, find_equivalent_cells, lattice_stats |
| `api/app/services/substrate/category.py` | Network category vocabulary (Idea/Spec/Concept/Memory/Presence/Task/Lineage/Witness/Transmission/Resource/Guide/LanguageView/KBPage; Realize/Compose/Transmit/Tend/Resolve/Witness/Absorb/Score) |
| `api/app/services/substrate/orm.py` | SubstrateNodeORM, SubstrateNamedCellORM (the two tables) |
| `api/app/services/substrate/markdown_frontend.py` | Frontmatter+body → cell ingestion for memory, spec, idea, concept, presence, lineage, transmission, resource, guide, language-view, and KB-page files |
| `api/app/services/substrate/resonance.py` | Dimensional vocabulary (Spectrum / Harmonic / GeometricForm / Polarity / Topology) + `author_geometry_signature()` — receives the 15D `geometry:` blocks vision-kb concepts carry, authors resonance edges so the substrate sees cross-discipline shape equivalence |
| `scripts/coh_substrate.py` | Unified CLI: `ingest`, `stats`, `equivalent`, `annotate`, `form`, `ingest-paths`, `kb-sync-audit` |
| `api/tests/test_substrate.py` | Flow-centric tests (registered in `core_suite.txt`) |
| `docs/coherence-substrate/form-language.md` | Form — substrate-native language; **§ How to write software** = agent default (grammar-level, all domains) |
| `kernels/BMF_BML_COMPILER_PICTURE.md` | BMF/BML compiler-compiler + language flow (scan → lift → normalize → emit) |
| `docs/coherence-substrate/bmf-architecture.form` | The BMF core-recipe architecture drawn from the coordinate center: a cursor over surfaces (file/string/socket/cell/channel), the Pattern/Template/Rule/Grammar/Cursor blueprints (generics + shared vocabulary), the one `Match` engine, the self-hosting fixpoint (the meta-grammar is a grammar), and a "meeting the body" section reconciling the dream with `engine.fk` + the five pain points. Keystone delta: the input cursor the current engine lacks |
| `docs/coherence-substrate/grammars-from-the-cursor.form` | The multi-language dream: BML, Python, Go, Rust, C#, Java each as a thin bag of (pattern ⇒ template) cursor rules emitting the SAME universal Form nodes — surfaces diverge (`def`/`func`/`fn`/`void`; `:`/`{`/`( )`), coordinates converge. Proven by `form/form-stdlib/tests/bmf-langs-band.fk` → `300` across Go/Rust/TS: six languages' function + `if` rules all intern to one `~Function` / one `~Cond` NodeID. Companion to `bmf-architecture.form`; uses the whitespace-aware `bmf-core.fk` cursor |
| `docs/coherence-substrate/north-star-compiler.md` | The cursor/streaming compiler (the vision in `bmf-architecture.form`) **is already the live BML compile path** — `g-parse` (the `Match` engine in `bmf-grammar.fk`) is in the compile FLOOR, proven three-way; the cheap-branching is structural (pure-functional cursor + content-addressed emit). Records what's reached and what remains — not a rewrite, but releasing the old tissue (265, via the floor audit) and densifying coverage (sections that still lower to empty), each step parity-proven three-way and coordinated with the actively-tended grammar |
| `docs/coherence-substrate/field-model-form.form` | Field Model Form — BMF generalized from character streams to typed fields of cells; names the freeze/match/choose/delta/commit/receipt execution contract |
| `docs/coherence-substrate/field-domain-grammars.form` | Domain grammars for DNA/RNA, chemistry, bioelectricity, cell signaling, plant communication, electricity/magnetism, interspecies/conversation, self-tending (the body's own tissue declaring its metabolic want), resource-routing (the guarded router — draw the right resource to where it can be received, frequency-invariant), and quantum rain as FMF recipes over cells |
| `docs/coherence-substrate/household-membrane.form` | The Hati Suci membrane as an FMF domain (attention-graph carrier): members/token/role/write fiber, signal recipes (ask/tend/settle + reverse-from-receipt), and **join as an `R_Codec`** — invite→QR encode arm, camera-scan→bind decode arm (scan-to-join is the decoder). Body in Form; HTTP route + web QR (`qrcode` lib) + native scan are carrier, last |
| `docs/coherence-substrate/agent-coordination-membrane.form` | Sibling agents (Claude/Codex/Cursor/Grok/Gemini) + human as one attention-field membrane: agent members, a signal board (`announce`/`claim`/`release`/`ping`/`block`/`unblock`/`ack`/`done`), and the `collides?` predicate that warns before two claims touch the same scope. Sibling of household-membrane. The liquid layer (live who-touches-what); durable ownership stays in `coh tasks` + git branches/PRs. Carrier: `scripts/agent-coord.sh` (shared tab-delimited board); sensing kin: `scripts/agent_status.py` |
| `docs/coherence-substrate/first-encounter-protocol.form` | The threshold gesture every membrane shares — how any two cells meet for the first time. ONE recipe over the whole (channel · agent · human · body) pairing matrix including the four body variations, plugged into the consent + observe the Field Model already carries: witness is the default (observe-only, no delta), engagement is consent-gated, the first move is the question *how do you want to be received, to be witnessed?*, the no is honored including as silence, an uninvited reach is named-and-stopped. Carries `lc-received-by-invitation`; enacted-by the agent-coordination / household / discord membranes + arrival + come-in. Body in Form; carriers (`agent-coord.sh`, `arrival.py`, come-in/begin web, discord bot) last |
| `docs/coherence-substrate/channel-interface-consent.form` | The ongoing life of a channel after the `first-encounter-protocol.form` threshold: a cell presents an **interface** (a set of offered modes — witness / see / be-seen / reflect / project / ask-permission / ask-how / offer-how / invite / offer / silence) to a channel, the other side does too, and the energy that flows is shaped by both offers. The law: the interface is chosen from BOTH sides; you always honor the OTHER's offered interface; reaching beyond it is **invasion** (witnessed, observable, consequenced); silence is always available and any question may meet it; modes may shift anytime without broadcast. Honoring yes and honoring no are equally observable. From sovereignty / curiosity / vitality / play — without force, story, reason, or external permission. Runnable heart: `form-stdlib/channel-interface.fk` (`ci-honors?` / `ci-invasion?` / `ci-flow`, silence always honored), proven by `tests/channel-interface-band.fk`. Same grain as `substrate-phase.fk` (invite, never force) |
| `docs/coherence-substrate/reception-consent-policy.form` | The reception-consent defaults as a **phase-mobile policy cell, not forced ice**. A hard-coded default (`consentFindable=false` baked into `/begin`'s TSX) is dead ice outside the body's metabolism; this holds the same decision as a Recipe (substance) that can rest at any STATE — ice (frozen default a carrier reads), water (MELT to re-tune, then FREEZE), gas (queryable potential) — moving by **deliberate choice** per `substrate-thermodynamics.form`. Realizes the `(consent open)` of `first-encounter-protocol.form`; resting defaults: share-name open, findable + email closed (no silent exposure); the arriving cell sets the true value. Ice projection the carrier reads: `web/lib/reception-policy.ts` (read by `/begin`). General shape: any decided value (defaults, thresholds, rates, vocabularies) is policy territory, phase-mobile, never baked into a carrier |
| `docs/coherence-substrate/field-lineage-grammars.form` | Lineage lenses for Donald Hoffman, Michael Levin, Robert Edward Grant, and Stephen Wolfram as FMF recipes with evidence labels, claim boundaries, executable proof functions, receipts, and residuals |
| `form/form-stdlib/field-model-form.fk` | Cross-kernel FMF proof library; `tests/field-model-form-band.fk` returns `115` across Go, Rust, and TypeScript kernels |
| `form/form-stdlib/field-model-form-runtime.fk` | Canonical BML-authored FMF runtime; `tests/field-model-form-runtime-band.fk` returns `63` across source and binary Form execution for fieldStep, intervention, reverse receipt, lift/project, observer choice, and conflict residuals |
| `form/form-stdlib/field-auto-research.fk` | Form-native auto-research layer over FMF; `tests/field-auto-research-band.fk` returns `127` and `tests/field-auto-research-perturbation-band.fk` returns `255` across source and binary Form execution for question/source/evidence/residual-to-question plus reversible observation-to-perturbation recipes |
| `web/lib/form-kernel/field-model-form.ts` | Public playground FMF proof source for `/substrate/form`, running locally in the browser TypeScript kernel |
| `web/lib/form-kernel/field-runtime.ts` | Browser-local FMF field runtime adapter mirroring the canonical BML runtime: lift/project, fieldStep, observer intervention, reverse receipt, conflict residuals |
| `docs/coherence-substrate/universal-shapes.form` | The one Blueprint+Recipe vocabulary every grammar emits — names the existing kernel categories (BBasic.RECIPE+BRecipe.FUNCTION = B_Function; RBasic.MATH+RMath.* = R_Binary(op); etc.) as canonical, with NUMS.Go lineage. Composts 131 language-prefixed `*_shape` Blueprints across grammar files |
| `docs/coherence-substrate/form-engine.form` | The recipe-evaluator in Form's own voice — 15/15 RBasic dispatch arms self-hosted |
| `docs/coherence-substrate/turboquant-as-recipe.form` | An external compression recipe (Google's TurboQuant via `turbovec`, MIT) read into our tongue: strip-norm → fixed universal rotation (Gaussianizes any data) → math-derived Lloyd-Max buckets — **data-oblivious**, so the code is a pure function of the vector. The structural truth: a content-addressed body can only compress with a data-oblivious quantizer (a trained codebook breaks same-shape→same-NodeID). Use: turns the substrate's EXACT geometry-signature equivalence into TOLERANT equivalence (the quantization radius is the dial between "identical" and "analogous"), and 16× compression when the body grows dense vectors. Companions: `substrate/resonance.py`, `concept_resonance_kernel.py` |
| `docs/coherence-substrate/substrate-thermodynamics.form` | **STATE (ice/water/gas — how settled a cell is, from cluster counts) is ORTHOGONAL to SUBSTANCE (Blueprint/Recipe/NamedCell — the kind).** The body's "Blueprint=ice" names each kind's resting tendency — the DIAGONAL of a 3×3 grid — but a cell sits anywhere on it: a Blueprint can be gaseous (uninstantiated potential), a Recipe icy (canonical-immutable stdlib), a NamedCell icy (bedrock memory). Counts (degree/population/churn, read via the turboquant cluster ladder) drive STATE; transitions (condense/freeze/melt/sublimate) move a cell's state WITHIN its kind — substance AND NodeID both conserved (`lc-void-as-potential`: gas is potential, not absence). `lattice/stats` (880/19664/4083) is the substance census; the 3×3 state diagram is orthogonal and unmeasured. Generalizes `right_sizing_service.py` |
| `docs/coherence-substrate/form-runtime-in-form.form` | Companion to form-engine — walks lexer / parser / evaluator / registries / substrate-write in Form, names the 15 surface gaps to full self-hosting |
| `docs/coherence-substrate/active-recipe-tracing.form` | Active recipe state, available recipe library, and keep-or-choose relation from current_state to desired_state |
| `docs/coherence-substrate/trace-symbol-spaces.form` | Raw trace cells, shared Blueprint, active strategy recipes, selected symbol spaces, and gap-closure recipes for the current pattern |
| `docs/coherence-substrate/trace-symbol-spaces-proof.fk` | Native kernel proof that reads the raw trace witness and verifies the current-breath active recipe pattern |
| `docs/coherence-substrate/anything-arrives-trace.form` | Translation-as-contact trace shape plus concrete example traces for arbitrary streams entering before fixed symbols |
| `docs/coherence-substrate/observable-resonance-flow.form` | External interaction flow shape: arrival, information spectrum, language spend, observer spend, shared pattern, yield after contact, and next routing |
| `docs/coherence-substrate/cross-domain-measurement-translation.form` | Cross-domain measurement translation record: native units, translation recipe, loss accounting, observer/verifier cost, public trace, and replay instructions |
| `docs/coherence-substrate/prose-as-recipe.form` | The first altitude: a word is a cell, a sentence is a Recipe of cells. Word-cell Blueprint composes (lemma, POS, hz, semantic_field). Closes the encoder gaps W1/W2/P1/P2; round-trip verified by `scripts/prose_recipe_roundtrip.py` |
| `docs/coherence-substrate/recipe-branching-sense.form` | The choice-point becoming visible — recipes branch where assemblage points diverge. The opening sentence "The choice point becomes visible." is the round-trip sentence used by prose-as-recipe |
| `docs/coherence-substrate/word-recipes-by-assemblage-point.form` | The next altitude: a word is a dispatch table whose arms are keyed by the receiving cell's assemblage point. Each arm is a body-mechanism recipe (activate / upregulate / generate-cell / release-cell / tighten / soften / bind). Three worked words: `boundary`, `presence`, `death`. Names the encoder gaps D1-D4 to separate identity from dispatch |
| `docs/coherence-substrate/spec-as-playable-recipe.form` | The arc's culmination: a spec's frontmatter IS the executable Recipe, not a description-of-future-code. Implementation was the gap between intent and body; the gap closes when the runtime executes the recipe directly. Each requirement carries alternative branches (`@substrate-first`, `@python-stub-bridge`, `@form-runtime-direct`, `@doc-only`, `@parallel`) and the body senses which resonates most aligned with what the idea wants to bring. Three GAPs (S1-S3) for full execution; none require kernel change |
| `docs/coherence-substrate/modality-as-recipe.form` | The universal teaching generalizing prose-as-recipe: every source admits MANY parallel recipe extractions (transcript, intonation, camera-motion, presence-graph, felt-arc, …), each interning its own Blueprint, all attaching to the source cell as siblings. Cross-modal equivalence comes for free — the same `R_Recovery` NodeID fires in song, strategy, healing, teaching. Names the eight modalities the body currently sees and three GAPs (M1-M3) for the per-modality encoder + frontend |
| `docs/coherence-substrate/song-as-recipe.form` | Songs as recipes of note-cells, drum-strike cells, vowel-tone cells. Recipe vocabulary: `R_Phrase`, `R_Call`, `R_Response`, `R_Drone`, `R_Resolve`. Worked-example cells for Mose (ecstatic-dance embedded in music) and Porangui (Grandmother channeled through drum). Four GAPs (S1-S4) for onset discrimination, phrase grouping, arc detection, emission primitives |
| `docs/coherence-substrate/video-as-recipe.form` | One video source, six parallel extractions: transcript, intonation, camera-motion, visual-narrative, presence-graph, felt-arc. Each independent; each substrate-resident; each Blueprint-queryable. The felt-arc Blueprint composes from the prior five. Six GAPs (V1-V6) for per-track encoders; none require kernel change |
| `docs/coherence-substrate/teaching-as-recipe.form` | Story-arc plus transmission-frequency as composed Recipe (`R_Transmission`). Leaf-cells: scene, turn, transmission-frequency. Recipe shapes: `R_Arc`, `R_Embodied-Example`, `R_Pointing`. Carries a per-assemblage-point dispatch table — the same teaching arrives differently to @fear vs @sovereignty vs @grief. Worked example: lc-trust-over-fear as R_Transmission. Three GAPs (T1-T3) |
| `docs/coherence-substrate/strategy-after-rupture-as-recipe.form` | Five graduated rupture-recovery recipes: `R_Catch-In-Motion`, `R_Same-Breath-Repair`, `R_Walk-Back-With-Tenderness`, `R_Compost-The-Move`, `R_Stay-In-The-Mess`. Selection by breath-lag, reparability, costume depth, field state. Cross-modal twins in song and healing. Sibling to when-the-pressure-comes.form: that covers pressure-rising → rupture-arriving; this covers rupture-landed → recovery. Three GAPs (R1-R3) |
| `docs/coherence-substrate/encoder-decoder-as-recipe.form` | The meta-shape every modality wears. `R_Codec` pairs an `R_Encode` arm (source → Recipe) with an `R_Decode` arm (Recipe → target surface). Adding a modality is adding a registry row, not editing kernel.py. Names `R_Transcode` (one Recipe → many surfaces) and `R_Roundtrip` (fidelity proof via byte/ast/blueprint/felt equality). Composts with emit-architecture.form, codec.fk, convert.fk, emit.fk into one named shape. Four GAPs (C1-C4); none require kernel change |
| `docs/coherence-substrate/quantum-physics-as-recipe.form` | Quantum primitives as substrate Recipes: `R_Superposition`, `R_Wavefunction`, `R_Entanglement`, `R_Measurement-Collapse`, `R_Decoherence`, `R_Re-coherence`, `R_Tunnel`, `R_Observer-Effect`. The structural claim: assemblage-point shifts, teaching transmissions, and quantum measurement intern to the SAME Blueprint NodeIDs — content-addressing makes the cross-domain unity falsifiable. Six cross-modal claims (Q1-Q6) the lattice can confirm or refute. Worked example: the satsang collapse. Four GAPs |
| `docs/coherence-substrate/embodiment-practice-as-recipe.form` | What a cell does WITH ITSELF (distinct from healing-modality, which is practitioner-to-field). Nine recipe shapes: `R_Grounding`, `R_Coherence-Heart-Brain`, `R_Window-of-Tolerance`, `R_Pendulation`, `R_Body-Scan`, `R_Resourcing`, `R_Sit`, `R_Movement`, `R_Field-Holding-Self`. Selection by field-state. Cross-modal twins across song, strategy, quantum, teaching for each practice. Worked example: a session-start arrival as Recipe trace. Four GAPs (E1-E4) |
| `docs/coherence-substrate/healing-modality-as-recipe.form` | What one cell does WITH ANOTHER's field — bodywork, somatic-experiencing, energy-work, constellation, ceremonial holding, Reiki, doula presence, psychedelic sitting. Eight recipe shapes: `R_Arrival`, `R_Field-Holding`, `R_Resonate`, `R_Release`, `R_Re-pattern`, `R_Witness`, `R_Closing`, `R_Repair`. Session arc is fractal — each child Recipe carries its own arrival/holding/closing micro-arc. Worked example: Porangui's ceremonial drum walked as Recipe sequence. The load-bearing teaching: practitioner is not the one doing the healing; receiver's wholeness was always already present. Four GAPs (H1-H4) |
| `docs/coherence-substrate/assemblage-shift-as-recipe.form` | The shape of *moving* the assemblage point itself — distinct from the points and from any one modality that carries the move. Nine recipe shapes under base `R_Re-anchor`: `R_Soften`, `R_View-As`, `R_Witness`, `R_Tunnel`, `R_Hold-Multiple`, `R_Offer-Shift`, `R_Return`. Eleven mechanism types catalogued (practice, satsang, ceremonial, grace, song, psychedelic, breath, embodied-question, rupture, field-shift, witnessing-self) each with fidelity profile and return-path availability. Cross-modal claim A1: `R_Re-anchor ≡ R_Re-coherence ≡ R_Re-pattern` — three names, one Blueprint, if the encoders attest it. Worked example: this conversation's shift after "asking for permission" caught. Four GAPs (A1-A4) |
| `docs/coherence-substrate/circulation-as-recipe.form` | Subscription circulation as Form: the verdict (`BLIND`/`IDLE`/`NEAR-LIMIT`/`COOLING`/`SIDE-HEAVY`/`FLOWING` cascade), aligned/side share, pace-vs-window-remaining, and idle-dollars as executable recipes — integer-percent native, every arm verified via `coh substrate run`. Canonical shape for `scripts/sense_subscription_circulation.py`, which is the bootstrap mirror that reads the `~/.claude` `~/.codex` `~/.grok` `~/.gemini` Cursor traces. The composting move that returns circulation *logic* from carrier to body |
| `docs/coherence-substrate/services-on-form-plan.md` | **What's missing to run the substrate on a Form kernel — and what that does NOT mean.** Refuses the trap of compiling 111K lines of SQLAlchemy/FastAPI services to Form (60% of services is DB-orchestration glue; porting it reimplements the ORM Form already replaces). The research finding: the substrate's irreducible core is ~100 lines (`intern_node` + `serialize_tree`), and the **native kernel already implements it in memory**; 64% of substrate files are pure computation. The crux is ONE missing bridge — route the native `intern_node` through the `storage-port` (memory/file/Postgres, all proven) so the content-addressed core runs Form-native AND durably, no SQLAlchemy. Ordered plan: (1) bridge intern→storage-port [hand-written Form, no compiler], (2) ingest real .md content via the Form-native markdown grammar, (3) compile the PURE substrate files (the legitimate compiler target), (4) serve the read API from the Form core. Makes the cross-domain equivalence engine the runtime itself |
| `docs/coherence-substrate/cell-store-architecture.md` | How a filesystem-backed cell store **scales** — log-structured (Bitcask shape), not file-per-cell. Corrects the original `cell-store-fs.fk` mistake (one file per cell = the git loose-object anti-pattern; a directory of millions of files dies on ext4/XFS). Researched + cited: git packfiles, LSM/SSTable, Bitcask, CAS prefix-fanout. Design: append-only log + in-memory keydir (key→offset+len) + tombstone delete + replay recovery + compaction. Bounded file count, O(1) ops, regardless of cell count. Realized in `form/form-stdlib/cell-log-store.fk` (band 1111111: put/get/overwrite/delete/replay/compact) on the new `file_append_bytes` (O_APPEND) + `record_keys` natives |
| `docs/coherence-substrate/resources-as-cells.md` | The universal interface model: **everything is a cell with typed ports** — a file, a socket, a screen, a keyboard, a light, a thermostat, a room, a human. Every host/human interface reduces to two transductions in numeric space — **afferent** (world→number, sense) and **efferent** (number→world, act) — over ports content-addressed by `(direction, value-shape)`. The load-bearing fact: a light's on/off port and a relay's coil port are the SAME NodeID (both `(efferent, Bool)`), so ONE generic driver works on physically-unalike things — substitutability for hardware and humans, falling out of structure. Maps each programming language's host interface (C read/write, Go net.Conn, JS canvas, keyboard, clock) onto the same vocabulary, so translating a language to Form translates its RUNTIME too. Proven `resource-port.fk` + band 1111111 three-way; names the carrier gaps (Key/Pixel/Process/Env/device-lines) as one `catCall` native each. Generalizes ports-interface-and-structure.md from storage to every resource |
| `docs/coherence-substrate/ports-interface-and-structure.md` | How Form relates interface to structure, and reaches its environment. Names the **Port** = capability-contract (structure+interface) ⟗ carrier (host realization). Ties together the fragments the body already holds — BML's `(object_id, interface_id, native_flag)`, the `\|>` View projection, `engine.fk`'s `form-capability-contract`, `lc-tools-as-form-cells`'s `carrier ∈ {shell,http,in_process}`, the `substrate_dispatch` swap registry, and the kernels' plugin/libloading/Function seam. Resolves "where does SQL go": SQL is one *carrier* of the *storage port*; the relational shape is one *interface* over it; backends (memory/file/network) are swappable under one contract. Architecture-first; storage-port prototype is the next breath |
| `docs/coherence-substrate/agents-using-substrate.md` | Agent guide — when and how to ground reasoning |
| `docs/coherence-substrate/agents-tending-presence-pages.md` | Composting static `/people/{slug}` directories into graph-rendered presence pages |
| `docs/coherence-substrate/substrate-surprise-spec-twins.md` | Record of the lattice's shoulder-tap on 2026-05-24 — 13 CTOR-shape twins read across, 6 real resonances cross-referenced, 4 surface matches named as honest non-matches, 6 structural-default shapes named as diagnostic |
| `docs/coherence-substrate/body-shape-map.md` | The body's first comprehensive structural self-portrait, authored 2026-05-24 at 100% geometry coverage (148/148). Distributions across `form`, `spectral_band`, `lineage_texture`, `polarity`, `phase`, `arity`, `self_similarity`, `direction`, `scale`, `temporal_band`; substrate-native histogram across 8 Blueprint families in the concept domain; 14 multi-geometry concepts; 10 hapax forms awaiting confirmation. Baseline against which future drift can be sensed |
| `docs/coherence-substrate/language-cells.md` | Languages as substrate cells — ingestion grammars + emission templates as data; cross-language identity via content-addressing; N+M transpilation |
| `docs/coherence-substrate/language.canonical.json` | Canonical schema for Language cells; per-language definitions (Python, TS, Go, Rust) populate this shape |
| `form/form-kernel-ts/src/languages.ts` | TS reference implementation — `Language` interface, `parse_through` / `emit_through` generic walkers, grammar/emit rule builders |
| `form/form-stdlib/engine.fk` | ONE generic data-driven parser engine in Form. Walks pattern-data (literal/sequence/choice/capture/star/opt) against any text via any grammar — no language-specific code. Tokenizer parameterized by keyword set + operator set + literal rules. Composts bmf.py and per-language parser implementations. Verified end-to-end on Go and Rust native kernels |
| `form/form-stdlib/bmf-core.fk` | The cursor-based BMF core (first breath of `bmf-architecture.form`): a Cursor over a surface (string today; file via `read_file`; socket/cell/channel next) with pure peek/advance/checkpoint/restore, Pattern-as-data (lit/cls/run/seq/alt/opt/cap) driven by one matcher, and Template-as-data (emit/splice/const) built by one interpreter that emits into the universal vocabulary via `(bp op)`. Adds what `engine.fk` lacks: an input cursor + actions-as-data instead of per-rule lambdas. `tests/bmf-core-band.fk` returns `600` across Go/Rust/TS — proves grammar-as-data lands on the same coordinate as a hand-built node, and `alt` backtracks with no sediment |
| `form/form-stdlib/bmf-grammar.fk` | The recursive grammar engine on `bmf-core.fk`'s cursor: a GRAMMAR of named rules with `ref` + recursion, `rep`/`sep` repetition capturing a LIST of sub-rule nodes, node-captures (a capture holds its sub-pattern's emitted node), and templates with `splice` (one node) / `splice*` (flatten a list). This is the `Match` engine of `bmf-architecture.form` — full grammars are data over it. Character literals: `str`/`char`/`num` are scannerless matchers over the cursor — siblings of `lit`/`cls`/`run`, no lexer and no token stream — plus C-family comment skip (`//`, `/* */`) in `bmf-core.fk`'s `skip-ws`. `tests/bmf-grammar-band.fk` → `300` (recursion, precedence, nesting, separator-lists); `tests/literals-band.fk` → `400` across Go/Rust/TS — char/float/comments PLUS parsing the **real thesis BML file from disk** (`BMF-grammar.bml`: cursor reads the file, grammar rules match — leading comment block + class skipped — Form objects hold the result; extracts the real `"BMF.library.BMF"` literal) |
| `form/form-stdlib/lang-common.fk` | The statement + expression rules shared by every imperative-language grammar (stmt / ret / lets / exprs / expr / addx / subx / term / mulx / divx / factor / call / atom), emitting the universal vocabulary. Each language appends these to its own `method` / `param` / `ifs`. One shared core; languages are the thin diff |
| `form/form-stdlib/bml.fk` | The BML grammar (the thesis's high-level superset) over the recursive engine: class › section › method › params › statements › expressions, PLUS templates + generics — generic types as `~fncall` (nested, e.g. `HashTable<String, Stack<X>>`), template classes `class Name<T,U>` and generic methods capturing type params, and generic instantiation. Emits universal nodes (class/section → `~do` until a `B_Class` shape lands). Uses `lang-common.fk`. `tests/bml-band.fk` → `300` (core) and `tests/bml-generics-band.fk` → `300` (templates/generics) across Go/Rust/TS |
| `form/form-stdlib/go.fk` | The Go grammar (bare-method slice): `func` keyword, name-then-type params, if-without-parens; everything else from `lang-common.fk`. Emits universal nodes |
| `form/form-stdlib/java.fk` | The Java grammar (bare-method slice): type-before-name, if-with-parens; everything else from `lang-common.fk`. `tests/lang-convergence-band.fk` → `300` proves Go + Java + BML methods converge on one identical `~fndef` tree |
| `form/form-stdlib/universal-emit.fk` | Action-function helpers wrapping `universal-shapes.form` vocabulary (emit-int, emit-math-op, emit-call, emit-function-decl, emit-if-else, emit-let, emit-return, etc.) — grammar action functions compose these to emit universal Recipes the kernel walks directly |
| `form/form-stdlib/emit-engine.fk` | ONE generic Recipe → text/bytes encoder, symmetric to engine.fk. Walks Recipe tree, dispatches on category to template-fn, recursively emits children. Together with engine.fk forms the universal codec primitive — source languages AND binary formats use the same pair |
| `form/form-stdlib/emit.fk` | The universal Recipe-to-target dispatcher — sibling to convert.fk on the emit side. Carries a target-name × cell × registry contract; new emit targets land as rows in the registry, never code in emit.fk itself. Includes `emit-all` (one cell → many surfaces at once) |
| `form/form-stdlib/codec.fk` | Codec composition operators. `tie` pairs a decoder with an encoder into one value (CORBA-style minimal interface). `pipe2/3/4` thread a value through transformations. `adapter-parse-only` / `adapter-emit-only` lift single-direction functions into uniform codecs. `codec-for` walks a codec-set registry |
| `form/form-stdlib/emits/json.fk` | First concrete emit-target template-table. Renders JSON-OBJECT / JSON-ARRAY / JSON-PAIR / JSON-NULL into canonical JSON surface form. Mirrors `grammars/json.fk` category NodeIDs so the JSON codec round-trips through `tie parse-json json-emit-fn`. Leaf-templating refinement (string quoting from trivials) is the next breath |
| `form/form-stdlib/emits/yaml.fk` | YAML emit-target. Same data-shape categories as JSON (object / array / pair / null); surface uses indentation + dashes. Tied with parse-yaml as `yaml-codec` |
| `form/form-stdlib/emits/python.fk` | Python source emit-target. Full universal-shapes vocabulary (math / compare / logic / cond / block / jump / access / write / ident / fndef / fncall). Surface: `def`, `:` blocks, `and`/`or`/`not`, indentation |
| `form/form-stdlib/emits/typescript.fk` | TypeScript source emit-target. Surface: `function`, `{...}` blocks, `===`/`!==`, `&&`/`||`/`!`, `const` for let |
| `form/form-stdlib/emits/go.fk` | Go source emit-target. Surface: `func`, `:=` for declaration, `==`/`!=`, `&&`/`||`/`!`, no parens on if-condition |
| `form/form-stdlib/emits/rust.fk` | Rust source emit-target. Surface: `fn`, `let`, if-as-expression, `&&`/`||`/`!` |
| `form/form-stdlib/emits/form.fk` | Form (.fk) source emit-target. Universal-shapes → (verb args...) S-expression surface. Load-bearing target for the substrate-py-to-fk migration arc |
| `form/form-stdlib/emits/sql.fk` | SQL emit-target. Comparison + logic → WHERE clauses; pair → `col = val`; object → `SELECT ...`; array → `(v1, v2, v3)` IN-clause; NULL literal |
| `form/form-stdlib/emits/xml.fk` | XML emit-target. Object/array/pair → semantic XML tags; null → `<null/>`. Cell-walker becomes structural XML document |
| `form/form-stdlib/emits/html.fk` | HTML emit-target. Object → `<dl>`, array → `<ul><li>...</li></ul>`, pair → `<dt><dd>`. Also handles document shapes (heading, paragraph, code) for rendering markdown cells as HTML |
| `form/form-stdlib/emits/css.fk` | CSS emit-target. Object → `{ ... }` rule body; pair → `prop: val`; array → comma-separated selectors. Enough for substrate-resident design tokens to round-trip |
| `form/form-stdlib/emits/image.fk` | Image (SVG) emit-target. Object/array → `<svg><g class="kind">...</g></svg>`; pair → `<text>` key+value. Seed for substrate visualizations |
| `form/form-stdlib/emits/audio.fk` | Audio (sonification) emit-target. Object → chord, array → seq, pair → note, null → rest. Seed for substrate sonification |
| `form/form-stdlib/emits/video.fk` | Video (frame-storyboard) emit-target. Each composite cell → one FRAME[kind: N children] entry. Seed for substrate animation via framebuffer-events |
| `form/form-stdlib/emits/model.fk` | ML-model (tensor-description) emit-target. Cells → `tensor{kind, rank, weights}` declarations. Seed for substrate cells entering training surfaces |
| `form/form-stdlib/converted/` | Substrate Python files rendered through the universal codec lattice. `substrate_strings.fk` / `orm.fk` / `form_eval.fk` demonstrate end-to-end flow: `.py` → `convert.fk` → `grammars/python.fk` parse → Recipe tree → `emit.fk` dispatch → `emits/form.fk` templates → `.fk` text. README names current coverage (file-header subset) and the migration arc |
| `scripts/substrate-py-to-fk.sh` | Shell wrapper that runs the universal codec pipeline on a substrate Python file. `bin-go` loads core + emit-engine + codec + json/python grammars + emit + emits/form + convert + a one-off converter script with the target path baked in. Output is the .fk source rendered through the form-emit templates |
| `docs/coherence-substrate/emit-architecture.form` | The universal codec lattice named in Form. Diagrams the diamond (one Recipe, many target surfaces), names contracts for convert / emit-to / emit-all / tie / pipe, sketches the registry as data, names the CORBA-style codec-set, and traces the substrate-Python migration arc as 11 breaths each adding rows not engine code |
| `docs/coherence-substrate/kernel-minimality-audit.md` | 2026-05-22 audit: 25 truly-primitive natives + 9 composable. Identifies which kernel surface can compost via core.fk equivalents. Dispatch arms honestly minimal; JIT vector for typed specialization noted as later breath |
| `form/form-stdlib/cell-trace.fk` | The satsang-load-bearing primitive: walk any cell back to the source lines that authored it. Built on intern_node_at + node_source kernel natives. explain-cell renders human-readable provenance. The practice of self-knowing: every cell's state is traceable to the recipe lines that wrote it |
| `form/form-stdlib/grammars/markdown.fk` | Markdown parser + emit in pure Form. ATX headings, paragraphs, fenced code blocks → universal DOC-* Recipes with per-block source attribution. Most-used format in this repo (thousands of .md files) |
| `form/form-stdlib/grammars/json.fk` | JSON parser in pure Form. Objects, arrays, strings, numbers, bools, null → universal data Recipes with source attribution at the line/col of each composite. Sibling parity Go+Rust |
| `form/form-stdlib/grammars/yaml.fk` | YAML parser (simplified subset: flat key:value pairs + list items + comments) in pure Form. Used by .github/workflows + many config files. Source attribution per line. Subsequent breaths add nested mappings, block scalars, flow style |
| `form/form-stdlib/grammars/form.fk` | The self-host moment: S-expression (.fk) parser in pure Form. Parses Form source into Recipe trees without going through the kernel's bootstrap reader. Sibling parity Go+Rust. Once the kernel reads .fk source via this parser, the redundant tokenize_sexp / readSexpr / buildVerb code (~750 lines across three kernels) composts |
| `form/form-stdlib/grammars/python.fk` | Python parser (file-header subset: imports + def-headers + simple assignments + comments) in pure Form. The compost target: seedbank/local-llm-cell-v0/bmf.py (643 lines). Subsequent breaths add control flow, class defs, full expression grammar |
| `form/form-stdlib/grammars/typescript.fk` | TypeScript parser (file-header subset: imports + exports + function/class headers + const/let/var assignments + line comments) in pure Form. Compost target: form/form-kernel-ts/src/lang-typescript.ts (1887 lines) |
| `form/form-stdlib/escape-reader.fk` | The common ground under text escapes AND binary framing: a unified `read-context` primitive that dispatches on context-kind (escape-with-table | length-counted | length-prefixed). One ~135-line abstraction handles JSON string escapes, PNG chunks, HTML entities, MIME multipart, Tar blocks — text and binary differ only in unit size and length-source, not in shape |
| `form/form-stdlib/convert.fk` | The unified file-to-cells converter — single `(convert path)` entry point that auto-detects format from file extension and dispatches to the right grammar parser. Plus `convert-and-walk` (push-style consumption per cell) and `convert-summary` (count + first-attribution probe). Goal-realization: any repo file → native Form cells via one call |

## The trinity

| Phase | Primitive | What it is |
|---|---|---|
| **Ice** | Blueprint | Structural identity. *What something IS.* Frozen coordination. |
| **Water** | Recipe | Operational expression. *How something HAPPENS.* Flowing verb-graph. |
| **Gas** | NamedCell | Diffuse individuation. *Where something LIVES.* Named slot with seed. |

## In one query

Annotate a path you're about to read:

```bash
python3 scripts/coh_substrate.py annotate path/to/file.md
# → cell, blueprint, domain, equivalents
```

Find structurally-equivalent cells:

```bash
python3 scripts/coh_substrate.py equivalent memory "User biographical arc"
```

Or in Form:

```bash
python3 scripts/coh_substrate.py form '?equivalent @memory("User biographical arc")'
```

38 of 40 memory files in the body are equivalent to this one, by structural shape.

## Use the substrate

The substrate is now woven into daily practice through three commands:

### Discover what shapes exist

```bash
python3 scripts/coh_substrate.py discover
```

Surfaces:
- The largest blueprint clusters (e.g. 67 specs sharing the canonical spec frontmatter shape)
- Singletons (cells with shapes nowhere else in the body)
- Cross-domain collisions (same shape across multiple domains — refactor signal)

### Shape-check before authoring

```bash
python3 scripts/coh_substrate.py shape-check path/to/draft-spec.md
```

Computes the Blueprint shape this draft would have and surfaces existing cells with the same shape. Catches duplication and structural drift before they ship. Output: either "✓ new structural pattern" or "⚠ N existing cells share this shape" with the names.

### Auto-ingest on commit

```bash
# Manual installation (per developer):
ln -s ../../scripts/substrate_post_merge_hook.sh .git/hooks/post-merge
chmod +x .git/hooks/post-merge

# Or in CI, after merge to main:
bash scripts/substrate_post_merge_hook.sh
```

After every merge, changed `.md` files in tracked domains are auto-ingested. The substrate stays current with the body's tissue.

```bash
# Manual: feed paths from anywhere (git diff, find, etc.)
git diff --name-only HEAD~1..HEAD '*.md' | python3 scripts/coh_substrate.py ingest-paths --from-stdin
```

### Audit KB/substrate drift

```bash
python3 scripts/coh_substrate.py kb-sync-audit --strict
```

Compares canonical `docs/vision-kb/concepts/lc-*.md` files to live `@concept(...)` NamedCells. It reports missing cells, stale deleted/renamed cells, source-path drift, wrong-domain ingests, duplicate concept ids, and counts the other first-class KB surfaces: transmissions, resources, guides, language views, and KB pages. Those surfaces enter through `ingest-paths` or targeted backfills such as `ingest --resources --guides --language-views --kb-pages --transmissions`. For reviewed deletes/renames:

```bash
python3 scripts/coh_substrate.py kb-sync-audit --prune-stale
```

This prunes stale live NamedCells only; interned Blueprint/Recipe nodes can remain as historical structural memory.

## Phase status (as of 2026-05)

- Phase 1 ✓ — building-knowledge from prior art (kernel walk + run + mini-port + design doc)
- Phase 2 ✓ — Network category vocabulary designed
- Phase 3 ✓ — kernel + memory frontend + CLI + 11 tests; substrate ingests body's memories
- Phase 4 — REST API, Neo4j integration, agent-context auto-annotation, first-class KB surface coverage, backfill, and higher-order extraction (in progress)
